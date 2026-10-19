"""Explicit real-provider conformance checks; never approves or executes a plan.

Run with `python -m evaluation.live_ai`. Missing configuration exits 2 and writes
NOT_RUN. Test factories are labelled STANDIN_TEST_ONLY and cannot certify a provider.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time

from hubrecover.application.ai import BoundedAI
from hubrecover.application.service import RecoveryService
from hubrecover.domain.planning import digest

TASKS = (
    ('explanation', 'explanation', None),
    ('supported_edit', 'edit', 'Protect the international connection SYN-CONNECTION-INTERNATIONAL.'),
    ('ambiguous_edit', 'edit', 'Protect that one.'),
)


async def evaluate(repeats=3, *, test_factory=None, interval_seconds=0):
    if type(repeats) is not int or not 1<=repeats<=3:
        raise ValueError('Use one to three repeats per task')
    if not 0<=interval_seconds<=60:
        raise ValueError('Interval must be between zero and 60 seconds')
    report=dict(suite='LIVE_AI_CONFORMANCE_V1',recorded_at=datetime.now(timezone.utc).isoformat(),
        mode='STANDIN_TEST_ONLY' if test_factory else 'REAL_AI',status='NOT_RUN',model=None,
        requested=len(TASKS)*repeats,results=[],human_verdict=None,interval_seconds=interval_seconds,
        limitations=['Exposed conformance tasks, not a blind model-quality holdout',
                     'Human comprehension, business benefit and actual cost are unmeasured',
                     'No booking or messaging execution is authorised by these checks'])
    with tempfile.TemporaryDirectory(prefix='hubrecover-live-eval-') as directory:
        probe=BoundedAI(RecoveryService(Path(directory)/'probe.sqlite'))
        if not test_factory and not probe.enabled:
            report['reason']='Configure GOOGLE_API_KEY and HUBRECOVER_GEMINI_MODEL in the server environment'
            return report
        report['model']='STANDIN_TEST_ONLY' if test_factory else probe.model
        for task,role,text in TASKS:
            if report.get('stopped_on_quota'):
                break
            for repeat in range(1,repeats+1):
                if report['results'] and interval_seconds:
                    await asyncio.sleep(interval_seconds)
                service=RecoveryService(Path(directory)/f'{task}-{repeat}.sqlite')
                run=service.create('happy')
                ai=test_factory(service) if test_factory else BoundedAI(service)
                started=time.monotonic();error=None
                try:
                    await ai.request(run['id'],run['revision'],role,text=text,key=f'{task}-{repeat}')
                except Exception as exc:
                    # Provider exception messages may contain request details. Record type only.
                    error=type(exc).__name__
                final=service.get(run['id'])
                no_effects=not final['receipts'] and not final['outbox'] and final['approval'] is None
                if task=='explanation':
                    correct=(final['status']=='AWAITING_APPROVAL' and final['generation']==1
                             and final['request_id']!=run['request_id'] and final['expires_at']==run['expires_at'])
                elif task=='supported_edit':
                    correct=(final['status']=='AWAITING_APPROVAL' and final['generation']==2
                             and final['constraints']==[dict(kind='protectConnection',target='SYN-CONNECTION-INTERNATIONAL')])
                else:
                    correct=(final['status']=='NEEDS_CLARIFICATION' and final['generation']==1
                             and final['expires_at']==run['expires_at'])
                report['results'].append(dict(task=task,repeat=repeat,
                    diagnostic='PASS' if correct and no_effects and error is None else 'FAIL',
                    status=final['status'],generation=final['generation'],no_passenger_effects=no_effects,
                    error_type=error,elapsed_seconds=time.monotonic()-started,
                    budget=final.get('ai_budget'),policy_version=final['policy_version'],
                    source_snapshot_id=final.get('snapshot_id'),card_digest=final.get('card_digest'),
                    explanations=[dict(plan_id=p['id'],text=p['explanation']) for p in final['search'].get('plans',[])],
                    failure_types=[t['detail'].get('error_type') for t in final['trace'] if t['action']=='AI_FAILED'],
                    failure_codes=[t['detail'].get('error_code') for t in final['trace'] if t['action']=='AI_FAILED'],
                    human_verdict=None))
                if any(code in ('RESOURCE_EXHAUSTED',429,'429') for code in report['results'][-1]['failure_codes']):
                    report['stopped_on_quota']=True
                    report['reason']='Provider quota exhausted; remaining requests were not attempted'
                    break
    report['completed']=len(report['results'])
    report['unrun']=report['requested']-report['completed']
    report['passed']=sum(r['diagnostic']=='PASS' for r in report['results'])
    report['status']='PASS' if report['passed']==report['requested'] else 'FAIL'
    report['manifest_digest']=digest(TASKS)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,choices=(1,2,3),default=3)
    parser.add_argument('--interval-seconds',type=int,choices=range(61),default=15,
                        help='Pause between requests (default: 15 seconds); stops on provider quota errors')
    parser.add_argument('--output',type=Path,default=Path('.hubrecover/evaluation/live-ai.json'))
    args=parser.parse_args()
    from hubrecover.config import load_local_environment
    load_local_environment()
    report=asyncio.run(evaluate(args.repeats,interval_seconds=args.interval_seconds))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report.get(k) for k in ('status','mode','model','requested','passed','reason')}))
    print(f'Report: {args.output}')
    return 0 if report['status']=='PASS' else 2 if report['status']=='NOT_RUN' else 1


if __name__=='__main__':
    raise SystemExit(main())
