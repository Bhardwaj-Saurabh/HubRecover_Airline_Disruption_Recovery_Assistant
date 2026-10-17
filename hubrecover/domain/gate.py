"""Configured fictional operational checks. Passing never grants write authority."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from pydantic import model_validator

from .allocation import DispatchEvidence
from .invariants import DAY, MINUTE, TURNAROUND, Issue
from .schemas import Flight, Identifier, Millis, Record, SeedSnapshot


class RestrictionWindow(Record):
    id: Identifier
    kind: Literal['GROUND_STOP', 'RUNWAY_CLOSURE', 'WEATHER_ADVISORY']
    applicable_flight_ids: list[Identifier]
    movement: Literal['DEPARTURE', 'ARRIVAL']
    effective_ms: Millis
    confirmed_end_ms: Millis | None
    # A forecast is never an execution-compatible release.
    forecast_end_ms: Millis | None

    @model_validator(mode='after')
    def interval_valid(self):
        if self.kind == 'GROUND_STOP' and self.movement != 'DEPARTURE':
            raise ValueError('Ground stop holds scoped flights at departure origins')
        if self.confirmed_end_ms is not None and self.confirmed_end_ms <= self.effective_ms:
            raise ValueError('Confirmed end must follow restriction start')
        if len(set(self.applicable_flight_ids)) != len(self.applicable_flight_ids):
            raise ValueError('Duplicate restriction flight scope')
        return self


@dataclass(frozen=True)
class GateReport:
    issues: tuple[Issue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def validate_operations(seed: SeedSnapshot, proposed: list[Flight], dispatch: list[DispatchEvidence],
                        restrictions: list[RestrictionWindow], *, restriction_source_verified: bool) -> GateReport:
    issues = []
    def fail(code, identity, detail):
        issues.append(Issue(code, identity, detail))
    if restriction_source_verified is not True:
        fail('RESTRICTION_SOURCE_UNKNOWN', seed.seed, 'Verified authority context required')
    originals = {f.id: f for f in seed.flights}
    flights = {f.id: f for f in proposed}
    tails = {a.id: a for a in seed.aircraft}
    crews = {c.id: c for c in seed.crews}
    evidence = {d.flight_id: d for d in dispatch}
    if len(tails) != len(seed.aircraft) or len(crews) != len(seed.crews) or len(originals) != len(seed.flights):
        fail('DUPLICATE_SOURCE', seed.seed, 'Source identities must be unique')
    if len(flights) != len(proposed) or set(flights) != set(originals):
        fail('FLIGHT_SET', seed.seed, 'Exact declared flight set required')
        return GateReport(tuple(issues))
    if len(evidence) != len(dispatch) or set(evidence) - set(flights):
        fail('DISPATCH_REFERENCE', seed.seed, 'Duplicate/unknown dispatch evidence')
    for r in restrictions:
        if set(r.applicable_flight_ids) - set(flights):
            fail('RESTRICTION_SCOPE', r.id, 'Unknown flight in declared applicability')
    by_tail, by_crew = defaultdict(list), defaultdict(list)
    for f in proposed:
        old = originals[f.id]
        if (f.origin, f.destination, f.aircraft_type, f.crew_id) != (old.origin, old.destination, old.aircraft_type, old.crew_id):
            fail('UNSUPPORTED_OPERATION', f.id, 'No endpoint/type changes or crew reassignment')
        if old.status in ('DEPARTED', 'COMPLETED') and f != old:
            fail('COMPLETED_LEG_CHANGED', f.id, 'Departed and completed legs remain fixed')
        if old.status == 'CANCELLED' and f.status != 'CANCELLED':
            fail('CANCELLED_LEG_REVIVED', f.id, 'Committed cancellation cannot be reversed')
        if old.status == 'SCHEDULED' and f.status not in ('SCHEDULED', 'CANCELLED'):
            fail('INVENTED_COMMITMENT', f.id, 'Plans cannot declare departures/completions')
        if f.status == 'CANCELLED':
            continue
        if f.arrival_ms-f.departure_ms != old.arrival_ms-old.departure_ms:
            fail('BLOCK_DURATION', f.id, 'Verified flight duration must be preserved')
        if f.departure_ms < old.departure_ms:
            fail('EARLY_DEPARTURE', f.id, 'Declared search never advances departure')
        if not seed.day_start_ms <= f.departure_ms < f.arrival_ms <= seed.day_start_ms+2*DAY:
            fail('HORIZON', f.id, 'Outside declared 48-hour horizon')
        if f.tail_id not in tails or f.crew_id not in crews:
            fail('RESOURCE_UNKNOWN', f.id, 'Missing aircraft or crew')
            continue
        tail, crew = tails[f.tail_id], crews[f.crew_id]
        if tail.aircraft_type != f.aircraft_type:
            fail('AIRCRAFT_TYPE', f.id, 'Incompatible tail')
        if f.aircraft_type not in crew.qualifications:
            fail('CREW_QUALIFICATION', f.id, 'Missing aircraft qualification')
        if not crew.duty.start_ms <= f.departure_ms < f.arrival_ms <= crew.duty.end_ms:
            fail('CREW_DUTY_COVERAGE', f.id, 'Proposed operation exceeds verified duty interval')
        if crew.duty.end_ms-crew.duty.start_ms > 600*MINUTE:
            fail('CREW_DUTY', f.id, 'Verified duty exceeds fictional ten-hour ceiling')
        if crew.prior_rest.end_ms > crew.duty.start_ms or crew.prior_rest.end_ms-crew.prior_rest.start_ms < 600*MINUTE:
            fail('CREW_REST', f.id, 'Insufficient verified prior rest')
        for resource in (tail, crew):
            if not resource.available.start_ms <= f.departure_ms < f.arrival_ms <= resource.available.end_ms:
                fail('RESOURCE_AVAILABILITY', f.id, resource.id)
        if any(f.departure_ms < gap.end_ms and gap.start_ms < f.arrival_ms for gap in tail.unavailable):
            fail('MAINTENANCE', f.id, tail.id)
        if f.status == 'SCHEDULED':
            if f.id not in evidence or not evidence[f.id].matches(f):
                fail('DISPATCH_UNVERIFIED', f.id, 'Verified evidence must match the exact proposed operation')
            for r in restrictions:
                movement_ms = f.departure_ms if r.movement == 'DEPARTURE' else f.arrival_ms
                if (r.kind != 'WEATHER_ADVISORY' and f.id in r.applicable_flight_ids
                        and movement_ms >= r.effective_ms
                        and (r.confirmed_end_ms is None or movement_ms < r.confirmed_end_ms)):
                    fail('ACTIVE_RESTRICTION', f.id, r.id)
        by_tail[f.tail_id].append(f)
        by_crew[f.crew_id].append(f)
    for is_tail, resources, groups in ((True, tails, by_tail), (False, crews, by_crew)):
        for resource_id, sequence in groups.items():
            resource = resources[resource_id]
            previous = None
            for flight in sorted(sequence, key=lambda f: (f.departure_ms, f.id)):
                expected_location = previous.destination if previous else resource.initial_location
                if flight.origin != expected_location:
                    fail('LOCATION_CONTINUITY', flight.id, resource_id)
                interval = TURNAROUND[flight.aircraft_type]*MINUTE if is_tail else 0
                if previous and flight.departure_ms < previous.arrival_ms + interval:
                    fail('TURNAROUND' if is_tail else 'CREW_OVERLAP', flight.id, resource_id)
                previous = flight
    return GateReport(tuple(issues))
