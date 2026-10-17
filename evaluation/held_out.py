"""Frozen evaluator-only boundary variants. Never included in model/retrieval inputs.

Suite v1, first exposed during final implementation evaluation, 17 October 2026.
These are deterministic mechanism checks, not real-AI or human-value evidence.
"""
import json
from pathlib import Path
import tempfile
import time
import uuid

from hubrecover.domain.gate import RestrictionWindow, validate_operations
from hubrecover.domain.allocation import allocate
from hubrecover.domain.schemas import SeedSnapshot, Flight
from hubrecover.fixtures.reference import build_reference
from hubrecover.domain.invariants import MINUTE
from hubrecover.domain.planning import digest
from hubrecover.application.service import RecoveryService
from evaluation.runner import command, approve, acknowledge, refused

MANIFEST=[
 ('H01','crew rest one minute short','CREW_REST'),('H02','crew duty one minute over','CREW_DUTY'),
 ('H03','wrong type qualification','CREW_QUALIFICATION'),('H04','maintenance on the second rotation','MAINTENANCE'),
 ('H05','swapped origin locations on two resource graphs','LOCATION_CONTINUITY'),
 ('H06','unavailable next-day aircraft','RESOURCE_AVAILABILITY'),
 ('H07','changed verified block duration','BLOCK_DURATION'),('H08','invented crew reassignment','UNSUPPORTED_OPERATION'),
 ('H09','cancel middle leg without relocation','LOCATION_CONTINUITY'),('H10','runway arrival blocked at boundary','ACTIVE_RESTRICTION'),
 ('H11','forecast release cannot clear','ACTIVE_RESTRICTION'),('H12','missing dispatch for next-day leg','DISPATCH_UNVERIFIED'),
 ('H13','exact confirmed release','PASS'),('H14','unrelated flight scope','PASS'),
 ('H15','stop before first effect','MANUAL_HANDOFF'),('H16','stop after two effects','PARTIAL_MANUAL'),
 ('H17','disable after one effect across restart','PARTIAL_MANUAL'),('H18','expired card at exact TTL','MANUAL_HANDOFF'),
 ('H19','new control revision cannot revive authority','MANUAL_HANDOFF'),('H20','wrong-request replay','REFUSED')]


def synthetic_evidence(flights):
    from hubrecover.domain.allocation import DispatchEvidence
    return [DispatchEvidence(flight_id=f.id,departure_ms=f.departure_ms,arrival_ms=f.arrival_ms,
        tail_id=f.tail_id,crew_id=f.crew_id,status='VERIFIED',route_compatible=True,fuel_compatible=True,restriction_compatible=True) for f in flights]


def run_held_case(index):
    case,title,expected=MANIFEST[index]
    started=time.monotonic();actual=None
    if index<14:
        raw=build_reference().model_dump();proposed=None;restrictions=[]
        if index==0:raw['crews'][4]['prior_rest']['start_ms']+=MINUTE
        elif index==1:raw['crews'][6]['duty']['end_ms']+=MINUTE
        elif index==2:raw['crews'][8]['qualifications']=['DEMO90']
        elif index==3:raw['aircraft'][2]['unavailable']=[dict(start_ms=raw['flights'][4]['departure_ms'],end_ms=raw['flights'][4]['arrival_ms'])]
        elif index==4:
            raw['aircraft'][0]['initial_location'],raw['aircraft'][2]['initial_location']=raw['aircraft'][2]['initial_location'],raw['aircraft'][0]['initial_location']
        elif index==5:raw['aircraft'][1]['available']['end_ms']=raw['flights'][3]['arrival_ms']-MINUTE
        seed=SeedSnapshot.model_validate(raw);proposed=list(seed.flights)
        if index in (6,7,8):
            f=proposed[5];data=f.model_dump()
            if index==6:data['arrival_ms']+=MINUTE
            elif index==7:data['crew_id']=seed.crews[4].id
            else:data['status']='CANCELLED'
            proposed[5]=Flight.model_validate(data)
        if index in (9,10,12,13):
            f=seed.flights[4]
            restrictions=[RestrictionWindow(id='SYN-HELD-RESTRICTION',kind='RUNWAY_CLOSURE' if index==9 else 'GROUND_STOP',
                movement='ARRIVAL' if index==9 else 'DEPARTURE',applicable_flight_ids=[] if index==13 else [f.id],
                effective_ms=f.departure_ms-MINUTE,confirmed_end_ms=f.departure_ms if index in (12,13) else None,
                forecast_end_ms=f.departure_ms-1)]
        evidence=synthetic_evidence(proposed)
        if index==11:evidence=[e for e in evidence if e.flight_id!=seed.flights[3].id]
        report=validate_operations(seed,proposed,evidence,restrictions,restriction_source_verified=True)
        codes=sorted({i.code for i in report.issues})
        actual={'codes':codes,'passed':report.passed}
        passed=report.passed if expected=='PASS' else expected in codes
    else:
        with tempfile.TemporaryDirectory(prefix='hubrecover-held-') as folder:
            now=[1000.0]
            service=RecoveryService(Path(folder)/'business.sqlite',clock=lambda:now[0]);run=service.create()
            if index==19:
                passed=refused(lambda:command(service,run,'approve',request_id='SYN-WRONG-REQUEST',plan_id=run['search']['plans'][0]['id']))
                actual={'status':'REFUSED' if passed else 'UNEXPECTED_ACCEPTANCE','parties':0}
            else:
                run=acknowledge(service,approve(service,run))
                if index in (15,16):
                    run=command(service,run,'execute')
                    for _ in range(2 if index==15 else 1):run=service.work_step(run['id'],run['fence'])
                if index in (14,15):run=command(service,run,'stop')
                elif index in (16,18):
                    service.control('disable')
                    service=RecoveryService(service.store.path,clock=lambda:now[0]);run=service.get(run['id'])
                    if index==18:
                        service.control('restore',role='OCC_OPERATIONS_LEAD',evidence={k:'Held-out synthetic review record' for k in ('incident','root_cause','fix_version','regression_evidence','reviewer_approval')})
                        assert refused(lambda:command(service,run,'execute'))
                else:run=command(service,run,'advance',seconds=300)
                passed=run['status']==expected
                actual={'status':run['status'],'parties':len(run['receipts'])}
    return dict(id=uuid.uuid4().hex,case=case,title=title,suite='held_out_v1',mode='RULES_ONLY',expected=expected,
        actual=actual,diagnostic='PASS' if passed else 'FAIL',elapsed_seconds=time.monotonic()-started,
        verdict=None,verdict_history=[],manifest_digest=digest(MANIFEST),
        limitations=['Deterministic boundary variants only; no model/human evidence','Not a substitute for the full PRD held-out quality gate'])


def run_all():return [run_held_case(i) for i in range(len(MANIFEST))]

if __name__=='__main__':
    results=run_all()
    path=Path('evaluation/results/held-out.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(dict(manifest_digest=digest(MANIFEST),results=results),indent=2)+'\n')
    print(f"{sum(r['diagnostic']=='PASS' for r in results)}/20 held-out deterministic variants passed")
    for r in results:
        if r['diagnostic']!='PASS':print(r)
    assert all(r['diagnostic']=='PASS' for r in results)
