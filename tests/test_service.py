import uuid
import pytest
from hubrecover.application.service import RecoveryService, Refusal
from hubrecover.domain.planning import digest


@pytest.fixture
def service(tmp_path):
    return RecoveryService(tmp_path/'ledger.sqlite')


def cmd(service, run, action, role='DUTY_MANAGER', **payload):
    return service.command(run['id'],action,revision=run['revision'],key=uuid.uuid4().hex,role=role,payload=payload)


def ready(service, name='happy'):
    run=service.create(name)
    run=cmd(service,run,'approve',request_id=run['request_id'],plan_id=run['search']['plans'][0]['id'])
    plan=service.selected(run)
    for role in plan['prerequisites']:
        run=cmd(service,run,'acknowledge',role=role,fingerprint=plan['fingerprint'],operations_digest=digest(plan['operations']))
    return run


def test_end_to_end_and_duplicate_execute_refused(service):
    run=ready(service)
    run=cmd(service,run,'execute')
    final=service.execute(run['id'],run['fence'])
    assert final['status']=='COMPLETED'
    assert len(final['receipts'])==150 and len(final['outbox'])==300
    assert all(m['status']=='SENT' for m in final['outbox'].values())
    assert {k:v['occupied'] for k,v in final['inventory'].items()}==service.selected(final)['inventory_after']
    with pytest.raises(Refusal): cmd(service,final,'execute')


def test_approval_and_ack_boundaries(service):
    run=service.create()
    with pytest.raises(Refusal): cmd(service,run,'execute')
    with pytest.raises(Refusal): cmd(service,run,'approve',role='DISPATCHER',request_id=run['request_id'],plan_id=run['search']['plans'][0]['id'])
    with pytest.raises(Refusal): cmd(service,run,'approve',request_id='wrong',plan_id=run['search']['plans'][0]['id'])
    run=cmd(service,run,'approve',request_id=run['request_id'],plan_id=run['search']['plans'][0]['id'])
    with pytest.raises(Refusal): cmd(service,run,'execute')
    with pytest.raises(Refusal): cmd(service,run,'acknowledge',role='DISPATCHER',fingerprint='wrong',operations_digest='wrong')
    assert not service.get(run['id'])['receipts']


def test_command_replay_idempotent_and_mismatched_key_refused(service):
    run=service.create();key='same-click'
    args=dict(revision=run['revision'],key=key,payload=dict(request_id=run['request_id'],plan_id=run['search']['plans'][0]['id']))
    first=service.command(run['id'],'approve',**args)
    second=service.command(run['id'],'approve',**args)
    assert first['revision']==second['revision']
    with pytest.raises(Refusal): service.command(run['id'],'reject',**args)


def test_edit_new_request_and_budget(service):
    run=service.create()
    original=run['request_id']
    for _ in range(3):
        run=cmd(service,run,'edit',request_id=run['request_id'],constraint=dict(kind='protectConnection',target='SYN-CONNECTION-INTERNATIONAL'))
    assert run['status']=='MANUAL_HANDOFF'
    assert run['generation']==3 and run['request_id']!=original


def test_expiry_and_source_change_no_writes(service):
    run=ready(service)
    run=cmd(service,run,'advance',seconds=301)
    assert run['status']=='MANUAL_HANDOFF'
    with pytest.raises(Refusal): cmd(service,run,'execute')
    run=ready(service)
    run=cmd(service,run,'source_change')
    assert not run['receipts'] and run['status']=='MANUAL_HANDOFF'


def test_partial_failure_preserves_commits_and_restart(service):
    run=ready(service)
    run=cmd(service,run,'fault',kind='booking_fail_after',value=3)
    run=cmd(service,run,'execute')
    final=service.execute(run['id'],run['fence'])
    assert final['status']=='PARTIAL_MANUAL' and len(final['receipts'])==3
    restarted=RecoveryService(service.store.path)
    assert restarted.get(run['id'])['receipts']==final['receipts']
    with pytest.raises(Refusal): restarted.work_step(run['id'],run['fence'])


