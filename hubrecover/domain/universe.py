"""Descriptor selection only; descriptors are not feasible/executable plans."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import combinations, zip_longest
import json

from .policy import POLICY


@dataclass(frozen=True)
class Descriptor:
    kind: str
    roots: tuple[str, ...]
    delay_minutes: int | None = None
    spare_tail: str | None = None


@dataclass(frozen=True)
class Universe:
    version: str
    raw_count: int
    selected: tuple[Descriptor, ...]
    descriptor_hash: str
    cap_applied: bool


def select_descriptors(roots: list[str], compatible_spares: dict[str, list[str]]) -> Universe:
    """Inputs are verified eligible roots/spares from the future snapshot validator."""
    if len(roots) > 18 or len(set(roots)) != len(roots):
        raise ValueError("Expected at most 18 unique roots")
    if any(not isinstance(root, str) or not root for root in roots):
        raise ValueError("Invalid root ID")
    if set(compatible_spares) - set(roots):
        raise ValueError("Spare mapping contains unknown roots")
    if any(not isinstance(t, str) or not t for tails in compatible_spares.values() for t in tails):
        raise ValueError("Invalid spare ID")
    ordered = sorted(roots)
    families = [
        [Descriptor("DELAY", (r,), delay_minutes=d) for r in ordered for d in POLICY.delay_minutes],
        [Descriptor("SWAP", (r,), spare_tail=t) for r in ordered
         for t in sorted(set(compatible_spares.get(r, [])))[:2]],
        [Descriptor("CANCEL_SINGLE", (r,)) for r in ordered],
        [Descriptor("CANCEL_PAIR", pair) for pair in combinations(ordered, 2)],
    ]
    selected = tuple(d for row in zip_longest(*families) for d in row if d is not None)[:POLICY.candidate_limit]
    encoded = json.dumps([asdict(d) for d in selected], sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    count = sum(map(len, families))
    return Universe("RECOVERY_UNIVERSE_V1", count, selected, sha256(encoded).hexdigest(), count > len(selected))
