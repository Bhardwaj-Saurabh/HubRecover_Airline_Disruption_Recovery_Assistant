"""Owned manual-work records. These commands confer no execution authority."""
from copy import deepcopy
import uuid

ROLES = {'DUTY_MANAGER', 'OCC_OPERATIONS_LEAD', 'AIRCRAFT_CONTROLLER',
         'CREW_CONTROLLER', 'DISPATCHER', 'PASSENGER_OPERATIONS'}


def packet(run, reason, owner, now, *, parties=None, required_action=None):
    plan = next((p for p in run.get('search', {}).get('plans', [])
                 if p['id'] == run.get('selected_plan')), {})
    affected = set(parties if parties is not None else
                   [p['party_id'] for p in run['scenario']['seed']['passengers']])
    passengers = [p['id'] for p in run['scenario']['seed']['passengers'] if p['party_id'] in affected]
    return dict(id=uuid.uuid4().hex, environment='SYNTHETIC', episode_id=run['id'],
        generation=run['generation'], plan_id=plan.get('id'), fingerprint=plan.get('fingerprint'),
        source_version=run['source_version'], policy_version=run['policy_version'],
        reason=reason, owner=owner, fallback='OCC_OPERATIONS_LEAD', status='OPEN',
        created_at=now, updated_at=now,
        history=[dict(actor='SYSTEM', at=now, action='ASSIGNED', owner=owner)],
        affected_passengers=passengers, remaining_parties=sorted(affected-set(run['receipts'])),
        committed_parties=sorted(affected & set(run['receipts'])),
        evidence=deepcopy(dict(receipts={k:v for k,v in run['receipts'].items() if k in affected},
            communication={k:v for k,v in run['outbox'].items() if k in passengers},
            proposed_operations=plan.get('operations', []),
            committed_operations_digest=run.get('committed_operations_digest'),
            sources_verified=run['scenario']['sources_verified'])),
        required_action=required_action or 'Inspect receipts and reconcile remaining work; no new automated booking authority')


def transition(packet, action, role, payload, now):
    if packet['status']=='RESOLVED_MANUALLY':
        raise ValueError('Manual handling already recorded')
    record = dict(actor=role, at=now, action=action.upper())
    if action=='assign_handoff':
        if role not in ('DUTY_MANAGER', 'OCC_OPERATIONS_LEAD'):
            raise ValueError('Duty Manager or OCC coordinator required')
        owner=payload.get('owner')
        if owner not in ROLES or owner==packet['owner']:
            raise ValueError('A different supported owner is required')
        record.update(previous_owner=packet['owner'], owner=owner)
        state='OPEN'
    else:
        if role!=packet['owner']:
            raise ValueError('Assigned owner required; coordinator must reassign first')
        if action=='accept_handoff':
            if packet['status']!='OPEN': raise ValueError('Only open work can be accepted')
            state='ACKNOWLEDGED'
        elif action=='return_handoff':
            if packet['status'] not in ('OPEN','ACKNOWLEDGED'): raise ValueError('Work already returned')
            state='RETURNED'
        elif action=='resolve_handoff':
            if packet['status']!='ACKNOWLEDGED': raise ValueError('Accept work before recording manual handling')
            evidence=payload.get('evidence')
            if not isinstance(evidence,str) or not 1<=len(evidence.strip())<=2000:
                raise ValueError('Manual evidence reference required (1–2000 characters)')
            record['evidence']=evidence.strip()
            state='RESOLVED_MANUALLY'
        else:
            raise ValueError('Unsupported handoff transition')
    if action!='accept_handoff':
        note=payload.get('note')
        if not isinstance(note,str) or not 1<=len(note.strip())<=2000:
            raise ValueError('Handling note required (1–2000 characters)')
        record['note']=note.strip()
    if action=='assign_handoff': packet['owner']=owner
    packet['status']=state
    packet['updated_at']=now
    packet['history'].append(record)
