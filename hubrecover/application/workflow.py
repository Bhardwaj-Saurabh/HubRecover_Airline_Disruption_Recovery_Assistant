"""ADK graph coordinates durable business work; domain ledger owns authority."""
from pathlib import Path

from google.adk.agents.context import Context
from google.adk.events.request_input import RequestInput
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.adk.workflow import START, Workflow
from google.genai import types

from .service import TERMINAL, Refusal
from . import jobs


class RecoveryWorkflow:
    def __init__(self, service, session_path):
        self.service=service
        self.sessions=DatabaseSessionService(db_url='sqlite+aiosqlite:///'+str(Path(session_path).resolve()))

        def prepare(ctx: Context):
            run_id=ctx.state.get('domain_run_id')
            run=service.get(run_id) if run_id else service.create(ctx.state['scenario'])
            ctx.state['domain_run_id']=run['id']
            return dict(run_id=run['id'],status=run['status'])

        def human_review(ctx: Context):
            run=service.get(ctx.state['domain_run_id'])
            if run['status'] in ('AWAITING_APPROVAL','NEEDS_CLARIFICATION'):
                return RequestInput(interrupt_id=run['request_id'],message='Duty Manager review required',
                                    payload=dict(run_id=run['id'],generation=run['generation']))
            return dict(status=run['status'])

        def wait_for_reconciliation(ctx: Context):
            run=service.get(ctx.state['domain_run_id'])
            if run['status'] not in TERMINAL:
                return RequestInput(interrupt_id='finish-'+run['id'],message='Waiting for guarded operational actions',payload=dict(run_id=run['id']))
            return dict(status=run['status'])

        def summary(ctx: Context):
            run=service.get(ctx.state['domain_run_id'])
            return dict(status=run['status'],committed_parties=len(run['receipts']),messages=len(run['outbox']))

        graph=Workflow(name='hubrecover_v1',edges=[(START,prepare,human_review,wait_for_reconciliation,summary)],max_concurrency=1)
        self.runner=Runner(node=graph,app_name='hubrecover',session_service=self.sessions)

    async def start(self, scenario='happy', run_id=None, job=None):
        expected=jobs.target(self.service.get(run_id)) if run_id else None
        state=dict(scenario=scenario)
        if run_id:
            state['domain_run_id']=run_id
        session=await self.sessions.create_session(app_name='hubrecover',user_id='local-synthetic',state=state)
        await self._run(session.id,types.Content(role='user',parts=[types.Part(text='Start synthetic recovery')]))
        session=await self.sessions.get_session(app_name='hubrecover',user_id='local-synthetic',session_id=session.id)
        run_id=session.state['domain_run_id']
        await self._record(run_id,session.id,expected,job)
        return self.service.get(run_id)

    async def _run(self, session_id, message, invocation_id=None):
        async for _ in self.runner.run_async(user_id='local-synthetic',session_id=session_id,
                                             new_message=message,invocation_id=invocation_id):
            pass

    async def _record(self, run_id, session_id, expected=None, job=None):
        session=await self.sessions.get_session(app_name='hubrecover',user_id='local-synthetic',session_id=session_id)
        pending=None
        # The most recent model request is the current interrupt, unless answered.
        for event in session.events:
            for part in (event.content.parts if event.content else []) or []:
                if part.function_call and part.function_call.name=='adk_request_input':
                    pending=dict(id=part.function_call.id,invocation_id=event.invocation_id)
                if part.function_response and pending and part.function_response.id==pending['id']:
                    pending=None
        with self.service.store.transaction() as db:
            run=self.service.store.load(db,run_id)
            if (expected and jobs.target(run)!=expected) or (job and (not jobs.valid(db,job) or job['id']!=jobs.target(run))):
                raise Refusal('Stale workflow continuation cannot publish a review mapping')
            run['adk']=dict(session_id=session_id,pending=pending,workflow_version='hubrecover_v1',domain_target=jobs.target(run))
            self.service.store.save(db,run)

    async def resume(self, run_id, job=None):
        run=self.service.get(run_id)
        mapping=run.get('adk')
        if not mapping:
            return await self.start(run['scenario']['name'],run_id=run_id,job=job)
        expected=jobs.target(run)
        pending=mapping['pending']
        if pending:
            message=types.Content(role='user',parts=[types.Part(function_response=types.FunctionResponse(
                id=pending['id'],name='adk_request_input',response=dict(status=run['status'])))])
            await self._run(mapping['session_id'],message,pending['invocation_id'])
            await self._record(run_id,mapping['session_id'],expected,job)
        else:
            await self._record(run_id,mapping['session_id'],expected,job)
        return self.service.get(run_id)

    async def close(self):
        await self.runner.close()
        await self.sessions.close()
