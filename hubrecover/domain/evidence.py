"""Frozen fictional playbooks and code-owned warnings; no operational authority."""
from dataclasses import dataclass
from .policy import POLICY


@dataclass(frozen=True)
class Playbook:
    id: str
    kind: str
    approval: str = 'APPROVED_DEMO'
    hub: str = 'SYN-HUB'
    restriction: str = 'GROUND_STOP'
    policy: str = 'HUBRECOVER-POLICY-001'
    valid_from: int = 1788134400000  # September 2026 synthetic service window
    valid_until: int = 1790726400000


CATALOG=(Playbook('SYN-PLAYBOOK-DELAY','DELAY'),
         Playbook('SYN-PLAYBOOK-SWAP','SWAP'),
         Playbook('SYN-PLAYBOOK-CANCEL','CANCEL_SINGLE'),
         Playbook('SYN-PLAYBOOK-STALE','DELAY',valid_until=1788134400000),
         Playbook('SYN-PLAYBOOK-DRAFT','DELAY',approval='DRAFT'),
         Playbook('SYN-PLAYBOOK-OTHER-HUB','DELAY',hub='SYN-OTHER'))


def retrieve(seed,restrictions,kind,*,limited=False,catalog=CATALOG):
    if limited: return []
    kinds={r.kind for r in restrictions}
    return [dict(id=p.id,kind=p.kind,approval=p.approval,policy=p.policy,
                 scope='Fictional teaching precedent; not real airline approval or execution permission')
            for p in sorted(catalog,key=lambda p:p.id)
            if p.approval=='APPROVED_DEMO' and p.kind==kind and p.hub==seed.hub_id
            and p.restriction in kinds and p.policy==POLICY.version
            and p.valid_from<=seed.day_start_ms<p.valid_until][:4]


def warnings(ranking,cohort,precedents):
    unresolved,next_day=ranking[:2]
    result=['Synthetic operations only','Approval does not mean recovery is complete']
    if not precedents: result.append('LIMITED_PRECEDENT')
    if unresolved: result.append(f'UNRESOLVED: {unresolved} of {cohort} passengers require manual handling')
    if next_day*100>=cohort*POLICY.next_day_warning_percent:
        result.append(f'HIGH_NEXT_DAY: {next_day} of {cohort} passengers arrive next day (threshold 25%)')
    if unresolved*100>=cohort*POLICY.unresolved_warning_percent:
        result.append(f'HIGH_UNRESOLVED: {unresolved} of {cohort} passengers remain unresolved (threshold 10%)')
    return result
