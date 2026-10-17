from evaluation.oracle import reference_oracle
from hubrecover.application.service import encode_scenario
from hubrecover.domain.allocation import allocate
from hubrecover.domain.gate import validate_operations
from hubrecover.domain.planning import materialize
from hubrecover.domain.universe import select_descriptors
from hubrecover.fixtures.scenarios import create_scenario


def test_every_reference_descriptor_matches_independent_oracle():
    scenario=create_scenario()
    expected=reference_oracle(encode_scenario(scenario))
    descriptors=select_descriptors(scenario.roots,{}).selected
    assert len(expected)==len(descriptors)==18
    for descriptor,oracle in zip(descriptors,expected):
        assert (descriptor.kind,descriptor.roots,descriptor.delay_minutes)==oracle['descriptor']
        flights=materialize(scenario.seed,scenario.current,descriptor)
        dispatch=scenario.dispatch_for(flights)
        gate=validate_operations(scenario.seed,flights,dispatch,scenario.restrictions,restriction_source_verified=True)
        assert gate.passed==oracle['viable']
        if gate.passed:
            result=allocate(scenario.seed,flights,dispatch,scenario.positions)
            assert result.ranking==oracle['ranking']
            assert {a.party_id:a.itinerary for a in result.allocations}==oracle['outcomes']
