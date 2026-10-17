"""Strict seed contracts for the initial schedule/resource/booking snapshot."""
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r'^SYN-[A-Z0-9-]+$')]
Millis = Annotated[int, Field(ge=0)]
Count = Annotated[int, Field(ge=0)]
AircraftType = Literal['DEMO180', 'DEMO90']


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class Interval(Record):
    start_ms: Millis
    end_ms: Millis

    @model_validator(mode='after')
    def chronological(self):
        if self.end_ms <= self.start_ms:
            raise ValueError('interval end must follow start')
        return self


class Flight(Record):
    id: Identifier
    origin: Identifier
    destination: Identifier
    origin_timezone: str
    destination_timezone: str
    departure_ms: Millis
    arrival_ms: Millis
    tail_id: Identifier
    crew_id: Identifier
    aircraft_type: AircraftType
    status: Literal['SCHEDULED', 'DEPARTED', 'COMPLETED', 'CANCELLED']
    predecessor_id: Identifier | None
    successor_id: Identifier | None
    day: Literal[1, 2]

    @field_validator('origin_timezone', 'destination_timezone')
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError('unknown timezone') from exc
        return value

    @model_validator(mode='after')
    def chronological(self):
        if self.arrival_ms <= self.departure_ms or self.origin == self.destination:
            raise ValueError('invalid flight times or endpoints')
        return self


class Aircraft(Record):
    id: Identifier
    aircraft_type: AircraftType
    initial_location: Identifier
    available: Interval
    unavailable: list[Interval]


class Crew(Record):
    id: Identifier
    initial_location: Identifier
    qualifications: list[AircraftType]
    available: Interval
    duty: Interval
    prior_rest: Interval


class Passenger(Record):
    id: Identifier
    booking_id: Identifier
    party_id: Identifier
    itinerary: Annotated[list[Identifier], Field(min_length=1, max_length=2)]
    original_arrival_ms: Millis
    eligible: bool
    assistance_required: bool
    assistance_confirmed: bool
    minimum_connection_minutes: Annotated[int, Field(ge=45)]
    contact_available: bool


class Inventory(Record):
    flight_id: Identifier
    capacity: Count
    occupied: Count
    other_bookings: Count
    version: Annotated[int, Field(ge=1)]


class SeedSnapshot(Record):
    schema_version: Literal['1']
    data_version: str
    seed: Literal['HUBRECOVER-001']
    hub_id: Identifier
    day_start_ms: Millis
    flights: list[Flight]
    aircraft: list[Aircraft]
    crews: list[Crew]
    passengers: list[Passenger]
    inventory: list[Inventory]
