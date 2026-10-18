import asyncio
import time
import pytest
from hubrecover.application.service import RecoveryService, Refusal
from hubrecover.application.workflow import RecoveryWorkflow
from hubrecover.application import jobs
from test_service import cmd


def test_lost_card_mapping_reuses_saved_card_and_deadline(tmp_path):
    async def exercise():
        service=RecoveryService(tmp_path/'business.sqlite');run=service.create()
        job=jobs.claim(service.store)
        workflow=RecoveryWorkflow(service,tmp_path/'adk.sqlite')
        try:
            restored=await workflow.resume(run['id'],job=job)
            jobs.finish(service.store,job)
            assert restored['request_id']==run['request_id']
            assert restored['expires_at']==run['expires_at']
            assert restored['adk']['pending']['id']==run['request_id']
            assert jobs.claim(service.store) is None
        finally: await workflow.close()
    asyncio.run(exercise())


def test_job_takeover_rejects_old_mapping_and_supersedes_stopped_work(tmp_path):
    async def exercise():
        service=RecoveryService(tmp_path/'business.sqlite');run=service.create()
        old=jobs.claim(service.store,now=time.time()-16)
        new=jobs.claim(service.store)
        assert new['fence']>old['fence'] and new['attempts']==2
        workflow=RecoveryWorkflow(service,tmp_path/'adk.sqlite')
        try:
            with pytest.raises(Refusal): await workflow.resume(run['id'],job=old)
            assert 'adk' not in service.get(run['id'])
            stopped=cmd(service,run,'stop')
            with pytest.raises(Refusal): await workflow.resume(run['id'],job=new)
            # A current mapping may only be published by the job for current state.
            current=jobs.claim(service.store)
            assert current['id']==jobs.target(stopped)
        finally: await workflow.close()
    asyncio.run(exercise())
