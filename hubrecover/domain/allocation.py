"""Pure, whole-party allocation with execution-prefix seat accounting.

This is a planning calculation, not an executable plan or booking API. Resource,
restriction, approval and operational prerequisite gates remain separate.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .invariants import DAY, MINUTE, validate_seed
from .schemas import Flight, Identifier, Millis, Record, SeedSnapshot
from typing import Literal


class DispatchEvidence(Record):
    flight_id: Identifier
    departure_ms: Millis
    arrival_ms: Millis
    tail_id: Identifier
    crew_id: Identifier
    status: Literal['VERIFIED', 'BLOCKED', 'UNKNOWN']
    route_compatible: bool
    fuel_compatible: bool
    restriction_compatible: bool

    def matches(self, flight: Flight) -> bool:
        return (self.status == 'VERIFIED' and self.route_compatible and self.fuel_compatible
                and self.restriction_compatible and self.flight_id == flight.id
                and self.departure_ms == flight.departure_ms and self.arrival_ms == flight.arrival_ms
                and self.tail_id == flight.tail_id and self.crew_id == flight.crew_id)


class Position(Record):
    party_id: Identifier
    airport_id: Identifier
    ready_ms: Millis
    completed_prefix: list[Identifier]


@dataclass(frozen=True)
class Allocation:
    party_id: str
    passenger_ids: tuple[str, ...]
    outcome: str
    itinerary: tuple[str, ...] | None
    final_arrival_ms: int | None
    next_day: bool
    arrival_delay_minutes: int | None
    reason: str


@dataclass(frozen=True)
class AllocationResult:
    allocations: tuple[Allocation, ...]
    occupied_after: tuple[tuple[str, int], ...]
    ranking: tuple[int, int, int, int, int]


def service_date(timestamp_ms: int, zone: str):
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).astimezone(ZoneInfo(zone)).date()


def allocate(seed: SeedSnapshot, proposed: list[Flight], dispatch: list[DispatchEvidence],
             positions: list[Position]) -> AllocationResult:
    errors = validate_seed(seed, reference=False)
    if errors:
        raise ValueError(f'Invalid baseline snapshot: {errors[0]}')
    original = {f.id: f for f in seed.flights}
    flights = {f.id: f for f in proposed}
    if len(flights) != len(proposed) or set(flights) != set(original):
        raise ValueError('Proposed schedule must contain exactly the original flight IDs')
    for f in proposed:
        old = original[f.id]
        if (f.origin, f.destination, f.aircraft_type, f.day, f.origin_timezone, f.destination_timezone) != (
            old.origin, old.destination, old.aircraft_type, old.day, old.origin_timezone, old.destination_timezone
        ) or f.arrival_ms - f.departure_ms != old.arrival_ms - old.departure_ms:
            raise ValueError('No invented endpoints, types, dates, zones or flight durations')
        if old.status in ('COMPLETED', 'DEPARTED') and f != old:
            raise ValueError('Departed/completed legs are fixed')
    evidence = {e.flight_id: e for e in dispatch}
    if len(evidence) != len(dispatch) or set(evidence) - set(flights):
        raise ValueError('Duplicate or unknown dispatch operation evidence')
    parties = defaultdict(list)
    for passenger in seed.passengers:
        parties[passenger.party_id].append(passenger)
    location = {p.party_id: p for p in positions}
    if len(location) != len(positions) or set(location) != set(parties):
        raise ValueError('Verified position required for every party exactly once')
    inventory = {r.flight_id: r for r in seed.inventory}
    occupied = {r.flight_id: r.occupied for r in seed.inventory}
    results = []
    for party_id in sorted(parties, key=lambda p: (parties[p][0].original_arrival_ms, p)):
        members = parties[party_id]
        first = members[0]
        size = len(members)
        place = location[party_id]
        prefix = place.completed_prefix
        if prefix != first.itinerary[:len(prefix)] or any(original[i].status != 'COMPLETED' for i in prefix):
            raise ValueError('Completed prefix must match confirmed completed original legs')
        expected_location = original[prefix[-1]].destination if prefix else original[first.itinerary[0]].origin
        if place.airport_id != expected_location or (prefix and place.ready_ms < original[prefix[-1]].arrival_ms):
            raise ValueError('Position inconsistent with completed prefix')
        destination = original[first.itinerary[-1]].destination
        destination_zone = original[first.itinerary[-1]].destination_timezone
        mct = max(p.minimum_connection_minutes for p in members) * MINUTE
        def usable(f):
            return (f.status == 'SCHEDULED' and seed.day_start_ms <= f.departure_ms < f.arrival_ms <= seed.day_start_ms + 2*DAY
                    and f.id in evidence and evidence[f.id].matches(f))
        candidates = []
        if len(prefix) == len(first.itinerary):
            candidates = [tuple(prefix)]
        else:
            earliest = max(place.ready_ms, original[prefix[-1]].arrival_ms + mct) if prefix else place.ready_ms
            for one in proposed:
                if not usable(one) or one.origin != place.airport_id or one.departure_ms < earliest:
                    continue
                if one.destination == destination:
                    candidates.append(tuple(prefix + [one.id]))
                for two in proposed:
                    visited = [original[i].origin for i in prefix] + [place.airport_id, one.destination, two.destination]
                    if (usable(two) and two.origin == one.destination and two.destination == destination
                            and two.departure_ms - one.arrival_ms >= mct and len(set(visited)) == len(visited)):
                        candidates.append(tuple(prefix + [one.id, two.id]))
        # No airport revisits, including a completed prefix, even for direct paths.
        candidates = [path for path in set(candidates) if len(set(
            [flights[path[0]].origin] + [flights[i].destination for i in path])) == len(path) + 1]
        candidates.sort(key=lambda path: (flights[path[-1]].arrival_ms, path))
        if any(p.assistance_required and not p.assistance_confirmed for p in members):
            candidates = []
        old_reserved = Counter({i: size for i in first.itinerary})
        chosen = None
        for path in candidates:
            if path != tuple(first.itinerary) and not all(p.eligible for p in members):
                continue
            new_reserved = Counter({i: size for i in path})
            delta = {i: new_reserved[i] - old_reserved[i] for i in new_reserved.keys() | old_reserved.keys()}
            if all(0 <= occupied[i] + seats <= inventory[i].capacity for i, seats in delta.items()):
                for flight_id, seats in delta.items():
                    occupied[flight_id] += seats
                chosen = path
                break
        if chosen is None:
            results.append(Allocation(party_id, tuple(p.id for p in members), 'UNRESOLVED', None,
                                      None, False, None, 'No eligible, supported whole-party itinerary with current seats'))
            continue
        arrival = flights[chosen[-1]].arrival_ms
        overnight = service_date(arrival, destination_zone) > service_date(first.original_arrival_ms, destination_zone)
        delay_ms = max(0, arrival - first.original_arrival_ms)
        if delay_ms % MINUTE:
            raise ValueError('Arrival delay must be whole minutes; never round operational values')
        outcome = ('RETAINED' if chosen == tuple(first.itinerary) else
                   'REBOOKED_NEXT_DAY' if overnight else 'REBOOKED_SAME_DAY')
        results.append(Allocation(party_id, tuple(p.id for p in members), outcome, chosen,
                                  arrival, overnight, delay_ms // MINUTE, 'Calculated; execution still requires all gates'))
    cancelled = sum(f.status == 'CANCELLED' and original[f.id].status != 'CANCELLED' for f in proposed)
    flight_delay_ms = sum(max(0, f.departure_ms-original[f.id].departure_ms) for f in proposed if f.status != 'CANCELLED')
    if flight_delay_ms % MINUTE:
        raise ValueError('Departure delay must be whole minutes')
    ranking = (sum(len(a.passenger_ids) for a in results if a.outcome == 'UNRESOLVED'),
               sum(len(a.passenger_ids) for a in results if a.next_day),
               sum(len(a.passenger_ids)*(a.arrival_delay_minutes or 0) for a in results),
               cancelled, flight_delay_ms//MINUTE)
    return AllocationResult(tuple(results), tuple(sorted(occupied.items())), ranking)
