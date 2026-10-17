"""Strict model selections rendered exclusively from verified numeric facts."""
from typing import Literal
from pydantic import Field
from .schemas import Record
from .planning import digest

class Claim(Record):
    kind: Literal['FACT','COMPARE']
    fact_ids: list[str]=Field(min_length=1,max_length=2)
    comparator: Literal['LT','EQ','GT'] | None=None
class Reason(Record):
    code: Literal['UNRESOLVED_REDUCTION','OVERNIGHT_REDUCTION','ARRIVAL_DELAY_TRADEOFF','DEPENDENCY_PENDING']
    fact_ids: list[str]=Field(min_length=1,max_length=4)
class PlanExplanation(Record):
    plan_id: str
    claims: list[Claim]=Field(min_length=1,max_length=6)
    reasons: list[Reason]=Field(max_length=4)
    precedent_ids: list[str]=Field(max_length=4)
class ExplanationBatch(Record):
    context_digest: str
    plans: list[PlanExplanation]=Field(min_length=1,max_length=4)
class EditProposal(Record):
    kind: Literal['protectFlight','protectConnection','maxArrivalDelay','CLARIFY']
    target: str | None=None
    minutes: int | None=Field(default=None,ge=0)
    clarification: Literal['AMBIGUOUS_REFERENCE','UNSUPPORTED_REQUEST','MISSING_VALUE'] | None=None

METRICS=['unresolved passengers','next-day arrivals','passenger arrival-delay minutes','cancelled flights','flight departure-delay minutes']

def context(plans,generation):
    facts={}
    for p in plans:
        for index,value in enumerate(p['ranking']):
            facts[f"{p['id']}:m{index}"]=dict(plan_id=p['id'],metric=METRICS[index],value=value,cohort='REFERENCE_300')
        facts[f"{p['id']}:dependencies"]=dict(plan_id=p['id'],metric='pending prerequisites',value=len(p['prerequisites']),cohort='REFERENCE_300')
    data=dict(generation=generation,plan_ids=[p['id'] for p in plans],facts=facts,eligible_precedents=[])
    data['context_digest']=digest(data)
    return data


def validate_explanations(batch:ExplanationBatch,ctx):
    if batch.context_digest!=ctx['context_digest'] or sorted(p.plan_id for p in batch.plans)!=sorted(ctx['plan_ids']):
        raise ValueError('Wrong explanation context or plan set')
    rendered={}
    for plan in batch.plans:
        if plan.precedent_ids:
            raise ValueError('No eligible precedent supplied in the synthetic reference')
        lines=[]
        for claim in plan.claims:
            facts=[ctx['facts'].get(i) for i in claim.fact_ids]
            if any(f is None for f in facts) or facts[0]['plan_id']!=plan.plan_id:
                raise ValueError('Unknown or wrong-plan fact')
            if claim.kind=='FACT':
                if len(facts)!=1 or claim.comparator is not None:
                    raise ValueError('FACT cardinality/comparator invalid')
                lines.append(f"{facts[0]['value']} {facts[0]['metric']}.")
            else:
                if len(facts)!=2 or (facts[0]['metric'],facts[0]['cohort'])!=(facts[1]['metric'],facts[1]['cohort']):
                    raise ValueError('Incompatible comparison witnesses')
                a,b=facts[0]['value'],facts[1]['value']
                actual='LT' if a<b else 'GT' if a>b else 'EQ'
                if actual!=claim.comparator:
                    raise ValueError('False comparison despite valid citations')
                word={'LT':'fewer than','GT':'more than','EQ':'equal to'}[actual]
                lines.append(f"{a} {facts[0]['metric']}, {word} option {facts[1]['plan_id']} ({b}).")
        for reason in plan.reasons:
            facts=[ctx['facts'].get(i) for i in reason.fact_ids]
            if any(f is None for f in facts) or facts[0]['plan_id']!=plan.plan_id:
                raise ValueError('Invalid reason witnesses')
            if reason.code=='DEPENDENCY_PENDING':
                if len(facts)!=1 or facts[0]['metric']!='pending prerequisites' or facts[0]['value']<=0:
                    raise ValueError('Dependency predicate failed')
                lines.append('Matching operational acknowledgements remain required.')
            else:
                metric={'UNRESOLVED_REDUCTION':METRICS[0],'OVERNIGHT_REDUCTION':METRICS[1],'ARRIVAL_DELAY_TRADEOFF':METRICS[2]}[reason.code]
                if len(facts)!=2 or any(f['metric']!=metric or f['cohort']!='REFERENCE_300' for f in facts):
                    raise ValueError('Reason metric/cardinality mismatch')
                if reason.code.endswith('REDUCTION') and not facts[0]['value']<facts[1]['value']:
                    raise ValueError('Reduction predicate false')
                if reason.code=='ARRIVAL_DELAY_TRADEOFF' and not facts[0]['value']>facts[1]['value']:
                    raise ValueError('Delay tradeoff predicate false')
                lines.append(f"{metric.capitalize()}: {facts[0]['value']} versus {facts[1]['value']} in option {facts[1]['plan_id']}.")
        rendered[plan.plan_id]=' '.join(lines)+' LIMITED_PRECEDENT. Passed configured demo checks only; approval and execution guards remain required.'
    return rendered
