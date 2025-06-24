"""Tests for JumpList utility"""

from spyder_okvim.utils.jump_list import JumpList, Jump


def test_push_and_navigation():
    jl = JumpList(max_items=5)
    jl.push("a.py", 1)
    jl.push("a.py", 2)
    jl.push("a.py", 3)

    assert jl.index == 3
    assert jl.jumps == [Jump("a.py", 1), Jump("a.py", 2), Jump("a.py", 3)]

    prev = jl.back()
    assert prev == Jump("a.py", 2)
    assert jl.index == 2

    nxt = jl.forward()
    assert nxt == Jump("a.py", 3)
    assert jl.index == 3


def test_duplicate_and_truncate():
    jl = JumpList(max_items=3)
    jl.push("a.py", 1)
    jl.push("a.py", 1)
    assert jl.jumps == [Jump("a.py", 1)]

    jl.push("b.py", 2)
    jl.push("c.py", 3)
    jl.push("d.py", 4)
    assert len(jl.jumps) == 3
    assert jl.jumps[0] == Jump("b.py", 2)

    jl.back()
    jl.push("e.py", 5)
    assert jl.jumps == [Jump("b.py", 2), Jump("c.py", 3), Jump("e.py", 5)]
    assert jl.index == 3
