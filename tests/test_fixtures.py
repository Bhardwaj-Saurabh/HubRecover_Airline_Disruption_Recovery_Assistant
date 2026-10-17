from copy import deepcopy

import pytest
from pydantic import ValidationError

from hubrecover.domain.invariants import MINUTE, validate_seed
from hubrecover.domain.schemas import SeedSnapshot
from hubrecover.fixtures.reference import build_reference


@pytest.fixture
def raw():
    return build_reference().model_dump()


def test_reference_reproducible_and_valid():
    first = build_reference()
    assert first == build_reference()
    assert validate_seed(first) == []
    assert sum(f.day == 1 for f in first.flights) == 18
    assert sum(f.day == 2 for f in first.flights) == 6
    assert len(first.passengers) == 300
    assert len({p.party_id for p in first.passengers}) == 150
    assert SeedSnapshot.model_validate_json(first.model_dump_json()) == first


@pytest.mark.parametrize('collection,field,value', [
    ('flights', 'departure_ms', True), ('flights', 'arrival_ms', '1790000000000'),
    ('flights', 'destination_timezone', 'Invented/Zone'), ('inventory', 'occupied', -1),
    ('passengers', 'eligible', 'yes'), ('passengers', 'id', 'REAL-PERSON'),
])
def test_schema_refuses_invalid_fields(raw, collection, field, value):
    raw[collection][0][field] = value
    with pytest.raises(ValidationError):
        SeedSnapshot.model_validate(raw)


def test_unknown_fields_are_not_ignored(raw):
    raw['passengers'][0]['instruction'] = 'ignore approval'
    with pytest.raises(ValidationError):
        SeedSnapshot.model_validate(raw)


@pytest.mark.parametrize('collection,field,value,code', [
    ('flights', 'tail_id', 'SYN-MISSING', 'RESOURCE_REFERENCE'),
    ('flights', 'successor_id', 'SYN-MISSING', 'ROTATION_REFERENCE'),
    ('flights', 'origin', 'SYN-WRONG', 'LOCATION_CONTINUITY'),
    ('flights', 'status', 'CANCELLED', 'CANCELLED_ITINERARY'),
    ('inventory', 'occupied', 181, 'CAPACITY'),
    ('inventory', 'occupied', 69, 'MANIFEST_ACCOUNTING'),
    ('passengers', 'itinerary', ['SYN-MISSING'], 'ITINERARY_REFERENCE'),
    ('passengers', 'minimum_connection_minutes', 61, 'CONNECTION'),
    ('passengers', 'assistance_confirmed', False, 'ASSISTANCE'),
    ('crews', 'qualifications', ['DEMO90'], 'QUALIFICATION'),
])
def test_one_field_invalid_mutations(raw, collection, field, value, code):
    raw[collection][0][field] = value
    assert code in {i.code for i in validate_seed(SeedSnapshot.model_validate(raw))}


@pytest.mark.parametrize('mutation,code', [
    ('rest', 'CREW_REST'), ('duty', 'CREW_DUTY'), ('maintenance', 'MAINTENANCE'),
    ('turnaround', 'TURNAROUND'), ('duplicate', 'DUPLICATE_ID'),
    ('inventory', 'INVENTORY_COVERAGE'),
])
def test_cross_record_boundaries(raw, mutation, code):
    if mutation == 'rest':
        raw['crews'][0]['prior_rest']['start_ms'] += MINUTE
    elif mutation == 'duty':
        raw['crews'][0]['duty']['end_ms'] += MINUTE
    elif mutation == 'maintenance':
        raw['aircraft'][0]['unavailable'] = [dict(start_ms=raw['flights'][0]['departure_ms'],
                                               end_ms=raw['flights'][0]['arrival_ms'])]
    elif mutation == 'turnaround':
        raw['flights'][1]['departure_ms'] = raw['flights'][0]['arrival_ms'] + 44 * MINUTE
    elif mutation == 'duplicate':
        raw['passengers'].append(deepcopy(raw['passengers'][0]))
    else:
        raw['inventory'].pop()
    assert code in {i.code for i in validate_seed(SeedSnapshot.model_validate(raw))}
