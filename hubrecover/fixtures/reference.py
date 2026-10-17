"""Reproducible healthy baseline. Restrictions/dispatch are separate future inputs."""
import json
from pathlib import Path

from hubrecover.domain.invariants import CAPACITY, DAY, MINUTE, validate_seed
from hubrecover.domain.schemas import SeedSnapshot

START = 1_790_121_600_000  # 2026-09-23 00:00:00 UTC; fictional service date


def build_reference() -> SeedSnapshot:
    flights, aircraft, crews, passengers, inventory = [], [], [], [], []
    for route in range(6):
        origin, destination = f'SYN-ORIGIN-{route}', f'SYN-DEST-{route}'
        for day in (1, 2):
            base = START + (day - 1) * DAY
            tail, crew = f'SYN-TAIL-{route}-{day}', f'SYN-CREW-{route}-{day}'
            legs = [(origin, 'SYN-HUB', 6, 7), ('SYN-HUB', destination, 8, 9),
                    (destination, 'SYN-HUB', 10, 11)] if day == 1 else [('SYN-HUB', destination, 8, 9)]
            ids = [f'SYN-F-{route}-{day}-{i}' for i in range(len(legs))]
            aircraft.append(dict(id=tail, aircraft_type='DEMO180', initial_location=legs[0][0],
                                 available=dict(start_ms=base, end_ms=base + DAY), unavailable=[]))
            crews.append(dict(id=crew, initial_location=legs[0][0], qualifications=['DEMO180'],
                              available=dict(start_ms=base, end_ms=base + DAY),
                              duty=dict(start_ms=base + 5*60*MINUTE, end_ms=base + 15*60*MINUTE),
                              prior_rest=dict(start_ms=base - 5*60*MINUTE, end_ms=base + 5*60*MINUTE)))
            for i, (source, target, depart, arrive) in enumerate(legs):
                flights.append(dict(id=ids[i], origin=source, destination=target,
                                    origin_timezone='UTC', destination_timezone='UTC',
                                    departure_ms=base + depart*60*MINUTE,
                                    arrival_ms=base + arrive*60*MINUTE,
                                    tail_id=tail, crew_id=crew, aircraft_type='DEMO180',
                                    status='SCHEDULED', predecessor_id=ids[i-1] if i else None,
                                    successor_id=ids[i+1] if i+1 < len(ids) else None, day=day))
                cohort = 50 if day == 1 and i < 2 else 0
                inventory.append(dict(flight_id=ids[i], capacity=CAPACITY['DEMO180'],
                                      occupied=cohort+20, other_bookings=20, version=1))
            if day == 1:
                for person in range(50):
                    passengers.append(dict(id=f'SYN-P-{route}-{person:02}',
                                           booking_id=f'SYN-B-{route}-{person:02}',
                                           party_id=f'SYN-PARTY-{route}-{person//2:02}', itinerary=ids[:2],
                                           original_arrival_ms=base+9*60*MINUTE, eligible=True,
                                           assistance_required=person < 2, assistance_confirmed=True,
                                           minimum_connection_minutes=60 if person < 2 else 45,
                                           contact_available=True))
    snapshot = SeedSnapshot.model_validate(dict(schema_version='1', data_version='BASELINE-001',
        seed='HUBRECOVER-001', hub_id='SYN-HUB', day_start_ms=START, flights=flights,
        aircraft=aircraft, crews=crews, passengers=passengers, inventory=inventory))
    issues = validate_seed(snapshot)
    if issues:
        raise ValueError(f'Invalid generated reference: {issues}')
    return snapshot


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Validate or export the fictional baseline')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    snapshot = build_reference()
    if args.output:
        args.output.write_text(json.dumps(snapshot.model_dump(), sort_keys=True, indent=2) + '\n')
    print(f'{len(snapshot.flights)} flights; {len(snapshot.passengers)} passengers; seed invariants PASS')
