"""Bounded candidate materialisation and complete-search publication."""
from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
import time

from .allocation import allocate
from .evidence import retrieve, warnings
from .gate import validate_operations
from .invariants import MINUTE, TURNAROUND
from .schemas import Flight
from .universe import select_descriptors


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                             allow_nan=False).encode()).hexdigest()


def propagate(seed, flights):
    current = {f.id: f.model_dump() for f in flights}
    groups = defaultdict(list)
    for f in seed.flights:
        groups['tail', f.tail_id].append(f)
        groups['crew', f.crew_id].append(f)
    for _ in range(len(flights) + 1):
        changed = False
        for (kind, _), sequence in groups.items():
            previous = None
            for old in sorted(sequence, key=lambda f: (f.departure_ms, f.id)):
                f = current[old.id]
                if f['status'] == 'CANCELLED':
                    continue
                if previous:
                    same_resource = (kind == 'crew' or previous['tail_id'] == f['tail_id'])
                    interval = TURNAROUND[f['aircraft_type']]*MINUTE if kind == 'tail' else 0
                    required = previous['arrival_ms'] + interval if same_resource else f['departure_ms']
                    shift = max(0, required-f['departure_ms'])
                    if shift:
                        if old.status != 'SCHEDULED':
                            raise ValueError('Propagation would change a fixed leg')
                        f['departure_ms'] += shift
                        f['arrival_ms'] += shift
                        changed = True
                previous = f
        if not changed:
            return [Flight.model_validate(current[f.id]) for f in seed.flights]
    raise ValueError('Propagation failed to converge')


def materialize(seed, current, descriptor):
    flights = {f.id: f.model_dump() for f in current}
    for root in descriptor.roots:
        if root not in flights or flights[root]['status'] != 'SCHEDULED':
            raise ValueError('Invalid candidate root')
    if descriptor.kind == 'DELAY':
        f = flights[descriptor.roots[0]]
        f['departure_ms'] += descriptor.delay_minutes*MINUTE
        f['arrival_ms'] += descriptor.delay_minutes*MINUTE
    elif descriptor.kind == 'SWAP':
        root = flights[descriptor.roots[0]]
        spare = next((t for t in seed.aircraft if t.id == descriptor.spare_tail), None)
        if not spare or spare.aircraft_type != root['aircraft_type'] or any(f.tail_id == spare.id for f in seed.flights):
            raise ValueError('Swap requires an unassigned compatible spare')
        tail = root['tail_id']
        for f in flights.values():
            if f['tail_id'] == tail and f['departure_ms'] >= root['departure_ms']:
                f['tail_id'] = spare.id
    elif descriptor.kind in ('CANCEL_SINGLE', 'CANCEL_PAIR'):
        for root in descriptor.roots:
            flights[root]['status'] = 'CANCELLED'
    else:
        raise ValueError('Unknown construction')
    return propagate(seed, [Flight.model_validate(flights[f.id]) for f in current])


def operation_key(f):
    return digest({k: getattr(f, k) for k in ('id', 'departure_ms', 'arrival_ms', 'tail_id', 'crew_id', 'status')})


def validate_constraints(constraints, seed):
    flights = {f.id for f in seed.flights}
    targets = {p.id for p in seed.passengers} | {p.party_id for p in seed.passengers}
    for c in constraints:
        if not isinstance(c, dict):
            raise ValueError('Invalid edit')
        kind = c.get('kind')
        allowed = {'kind', 'target', 'minutes'} if kind == 'maxArrivalDelay' else {'kind', 'target'}
        if set(c) != allowed:
            raise ValueError('Unsupported or ambiguous edit fields')
        if kind == 'protectFlight' and c['target'] in flights:
            continue
        if kind == 'protectConnection' and c['target'] == 'SYN-CONNECTION-INTERNATIONAL':
            continue
        if kind == 'maxArrivalDelay' and c['target'] in targets and type(c['minutes']) is int and c['minutes'] >= 0:
            continue
        raise ValueError('Unsupported edit or unknown target')


def satisfies(constraints, seed, flights, allocations):
    schedule = {f.id: f for f in flights}
    for c in constraints:
        if c['kind'] == 'protectFlight' and schedule[c['target']].status == 'CANCELLED':
            return False
        if c['kind'] == 'protectConnection':
            for a in allocations:
                if a.party_id.startswith('SYN-PARTY-0-') and (a.itinerary != ('SYN-F-0-1-0', 'SYN-F-0-1-1')):
                    return False
        if c['kind'] == 'maxArrivalDelay':
            for a in allocations:
                if c['target'] == a.party_id or c['target'] in a.passenger_ids:
                    if a.arrival_delay_minutes is None or a.arrival_delay_minutes > c['minutes']:
                        return False
    return True


