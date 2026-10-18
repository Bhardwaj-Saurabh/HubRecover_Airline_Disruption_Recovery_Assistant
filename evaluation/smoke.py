"""Actual loopback HTTP smoke, isolated synthetic ledger and owned server process."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen


def run():
    with tempfile.TemporaryDirectory(prefix='hubrecover-http-') as folder:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        with open(Path(folder)/'server.log','w') as log:
            server=subprocess.Popen([sys.executable,'-m','hubrecover','--port',str(port),'--data-dir',folder],stdout=log,stderr=log)
            def request(path,body=None):
                req=Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(body).encode() if body is not None else None,
                            headers={'Content-Type':'application/json'})
                with urlopen(req,timeout=30) as response:return json.load(response)
            try:
                for _ in range(100):
                    try: request('/health');break
                    except OSError: time.sleep(.1)
                else: raise RuntimeError('Owned local server did not start')
                state=request('/api/runs',{'scenario':'happy'})
                def command(action,role='DUTY_MANAGER',**payload):
                    nonlocal state
                    state=request(f"/api/runs/{state['id']}/{action}",dict(revision=state['revision'],key=f'{action}-{state["revision"]}',role=role,payload=payload))
                    state=request('/api/runs/'+state['id'])
                command('source_update',source='schedule',operation='refresh')
                command('edit',request_id=state['request_id'],constraint=dict(kind='protectConnection',target='SYN-CONNECTION-INTERNATIONAL'))
                command('approve',request_id=state['request_id'],plan_id=state['search']['plans'][0]['id'])
                plan=next(p for p in state['search']['plans'] if p['id']==state['selected_plan'])
                for role in plan['prerequisites']:
                    command('acknowledge',role,fingerprint=plan['fingerprint'],operations_digest=plan['operations_digest'])
                command('execute')
                deadline=time.monotonic()+120
                while state['status']=='EXECUTING' and time.monotonic()<deadline:
                    time.sleep(.25);state=request('/api/runs/'+state['id'])
                assert state['status']=='COMPLETED',state['status']
                assert len(state['receipts'])==150
                sent=sum(m['status']=='SENT' for m in state['outbox'].values())
                assert sent==300
                snapshot=request(f"/api/runs/{state['id']}/snapshots/{state['snapshot_id']}")
                assert len(snapshot['content']['passengers'])==300
                report=dict(mode='RULES_ONLY',transport='ACTUAL_LOOPBACK_HTTP',status=state['status'],
                    parties=len(state['receipts']),messages_sent=sent,generation=state['generation'],
                    immutable_snapshot_verified=True,provider_configured=bool(os.environ.get('GOOGLE_API_KEY') and os.environ.get('HUBRECOVER_GEMINI_MODEL')),
                    browser_visual_qa='NOT_RUN',limitations=['Synthetic local server only; no real operational or provider calls'])
                Path('evaluation/results/http-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
                print(json.dumps(report))
            finally:
                server.terminate()
                try: server.wait(timeout=30)
                except subprocess.TimeoutExpired: server.kill();server.wait()

if __name__=='__main__':run()
