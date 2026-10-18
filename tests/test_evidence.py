from dataclasses import replace
import pytest
from hubrecover.domain.evidence import warnings, retrieve, CATALOG
from hubrecover.fixtures.scenarios import create_scenario
from hubrecover.domain.planning import build_plans
from hubrecover.domain.claims import context, ExplanationBatch, validate_explanations
from test_claims_ai import batch


def test_inclusive_warning_thresholds_and_every_unresolved_count():
    assert not any(w.startswith('HIGH_') for w in warnings((29,74),300,[]))
    result=warnings((30,75),300,[])
    assert sum(w.startswith('HIGH_') for w in result)==2
    assert any('1 of 300' in w for w in warnings((1,0),300,[]))


def test_fictional_precedents_filter_scope_approval_policy_and_dates():
    s=create_scenario()
    assert [p['id'] for p in retrieve(s.seed,s.restrictions,'DELAY')]==['SYN-PLAYBOOK-DELAY']
    assert retrieve(s.seed,s.restrictions,'DELAY',limited=True)==[]
    assert retrieve(s.seed,s.restrictions,'DELAY',catalog=[replace(CATALOG[0],policy='wrong')])==[]
    assert retrieve(s.seed,s.restrictions,'DELAY',catalog=[replace(CATALOG[0],valid_until=s.seed.day_start_ms)])==[]


def test_precedent_citations_are_strategy_scoped_and_do_not_remove_warnings():
    plans=build_plans(create_scenario())['plans'];ctx=context(plans,1)
    raw=batch(ctx);raw['plans'][0]['precedent_ids']=['SYN-PLAYBOOK-DELAY']
    assert 'GROUNDED fictional' in validate_explanations(ExplanationBatch.model_validate(raw),ctx)[plans[0]['id']]
    raw['plans'][0]['precedent_ids']=['SYN-PLAYBOOK-DRAFT']
    with pytest.raises(ValueError): validate_explanations(ExplanationBatch.model_validate(raw),ctx)
    assert all('LIMITED_PRECEDENT' in p['warnings'] for p in build_plans(create_scenario('limited'))['plans'])
