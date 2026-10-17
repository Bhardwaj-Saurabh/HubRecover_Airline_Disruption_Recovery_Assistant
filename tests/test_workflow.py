import asyncio
from hubrecover.application.service import RecoveryService
from hubrecover.application.workflow import RecoveryWorkflow
from test_service import cmd


def test_durable_adk_review_pause_restart_and_stop_resume(tmp_path):
    async def check():
        service=RecoveryService(tmp_path/'business.sqlite')
        workflow=RecoveryWorkflow(service,tmp_path/'adk.sqlite')
        run=await workflow.start()
        assert run['status']=='AWAITING_APPROVAL'
        assert run['adk']['pending']['id']==run['request_id']
        session_id=run['adk']['session_id']
        await workflow.close()
        workflow=RecoveryWorkflow(service,tmp_path/'adk.sqlite')
        run=cmd(service,run,'stop')
        run=await workflow.resume(run['id'])
        assert run['status']=='MANUAL_HANDOFF'
        assert run['adk']['session_id']==session_id
        assert run['adk']['pending'] is None
        await workflow.close()
    asyncio.run(check())
