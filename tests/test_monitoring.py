from dataclasses import replace

import pytest

from hubrecover.domain.monitoring import Decision, Monitor, RestrictionEvent, ingest, tick


def event(minute=0, version=1, **changes):
    return replace(RestrictionEvent("SYN-RESTRICTION", version, minute * 60_000,
                                   minute * 60_000, "GROUND_STOP", True, True, True, True), **changes)


def advance(state, minute, **changes):
    args = dict(downline_flights=2, crew_conflict=False, precheck_verified=True)
    args.update(changes)
    return tick(state, int(minute * 60_000), **args)


@pytest.mark.parametrize("minute,flights,conflict,expected", [
    (60, 2, False, Decision.MONITOR), (60.001, 2, False, Decision.TRIGGER),
    (61, 1, False, Decision.MONITOR), (61, 1, True, Decision.TRIGGER),
])
def test_strict_trigger(minute, flights, conflict, expected):
    state, _ = ingest(Monitor(), event())
    assert advance(state, minute, downline_flights=flights, crew_conflict=conflict)[1] == expected


@pytest.mark.parametrize("change", [{"kind": "WEATHER_ADVISORY"}, {"applicable": False}, {"weather": False}])
def test_nonqualifying_event(change):
    state, _ = ingest(Monitor(), event(**change))
    assert advance(state, 90)[1] == Decision.MONITOR


def test_trigger_once_and_ignore_duplicate_or_older_version():
    state, _ = ingest(Monitor(), event(version=2))
    state, decision = advance(state, 61)
    assert decision == Decision.TRIGGER
    for version in (1, 2):
        assert ingest(state, event(version=version, active=False)) == (state, Decision.IGNORED)
    assert advance(state, 62)[1] == Decision.MONITOR


@pytest.mark.parametrize("recurrence,expected_start", [(69, 0), (70, 70 * 60_000)])
def test_lift_reset_boundary(recurrence, expected_start):
    state, _ = ingest(Monitor(), event())
    state, _ = ingest(state, event(55, 2, active=False))
    assert advance(state, 61)[1] == Decision.MONITOR
    state, _ = ingest(state, event(recurrence, 3))
    assert state.start_ms == expected_start
    assert advance(state, recurrence)[1] == (Decision.TRIGGER if recurrence == 69 else Decision.MONITOR)


def test_missing_precheck_never_triggers():
    state, _ = ingest(Monitor(), event())
    assert advance(state, 61, precheck_verified=False)[1] == Decision.MANUAL_HANDOFF


def test_late_history_is_blocked_not_overwritten():
    state, _ = ingest(Monitor(), event(10))
    state, result = ingest(state, event(5, 2, active=False))
    assert result == Decision.CLASSIFY
    assert advance(state, 90)[1] == Decision.CLASSIFY


def test_unconfirmed_requires_classification():
    assert ingest(Monitor(), event(confirmed=False))[1] == Decision.CLASSIFY


@pytest.mark.parametrize("change", [{"active": "false"}, {"version": True},
                                    {"effective_ms": 0.5}, {"received_ms": -1}])
def test_strict_event_validation(change):
    with pytest.raises(ValueError):
        event(**change)
