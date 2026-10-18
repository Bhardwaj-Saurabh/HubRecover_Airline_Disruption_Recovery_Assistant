"""Typed local adapters and server-classified source changes, never client authority."""
from copy import deepcopy
from typing import Literal
from pydantic import Field
from hubrecover.domain.schemas import Record, Flight, Aircraft, Crew, Passenger, Inventory
from hubrecover.domain.gate import RestrictionWindow
from hubrecover.domain.allocation import DispatchEvidence
from hubrecover.domain.planning import digest

MODELS = dict(schedule=Flight, aircraft=Aircraft, crews=Crew, passengers=Passenger,
              inventory=Inventory, restrictions=RestrictionWindow, dispatch=DispatchEvidence)


class SourceUpdate(Record):
    source: Literal['schedule','aircraft','crews','passengers','inventory','restrictions','dispatch']
    operation: Literal['refresh','label','replace']
    record_id: str | None = None
    value: dict | None = None
    label: str | None = Field(default=None,max_length=200)


def records(run, source):
    scenario=run['scenario']
    if source=='schedule': return run.get('committed_schedule',scenario['current'])
    if source=='inventory': return list(run['inventory'].values())
    if source=='restrictions': return scenario['restrictions']
    if source=='dispatch': return list(scenario['dispatch_records'].values())
    return scenario['seed'][source]


def material(run):
    return dict(**{s:digest(records(run,s)) for s in MODELS},bookings=digest(run['bookings']))


def initialize(run, now):
    if 'sources' in run: return
    run['scenario_version']=1
    run['seed_digest']=digest(run['scenario'])
    run['sources']={s:dict(version=1,verified_at=now,status='VERIFIED' if run['scenario']['sources_verified'] else 'UNAVAILABLE',
                          material_digest=digest(records(run,s)),labels={}) for s in MODELS}
    run['expected_material']=material(run)
    run['source_updates']=[]
    run['snapshots']=[]


def snapshot(run, now):
    initialize(run,now)
    content={s:deepcopy(records(run,s)) for s in MODELS}
    content['bookings']=deepcopy(run['bookings'])
    snap=dict(id=digest([run['id'],run['generation'],run['scenario_version'],content]),
              scenario_version=run['scenario_version'],generation=run['generation'],
              versions={s:v['version'] for s,v in run['sources'].items()},
              material=material(run),content=content,at=now)
    run['snapshots'].append(snap)
    run['snapshot_id']=snap['id']


def expected_change(run, classification, reference, now):
    """Only called inside the acknowledgement/receipt transaction, never exposed as a command."""
    initialize(run,now)
    current=material(run)
    for source in MODELS:
        if current[source]!=run['sources'][source]['material_digest']:
            run['sources'][source].update(version=run['sources'][source]['version']+1,
                                         material_digest=current[source],verified_at=now)
    run['scenario_version']+=1
    run['expected_material']=current
    run['source_updates'].append(dict(classification=classification,reference=reference,
                                     scenario_version=run['scenario_version'],at=now,material_digest=digest(current)))


def verify(run, source):
    values=records(run,source)
    parsed=[MODELS[source].model_validate(v) for v in values]
    flights={f['id'] for f in run['scenario']['seed']['flights']}
    tails={a['id'] for a in run['scenario']['seed']['aircraft']}
    crews={c['id'] for c in run['scenario']['seed']['crews']}
    identities=[getattr(v,'id',getattr(v,'flight_id',None)) for v in parsed]
    if source!='dispatch' and len(identities)!=len(set(identities)):
        raise ValueError('Duplicate source identity')
    for v in parsed:
        if source=='schedule' and (v.id not in flights or v.tail_id not in tails or v.crew_id not in crews):
            raise ValueError('Unknown schedule reference')
        if source=='inventory' and (v.flight_id not in flights or v.occupied>v.capacity):
            raise ValueError('Invalid inventory reference or capacity')
        if source=='passengers' and set(v.itinerary)-flights: raise ValueError('Unknown itinerary flight')
        if source=='restrictions' and set(v.applicable_flight_ids)-flights: raise ValueError('Unknown restriction scope')
        if source=='dispatch' and (v.flight_id not in flights or v.tail_id not in tails or v.crew_id not in crews):
            raise ValueError('Unknown dispatch reference')
    if not parsed: raise ValueError('Required source is empty')


def apply(run, payload, now):
    initialize(run,now)
    update=SourceUpdate.model_validate(payload)
    source=update.source;envelope=run['sources'][source]
    classification='NONMATERIAL'
    if update.operation=='refresh':
        if update.record_id is not None or update.value is not None or update.label is not None:
            raise ValueError('Refresh accepts no client timestamp or content')
        verify(run,source)
        if envelope['status']!='VERIFIED': raise ValueError('Unavailable adapter cannot verify a heartbeat')
        if material(run)!=run['expected_material']: raise ValueError('Unclassified source change cannot be refreshed')
        envelope['verified_at']=now
    elif update.operation=='label':
        if update.label is None or update.value is not None or update.record_id is not None:
            raise ValueError('Display-label update requires only a label')
        envelope['labels']['display']=update.label
    else:
        if update.value is None or update.record_id is None or update.label is not None:
            raise ValueError('Replacement needs a source record identity and full typed record')
        replacement=MODELS[source].model_validate(update.value).model_dump()
        if source=='dispatch':
            target=run['scenario']['dispatch_records']
            if update.record_id not in target: raise ValueError('Unknown dispatch record key')
            target[update.record_id]=replacement
        else:
            values=records(run,source)
            identity='flight_id' if source=='inventory' else 'id'
            if replacement[identity]!=update.record_id: raise ValueError('Source identity cannot change')
            old=next((r for r in values if r[identity]==update.record_id),None)
            if old is None: raise ValueError('Unknown source record')
            if source=='inventory': run['inventory'][update.record_id]=replacement
            else: values[values.index(old)]=replacement
        verify(run,source)
        classification='NONMATERIAL' if material(run)==run['expected_material'] else 'UNEXPECTED_MATERIAL'
    envelope['version']+=1
    envelope['material_digest']=digest(records(run,source))
    run['scenario_version']+=1
    run['source_verified_at']=min(v['verified_at'] for v in run['sources'].values())
    run['source_updates'].append(dict(source=source,classification=classification,at=now,
                                     scenario_version=run['scenario_version'],source_version=envelope['version']))
    return classification
