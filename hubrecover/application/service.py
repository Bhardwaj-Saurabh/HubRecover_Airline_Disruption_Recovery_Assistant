from .handoffs import packet as handoff_packet, transition as handoff_transition
"""Authoritative synthetic review, approval, execution and reconciliation service."""
from collections import Counter
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime, timezone
import json
import time
import uuid

from hubrecover.domain.allocation import DispatchEvidence, Position
from hubrecover.domain.gate import RestrictionWindow, validate_operations
from hubrecover.domain.monitoring import Monitor, RestrictionEvent, ingest, tick, Decision
from hubrecover.domain.planning import build_plans, digest, validate_constraints
from hubrecover.domain.policy import POLICY
from hubrecover.domain.schemas import SeedSnapshot, Flight
from hubrecover.fixtures.scenarios import Scenario, create_scenario
from .store import Store
from . import sources

TERMINAL = {'COMPLETED', 'MANUAL_HANDOFF', 'PARTIAL_MANUAL'}
ROLES = {'DUTY_MANAGER','OCC_OPERATIONS_LEAD','AIRCRAFT_CONTROLLER','CREW_CONTROLLER','DISPATCHER','PASSENGER_OPERATIONS'}

class Refusal(ValueError):
    pass


def encode_scenario(s):
    return dict(name=s.name, seed=s.seed.model_dump(), current=[f.model_dump() for f in s.current],
                restrictions=[r.model_dump() for r in s.restrictions], roots=s.roots,
                positions=[p.model_dump() for p in s.positions], sources_verified=s.sources_verified,
                dispatch_records={k:v.model_dump() for k,v in s.dispatch_records.items()})


def decode_scenario(data):
    return Scenario(data['name'], SeedSnapshot.model_validate(data['seed']),
                    [Flight.model_validate(f) for f in data['current']],
                    [RestrictionWindow.model_validate(r) for r in data['restrictions']], data['roots'],
                    [Position.model_validate(p) for p in data['positions']], data['sources_verified'],
                    {k:DispatchEvidence.model_validate(v) for k,v in data['dispatch_records'].items()})