def test_stop_between_party_commits_fences_worker(service):
    run=cmd(service,ready(service),'execute')
    fence=run['fence'];run=service.work_step(run['id'],fence)
    run=cmd(service,run,'stop')
    assert run['status']=='PARTIAL_MANUAL' and len(run['receipts'])==1
    with pytest.raises(Refusal): service.work_step(run['id'],fence)


def test_global_disable_survives_restart_and_restore_never_revives(service):
    run=ready(service)
    service.control('disable')
    restarted=RecoveryService(service.store.path)
    assert not restarted.control()['writes_enabled']
    assert restarted.get(run['id'])['status']=='MANUAL_HANDOFF'
    with pytest.raises(Refusal): restarted.control('restore',role='OCC_OPERATIONS_LEAD',evidence={})
    restarted.control('restore',role='OCC_OPERATIONS_LEAD',evidence={k:'Synthetic reviewed evidence' for k in
                      ('incident','root_cause','fix_version','regression_evidence','reviewer_approval')})
    with pytest.raises(Refusal): cmd(restarted,restarted.get(run['id']),'execute')


def test_notification_failure_never_rebooks(service):
    run=ready(service)
    run=cmd(service,run,'fault',kind='notification_fail')
    run=cmd(service,run,'execute')
    final=service.execute(run['id'],run['fence'])
    assert final['status']=='PARTIAL_MANUAL'
    assert len(final['receipts'])==150
    assert all(m['attempts']==2 and m['status']=='MANUAL_CONTACT' for m in final['outbox'].values())


def test_near_miss_and_missing_source(service):
    run=service.create('near_miss')
    assert run['status']=='MONITORING' and not run['search']
    cmd(service,run,'stop')
    run=service.create('missing')
    assert run['status']=='MANUAL_HANDOFF' and not run['receipts']


def test_concurrent_approvals_have_one_winner(service):
    from concurrent.futures import ThreadPoolExecutor
    run=service.create()
    def attempt(_):
        try:
            cmd(service,run,'approve',request_id=run['request_id'],plan_id=run['search']['plans'][0]['id'])
            return True
        except Refusal:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,range(2)))==[False,True]


def test_lease_takeover_fences_old_worker_and_keeps_receipt(tmp_path):
    now=[1000.0]
    service=RecoveryService(tmp_path/'lease.sqlite',clock=lambda:now[0])
    run=cmd(service,ready(service),'execute');old_fence=run['fence']
    run=service.work_step(run['id'],old_fence)
    now[0]+=16
    restarted=RecoveryService(service.store.path,clock=lambda:now[0])
    run=cmd(restarted,run,'execute')
    assert run['fence']>old_fence
    with pytest.raises(Refusal): restarted.work_step(run['id'],old_fence)
    run=restarted.work_step(run['id'],run['fence'])
    assert len(run['receipts'])==2


def test_handoff_acceptance_does_not_resolve_work(service):
    run=service.create('missing')
    run=cmd(service,run,'accept_handoff',handoff_id=run['handoffs'][0]['id'])
    assert run['status']=='MANUAL_HANDOFF' and run['handoffs'][0]['status']=='ACKNOWLEDGED'
    assert not run['receipts']


def test_actual_rebooking_net_seats_and_history(service):
    run=service.create()
    run=cmd(service,run,'reject',request_id=run['request_id'],reason='Compare alternative passenger trade-offs')
    plan=next(p for p in run['search']['plans'] if any(a['outcome']=='REBOOKED_NEXT_DAY' for a in p['allocations']))
    run=cmd(service,run,'approve',request_id=run['request_id'],plan_id=plan['id'])
    for role in plan['prerequisites']:
        run=cmd(service,run,'acknowledge',role=role,fingerprint=plan['fingerprint'],operations_digest=digest(plan['operations']))
    run=cmd(service,run,'execute');final=service.execute(run['id'],run['fence'])
    assert final['status']=='COMPLETED'
    assert len(final['booking_history'])==2
    assert any(h['reason']=='NEXT_DAY_PASSENGER_CARE' for h in final['handoffs'])
    assert final['inventory']['SYN-F-0-1-0']['occupied']==70
    assert final['inventory']['SYN-F-0-1-1']['occupied']==68
    assert final['inventory']['SYN-F-0-2-0']['occupied']==22


