"""Pure event-time reducer for one explicitly mapped restriction episode.

The caller supplies validated scope/precheck evidence. This reducer grants no
booking authority. Ambiguous histories stay blocked for human classification.
"""
from dataclasses import asdict, dataclass, replace
from enum import Enum

from .policy import POLICY


class Decision(str, Enum):
    MONITOR = "MONITOR"
    TRIGGER = "TRIGGER"
    CLASSIFY = "CLASSIFY"
    MANUAL_HANDOFF = "MANUAL_HANDOFF"
    IGNORED = "IGNORED"


@dataclass(frozen=True)
class RestrictionEvent:
    event_id: str
    version: int
    effective_ms: int
    received_ms: int
    kind: str
    active: bool
    applicable: bool
    confirmed: bool
    weather: bool

    def __post_init__(self):
        if not self.event_id or self.kind not in {
            "GROUND_STOP", "RUNWAY_CLOSURE", "WEATHER_ADVISORY"
        }:
            raise ValueError("Invalid restriction identity/type")
        for value in (self.version, self.effective_ms, self.received_ms):
            if type(value) is not int or value < 0:
                raise ValueError("Versions and UTC milliseconds must be nonnegative integers")
        if self.version < 1 or self.received_ms < self.effective_ms:
            raise ValueError("Invalid version or event chronology")
        for value in (self.active, self.applicable, self.confirmed, self.weather):
            if type(value) is not bool:
                raise ValueError("Restriction flags must be booleans")


@dataclass(frozen=True)
class Monitor:
    start_ms: int | None = None
    lift_ms: int | None = None
    latest_effective_ms: int = -1
    active: bool = False
    triggered: bool = False
    blocked: bool = False
    versions: tuple[tuple[str, int], ...] = ()
    history: tuple[dict, ...] = ()
    latest_tick_ms: int = -1


def ingest(state: Monitor, event: RestrictionEvent) -> tuple[Monitor, Decision]:
    if state.blocked:
        return state, Decision.CLASSIFY
    versions = dict(state.versions)
    if event.version <= versions.get(event.event_id, 0):
        return state, Decision.IGNORED
    history=[RestrictionEvent(**raw) for raw in state.history]
    # Same-authority version chronology cannot run backwards. Different mapped
    # authorities may arrive late and are reconciled by effective time.
    previous=next((e for e in reversed(history) if e.event_id==event.event_id),None)
    if previous and (event.effective_ms<previous.effective_ms or
                     (event.effective_ms==previous.effective_ms and event.active!=previous.active)):
        return replace(state,blocked=True),Decision.CLASSIFY
    if not event.confirmed or (not history and state.latest_effective_ms>=0):
        return replace(state,blocked=True),Decision.CLASSIFY
    history.append(event)
    ordered=sorted(history,key=lambda e:(e.effective_ms,e.event_id,e.version))
    active_by_authority={}
    start=None;lift=None;active=False
    for item in ordered:
        qualifying=item.applicable and item.weather and item.kind!='WEATHER_ADVISORY'
        if not qualifying:
            continue  # An advisory cannot lift a verified restriction.
        active_by_authority[item.event_id]=item.active
        next_active=any(active_by_authority.values())
        if next_active and not active:
            reset=lift is not None and item.effective_ms-lift>=POLICY.lift_reset_minutes*60_000
            if start is None or reset: start=item.effective_ms
            lift=None
        elif active and not next_active:
            lift=item.effective_ms
        active=next_active
    now=max(state.latest_tick_ms,event.effective_ms,state.latest_effective_ms)
    if not active and lift is not None and now-lift>=POLICY.lift_reset_minutes*60_000:
        start=None
    # Previously emitted decisions are never retroactively changed by late data.
    if state.triggered and event.effective_ms<state.latest_effective_ms and start!=state.start_ms:
        return replace(state,blocked=True),Decision.CLASSIFY
    versions[event.event_id]=event.version
    return replace(state,versions=tuple(sorted(versions.items())),
        latest_effective_ms=max(state.latest_effective_ms,event.effective_ms),
        history=tuple(asdict(e) for e in ordered),active=active,start_ms=start,lift_ms=lift,
        triggered=state.triggered if start==state.start_ms else False),Decision.MONITOR


def tick(state: Monitor, now_ms: int, *, downline_flights: int,
         crew_conflict: bool, precheck_verified: bool) -> tuple[Monitor, Decision]:
    if type(now_ms) is not int or now_ms < state.latest_effective_ms:
        raise ValueError("Tick must follow known event time")
    if type(downline_flights) is not int or downline_flights < 0:
        raise ValueError("Invalid affected-flight count")
    if type(crew_conflict) is not bool or type(precheck_verified) is not bool:
        raise ValueError("Precheck flags must be booleans")
    if state.blocked:
        return state, Decision.CLASSIFY
    state=replace(state,latest_tick_ms=now_ms)
    if not state.active:
        if state.lift_ms is not None and now_ms - state.lift_ms >= POLICY.lift_reset_minutes * 60_000:
            return replace(state, start_ms=None, triggered=False), Decision.MONITOR
        return state, Decision.MONITOR
    if not precheck_verified:
        return state, Decision.MANUAL_HANDOFF
    if (not state.triggered and state.start_ms is not None
            and now_ms - state.start_ms > POLICY.trigger_minutes * 60_000
            and (downline_flights >= 2 or crew_conflict)):
        return replace(state, triggered=True), Decision.TRIGGER
    return state, Decision.MONITOR
