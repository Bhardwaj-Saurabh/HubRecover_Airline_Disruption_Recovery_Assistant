"""Independent reference-universe oracle; no production planner/allocator imports.

Inputs are frozen, declarative records. This implementation is intentionally
straightforward and covers delay/cancellation and compatible spare-tail variants.
"""
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from copy import deepcopy


def reference_oracle(data):
    seed=data['seed'];original={f['id']:f for f in seed['flights']}
    roots=sorted(data['roots']);families=[[],[],[],[]]
    for root in roots:
        for minutes in (30,60,90,120):families[0].append(('DELAY',(root,),minutes))
        families[2].append(('CANCEL_SINGLE',(root,),None))
        f=next(f for f in data['current'] if f['id']==root)
        used={v['tail_id'] for v in seed['flights']}
        spares=[a for a in sorted(seed['aircraft'],key=lambda a:a['id']) if a['id'] not in used
                and a['aircraft_type']==f['aircraft_type'] and a['initial_location']==f['origin']
                and a['available']['start_ms']<=f['departure_ms']<a['available']['end_ms']
                and not any(u['start_ms']<=f['departure_ms']<u['end_ms'] for u in a['unavailable'])]
        for spare in spares[:2]: families[1].append(('SWAP',(root,),None,spare['id']))
    for i,left in enumerate(roots):
        for right in roots[i+1:]:families[3].append(('CANCEL_PAIR',(left,right),None))
    descriptors=[]
    while any(families) and len(descriptors)<100:
        for family in families:
            if family and len(descriptors)<100:descriptors.append(family.pop(0))
    tails={t['id']:t for t in seed['aircraft']};crews={c['id']:c for c in seed['crews']}
    parties=defaultdict(list)
    for p in seed['passengers']:parties[p['party_id']].append(p)
    positions={p['party_id']:p for p in data['positions']}
    output=[]
    for descriptor in descriptors:
        kind,affected,minutes=descriptor[:3]
        flights={f['id']:deepcopy(f) for f in data['current']}
        if kind=='DELAY':
            flights[affected[0]]['departure_ms']+=minutes*60000
            flights[affected[0]]['arrival_ms']+=minutes*60000
        elif kind=='SWAP':
            root=deepcopy(flights[affected[0]])
            for f in flights.values():
                if f['tail_id']==root['tail_id'] and f['departure_ms']>=root['departure_ms']:
                    f['tail_id']=descriptor[3]
        else:
            for f in affected:flights[f]['status']='CANCELLED'
        # Build independent pairwise precedence inequalities, then relax.
        edges=[]
        for resource in ('tail_id','crew_id'):
            groups=defaultdict(list)
            for f in seed['flights']:
                if flights[f['id']]['status']!='CANCELLED':groups[f[resource]].append(f)
            for group in groups.values():
                order=sorted(group,key=lambda f:(f['departure_ms'],f['id']))
                for left,right in zip(order,order[1:]):
                    if resource=='tail_id' and flights[left['id']]['tail_id']!=flights[right['id']]['tail_id']: continue
                    edges.append((left['id'],right['id'],(45 if right['aircraft_type']=='DEMO180' else 35)*60000 if resource=='tail_id' else 0))
        for _ in range(24):
            changed=False
            for left,right,gap in edges:
                need=flights[left]['arrival_ms']+gap-flights[right]['departure_ms']
                if need>0:
                    flights[right]['departure_ms']+=need;flights[right]['arrival_ms']+=need;changed=True
            if not changed:break
        feasible=data['sources_verified']
        for resource,records in [('tail_id',tails),('crew_id',crews)]:
            groups=defaultdict(list)
            for f in flights.values():
                if f['status']!='CANCELLED':groups[f[resource]].append(f)
            for rid,group in groups.items():
                r=records[rid];location=r['initial_location'];last_end=None
                for f in sorted(group,key=lambda f:(f['departure_ms'],f['id'])):
                    if f['origin']!=location or not r['available']['start_ms']<=f['departure_ms']<f['arrival_ms']<=r['available']['end_ms']:feasible=False
                    gap=(45 if f['aircraft_type']=='DEMO180' else 35)*60000 if resource=='tail_id' else 0
                    if last_end is not None and f['departure_ms']<last_end+gap:feasible=False
                    if resource=='crew_id':
                        if (f['aircraft_type'] not in r['qualifications'] or f['arrival_ms']>r['duty']['end_ms']
                            or f['departure_ms']<r['duty']['start_ms'] or r['duty']['end_ms']-r['duty']['start_ms']>10*3600000
                            or r['prior_rest']['end_ms']-r['prior_rest']['start_ms']<10*3600000
                            or r['prior_rest']['end_ms']>r['duty']['start_ms']): feasible=False
                    else:
                        if f['aircraft_type']!=r['aircraft_type'] or any(f['departure_ms']<u['end_ms'] and f['arrival_ms']>u['start_ms'] for u in r['unavailable']): feasible=False
                    location=f['destination'];last_end=f['arrival_ms']
        for f in flights.values():
            if f['status']=='CANCELLED':continue
            for r in data['restrictions']:
                when=f['departure_ms'] if r['movement']=='DEPARTURE' else f['arrival_ms']
                if f['id'] in r['applicable_flight_ids'] and r['kind']!='WEATHER_ADVISORY' and when>=r['effective_ms'] and (r['confirmed_end_ms'] is None or when<r['confirmed_end_ms']):feasible=False
            if not any(e['status']=='VERIFIED' and all(e[k] for k in ('route_compatible','fuel_compatible','restriction_compatible')) and all(e[k]==f[k] for k in ('departure_ms','arrival_ms','tail_id','crew_id')) and e['flight_id']==f['id'] for e in data['dispatch_records'].values()):feasible=False
        if not feasible:
            output.append(dict(descriptor=descriptor,viable=False));continue
        occupancy={r['flight_id']:r['occupied'] for r in seed['inventory']}
        caps={r['flight_id']:r['capacity'] for r in seed['inventory']}
        outcomes={};unresolved=overnight=delay=0
        for pid,members in sorted(parties.items(),key=lambda item:(item[1][0]['original_arrival_ms'],item[0])):
            p=members[0];position=positions[pid];dest=original[p['itinerary'][-1]]['destination'];paths=[]
            usable=[f for f in flights.values() if f['status']=='SCHEDULED']
            for first in usable:
                if first['origin']!=position['airport_id'] or first['departure_ms']<position['ready_ms']:continue
                if first['destination']==dest:paths.append((first['id'],))
                for second in usable:
                    if second['origin']==first['destination'] and second['destination']==dest and len({first['origin'],first['destination'],dest})==3 and second['departure_ms']-first['arrival_ms']>=max(m['minimum_connection_minutes'] for m in members)*60000:
                        paths.append((first['id'],second['id']))
            selected=None
            if any(m['assistance_required'] and not m['assistance_confirmed'] for m in members): paths=[]
            for path in sorted(paths,key=lambda path:(flights[path[-1]]['arrival_ms'],path)):
                if list(path)!=p['itinerary'] and not all(m['eligible'] for m in members):continue
                size=len(members);delta={f:size*((f in path)-(f in p['itinerary'])) for f in set(path)|set(p['itinerary'])}
                if all(0<=occupancy[f]+d<=caps[f] for f,d in delta.items()):
                    for f,d in delta.items():occupancy[f]+=d
                    selected=path;break
            outcomes[pid]=selected
            if selected is None:unresolved+=len(members);continue
            arrival=flights[selected[-1]]['arrival_ms'];zone=ZoneInfo(original[p['itinerary'][-1]]['destination_timezone'])
            date=lambda ms:datetime.fromtimestamp(ms/1000,timezone.utc).astimezone(zone).date()
            overnight+=len(members)*(date(arrival)>date(p['original_arrival_ms']))
            delay+=len(members)*max(0,(arrival-p['original_arrival_ms'])//60000)
        ranking=(unresolved,overnight,delay,sum(f['status']=='CANCELLED' for f in flights.values()),sum(max(0,f['departure_ms']-original[f['id']]['departure_ms'])//60000 for f in flights.values() if f['status']!='CANCELLED'))
        output.append(dict(descriptor=descriptor,viable=True,ranking=ranking,outcomes=outcomes))
    return output
