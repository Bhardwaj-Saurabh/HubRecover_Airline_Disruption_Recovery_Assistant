import pytest

from hubrecover.domain.gate import RestrictionWindow, validate_operations
from hubrecover.domain.invariants import MINUTE
from hubrecover.domain.schemas import SeedSnapshot
from hubrecover.fixtures.reference import build_reference
from test_allocation import change, evidence


def gate(seed, flights=None, restrictions=None, **kwargs):
    flights = seed.flights if flights is None else flights
    return validate_operations(seed, flights, evidence(flights), restrictions or [],
                               restriction_source_verified=kwargs.get('verified', True))


def test_healthy_operations_pass_but_are_not_write_authority():
    assert gate(build_reference()).passed


@pytest.mark.parametrize('mutation,expected', [
    ('rest', 'CREW_REST'), ('duty', 'CREW_DUTY'), ('qualification', 'CREW_QUALIFICATION'),
    ('maintenance', 'MAINTENANCE'), ('location', 'LOCATION_CONTINUITY'),
    ('availability', 'RESOURCE_AVAILABILITY'),
])
def test_resource_failures(mutation, expected):
    raw = build_reference().model_dump()
    if mutation == 'rest':
        raw['crews'][0]['prior_rest']['start_ms'] += MINUTE
    elif mutation == 'duty':
        raw['crews'][0]['duty']['end_ms'] += MINUTE
    elif mutation == 'qualification':
        raw['crews'][0]['qualifications'] = ['DEMO90']
    elif mutation == 'maintenance':
        raw['aircraft'][0]['unavailable'] = [dict(start_ms=raw['flights'][0]['departure_ms'], end_ms=raw['flights'][0]['arrival_ms'])]
    elif mutation == 'location':
        raw['aircraft'][0]['initial_location'] = 'SYN-WRONG'
    else:
        raw['aircraft'][0]['available']['start_ms'] = raw['flights'][0]['departure_ms'] + MINUTE
    assert expected in {i.code for i in gate(SeedSnapshot.model_validate(raw)).issues}


def test_cancellation_cannot_teleport_tail_or_crew():
    seed = build_reference()
    flights = change(seed.flights, seed.flights[0].id, status='CANCELLED')
    report = gate(seed, flights)
    assert not report.passed
    assert sum(i.code == 'LOCATION_CONTINUITY' for i in report.issues) == 2


def test_unpropagated_delay_breaks_turnaround_and_crew_overlap():
    seed = build_reference()
    first = seed.flights[0]
    flights = change(seed.flights, first.id, departure_ms=first.departure_ms+90*MINUTE,
                     arrival_ms=first.arrival_ms+90*MINUTE)
    codes = {i.code for i in gate(seed, flights).issues}
    assert {'TURNAROUND', 'CREW_OVERLAP'} <= codes


@pytest.mark.parametrize('end_offset,kind,passes', [(None, 'GROUND_STOP', False),
    (0, 'GROUND_STOP', True), (1, 'GROUND_STOP', False), (None, 'WEATHER_ADVISORY', True)])
def test_confirmed_release_boundary_and_advisory(end_offset, kind, passes):
    seed = build_reference()
    f = seed.flights[0]
    restriction = RestrictionWindow(id='SYN-RESTRICTION', kind=kind, applicable_flight_ids=[f.id], movement='DEPARTURE',
        effective_ms=f.departure_ms-MINUTE, confirmed_end_ms=None if end_offset is None else f.departure_ms+end_offset,
        forecast_end_ms=f.departure_ms-1)
    assert gate(seed, restrictions=[restriction]).passed == passes


def test_runway_scope_does_not_close_other_flights():
    seed = build_reference()
    f = seed.flights[0]
    restriction = RestrictionWindow(id='SYN-RUNWAY', kind='RUNWAY_CLOSURE', applicable_flight_ids=[f.id], movement='DEPARTURE',
        effective_ms=f.departure_ms-MINUTE, confirmed_end_ms=None, forecast_end_ms=None)
    report = gate(seed, restrictions=[restriction])
    assert [(i.code, i.record_id) for i in report.issues] == [('ACTIVE_RESTRICTION', f.id)]


def test_unknown_authority_blocks_empty_restriction_list():
    assert not gate(build_reference(), verified=False).passed


def test_wrong_dispatch_operation_blocks():
    seed = build_reference()
    assert not validate_operations(seed, seed.flights, [], [], restriction_source_verified=True).passed


def test_runway_arrival_closure_checks_arrival_time():
    seed = build_reference()
    f = seed.flights[0]
    restriction = RestrictionWindow(id='SYN-RUNWAY', kind='RUNWAY_CLOSURE', applicable_flight_ids=[f.id],
        movement='ARRIVAL', effective_ms=f.arrival_ms-MINUTE, confirmed_end_ms=None, forecast_end_ms=None)
    assert not gate(seed, restrictions=[restriction]).passed
