from fastapi.testclient import TestClient
from hubrecover.application.api import create_app


def test_api_browser_flow_and_security(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/').status_code==200
        assert client.get('/assets/app.js').status_code==200
        assert client.get('/health').json()['mode']=='SYNTHETIC'
        assert len(client.get('/api/cases').json())==18
        assert client.post('/api/runs',json={},headers={'Origin':'https://untrusted.example'}).status_code==403
        assert client.get('/health',headers={'Host':'untrusted.example'}).status_code==403
        run=client.post('/api/runs',json={'scenario':'happy'}).json()
        assert run['status']=='AWAITING_APPROVAL'
        assert run['adk']['pending']['id']==run['request_id']
        assert client.post('/api/runs/'+run['id']+'/execute',json=dict(revision=run['revision'],key='bad',payload={})).status_code==409
        response=client.post('/api/runs/'+run['id']+'/approve',json=dict(revision=run['revision'],key='approve',payload=dict(request_id=run['request_id'],plan_id=run['search']['plans'][0]['id'])))
        assert response.status_code==200
        run=response.json()
        assert run['status']=='AWAITING_OPERATIONAL_ACK'
        assert run['adk']['pending']['id']=='finish-'+run['id']
        assert client.get('/api/runs/'+run['id']+'/trace/export').status_code==200


def test_research_records_remain_explicit_human_observations(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        run=client.post('/api/runs',json={}).json()
        body=dict(kind='review',run_id=run['id'],actor='SYN-REVIEWER',expertise='Test proxy',notes='Synthetic test of recording only',clarity=4,evidence=3,tradeoffs=4)
        response=client.post('/api/research',json=body)
        assert response.status_code==200
        assert response.json()['review_status']=='RECORDED_NOT_VERIFIED'
        assert client.get('/api/evaluations').json()['results']==[]
        assert len(client.get('/api/research').json())==1


def test_server_restart_recovers_abandoned_execution(tmp_path):
    import time
    from hubrecover.domain.planning import digest
    with TestClient(create_app(tmp_path)) as client:
        run=client.post('/api/runs',json={}).json()
        service=client.app.state.service
        service.clock=lambda:1000.0
        # Keep fixture/card clock coherent while simulating a process disappearing.
        with service.store.transaction() as db:
            saved=service.store.load(db,run['id'])
            saved['expires_at']=1300.0;saved['source_verified_at']=1000.0
            service.store.save(db,saved)
        def command(action,role='DUTY_MANAGER',**payload):
            nonlocal run
            run=service.command(run['id'],action,revision=run['revision'],key=action+role,role=role,payload=payload)
        command('approve',request_id=run['request_id'],plan_id=run['search']['plans'][0]['id'])
        plan=service.selected(run)
        for role in plan['prerequisites']:
            command('acknowledge',role,fingerprint=plan['fingerprint'],operations_digest=digest(plan['operations']))
        command('execute')
        run=service.work_step(run['id'],run['fence'])
        first_receipts=run['receipts'].copy()
    restarted=create_app(tmp_path)
    restarted.state.service.clock=lambda:1015.0
    with TestClient(restarted) as client:
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            final=client.get('/api/runs/'+run['id']).json()
            if final['status']=='COMPLETED': break
            time.sleep(.2)
        assert final['status']=='COMPLETED'
        assert len(final['receipts'])==150 and len(final['outbox'])==300
        assert all(final['receipts'][k]==v for k,v in first_receipts.items())
        assert any(t['action']=='WORKER_RECLAIMED' for t in final['trace'])
