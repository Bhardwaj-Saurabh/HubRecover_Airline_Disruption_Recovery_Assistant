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
