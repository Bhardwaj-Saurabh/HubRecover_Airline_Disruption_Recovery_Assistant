"""Loopback-only local demonstration API, with explicitly simulated roles."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from urllib.parse import urlparse
import uuid

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

from .service import RecoveryService, Refusal, TERMINAL
from .workflow import RecoveryWorkflow
from .ai import BoundedAI
from hubrecover.domain.planning import digest
from hubrecover.fixtures.scenarios import CASES

WEB=Path(__file__).resolve().parents[1]/'web'

class Body(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
class NewRun(Body):
    scenario: str='happy'
class Command(Body):
    revision: int
    key: str=Field(min_length=1,max_length=128)
    role: str='DUTY_MANAGER'
    payload: dict=Field(default_factory=dict)
class ControlCommand(Body):
    role: str
    evidence: dict | None=None
class Verdict(Body):
    verdict: str
    reason: str=Field(min_length=1,max_length=2000)
    actor: str=Field(min_length=1,max_length=100)


class ResearchRecord(Body):
    kind: Literal['review','comparison','feedback']
    run_id: str
    actor: str=Field(min_length=1,max_length=100)
    expertise: str=Field(min_length=1,max_length=200)
    notes: str=Field(min_length=1,max_length=4000)
    clarity: int | None=Field(default=None,ge=1,le=5)
    evidence: int | None=Field(default=None,ge=1,le=5)
    tradeoffs: int | None=Field(default=None,ge=1,le=5)
    task_id: str | None=None
    mode: Literal['MANUAL','RULES_ONLY','REAL_AI'] | None=None
    started_ms: int | None=Field(default=None,ge=0)
    ended_ms: int | None=Field(default=None,ge=0)
    @model_validator(mode='after')
    def required_fields(self):
        if self.kind=='review' and any(v is None for v in (self.clarity,self.evidence,self.tradeoffs)):
            raise ValueError('All three review scores required')
        if self.kind=='comparison' and (not self.task_id or not self.mode or self.started_ms is None or self.ended_ms is None or self.ended_ms<self.started_ms):
            raise ValueError('Matched task, mode and chronological observed timing required')
        return self


def create_app(data_dir=None):
    folder=Path(data_dir or os.environ.get('HUBRECOVER_DATA_DIR','.hubrecover')).resolve()
    service=RecoveryService(folder/'business.sqlite')
    service.recover_interrupted_ai()
    workflow=RecoveryWorkflow(service,folder/'adk.sqlite')
    workflow_lock=asyncio.Lock()
    ai=BoundedAI(service)
    eval_state={'running':False,'completed':0,'total':len(CASES),'error':None}

    @asynccontextmanager
    async def lifespan(app):
        yield
        await workflow.close()
    app=FastAPI(title='HubRecover synthetic recovery',lifespan=lifespan)
    app.state.service=service

    @app.middleware('http')
    async def local_only(request,call_next):
        if request.url.hostname not in ('localhost','127.0.0.1','::1','testserver'):
            return JSONResponse({'detail':'Local synthetic demonstration only'},status_code=403)
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'Cross-origin commands are disabled'},status_code=403)
        if int(request.headers.get('content-length','0'))>100_000:
            return JSONResponse({'detail':'Request too large'},status_code=413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.exception_handler(Refusal)
    async def refused_handler(request,exc):
        return JSONResponse({'detail':str(exc)},status_code=409)
    @app.exception_handler(KeyError)
    async def not_found(request,exc):
        return JSONResponse({'detail':'Record not found'},status_code=404)

    @app.get('/')
    def index(): return FileResponse(WEB/'index.html')
    app.mount('/assets',StaticFiles(directory=WEB),name='assets')
    @app.get('/health')
    def health(): return dict(status='ok',mode='SYNTHETIC',ai='RULES_ONLY',workflow='hubrecover_v1')
    @app.get('/api/ai')
    def ai_status(): return ai.status()
    @app.get('/api/cases')
    def cases(): return [dict(id=i,title=t) for i,t in CASES]
    @app.get('/api/runs')
    def runs(): return service.list_runs()
    @app.post('/api/runs')
    async def new_run(body:NewRun):
        if body.scenario not in dict(CASES): raise HTTPException(422,'Unknown scenario')
        async with workflow_lock:
            return await workflow.start(body.scenario)
    @app.get('/api/runs/{run_id}')
    def get_run(run_id:str):
        run=service.get(run_id)
        for plan in run.get('search',{}).get('plans',[]):
            plan['operations_digest']=digest(plan['operations'])
        return run
    @app.post('/api/runs/{run_id}/{action}')
    async def mutate(run_id:str,action:str,body:Command,background:BackgroundTasks):
        if action in ('ai_explain','ai_edit'):
            if body.role!='DUTY_MANAGER': raise Refusal('Duty Manager role required')
            run=await ai.request(run_id,body.revision,'explanation' if action=='ai_explain' else 'edit',body.payload.get('text'),body.key)
            async with workflow_lock:
                return await workflow.resume(run_id)
        if action=='reset':
            old=service.get(run_id)
            if body.role!='DUTY_MANAGER' or body.revision!=old['revision'] or old['status'] not in TERMINAL:
                raise Refusal('Only a stopped or finished episode can be reset by the Duty Manager')
            async with workflow_lock:
                return await workflow.start(old['scenario']['name'])
        run=await asyncio.to_thread(service.command,run_id,action,revision=body.revision,key=body.key,role=body.role,payload=body.payload)
        if action=='execute' and run['status']=='EXECUTING':
            async def execute_and_resume():
                try:
                    await asyncio.to_thread(service.execute,run_id,run['fence'])
                except Refusal:
                    pass # Stop or a newer worker fenced this continuation.
                async with workflow_lock:
                    await workflow.resume(run_id)
            background.add_task(execute_and_resume)
        elif action in ('approve','edit','reject','stop','advance','source_change','resume_monitor'):
            async with workflow_lock:
                run=await workflow.resume(run_id)
        return run
    @app.get('/api/runs/{run_id}/trace/export')
    def trace(run_id:str):
        return JSONResponse(service.get(run_id),headers={'Content-Disposition':f'attachment; filename="hubrecover-{run_id}.json"'})
    @app.get('/api/control')
    def control(): return service.control()
    @app.post('/api/control/{action}')
    def change_control(action:str,body:ControlCommand):
        return service.control(action,role=body.role,evidence=body.evidence)

    def evaluate(suite='development'):
        from evaluation.runner import run_case
        from evaluation.held_out import run_held_case
        cases=list(range(20)) if suite=='held_out' else [name for name,_ in CASES]
        try:
            for case in cases:
                result=run_held_case(case) if suite=='held_out' else run_case(case)
                with service.store.transaction() as db:
                    db.execute('INSERT INTO observations VALUES(?,?)',(result['id'],json.dumps(result)))
                eval_state['completed']+=1
        except Exception as exc:
            eval_state['error']=str(exc)
        finally:
            eval_state['running']=False
    @app.post('/api/evaluations')
    def start_evaluation(background:BackgroundTasks):
        if eval_state['running']: raise Refusal('Evaluation already running')
        eval_state.update(running=True,completed=0,total=18,error=None)
        background.add_task(evaluate)
        return eval_state
    @app.post('/api/evaluations/held-out')
    def held_out(background:BackgroundTasks):
        if eval_state['running']: raise Refusal('Evaluation already running')
        eval_state.update(running=True,completed=0,total=20,error=None)
        background.add_task(evaluate,'held_out')
        return eval_state
    @app.get('/api/research')
    def research():
        with service.store.connect() as db:
            return [json.loads(row['body']) for row in db.execute('SELECT body FROM research ORDER BY rowid')]
    @app.post('/api/research')
    def record_research(body:ResearchRecord):
        run=service.get(body.run_id)
        record=dict(**body.model_dump(),id=uuid.uuid4().hex,at=service.clock(),generation=run['generation'],
                    card_digest=run.get('card_digest'),source_version=run['source_version'],review_status='RECORDED_NOT_VERIFIED')
        with service.store.transaction() as db:
            db.execute('INSERT INTO research VALUES(?,?)',(record['id'],json.dumps(record)))
        return record
    @app.get('/api/evaluations')
    def evaluations():
        with service.store.connect() as db:
            results=[json.loads(r['body']) for r in db.execute('SELECT body FROM observations ORDER BY rowid')]
        return dict(progress=eval_state,results=results,held_out=dict(status='OBSERVED' if any(r.get('suite')=='held_out_v1' for r in results) else 'NOT_RUN',cases=20),
                    human_review='REQUIRES_REVIEW',real_ai='NOT_RUN',value_comparison='REQUIRES_MATCHED_ANALYSIS',research=research())
    @app.post('/api/evaluations/{result_id}/verdict')
    def verdict(result_id:str,body:Verdict):
        if body.verdict not in ('PASS','NEEDS_WORK','FAIL'): raise HTTPException(422,'Unknown verdict')
        with service.store.transaction() as db:
            row=db.execute('SELECT body FROM observations WHERE id=?',(result_id,)).fetchone()
            if not row: raise KeyError(result_id)
            value=json.loads(row['body']);value['verdict']=body.verdict
            value['verdict_history'].append(dict(**body.model_dump(),at=service.clock()))
            db.execute('UPDATE observations SET body=? WHERE id=?',(json.dumps(value),result_id))
        return value
    return app
