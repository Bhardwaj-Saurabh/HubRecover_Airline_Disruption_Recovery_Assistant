import pytest

from hubrecover.domain.universe import Descriptor, select_descriptors


def test_small_hand_calculated_selection():
    result = select_descriptors(["B", "A"], {"A": ["T2", "T1"]})
    assert result.raw_count == 13  # 8 delays + 2 swaps + 2 singles + 1 pair
    assert result.selected[:8] == (
        Descriptor("DELAY", ("A",), 30), Descriptor("SWAP", ("A",), spare_tail="T1"),
        Descriptor("CANCEL_SINGLE", ("A",)), Descriptor("CANCEL_PAIR", ("A", "B")),
        Descriptor("DELAY", ("A",), 60), Descriptor("SWAP", ("A",), spare_tail="T2"),
        Descriptor("CANCEL_SINGLE", ("B",)), Descriptor("DELAY", ("A",), 90),
    )
    assert not result.cap_applied


def test_cap_and_independent_selection_oracle():
    roots = [f"F{i:02}" for i in range(18)]
    result = select_descriptors(roots, {r: ["Z", "Y", "X"] for r in roots})
    assert result.raw_count == 279
    # Independent family queues with explicit index consumption; no engine helpers.
    queues = [[], [], [], []]
    for root in roots:
        for delay in (30, 60, 90, 120):
            queues[0].append(("DELAY", (root,), delay, None))
        for tail in ("X", "Y"):
            queues[1].append(("SWAP", (root,), None, tail))
        queues[2].append(("CANCEL_SINGLE", (root,), None, None))
    for i, left in enumerate(roots):
        for right in roots[i + 1:]:
            queues[3].append(("CANCEL_PAIR", (left, right), None, None))
    expected = []
    while len(expected) < 100:
        for queue in queues:
            if queue and len(expected) < 100:
                expected.append(queue.pop(0))
    assert [(d.kind, d.roots, d.delay_minutes, d.spare_tail) for d in result.selected] == expected
    assert result.cap_applied


def test_input_order_does_not_change_digest():
    a = select_descriptors(["A", "B"], {"A": ["X", "Y"]})
    b = select_descriptors(["B", "A"], {"A": ["Y", "X", "X"]})
    assert a == b


@pytest.mark.parametrize("roots,spares", [(["A", "A"], {}), ([str(i) for i in range(19)], {}),
                                        (["A"], {"B": ["T"]}), ([""], {})])
def test_invalid_universe_inputs(roots, spares):
    with pytest.raises(ValueError):
        select_descriptors(roots, spares)


def test_empty_universe():
    result = select_descriptors([], {})
    assert result.raw_count == 0
    assert result.selected == ()
