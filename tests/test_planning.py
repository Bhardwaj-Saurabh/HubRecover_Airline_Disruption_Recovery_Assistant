from hubrecover.domain.planning import build_plans
from hubrecover.fixtures.scenarios import create_scenario


def test_full_search_and_independent_reference_arithmetic():
    result = build_plans(create_scenario())
    assert result['status'] == 'READY'
    assert result['completed'] == result['selected'] == 18
    # Inbound +30; outward +45; return +30. Fifty passengers arrive 45m later.
    assert result['plans'][0]['ranking'] == (0, 0, 50*45, 0, 30+45+30)
    assert len(result['plans']) == 4
    assert result['rejected']
    assert result['plans'] == sorted(result['plans'], key=lambda p:(p['ranking'], p['fingerprint']))


def test_protected_connection_and_rejection_fingerprint():
    scenario = create_scenario()
    result = build_plans(scenario)
    rejected = [result['plans'][0]['fingerprint']]
    edited = build_plans(scenario, [dict(kind='protectConnection',target='SYN-CONNECTION-INTERNATIONAL')], rejected)
    assert all(p['fingerprint'] not in rejected for p in edited['plans'])
    assert edited['plans'][0]['ranking'][2] == 3750


def test_impossible_edit_and_unknown_dispatch_never_publish():
    assert not build_plans(create_scenario('no_viable'))['plans']
    assert not build_plans(create_scenario(), [dict(kind='maxArrivalDelay', target='SYN-PARTY-0-00', minutes=0)])['plans']
    assert not build_plans(create_scenario('missing'))['plans']


def test_search_timeout_never_returns_partial_best():
    assert build_plans(create_scenario(), deadline_seconds=0)['status'] == 'SEARCH_INCOMPLETE'
    assert build_plans(create_scenario(), deadline_seconds=0)['plans'] == []
