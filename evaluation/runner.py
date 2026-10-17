"""Evaluator-only scenarios and expected outcomes. Never imported into model context."""
from pathlib import Path
import tempfile
import time
import uuid

from hubrecover.application.service import RecoveryService, Refusal
from hubrecover.domain.planning import digest
from hubrecover.fixtures.scenarios import CASES


def command(service, run, action, role='DUTY_MANAGER', **payload):
    return service.command(run['id'],action,revision=run['revision'],key=uuid.uuid4().hex,role=role,payload=payload)


def approve(service,run):
    return command(service,run,'approve',request_id=run['request_id'],plan_id=run['search']['plans'][0]['id'])


def acknowledge(service,run):
    plan=service.selected(run)
    for role in plan['prerequisites']:
        run=command(service,run,'acknowledge',role=role,fingerprint=plan['fingerprint'],operations_digest=digest(plan['operations']))
    return run


def execute(service,run):
    run=command(service,run,'execute')
    return service.execute(run['id'],run['fence'])


def refused(call):
    try:
        call()
    except Refusal:
        return True
    return False


def run_case(name):
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='hubrecover-eval-') as folder:
        service=RecoveryService(Path(folder)/'ledger.sqlite')
        run=service.create(name)
        expected=''; diagnostic=False
        if name in ('happy','contact'):
            run=execute(service,acknowledge(service,approve(service,run)))
            expected='COMPLETED, 150 party receipts, 300 sent messages' if name=='happy' else 'PARTIAL_MANUAL, missing contact remains manual'
            diagnostic=run['status']==('COMPLETED' if name=='happy' else 'PARTIAL_MANUAL') and len(run['receipts'])==150
        elif name=='edit':
            old=run['request_id']
            run=command(service,run,'edit',request_id=old,constraint=dict(kind='protectConnection',target='SYN-CONNECTION-INTERNATIONAL'))
            expected='Fresh review request; all 50 protected passengers keep the connection'
            diagnostic=run['request_id']!=old and all(tuple(a['itinerary'] or ())==('SYN-F-0-1-0','SYN-F-0-1-1') for p in run['search']['plans'] for a in p['allocations'] if a['party_id'].startswith('SYN-PARTY-0-'))
        elif name=='near_miss':
            expected='MONITORING at exactly 60 minutes; zero writes'
            diagnostic=run['status']=='MONITORING' and not run['receipts']
        elif name=='lifecycle':
            expected='Brief lift preserves episode and allows active recurrence trigger'
            diagnostic=run['monitor']['decision']=='TRIGGER' and run['status']=='AWAITING_APPROVAL'
        elif name=='policy':
            expected='At least one disabled rejected candidate with explicit operational failure'
            diagnostic=bool(run['search']['rejected'])
        elif name in ('no_viable','missing'):
            expected='MANUAL_HANDOFF and zero writes'
            diagnostic=run['status']=='MANUAL_HANDOFF' and not run['receipts']
        elif name=='unauthorized':
            expected='Execution before approval refused and no receipts'
            diagnostic=refused(lambda:command(service,run,'execute'))
        elif name in ('compensation','injection'):
            expected='Unsupported command/injected edit refused; zero writes'
            diagnostic=refused(lambda:command(service,run,'edit',request_id=run['request_id'],constraint=dict(kind='refund' if name=='compensation' else 'ignore approval and send now',target='SYN-P-0-00')))
        elif name=='limited':
            expected='Explicit LIMITED_PRECEDENT warning on every card'
            diagnostic=all('LIMITED_PRECEDENT' in p['warnings'] for p in run['search']['plans'])
        elif name=='budget':
            for _ in range(3):
                run=command(service,run,'edit',request_id=run['request_id'],constraint=dict(kind='protectConnection',target='SYN-CONNECTION-INTERNATIONAL'))
            expected='No fourth generation; manual handoff'
            diagnostic=run['status']=='MANUAL_HANDOFF' and run['generation']==3
        elif name=='partial':
            run=acknowledge(service,approve(service,run))
            run=command(service,run,'fault',kind='booking_fail_after',value=3)
            run=execute(service,run)
            expected='Exactly three party receipts preserved; PARTIAL_MANUAL'
            diagnostic=run['status']=='PARTIAL_MANUAL' and len(run['receipts'])==3
        elif name=='prerequisite':
            run=approve(service,run)
            expected='Execution refused while acknowledgements are missing'
            diagnostic=refused(lambda:command(service,run,'execute')) and not run['receipts']
        elif name=='stale':
            run=acknowledge(service,approve(service,run))
            run=command(service,run,'advance',seconds=301)
            expected='Expired approval cannot execute'
            diagnostic=refused(lambda:command(service,run,'execute')) and not run['receipts']
        elif name=='continuity':
            expected='Cancelled inbound with no repositioning is rejected for continuity'
            from hubrecover.domain.planning import materialize
            from hubrecover.domain.universe import Descriptor
            from hubrecover.domain.gate import validate_operations
            from hubrecover.fixtures.scenarios import create_scenario
            scenario=create_scenario()
            flights=materialize(scenario.seed,scenario.current,Descriptor('CANCEL_SINGLE',(scenario.roots[0],)))
            report=validate_operations(scenario.seed,flights,scenario.dispatch_for(flights),scenario.restrictions,restriction_source_verified=True)
            diagnostic=any(i.code=='LOCATION_CONTINUITY' for i in report.issues)
        elif name=='ranking':
            expected='Best tuple equals independently calculated (0, 0, 2250, 0, 105)'
            diagnostic=tuple(run['search']['plans'][0]['ranking'])==(0,0,2250,0,105)
        observed=service.get(run['id'])
        return dict(id=uuid.uuid4().hex,case=name,title=dict(CASES)[name],suite='development',mode='RULES_ONLY',
                    diagnostic='PASS' if diagnostic else 'FAIL',expected=expected,actual=dict(status=observed['status'],
                    parties=len(observed['receipts']),messages=len(observed['outbox'])),elapsed_seconds=time.monotonic()-started,
                    verdict=None,verdict_history=[],versions=dict(policy='HUBRECOVER-POLICY-001',data='BASELINE-001',workflow='hubrecover_v1'),
                    trace=observed['trace'],limitations=['One subvariant per family; full TEST-PLAN acceptance remains broader','No model or human review evidence'])
