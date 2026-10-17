"""Cross-record checks for a healthy initial seed, before disruption mutations.

Does not establish dispatch, restriction or proposed-operation feasibility.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass

from .schemas import SeedSnapshot

MINUTE = 60_000
DAY = 24 * 60 * MINUTE
CAPACITY = {'DEMO180': 180, 'DEMO90': 90}
TURNAROUND = {'DEMO180': 45, 'DEMO90': 35}


@dataclass(frozen=True)
class Issue:
    code: str
    record_id: str
    detail: str


def validate_seed(seed: SeedSnapshot, *, reference: bool = True) -> list[Issue]:
    issues = []

    def add(code, record_id, detail):
        issues.append(Issue(code, record_id, detail))

    def index(records, key='id'):
        values = [getattr(r, key) for r in records]
        for identity, count in Counter(values).items():
            if count != 1:
                add('DUPLICATE_ID', identity, f'{count} records')
        return dict(zip(values, records))

    flights = index(seed.flights)
    aircraft = index(seed.aircraft)
    crews = index(seed.crews)
    index(seed.passengers)
    inventory = index(seed.inventory, 'flight_id')
    index(seed.passengers, 'booking_id')
    if reference and (Counter(f.day for f in seed.flights) != {1: 18, 2: 6} or len(seed.passengers) != 300):
        add('REFERENCE_COUNTS', seed.seed, 'Expected 18 day-one flights, six next-day flights and 300 passengers')
    if set(inventory) != set(flights):
        add('INVENTORY_COVERAGE', seed.seed, 'Exactly one inventory record per flight required')
    tails, assignments = defaultdict(list), defaultdict(list)
    for flight in seed.flights:
        tails[flight.tail_id].append(flight)
        assignments[flight.crew_id].append(flight)
        if not seed.day_start_ms <= flight.departure_ms < flight.arrival_ms <= seed.day_start_ms + 2 * DAY:
            add('HORIZON', flight.id, 'Flight outside declared 48-hour horizon')
        if (flight.departure_ms - seed.day_start_ms) // DAY + 1 != flight.day:
            add('SERVICE_DAY', flight.id, 'Day label differs from UTC fixture day')
        if flight.tail_id not in aircraft or flight.crew_id not in crews:
            add('RESOURCE_REFERENCE', flight.id, 'Unknown tail or crew')
        elif aircraft[flight.tail_id].aircraft_type != flight.aircraft_type:
            add('AIRCRAFT_TYPE', flight.id, 'Tail type differs from flight')
        for field, reverse in [('predecessor_id', 'successor_id'), ('successor_id', 'predecessor_id')]:
            linked = getattr(flight, field)
            if linked is not None:
                other = flights.get(linked)
                if other is None or getattr(other, reverse) != flight.id or other.tail_id != flight.tail_id:
                    add('ROTATION_REFERENCE', flight.id, f'Invalid {field}')
        row = inventory.get(flight.id)
        if row and (row.capacity > CAPACITY[flight.aircraft_type] or row.occupied > row.capacity):
            add('CAPACITY', flight.id, 'Inventory exceeds usable or type capacity')
    for is_tail, resource_id, sequence in ([(True, k, v) for k, v in tails.items()]
                                           + [(False, k, v) for k, v in assignments.items()]):
        resource = (aircraft if is_tail else crews).get(resource_id)
        if resource is None:
            continue
        sequence.sort(key=lambda f: (f.departure_ms, f.id))
        previous = None
        for flight in sequence:
            if flight.origin != (previous.destination if previous else resource.initial_location):
                add('LOCATION_CONTINUITY', flight.id, resource_id)
            minimum = TURNAROUND[flight.aircraft_type] * MINUTE if is_tail else 0
            if previous and flight.departure_ms < previous.arrival_ms + minimum:
                add('TURNAROUND' if is_tail else 'CREW_OVERLAP', flight.id, resource_id)
            if not resource.available.start_ms <= flight.departure_ms < flight.arrival_ms <= resource.available.end_ms:
                add('AVAILABILITY', flight.id, resource_id)
            if is_tail:
                if any(flight.departure_ms < gap.end_ms and gap.start_ms < flight.arrival_ms for gap in resource.unavailable):
                    add('MAINTENANCE', flight.id, resource_id)
                expected = previous.id if previous else None
                if flight.predecessor_id != expected:
                    add('ROTATION_ORDER', flight.id, 'Predecessor must match chronological tail sequence')
            else:
                if flight.aircraft_type not in resource.qualifications:
                    add('QUALIFICATION', flight.id, resource_id)
                if not resource.duty.start_ms <= flight.departure_ms < flight.arrival_ms <= resource.duty.end_ms:
                    add('DUTY_COVERAGE', flight.id, resource_id)
            previous = flight
        if not is_tail:
            if resource.duty.end_ms - resource.duty.start_ms > 600 * MINUTE:
                add('CREW_DUTY', resource_id, 'Duty exceeds fictional ten-hour rule')
            if resource.prior_rest.end_ms > resource.duty.start_ms or resource.prior_rest.end_ms - resource.prior_rest.start_ms < 600 * MINUTE:
                add('CREW_REST', resource_id, 'Prior rest must end before duty and last at least ten hours')
    reserved = Counter()
    parties = defaultdict(list)
    for passenger in seed.passengers:
        parties[passenger.party_id].append(passenger)
        if len(set(passenger.itinerary)) != len(passenger.itinerary):
            add('ITINERARY_CYCLE', passenger.id, 'Repeated flight')
        legs = [flights.get(i) for i in passenger.itinerary]
        if any(leg is None for leg in legs):
            add('ITINERARY_REFERENCE', passenger.id, 'Unknown flight')
            continue
        reserved.update(passenger.itinerary)
        if any(leg.status == "CANCELLED" for leg in legs):
            add("CANCELLED_ITINERARY", passenger.id, "Healthy baseline cannot include a cancelled leg")
        if legs[-1].arrival_ms != passenger.original_arrival_ms:
            add('ARRIVAL_BASELINE', passenger.id, 'Original arrival differs from original itinerary')
        airports = [legs[0].origin] + [leg.destination for leg in legs]
        if len(set(airports)) != len(airports):
            add('ITINERARY_CYCLE', passenger.id, 'Airport revisit')
        for first, second in zip(legs, legs[1:]):
            if first.destination != second.origin or second.departure_ms - first.arrival_ms < passenger.minimum_connection_minutes * MINUTE:
                add('CONNECTION', passenger.id, 'Broken location or insufficient connection time')
        if passenger.assistance_required and not passenger.assistance_confirmed:
            add('ASSISTANCE', passenger.id, 'Healthy baseline requires confirmed support')
    for party_id, members in parties.items():
        if len({(tuple(p.itinerary), p.original_arrival_ms) for p in members}) != 1:
            add('PARTY_COHESION', party_id, 'Members have different original itineraries')
    for row in seed.inventory:
        if row.occupied != reserved[row.flight_id] + row.other_bookings:
            add('MANIFEST_ACCOUNTING', row.flight_id, 'Occupied differs from cohort plus other bookings')
    return issues
