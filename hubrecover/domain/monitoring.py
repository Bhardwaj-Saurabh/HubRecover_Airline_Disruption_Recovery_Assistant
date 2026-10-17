"""Pure event-time reducer for one explicitly mapped restriction episode.

The caller supplies validated scope/precheck evidence. This reducer grants no
booking authority. Ambiguous histories stay blocked for human classification.
"""
from dataclasses import dataclass, replace
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


def ingest(state: Monitor, event: RestrictionEvent) -> tuple[Monitor, Decision]:
    if state.blocked:
        return state, Decision.CLASSIFY
    versions = dict(state.versions)
    if event.version <= versions.get(event.event_id, 0):
        return state, Decision.IGNORED
    # A late status change requires history reconciliation, never blind overwrite.
    if event.effective_ms < state.latest_effective_ms:
        return replace(state, blocked=True), Decision.CLASSIFY
    versions[event.event_id] = event.version
    next_state = replace(state, versions=tuple(sorted(versions.items())),
                         latest_effective_ms=event.effective_ms)
    if not event.confirmed:
        return replace(next_state, blocked=True), Decision.CLASSIFY
    qualifying = event.applicable and event.weather and event.kind != "WEATHER_ADVISORY"
    if not qualifying:
        # Unrelated/advisory records cannot lift an existing qualifying restriction.
        return next_state, Decision.MONITOR
    if not event.active:
        return replace(next_state, active=False,
                       lift_ms=state.lift_ms if state.lift_ms is not None else event.effective_ms), Decision.MONITOR
    reset = state.lift_ms is not None and (
        event.effective_ms - state.lift_ms >= POLICY.lift_reset_minutes * 60_000
    )
    return replace(next_state, active=True, lift_ms=None,
                   start_ms=event.effective_ms if reset or state.start_ms is None else state.start_ms,
                   triggered=False if reset else state.triggered), Decision.MONITOR


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
