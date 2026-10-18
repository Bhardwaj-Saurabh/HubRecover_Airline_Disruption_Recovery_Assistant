"""Fictional teaching constants; not airline operating rules."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    version: str = "HUBRECOVER-POLICY-001"
    trigger_minutes: int = 60
    lift_reset_minutes: int = 15
    candidate_limit: int = 100
    delay_minutes: tuple[int, ...] = (30, 60, 90, 120)
    card_validity_seconds: int = 300
    regeneration_limit: int = 2
    enumeration_seconds: int = 20
    next_day_warning_percent: int = 25
    unresolved_warning_percent: int = 10


POLICY = Policy()
