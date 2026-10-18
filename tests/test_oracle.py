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


def test_spare_suffix_and_mutated_resource_graphs_match_independent_oracle():
    from copy import deepcopy
    from hubrecover.domain.schemas import SeedSnapshot
    from hubrecover.domain.allocation import DispatchEvidence
    from hubrecover.domain.planning import compatible_spares, operation_key, build_plans
    for defect in ('none','maintenance','rest','qualification','dispatch'):
        scenario=create_scenario();raw=scenario.seed.model_dump()
        spare=deepcopy(raw['aircraft'][0]);spare['id']='SYN-SPARE-001';raw['aircraft'].append(spare)
        if defect=='maintenance': spare['unavailable']=[dict(start_ms=raw['day_start_ms'],end_ms=raw['day_start_ms']+86400000)]
        if defect=='rest': raw['crews'][0]['prior_rest']['start_ms']=raw['crews'][0]['prior_rest']['end_ms']-9*3600000
        if defect=='qualification': raw['crews'][0]['qualifications']=[]
        scenario.seed=SeedSnapshot.model_validate(raw)
        descriptors=select_descriptors(scenario.roots,compatible_spares(scenario)).selected
        # Explicit fixture adapter evidence, frozen before either implementation runs.
        for descriptor in descriptors:
            if descriptor.kind!='SWAP': continue
            for f in materialize(scenario.seed,scenario.current,descriptor):
                scenario.dispatch_records[operation_key(f)]=DispatchEvidence(flight_id=f.id,departure_ms=f.departure_ms,
                    arrival_ms=f.arrival_ms,tail_id=f.tail_id,crew_id=f.crew_id,status='VERIFIED',
                    route_compatible=defect!='dispatch',fuel_compatible=True,restriction_compatible=True)
        expected=reference_oracle(encode_scenario(scenario))
        assert len(expected)==len(descriptors)
        for descriptor,oracle in zip(descriptors,expected):
            key=(descriptor.kind,descriptor.roots,descriptor.delay_minutes)
            if descriptor.kind=='SWAP': key+=(descriptor.spare_tail,)
            assert key==oracle['descriptor']
            flights=materialize(scenario.seed,scenario.current,descriptor)
            report=validate_operations(scenario.seed,flights,scenario.dispatch_for(flights),scenario.restrictions,restriction_source_verified=True)
            assert report.passed==oracle['viable'],(defect,key,report.issues)
            if report.passed:
                actual=allocate(scenario.seed,flights,scenario.dispatch_for(flights),scenario.positions)
                assert actual.ranking==oracle['ranking']
                assert {a.party_id:a.itinerary for a in actual.allocations}==oracle['outcomes']
        if defect=='none':
            result=build_plans(scenario)
            assert result['selected']>18
            swap=next(v for v in expected if v['descriptor'][0]=='SWAP')
            assert swap['viable'] and swap['ranking']==(0,2,3600,0,45)
            # Fewer flight-delay minutes lose to the passenger-protecting delay.
            assert result['plans'][0]['descriptor']['kind']=='DELAY'
