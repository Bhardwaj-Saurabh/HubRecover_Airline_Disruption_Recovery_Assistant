from copy import deepcopy

import pytest

from hubrecover.domain.allocation import DispatchEvidence, Position, allocate
from hubrecover.domain.invariants import DAY, MINUTE
from hubrecover.domain.schemas import Flight, SeedSnapshot
from hubrecover.fixtures.reference import build_reference


def evidence(flights):
    # Explicit synthetic evidence for unit tests, not an operational verifier.
    return [DispatchEvidence(flight_id=f.id, departure_ms=f.departure_ms, arrival_ms=f.arrival_ms,
                             tail_id=f.tail_id, crew_id=f.crew_id, status='VERIFIED',
                             route_compatible=True, fuel_compatible=True, restriction_compatible=True)
            for f in flights]


def positions(seed):
    flights = {f.id: f for f in seed.flights}
    parties = {p.party_id: p for p in seed.passengers}
    return [Position(party_id=key, airport_id=flights[p.itinerary[0]].origin,
                     ready_ms=seed.day_start_ms, completed_prefix=[]) for key, p in parties.items()]


def change(flights, flight_id, **updates):
    return [Flight.model_validate(dict(f.model_dump(), **updates)) if f.id == flight_id else f for f in flights]


def test_reference_all_retained_and_counts_reconcile():
    seed = build_reference()
    result = allocate(seed, seed.flights, evidence(seed.flights), positions(seed))
    assert result.ranking == (0, 0, 0, 0, 0)
    assert len(result.allocations) == 150
    assert all(a.outcome == 'RETAINED' for a in result.allocations)
    assert sum(len(a.passenger_ids) for a in result.allocations) == 300
    assert dict(result.occupied_after) == {r.flight_id: r.occupied for r in seed.inventory}


def test_cancel_outbound_rebooks_fifty_next_day_with_shared_leg_net_zero():
    seed = build_reference()
    proposed = change(seed.flights, 'SYN-F-0-1-1', status='CANCELLED')
    result = allocate(seed, proposed, evidence(proposed), positions(seed))
    # 50 passengers × exactly 24 hours, one cancelled flight, no departure delay.
    assert result.ranking == (0, 50, 50*24*60, 1, 0)
    occupancy = dict(result.occupied_after)
    assert occupancy['SYN-F-0-1-0'] == 70  # shared first leg unchanged
    assert occupancy['SYN-F-0-1-1'] == 20  # original reservations released
    assert occupancy['SYN-F-0-2-0'] == 70  # new reservations added
    cohort = [a for a in result.allocations if a.party_id.startswith('SYN-PARTY-0-')]
    assert all(a.outcome == 'REBOOKED_NEXT_DAY' for a in cohort)
    assert all(len(a.passenger_ids) == 2 for a in cohort)


def test_one_seat_cannot_split_party_or_release_old_reservations():
    raw = build_reference().model_dump()
    for row in raw['inventory']:
        if row['flight_id'] == 'SYN-F-0-2-0':
            row['other_bookings'] = row['occupied'] = 179
    seed = SeedSnapshot.model_validate(raw)
    proposed = change(seed.flights, 'SYN-F-0-1-1', status='CANCELLED')
    result = allocate(seed, proposed, evidence(proposed), positions(seed))
    assert result.ranking == (50, 0, 0, 1, 0)
    occupancy = dict(result.occupied_after)
    assert occupancy['SYN-F-0-1-1'] == 70
    assert occupancy['SYN-F-0-2-0'] == 179
    assert all(a.final_arrival_ms is None for a in result.allocations if a.outcome == 'UNRESOLVED')


def test_shared_full_flight_does_not_need_duplicate_seats():
    raw = build_reference().model_dump()
    row = next(r for r in raw['inventory'] if r['flight_id'] == 'SYN-F-0-1-0')
    row.update(occupied=180, other_bookings=130)
    seed = SeedSnapshot.model_validate(raw)
    proposed = change(seed.flights, 'SYN-F-0-1-1', status='CANCELLED')
    result = allocate(seed, proposed, evidence(proposed), positions(seed))
    assert result.ranking[0] == 0
    assert dict(result.occupied_after)['SYN-F-0-1-0'] == 180


@pytest.mark.parametrize('failure', ['missing', 'unknown', 'blocked', 'stale', 'restriction'])
def test_dispatch_missing_or_wrong_operation_blocks_affected_leg(failure):
    seed = build_reference()
    records = evidence(seed.flights)
    index = next(i for i, r in enumerate(records) if r.flight_id == 'SYN-F-0-1-0')
    if failure == 'missing':
        records.pop(index)
    else:
        data = records[index].model_dump()
        if failure in ('unknown', 'blocked'):
            data['status'] = failure.upper()
        elif failure == 'stale':
            data['departure_ms'] += MINUTE
        else:
            data['restriction_compatible'] = False
        records[index] = DispatchEvidence.model_validate(data)
    result = allocate(seed, seed.flights, records, positions(seed))
    assert result.ranking[0] == 50