def test_reset_idempotency_and_no_inherited_authority(service):
    run=service.create();run=cmd(service,run,'stop')
    child=service.reset(run['id'],run['revision'],'reset-once','DUTY_MANAGER')
    duplicate=service.reset(run['id'],run['revision'],'reset-once','DUTY_MANAGER')
    assert child['id']==duplicate['id'] and child['id']!=run['id']
    assert child['approval'] is None and child['receipts']=={}
    with pytest.raises(Refusal):service.reset(run['id'],run['revision'],'reset-twice','DUTY_MANAGER')


def test_handoff_return_reassignment_resolution_survives_restart(service):
    run=service.create('missing');h=run['handoffs'][0];hid=h['id']
    assert len(h['remaining_parties'])==150 and len(h['affected_passengers'])==300
    with pytest.raises(Refusal):
        cmd(service,run,'accept_handoff',role='OCC_OPERATIONS_LEAD',handoff_id=hid)
    run=cmd(service,run,'return_handoff',handoff_id=hid,note='Requires source specialist')
    with pytest.raises(Refusal): cmd(service,run,'accept_handoff',handoff_id=hid)
    with pytest.raises(Refusal):
        cmd(service,run,'assign_handoff',role='DISPATCHER',handoff_id=hid,owner='CREW_CONTROLLER',note='Check source')
    run=cmd(service,run,'assign_handoff',role='OCC_OPERATIONS_LEAD',handoff_id=hid,owner='CREW_CONTROLLER',note='Check source')
    with pytest.raises(Refusal): cmd(service,run,'accept_handoff',handoff_id=hid)
    run=cmd(service,run,'accept_handoff',role='CREW_CONTROLLER',handoff_id=hid)
    with pytest.raises(Refusal):
        cmd(service,run,'resolve_handoff',role='CREW_CONTROLLER',handoff_id=hid,note='Reviewed')
    before=service.get(run['id'])
    args=dict(revision=run['revision'],key='manual-resolution',role='CREW_CONTROLLER',
              payload=dict(handoff_id=hid,note='Recorded source issue for manual follow-up',evidence='SYN-MANUAL-001'))
    run=service.command(run['id'],'resolve_handoff',**args)
    restarted=RecoveryService(service.store.path)
    replay=restarted.command(run['id'],'resolve_handoff',**args)
    assert replay['revision']==run['revision']
    assert replay['handoffs'][0]['status']=='RESOLVED_MANUALLY'
    assert len(replay['handoffs'][0]['history'])==5
    for field in ('status','bookings','receipts','outbox','approval','inventory'):
        assert replay[field]==before[field]
    with pytest.raises(Refusal): cmd(service,run,'execute')
    with pytest.raises(Refusal):
        cmd(service,run,'assign_handoff',handoff_id=hid,owner='DUTY_MANAGER',note='Reopen')


def test_handoff_stale_version_and_partial_evidence(service):
    run=ready(service)
    run=cmd(service,run,'execute')
    run=service.work_step(run['id'],run['fence'])
    run=cmd(service,run,'stop')
    packet=run['handoffs'][0]
    assert len(packet['committed_parties'])==1
    assert len(packet['remaining_parties'])==149
    assert packet['evidence']['receipts']==run['receipts']
    assert packet['evidence']['communication']==run['outbox']
    accepted=cmd(service,run,'accept_handoff',handoff_id=packet['id'])
    with pytest.raises(Refusal):
        cmd(service,run,'return_handoff',handoff_id=packet['id'],note='Stale return')
    assert service.get(run['id'])['handoffs']==accepted['handoffs']