def compatible_spares(scenario):
    assigned={f.tail_id for f in scenario.seed.flights}
    flights={f.id:f for f in scenario.current}
    return {root:[a.id for a in sorted(scenario.seed.aircraft,key=lambda a:a.id)
                  if a.id not in assigned and a.aircraft_type==flights[root].aircraft_type
                  and a.initial_location==flights[root].origin
                  and a.available.start_ms<=flights[root].departure_ms<a.available.end_ms
                  and not any(u.start_ms<=flights[root].departure_ms<u.end_ms for u in a.unavailable)][:2]
            for root in scenario.roots}


def build_plans(scenario, constraints=(), rejected=(), clock=time.monotonic, deadline_seconds=20):
    seed = scenario.seed
    validate_constraints(constraints, seed)
    started = clock()
    universe = select_descriptors(scenario.roots, compatible_spares(scenario))
    viable, failures, seen = [], [], set()
    for descriptor in universe.selected:
        if clock()-started >= deadline_seconds:
            return dict(status='SEARCH_INCOMPLETE', plans=[], rejected=[], completed=len(viable)+len(failures),
                        selected=len(universe.selected), raw=universe.raw_count)
        try:
            proposed = materialize(seed, scenario.current, descriptor)
            dispatch = scenario.dispatch_for(proposed)
            report = validate_operations(seed, proposed, dispatch, scenario.restrictions,
                                         restriction_source_verified=scenario.sources_verified)
            if not report.passed:
                failures.append(dict(descriptor=asdict(descriptor), reasons=[asdict(i) for i in report.issues]))
                continue
            allocation = allocate(seed, proposed, dispatch, scenario.positions)
            if not satisfies(constraints, seed, proposed, allocation.allocations):
                failures.append(dict(descriptor=asdict(descriptor), reasons=[dict(code='EDIT_CONSTRAINT', detail='Supported constraint not satisfied')]))
                continue
            operations = [dict(kind='FLIGHT', resource_id=f.id, departure_ms=f.departure_ms,
                               arrival_ms=f.arrival_ms, tail_id=f.tail_id, crew_id=f.crew_id, status=f.status)
                          for f, old in zip(proposed, seed.flights) if operation_key(f) != operation_key(old)]
            operations.sort(key=lambda o: (o['kind'], o['resource_id']))
            actions = [dict(party_id=a.party_id, passenger_ids=sorted(a.passenger_ids), outcome=a.outcome,
                            legs=list(a.itinerary) if a.itinerary else [], cabin='ECONOMY') for a in allocation.allocations]
            fingerprint = digest(dict(version=1, operations=operations, allocations=sorted(actions, key=lambda a: a['party_id'])))
            if fingerprint in seen or fingerprint in rejected:
                failures.append(dict(descriptor=asdict(descriptor), reasons=[dict(code='DUPLICATE_OR_REJECTED', detail='Unchanged action fingerprint excluded')]))
                continue
            seen.add(fingerprint)
            precedents=retrieve(seed,scenario.restrictions,descriptor.kind,limited=scenario.name=='limited')
            viable.append(dict(id=fingerprint[:16], fingerprint=fingerprint, descriptor=asdict(descriptor),
                ranking=allocation.ranking, operations=operations, flights=[f.model_dump() for f in proposed],
                allocations=[asdict(a) for a in allocation.allocations], inventory_after=dict(allocation.occupied_after),
                prerequisites=['AIRCRAFT_CONTROLLER', 'CREW_CONTROLLER', 'DISPATCHER', 'PASSENGER_OPERATIONS'],
                explanation='Calculated from synthetic schedule, crew, aircraft, inventory and passenger records. Passed the configured demo checks; operational acknowledgements and current approval are still required.',
                evidence=['SYN-SCHEDULE', 'SYN-CREW', 'SYN-AIRCRAFT', 'SYN-DISPATCH', 'SYN-INVENTORY'],
                precedents=precedents,evidence_status='GROUNDED' if precedents else 'LIMITED_PRECEDENT',
                warnings=warnings(allocation.ranking,len(seed.passengers),precedents)))
        except ValueError as exc:
            failures.append(dict(descriptor=asdict(descriptor), reasons=[dict(code='INVALID_CANDIDATE', detail=str(exc))]))
    if clock()-started >= deadline_seconds:
        return dict(status='SEARCH_INCOMPLETE', plans=[], rejected=[], completed=len(universe.selected), selected=len(universe.selected), raw=universe.raw_count)
    viable.sort(key=lambda p: (p['ranking'], p['fingerprint']))
    return dict(status='READY' if viable else 'NO_VIABLE_OPTION', plans=viable[:4], rejected=failures[:1],
                completed=len(universe.selected), selected=len(universe.selected), raw=universe.raw_count,
                viable=len(viable), distinct=len(seen), cap_applied=universe.cap_applied,
                universe_hash=universe.descriptor_hash, duration_seconds=clock()-started)