class RecoveryService:
    def __init__(self, path, clock=time.time):
        self.store = Store(path)
        self.clock = clock

    def recover_interrupted_ai(self):
        with self.store.transaction() as db:
            for row in db.execute('SELECT body FROM runs').fetchall():
                run=json.loads(row['body'])
                if run['status']=='EXPLAINING':
                    self.handoff(run,'MODEL_OUTCOME_UNKNOWN_AFTER_RESTART')
                    run['revision']+=1
                    self.store.save(db,run)

    def expire_waiting_work(self):
        expired=[]
        with self.store.transaction() as db:
            for row in db.execute('SELECT body FROM runs').fetchall():
                run=json.loads(row['body'])
                if run['status'] in ('AWAITING_APPROVAL','AWAITING_OPERATIONAL_ACK','NEEDS_CLARIFICATION','REVALIDATING') and self.now(run)>=run.get('expires_at',float('inf')):
                    self.handoff(run,'WAIT_DEADLINE_EXPIRED')
                    run['revision']+=1
                    self.store.save(db,run)
                    expired.append(run['id'])
        return expired

    def reclaim_interrupted_execution(self):
        """Claim one abandoned execution from the durable ledger, never renew its budget."""
        with self.store.transaction() as db:
            for row in db.execute('SELECT body FROM runs ORDER BY rowid').fetchall():
                run=json.loads(row['body'])
                if run['status']!='EXECUTING' or self.clock()<run['lease_until']:
                    continue
                try:
                    self.guard(db,run,approval=True)
                    if self.now(run)>=run['execution_deadline']:
                        raise Refusal('Execution deadline expired during recovery')
                except Refusal as exc:
                    self.handoff(run,str(exc),'PASSENGER_OPERATIONS' if run['receipts'] else 'DUTY_MANAGER')
                else:
                    run['fence']+=1
                    run['lease_until']=self.clock()+15
                    self.trace(run,'WORKER_RECLAIMED',dict(fence=run['fence'],deadline=run['execution_deadline']))
                run['revision']+=1
                self.store.save(db,run)
                return run
        return None

    def now(self, run):
        return self.clock()+run.get('clock_offset', 0)

    def trace(self, run, action, detail, actor='SYSTEM'):
        run['trace'].append(dict(sequence=len(run['trace'])+1, at=self.now(run), action=action,
                                 detail=detail, actor=actor, generation=run['generation']))

    def handoff(self, run, reason, owner='DUTY_MANAGER'):
        run['status'] = 'PARTIAL_MANUAL' if run['receipts'] else 'MANUAL_HANDOFF'
        run['approval'] = None
        run['fence'] += 1
        run['handoffs'].append(handoff_packet(run, reason, owner, self.now(run)))
        self.trace(run, 'HANDOFF', reason)

    def selected(self, run):
        return next((p for p in run.get('search', {}).get('plans', []) if p['id']==run.get('selected_plan')), {})

    def plan(self, run):
        if run['generation'] >= 3:
            self.handoff(run, 'REGENERATION_BUDGET_EXHAUSTED')
            return
        run['generation'] += 1
        run['mode'] = 'RULES_ONLY'
        run.pop('clarification',None)
        run.pop('clarification_resume',None)
        run['approval'] = None
        run['acknowledgements'] = {}
        run['selected_plan'] = None
        run['status'] = 'GENERATING'
        sources.snapshot(run,self.now(run))
        scenario = decode_scenario(run['scenario'])
        if not scenario.sources_verified:
            self.handoff(run, 'REQUIRED_SOURCE_UNAVAILABLE')
            return
        self.trace(run, 'PLANNING', 'Fresh bounded search; no executable partial search results')
        run['search'] = build_plans(scenario, run['constraints'], run['rejected'])
        if not run['search']['plans']:
            self.handoff(run, run['search']['status'])
            return
        run['status'] = 'AWAITING_APPROVAL'
        run['request_id'] = uuid.uuid4().hex
        run['expires_at'] = self.now(run)+300
        run['card_source_version'] = run['source_version']
        run['card_digest'] = digest(run['search']['plans'])
        self.trace(run, 'CARD_READY', dict(ranking=run['search']['plans'][0]['ranking'], search=run['search']['selected']))

    def create(self, scenario_name='happy', *, db=None):
        scenario = create_scenario(scenario_name)
        with (self.store.transaction() if db is None else nullcontext(db)) as db:
            for row in db.execute('SELECT body FROM runs'):
                if json.loads(row['body'])['status'] not in TERMINAL:
                    raise Refusal('Stop or finish the active episode before starting another')
            control = self.store.control(db)
            run = dict(id=uuid.uuid4().hex, status='MONITORING', revision=1, generation=0,
                mode='RULES_ONLY', policy_version=POLICY.version, scenario=encode_scenario(scenario), source_version=1,
                source_verified_at=self.clock(), control_version=control['version'], clock_offset=0,
                constraints=[], rejected=[], search={}, approval=None, acknowledgements={}, selected_plan=None,
                trace=[], handoffs=[], receipts={}, outbox={}, booking_history=[], fence=0, lease_until=0,
                created_at=self.clock(), faults={}, inventory={r.flight_id:r.model_dump() for r in scenario.seed.inventory},
                bookings={p.id:dict(legs=p.itinerary, version=1) for p in scenario.seed.passengers})
            run['expected_inventory'] = digest(run['inventory'])
            sources.initialize(run,self.now(run))
            self.trace(run, 'START', 'Synthetic sources loaded; all effects are local simulations')
            if not control['writes_enabled']:
                self.handoff(run, 'APPLICATION_WRITES_DISABLED')
            else:
                start = scenario.seed.day_start_ms + 5*60*60_000
                monitor, _ = ingest(Monitor(), RestrictionEvent('SYN-AUTHORITY',1,start,start,'GROUND_STOP',True,True,True,True))
                elapsed = 60 if scenario_name=='near_miss' else 61
                if scenario_name=='lifecycle':
                    monitor,_=ingest(monitor,RestrictionEvent('SYN-AUTHORITY',2,start+55*60_000,start+55*60_000,'GROUND_STOP',False,True,True,True))
                    monitor,_=ingest(monitor,RestrictionEvent('SYN-AUTHORITY',3,start+59*60_000,start+59*60_000,'GROUND_STOP',True,True,True,True))
                monitor, decision = tick(monitor,start+elapsed*60_000,downline_flights=2,crew_conflict=False,precheck_verified=scenario.sources_verified)
                run['monitor'] = dict(decision=decision.value, duration_minutes=elapsed, downline_flights=2,
                                      scope='SYN-F-0-1-0 inbound to SYN-HUB', state=asdict(monitor))
                self.trace(run,'TRIGGER_CHECK',run['monitor'])
                if decision==Decision.TRIGGER:
                    self.plan(run)
                elif decision==Decision.MANUAL_HANDOFF:
                    self.handoff(run,'REQUIRED_PRECHECK_UNAVAILABLE')
            self.store.save(db,run)
            return run

    def reset(self,run_id,revision,key,role):
        fingerprint=digest(dict(action='reset',revision=revision,role=role))
        with self.store.transaction() as db:
            old=self.store.load(db,run_id)
            command=db.execute('SELECT hash FROM commands WHERE run_id=? AND key=?',(run_id,key)).fetchone()
            if command:
                if command['hash']!=fingerprint: raise Refusal('Reset idempotency key reused')
                return self.store.load(db,old['reset_run_id'])
            if role!='DUTY_MANAGER' or old['revision']!=revision or old['status'] not in TERMINAL:
                raise Refusal('Only a current stopped or finished episode can be reset by its Duty Manager')
            child=self.create(old['scenario']['name'],db=db)
            old['reset_run_id']=child['id'];old['revision']+=1
            self.trace(old,'RESET',dict(new_run_id=child['id']),role)
            self.store.save(db,old)
            db.execute('INSERT INTO commands VALUES(?,?,?)',(run_id,key,fingerprint))
            return child

    def get(self, run_id):
        with self.store.connect() as db:
            run = self.store.load(db, run_id)
            run['server_now'] = self.now(run)
            run['control'] = self.store.control(db)
            return run

    def list_runs(self):
        with self.store.connect() as db:
            return [dict(id=r['id'], status=r['status'], scenario=r['scenario']['name']) for row in
                    db.execute('SELECT body FROM runs ORDER BY rowid DESC LIMIT 30') for r in [json.loads(row['body'])]]

    def guard(self, db, run, *, approval=False):
        control=self.store.control(db)
        if run.get('policy_version')!=POLICY.version:
            raise Refusal('Policy version changed; old cards cannot execute')
        if not control['writes_enabled'] or control['version']!=run['control_version']:
            raise Refusal('Application write control changed or disabled')
        if run['status'] in TERMINAL:
            raise Refusal('Episode is terminal; reset cannot reuse its authority')
        if self.now(run) >= run.get('expires_at', float('inf')):
            raise Refusal('Approval card expired')
        if run['source_version'] != run.get('card_source_version') or not run['scenario']['sources_verified']:
            raise Refusal('Required source changed or is unavailable')
        if self.now(run)-run['source_verified_at'] > 300:
            raise Refusal('Synthetic source verification is stale')
        if run.get('expected_material') and sources.material(run)!=run['expected_material']:
            raise Refusal('Unexpected material source content')
        if approval:
            a=run['approval']; plan=self.selected(run)
            if not a or not plan or a['generation']!=run['generation'] or a['fingerprint']!=plan['fingerprint'] or a['constraints_digest']!=digest(run['constraints']):
                raise Refusal('No matching current Duty Manager approval')
            if set(run['acknowledgements'])!=set(plan['prerequisites']):
                raise Refusal('Matching operational prerequisites are missing')
            if any(v['fingerprint']!=plan['fingerprint'] or v['operations_digest']!=digest(plan['operations']) for v in run['acknowledgements'].values()):
                raise Refusal('Operational acknowledgement does not match approved postconditions')
            if run.get('committed_operations_digest')!=digest(plan['operations']):
                raise Refusal('Approved operational postconditions are not committed in the simulated source')
            if digest(run['inventory']) != run['expected_inventory']:
                raise Refusal('Unexpected inventory change')
            scenario=decode_scenario(run['scenario'])
            proposed=[Flight.model_validate(f) for f in plan['flights']]
            report=validate_operations(scenario.seed,proposed,scenario.dispatch_for(proposed),scenario.restrictions,restriction_source_verified=True)
            if not report.passed:
                raise Refusal('Final operational gate failed')

    def command(self, run_id, action, *, revision, key, role='DUTY_MANAGER', payload=None):
        payload=payload or {}
        if role not in ROLES or not key or len(key)>128:
            raise Refusal('Valid simulated role and idempotency key required')
        command_hash=digest(dict(action=action,role=role,payload=payload,revision=revision))
        error=None
        with self.store.transaction() as db:
            run=self.store.load(db,run_id)
            old=db.execute('SELECT hash FROM commands WHERE run_id=? AND key=?',(run_id,key)).fetchone()
            if old:
                if old['hash']!=command_hash:
                    raise Refusal('Idempotency key reused for a different command')
                return run
            try:
                if type(revision) is not int or run['revision']!=revision:
                    raise Refusal('Stale episode version; refresh before acting')
                if action in ('approve','edit','reject','stop','advance','source_change','source_update','fault','resume_monitor','clarify') and role!='DUTY_MANAGER':
                    raise Refusal('Duty Manager role required')
                if action in ('approve','edit','reject'):
                    if run['status']!='AWAITING_APPROVAL':
                        raise Refusal('No pending review request')
                    self.guard(db,run)
                    if payload.get('request_id')!=run['request_id']:
                        raise Refusal('Wrong review request')
                if action=='approve':
                    plan=next((p for p in run['search']['plans'] if p['id']==payload.get('plan_id')),None)
                    if not plan:
                        raise Refusal('Only a current viable option may be approved')
                    run['selected_plan']=plan['id']
                    run['approval']=dict(actor=role,at=self.now(run),generation=run['generation'],fingerprint=plan['fingerprint'],
                                         constraints_digest=digest(run['constraints']),request_id=run['request_id'])
                    run['status']='AWAITING_OPERATIONAL_ACK'
                elif action=='edit':
                    constraint=payload.get('constraint')
                    validate_constraints([constraint],decode_scenario(run['scenario']).seed)
                    run['constraints'].append(constraint)
                    self.plan(run)
                elif action=='clarify':
                    if run['status']!='NEEDS_CLARIFICATION' or run.get('clarification_resume')!='SUPPORTED_EDIT':
                        raise Refusal('No supported edit clarification is pending')
                    self.guard(db,run)
                    if payload.get('request_id')!=run['request_id'] or self.now(run)>=run['clarification_deadline']:
                        raise Refusal('Clarification request is stale or expired')
                    constraint=payload.get('constraint')
                    validate_constraints([constraint],decode_scenario(run['scenario']).seed)
                    run['constraints'].append(constraint)
                    self.plan(run)
                elif action=='reject':
                    if not isinstance(payload.get('reason'),str) or not payload['reason'].strip():
                        raise Refusal('Rejection feedback required')
                    run['rejected'].extend(p['fingerprint'] for p in run['search']['plans'])
                    self.plan(run)
                elif action=='acknowledge':
                    if run['status']!='AWAITING_OPERATIONAL_ACK':
                        raise Refusal('No operational acknowledgement pending')
                    self.guard(db,run)
                    plan=self.selected(run)
                    if role not in plan['prerequisites'] or payload.get('fingerprint')!=plan['fingerprint'] or payload.get('operations_digest')!=digest(plan['operations']):
                        raise Refusal('Specialist role and exact approved postcondition evidence required')
                    run['acknowledgements'][role]=dict(fingerprint=plan['fingerprint'],operations_digest=digest(plan['operations']),at=self.now(run),simulated=True)
                    if set(run['acknowledgements'])==set(plan['prerequisites']):
                        run['committed_schedule']=plan['flights']
                        run['committed_operations_digest']=digest(plan['operations'])
                        sources.expected_change(run,'EXPECTED_PREREQUISITE',plan['fingerprint'],self.now(run))
                        self.trace(run,'SIMULATED_OPERATIONAL_COMMIT',dict(fingerprint=plan['fingerprint'],source='SYN-OPERATIONAL-ACKS'))
                        run['status']='REVALIDATING'
                elif action=='execute':
                    if role!='DUTY_MANAGER' or run['status'] not in ('REVALIDATING','EXECUTING'):
                        raise Refusal('Ready approval and Duty Manager initiation required')
                    self.guard(db,run,approval=True)
                    if run['status']=='EXECUTING' and self.clock()<run['lease_until']:
                        raise Refusal('Execution worker already owns an active lease')
                    run['status']='EXECUTING';run['fence']+=1;run['lease_until']=self.clock()+15
                    run.setdefault('execution_deadline',self.now(run)+120)
                elif action=='stop':
                    if run['status'] in TERMINAL:
                        raise Refusal('Episode already finished')
                    self.handoff(run,'DUTY_MANAGER_STOP')
                elif action=='advance':
                    seconds=payload.get('seconds')
                    if type(seconds) is not int or not 1<=seconds<=3600:
                        raise Refusal('Clock advance must be 1–3600 seconds')
                    run['clock_offset']+=seconds
                    if run['status'] not in TERMINAL and self.now(run)>=run.get('expires_at',float('inf')):
                        self.handoff(run,'CARD_EXPIRED')
                elif action=='source_change':
                    if run['status'] in TERMINAL:
                        raise Refusal('Episode is terminal')
                    run['source_version']+=1
                    self.handoff(run,'UNEXPECTED_MATERIAL_SOURCE_CHANGE')
                elif action=='source_update':
                    if run['status'] in TERMINAL: raise Refusal('Episode is terminal')
                    original=json.loads(json.dumps(run))
                    try:
                        classification=sources.apply(run,payload,self.now(run))
                    except ValueError as exc:
                        run=original
                        run['scenario']['sources_verified']=False
                        run['source_version']+=1
                        run['source_updates'].append(dict(classification='INVALID_UNKNOWN',source=payload.get('source'),reason=str(exc),at=self.now(run)))
                        self.handoff(run,'INVALID_SOURCE_UPDATE: '+str(exc))
                    else:
                        if classification=='UNEXPECTED_MATERIAL':
                            run['source_version']+=1
                            self.handoff(run,'UNEXPECTED_MATERIAL_SOURCE_CHANGE: '+payload['source'])
                elif action=='fault':
                    allowed={'booking_fail_after','notification_fail','missing_ack'}
                    if payload.get('kind') not in allowed or run['status'] in TERMINAL:
                        raise Refusal('Unknown fault or terminal episode')
                    if payload['kind']=='booking_fail_after':
                        count=payload.get('value')
                        if type(count) is not int or not 0<=count<=150:
                            raise Refusal('Invalid failure position')
                        run['faults']['booking_fail_after']=count
                    else:
                        run['faults'][payload['kind']]=True
                elif action=='resume_monitor':
                    if run['status']!='MONITORING':
                        raise Refusal('Not monitoring')
                    monitor=Monitor(**run['monitor']['state'])
                    start=run['scenario']['seed']['day_start_ms']+5*60*60_000
                    monitor,decision=tick(monitor,start+61*60_000,downline_flights=run['monitor']['downline_flights'],crew_conflict=False,precheck_verified=run['scenario']['sources_verified'])
                    run['monitor'].update(duration_minutes=61,decision=decision.value,state=asdict(monitor))
                    if decision!=Decision.TRIGGER: raise Refusal('Trigger did not qualify')
                    self.plan(run)
                elif action in ('accept_handoff','assign_handoff','return_handoff','resolve_handoff'):
                    packet=next((h for h in run['handoffs'] if h['id']==payload.get('handoff_id')),None)
                    if not packet: raise Refusal('Unknown handoff')
                    handoff_transition(packet,action,role,payload,self.now(run))
                else:
                    raise Refusal('Unknown command')
            except (ValueError, Refusal) as exc:
                error=Refusal(str(exc))
                # Reload so rejected commands cannot leave partially mutated authority.
                run=self.store.load(db,run_id)
                self.trace(run,'REFUSED',str(exc),role)
            else:
                run['revision']+=1
                self.trace(run,action.upper(),payload,role)
                db.execute('INSERT INTO commands VALUES(?,?,?)',(run_id,key,command_hash))
            self.store.save(db,run)
        if error:
            raise error
        return run

    def work_step(self, run_id, fence):
        """One atomic party transition or notification. Safe to resume after process restart."""
        with self.store.transaction() as db:
            run=self.store.load(db,run_id)
            if run['status']!='EXECUTING' or run['fence']!=fence:
                raise Refusal('Stale worker fence or stopped episode')
            before_effect = json.dumps(run)
            try:
                if self.clock()>=run['lease_until']:
                    raise Refusal('Worker lease expired; reclaim through guarded execution command')
                self.guard(db,run,approval=True)
                if self.now(run)>=run['execution_deadline']:
                    raise Refusal('Execution deadline expired')
                if run['faults'].get('missing_ack'):
                    raise Refusal('Injected prerequisite failure')
                plan=self.selected(run)
                pending=next((a for a in plan['allocations'] if a['party_id'] not in run['receipts']),None)
                if pending:
                    if len(run['receipts'])>=run['faults'].get('booking_fail_after',151):
                        raise Refusal('Injected booking failure; committed receipts preserved')
                    self.commit_party(run,pending)
                else:
                    message=next((m for m in run['outbox'].values() if m['status']=='PENDING'),None)
                    if message:
                        message['attempts']+=1
                        if run['faults'].get('notification_fail'):
                            if message['attempts']>=2:
                                message['status']='MANUAL_CONTACT'
                        else:
                            message['status']='SENT';message['receipt']=digest([run_id,message['passenger_id'],message['template']])
                        self.trace(run,'MESSAGE_ATTEMPT',dict(passenger_id=message['passenger_id'],status=message['status']))
                    else:
                        unresolved=any(a['outcome']=='UNRESOLVED' for a in plan['allocations'])
                        unsent=any(m['status']!='SENT' for m in run['outbox'].values())
                        if unresolved or unsent:
                            self.handoff(run,'PASSENGER_OR_COMMUNICATION_WORK_REMAINS','PASSENGER_OPERATIONS')
                        else:
                            run['status']='COMPLETED'
                            self.trace(run,'COMPLETED',dict(passengers=len(run['outbox']),messages_sent=len(run['outbox'])))
                if run['status']=='EXECUTING':
                    self.guard(db,run,approval=True)
                    if self.now(run)>=run['execution_deadline']:
                        raise Refusal('Execution deadline expired before commit')
            except Refusal as exc:
                run=json.loads(before_effect)
                self.handoff(run,str(exc),'PASSENGER_OPERATIONS' if run['receipts'] else 'DUTY_MANAGER')
            run['lease_until']=self.clock()+15
            run['revision']+=1
            self.store.save(db,run)
            return run

    def commit_party(self,run,allocation):
        pid=allocation['party_id']
        if pid in run['receipts']:
            return
        passenger_ids=allocation['passenger_ids']
        old=Counter(leg for p in passenger_ids for leg in run['bookings'][p]['legs'])
        new_legs=allocation['itinerary']
        new=Counter(leg for p in passenger_ids for leg in (new_legs or run['bookings'][p]['legs']))
        deltas={leg:new[leg]-old[leg] for leg in old.keys()|new.keys()}
        for leg,delta in deltas.items():
            row=run['inventory'][leg]
            if not 0<=row['occupied']+delta<=row['capacity']:
                raise Refusal('Atomic whole-party capacity check failed')
        for leg,delta in deltas.items():
            if delta:
                run['inventory'][leg]['occupied']+=delta
                run['inventory'][leg]['version']+=1
        passengers={p['id']:p for p in run['scenario']['seed']['passengers']}
        for p in passenger_ids:
            if new_legs and list(new_legs)!=run['bookings'][p]['legs']:
                run['booking_history'].append(dict(passenger_id=p,**run['bookings'][p]))
                run['bookings'][p]=dict(legs=list(new_legs),version=run['bookings'][p]['version']+1)
            template='UNRESOLVED' if allocation['outcome']=='UNRESOLVED' else ('RETAINED' if allocation['outcome']=='RETAINED' else 'REBOOKED')
            run['outbox'][p]=dict(passenger_id=p,template=template,legs=list(new_legs or []),
                status='PENDING' if passengers[p]['contact_available'] else 'MANUAL_CONTACT',attempts=0)
        run['receipts'][pid]=dict(key=digest([run['id'],run['generation'],pid]),outcome=allocation['outcome'],
            passenger_ids=passenger_ids,legs=new_legs,deltas=deltas,at=self.now(run))
        if allocation['next_day']:
            run['handoffs'].append(handoff_packet(run,'NEXT_DAY_PASSENGER_CARE','PASSENGER_OPERATIONS',
                self.now(run),parties=[pid],required_action=
                'Review overnight passenger-care needs. No compensation or paid service has been promised.'))
        run['expected_inventory']=digest(run['inventory'])
        sources.expected_change(run,'OWN_BATCH_EFFECT',run['receipts'][pid]['key'],self.now(run))
        self.trace(run,'PARTY_COMMITTED',dict(party_id=pid,outcome=allocation['outcome']))

    def execute(self, run_id, fence):
        for _ in range(1000):
            state=self.work_step(run_id,fence)
            if state['status']!='EXECUTING':
                return state
        raise Refusal('Execution work ceiling exceeded')

    def control(self, action=None, *, role='DUTY_MANAGER', evidence=None):
        with self.store.transaction() as db:
            control=self.store.control(db)
            if action:
                if action=='disable' and role in ('DUTY_MANAGER','OCC_OPERATIONS_LEAD'):
                    control['writes_enabled']=False
                elif action=='restore' and role=='OCC_OPERATIONS_LEAD':
                    required={'incident','root_cause','fix_version','regression_evidence','reviewer_approval'}
                    if not isinstance(evidence,dict) or set(evidence)!=required or not all(isinstance(v,str) and v.strip() for v in evidence.values()):
                        raise Refusal('Restoration requires incident, root cause, fix version, regression evidence and reviewer approval')
                    control['writes_enabled']=True
                else:
                    raise Refusal('Operation or role not authorised')
                control['version']+=1
                control['history'].append(dict(action=action,role=role,at=self.clock(),evidence=evidence))
                db.execute('UPDATE control SET body=? WHERE id=1',(json.dumps(control),))
                for row in db.execute('SELECT body FROM runs').fetchall():
                    run=json.loads(row['body'])
                    if run['status'] not in TERMINAL:
                        self.handoff(run,'APPLICATION_CONTROL_CHANGED')
                        run['revision']+=1
                        self.store.save(db,run)
            return control
