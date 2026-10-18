from copy import deepcopy
import pytest
from test_service import cmd, ready
from hubrecover.application.service import RecoveryService, Refusal

@pytest.fixture
def service(tmp_path): return RecoveryService(tmp_path/'source.sqlite')


def test_refresh_and_label_preserve_card_and_snapshot(service):
    run=service.create();before=deepcopy(run)
    run=cmd(service,run,'source_update',source='schedule',operation='refresh')
    run=cmd(service,run,'source_update',source='schedule',operation='label',label='Synthetic timetable')
    assert run['scenario_version']==3
    for key in ('expires_at','request_id','source_version','snapshots','expected_material'):
        assert run[key]==before[key]
    assert run['sources']['schedule']['version']==3
    assert run['source_updates'][-1]['classification']=='NONMATERIAL'
    run=cmd(service,run,'approve',request_id=run['request_id'],plan_id=run['search']['plans'][0]['id'])
    assert run['status']=='AWAITING_OPERATIONAL_ACK'


@pytest.mark.parametrize('source',['schedule','aircraft','crews','passengers','inventory','restrictions','dispatch'])
def test_material_changes_invalidate_without_mutating_snapshot(service,source):
    from hubrecover.application.sources import records
    run=ready(service);snapshot=deepcopy(run['snapshots'])
    record=deepcopy(records(run,source)[0]);rid=record.get('id',record.get('flight_id'))
    if source=='schedule': record['status']='CANCELLED'
    elif source=='aircraft': record['initial_location']='SYN-OTHER'
    elif source=='crews': record['qualifications']=[]
    elif source=='passengers': record['eligible']=False
    elif source=='inventory': record['capacity']+=1
    elif source=='restrictions': record['confirmed_end_ms']=None
    else:
        rid=next(iter(run['scenario']['dispatch_records']));record=deepcopy(run['scenario']['dispatch_records'][rid]);record['status']='UNKNOWN'
    run=cmd(service,run,'source_update',source=source,operation='replace',record_id=rid,value=record)
    assert run['status']=='MANUAL_HANDOFF' and run['approval'] is None
    assert run['snapshots']==snapshot and not run['receipts']
    assert run['source_updates'][-1]['classification']=='UNEXPECTED_MATERIAL'
    with pytest.raises(Refusal): cmd(service,run,'execute')


def test_invalid_fields_fail_closed_and_client_cannot_supply_verification(service):
    run=service.create();original=deepcopy(run['scenario'])
    run=cmd(service,run,'source_update',source='schedule',operation='refresh',verified_at=9999999999)
    assert run['status']=='MANUAL_HANDOFF'
    assert run['source_updates'][-1]['classification']=='INVALID_UNKNOWN'
    assert run['scenario']['current']==original['current']


def test_expected_commits_and_own_batch_have_explicit_evidence(service):
    run=ready(service)
    assert run['source_updates'][-1]['classification']=='EXPECTED_PREREQUISITE'
    run=cmd(service,run,'execute');run=service.work_step(run['id'],run['fence'])
    assert run['source_updates'][-1]['classification']=='OWN_BATCH_EFFECT'
    assert run['source_updates'][-1]['reference']==next(iter(run['receipts'].values()))['key']
    with service.store.transaction() as db:
        saved=service.store.load(db,run['id']);saved['bookings'][next(iter(saved['bookings']))]['version']+=1
        service.store.save(db,saved)
    run=service.work_step(run['id'],run['fence'])
    assert run['status']=='PARTIAL_MANUAL' and len(run['receipts'])==1
