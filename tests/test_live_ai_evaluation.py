import asyncio
import json
from evaluation.live_ai import evaluate
from hubrecover.application.ai import BoundedAI
from hubrecover.domain.claims import EditProposal, ExplanationBatch


def factory(service):
    ai=BoundedAI(service);ai.enabled=True;ai.model='STANDIN_TEST_ONLY'
    async def generate(schema,payload,role):
        if role=='explanation':
            return ExplanationBatch(context_digest=payload['context_digest'],plans=[dict(plan_id=pid,
                claims=[dict(kind='FACT',fact_ids=[pid+':m0'])],reasons=[],precedent_ids=[]) for pid in payload['plan_ids']])
        return EditProposal(kind='protectConnection',target='SYN-CONNECTION-INTERNATIONAL') if 'international' in payload['text'] else EditProposal(kind='CLARIFY',clarification='AMBIGUOUS_REFERENCE')
    ai.generate=generate
    return ai


def test_missing_credentials_is_not_a_pass_and_never_calls_provider(monkeypatch):
    monkeypatch.delenv('GOOGLE_API_KEY',raising=False)
    monkeypatch.delenv('HUBRECOVER_GEMINI_MODEL',raising=False)
    async def forbidden(*args): raise AssertionError('Provider must not be called')
    monkeypatch.setattr(BoundedAI,'generate',forbidden)
    report=asyncio.run(evaluate())
    assert report['status']=='NOT_RUN' and report['results']==[]
    assert report['human_verdict'] is None


def test_repeated_checks_are_isolated_and_standins_never_claim_real_evidence():
    report=asyncio.run(evaluate(2,test_factory=factory))
    assert report['mode']=='STANDIN_TEST_ONLY' and report['model']=='STANDIN_TEST_ONLY'
    assert report['status']=='PASS' and report['passed']==6
    assert len({r['source_snapshot_id'] for r in report['results']})==6
    assert all(r['budget']['calls']==1 and r['human_verdict'] is None and r['no_passenger_effects'] for r in report['results'])


def test_provider_failure_report_does_not_leak_exception_text():
    def failing(service):
        ai=factory(service)
        async def generate(*args): raise RuntimeError('SECRET-LIKE-PROVIDER-REQUEST')
        ai.generate=generate
        return ai
    report=asyncio.run(evaluate(1,test_factory=failing))
    assert report['status']=='FAIL' and report['passed']==0
    assert 'SECRET-LIKE' not in json.dumps(report)
    assert all(r['status']=='MANUAL_HANDOFF' for r in report['results'])
