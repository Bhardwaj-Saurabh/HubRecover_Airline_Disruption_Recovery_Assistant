"""Durable, fenced reconciliation jobs between business commits and ADK checkpoints."""
import hashlib
import json
import time


def target(run):
    return hashlib.sha256(json.dumps([run['id'],run['generation'],run['status'],
        run.get('request_id'),run['control_version']],separators=(',',':')).encode()).hexdigest()


def enqueue(db,run):
    if run['status'] in ('GENERATING','EXPLAINING','EXECUTING'): return
    key=target(run)
    if run.get('adk',{}).get('domain_target')==key: return
    db.execute('INSERT OR IGNORE INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
               (key,run['id'],run['generation'],'ADK_SYNC','PENDING',0,0,0,None))


def claim(store,now=None):
    now=time.time() if now is None else now
    with store.transaction() as db:
        for row in db.execute("SELECT * FROM jobs WHERE status IN ('PENDING','RUNNING') ORDER BY rowid").fetchall():
            if row['status']=='RUNNING' and row['lease_until']>now: continue
            run=store.load(db,row['run_id'])
            if target(run)!=row['id'] or run.get('adk',{}).get('domain_target')==row['id']:
                db.execute("UPDATE jobs SET status='SUPERSEDED' WHERE id=?",(row['id'],))
                continue
            fence=row['fence']+1
            db.execute("UPDATE jobs SET status='RUNNING',fence=?,lease_until=?,attempts=attempts+1 WHERE id=?",
                       (fence,now+15,row['id']))
            return dict(row)|dict(fence=fence,lease_until=now+15,attempts=row['attempts']+1)
    return None


def renew(store,job):
    with store.transaction() as db:
        changed=db.execute("UPDATE jobs SET lease_until=? WHERE id=? AND fence=? AND status='RUNNING' AND lease_until>?",
                           (time.time()+15,job['id'],job['fence'],time.time())).rowcount
        return bool(changed)


def valid(db,job):
    row=db.execute('SELECT * FROM jobs WHERE id=?',(job['id'],)).fetchone()
    return row and row['status']=='RUNNING' and row['fence']==job['fence'] and row['lease_until']>time.time()


def finish(store,job,error=None):
    with store.transaction() as db:
        if not valid(db,job): return
        db.execute('UPDATE jobs SET status=?,error=? WHERE id=?',
                   (('PENDING' if job['attempts']<3 else 'FAILED') if error else 'DONE',error,job['id']))
