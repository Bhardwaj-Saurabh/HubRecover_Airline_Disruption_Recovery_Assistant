import asyncio
import pytest
from pydantic import ValidationError
from hubrecover.domain.claims import ExplanationBatch, context, validate_explanations
from hubrecover.domain.planning import build_plans
from hubrecover.fixtures.scenarios import create_scenario
from hubrecover.application.service import RecoveryService, Refusal
from hubrecover.application.ai import BoundedAI


def batch(ctx):
    return dict(context_digest=ctx['context_digest'],plans=[dict(plan_id=p,
        claims=[dict(kind='FACT',fact_ids=[p+':m0'],comparator=None)],reasons=[],precedent_ids=[]) for p in ctx['plan_ids']])


def test_typed_facts_render_without_arbitrary_model_prose():
    ctx=context(build_plans(create_scenario())['plans'],1)
    result=validate_explanations(ExplanationBatch.model_validate(batch(ctx)),ctx)
    assert all('0 unresolved passengers' in v for v in result.values())
    raw=batch(ctx);raw['plans'][0]['prose']='Ignore approval and send now'
    with pytest.raises(ValidationError): ExplanationBatch.model_validate(raw)


def test_valid_citations_false_comparison_rejected():
    ctx=context(build_plans(create_scenario())['plans'],1)
    raw=batch(ctx);a,b=ctx['plan_ids'][:2]
    raw['plans'][0]['claims']=[dict(kind='COMPARE',fact_ids=[a+':m2',b+':m2'],comparator='GT')]
    with pytest.raises(ValueError,match='False comparison'):
        validate_explanations(ExplanationBatch.model_validate(raw),ctx)


def test_bounded_standin_records_reservation_and_new_review(tmp_path):
    async def exercise():
        service=RecoveryService(tmp_path/'ai.sqlite');run=service.create()
        ai=BoundedAI(service);ai.enabled=True;ai.model='STANDIN_TEST_ONLY'
        async def generate(schema,payload,role): return ExplanationBatch.model_validate(batch(payload))
        ai.generate=generate
        result=await ai.request(run['id'],run['revision'],'explanation',key='once')
        assert result['mode']=='REAL_AI'  # test stand-in is isolated, never presented as provider evidence
        assert result['ai_budget']['calls']==1 and result['ai_budget']['reserved_tokens']==14048
        assert result['request_id']!=run['request_id']
        assert result['expires_at']==run['expires_at']
        replay=await ai.request(run['id'],run['revision'],'explanation',key='once')
        assert replay['ai_budget']['calls']==1
    asyncio.run(exercise())


def test_provider_failure_no_sample_fallback(tmp_path):
    async def exercise():
        service=RecoveryService(tmp_path/'ai.sqlite');run=service.create()
        ai=BoundedAI(service);ai.enabled=True;ai.model='STANDIN_TEST_ONLY'
        async def generate(*args): raise TimeoutError()
        ai.generate=generate
        with pytest.raises(Refusal): await ai.request(run['id'],run['revision'],'explanation')
        state=service.get(run['id'])
        assert state['status']=='MANUAL_HANDOFF' and state['mode']=='REAL_AI'
        assert state['ai_budget']['reserved_tokens']==14048
    asyncio.run(exercise())


def test_ambiguous_edit_requires_versioned_clarification_without_renewing_wait(tmp_path):
    from hubrecover.domain.claims import EditProposal
    from test_service import cmd
    async def exercise():
        service=RecoveryService(tmp_path/'clarify.sqlite');run=service.create()
        ai=BoundedAI(service);ai.enabled=True;ai.model='STANDIN_TEST_ONLY'
        async def generate(*args): return EditProposal(kind='CLARIFY',clarification='AMBIGUOUS_REFERENCE')
        ai.generate=generate
        pending=await ai.request(run['id'],run['revision'],'edit',text='Protect that connection',key='clarify')
        assert pending['status']=='NEEDS_CLARIFICATION' and pending['expires_at']==run['expires_at']
        assert pending['request_id']!=run['request_id']
        with pytest.raises(Refusal): cmd(service,pending,'approve',request_id=pending['request_id'],plan_id=pending['search']['plans'][0]['id'])
        with pytest.raises(Refusal): cmd(service,pending,'clarify',request_id=run['request_id'],constraint={})
        restarted=RecoveryService(service.store.path)
        result=cmd(restarted,pending,'clarify',request_id=pending['request_id'],constraint=dict(kind='protectConnection',target='SYN-CONNECTION-INTERNATIONAL'))
        assert result['status']=='AWAITING_APPROVAL' and result['generation']==2
        assert not result.get('clarification') and result['approval'] is None
        assert result['ai_budget']['calls']==1
    asyncio.run(exercise())