def test_ineligible_party_can_retain_but_cannot_rebook():
    raw = build_reference().model_dump()
    raw['passengers'][0]['eligible'] = False
    seed = SeedSnapshot.model_validate(raw)
    assert allocate(seed, seed.flights, evidence(seed.flights), positions(seed)).ranking[0] == 0
    proposed = change(seed.flights, 'SYN-F-0-1-1', status='CANCELLED')
    result = allocate(seed, proposed, evidence(proposed), positions(seed))
    assert result.ranking[0] == 2
    assert result.allocations[0].outcome == 'UNRESOLVED'


def test_lexicographic_party_priority_for_scarce_seats():
    raw = build_reference().model_dump()
    row = next(r for r in raw['inventory'] if r['flight_id'] == 'SYN-F-0-2-0')
    row.update(occupied=178, other_bookings=178)
    seed = SeedSnapshot.model_validate(raw)
    proposed = change(seed.flights, 'SYN-F-0-1-1', status='CANCELLED')
    result = allocate(seed, list(reversed(proposed)), evidence(proposed), list(reversed(positions(seed))))
    assert result.allocations[0].party_id == 'SYN-PARTY-0-00'
    assert result.allocations[0].outcome == 'REBOOKED_NEXT_DAY'
    assert result.ranking[:3] == (48, 2, 2880)


def test_missing_position_fails_closed():
    seed = build_reference()
    with pytest.raises(ValueError, match='position'):
        allocate(seed, seed.flights, evidence(seed.flights), positions(seed)[1:])


def test_invented_flight_duration_fails_closed():
    seed = build_reference()
    proposed = change(seed.flights, seed.flights[0].id, arrival_ms=seed.flights[0].arrival_ms+MINUTE)
    with pytest.raises(ValueError, match='durations'):
        allocate(seed, proposed, evidence(proposed), positions(seed))


def test_model_inputs_not_mutated():
    seed = build_reference()
    before = deepcopy(seed.model_dump())
    allocate(seed, seed.flights, evidence(seed.flights), positions(seed))
    assert seed.model_dump() == before


def test_retained_itineraries_can_still_count_as_next_day():
    seed = build_reference()
    proposed = [Flight.model_validate(dict(f.model_dump(), departure_ms=f.departure_ms+DAY,
                                          arrival_ms=f.arrival_ms+DAY)) if f.day == 1 else f for f in seed.flights]
    result = allocate(seed, proposed, evidence(proposed), positions(seed))
    assert all(a.outcome == 'RETAINED' for a in result.allocations)
    assert result.ranking == (0, 300, 300*1440, 0, 18*1440)


def test_completed_prefix_is_preserved():
    raw = build_reference().model_dump()
    raw['flights'][0]['status'] = 'COMPLETED'
    seed = SeedSnapshot.model_validate(raw)
    places = positions(seed)
    places = [Position(party_id=p.party_id, airport_id='SYN-HUB', ready_ms=seed.flights[0].arrival_ms,
                       completed_prefix=[seed.flights[0].id]) if p.party_id.startswith('SYN-PARTY-0-') else p
              for p in places]
    result = allocate(seed, seed.flights, evidence(seed.flights), places)
    assert result.ranking == (0, 0, 0, 0, 0)
    assert all(a.itinerary[0] == seed.flights[0].id for a in result.allocations[:25])


def test_earlier_party_cannot_borrow_later_party_released_seats():
    raw = build_reference().model_dump()
    # Three independent, same-route flights. Parties hold the first and second.
    source = raw['flights'][0]
    flights, aircraft, crews = [], [], []
    for index, hour in enumerate((6, 10, 8)):
        tail, crew = f'SYN-T-{index}', f'SYN-C-{index}'
        flights.append(dict(source, id=f'SYN-TEST-{index}', departure_ms=raw['day_start_ms']+hour*60*MINUTE,
                            arrival_ms=raw['day_start_ms']+(hour+1)*60*MINUTE,
                            tail_id=tail, crew_id=crew, predecessor_id=None, successor_id=None))
        aircraft.append(dict(raw['aircraft'][0], id=tail))
        crews.append(dict(raw['crews'][0], id=crew))
    passengers = []
    for i in range(4):
        group = i//2
        passengers.append(dict(raw['passengers'][i], party_id=f'SYN-GROUP-{group}',
                               itinerary=[flights[group]['id']], original_arrival_ms=flights[group]['arrival_ms']))
    raw.update(flights=flights, aircraft=aircraft, crews=crews, passengers=passengers,
               inventory=[dict(flight_id=f['id'], capacity=2, occupied=2 if i<2 else 0,
                               other_bookings=0, version=1) for i, f in enumerate(flights)])
    seed = SeedSnapshot.model_validate(raw)
    proposed = change(seed.flights, 'SYN-TEST-0', status='CANCELLED')
    places = [Position(party_id=f'SYN-GROUP-{i}', airport_id=source['origin'], completed_prefix=[],
                       ready_ms=raw['day_start_ms']+(9 if i == 0 else 5)*60*MINUTE) for i in range(2)]
    result = allocate(seed, proposed, evidence(proposed), places)
    assert result.allocations[0].outcome == 'UNRESOLVED'
    assert result.allocations[1].itinerary == ('SYN-TEST-2',)
    assert dict(result.occupied_after)['SYN-TEST-1'] == 0
    assert dict(result.occupied_after)['SYN-TEST-0'] == 2
