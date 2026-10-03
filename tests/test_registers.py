"""
Unit tests for RegisterBank.
"""

import pytest
from scpu.registers import RegisterBank


def test_general_registers_read_write():
    rb = RegisterBank()
    assert rb.read("R0") == 0.0
    rb.write_general("R0", 42.5)
    assert rb.read("R0") == 42.5

    with pytest.raises(KeyError):
        rb.write_general("R8", 1.0)

    with pytest.raises(KeyError):
        rb.read("INVALID")


def test_sensor_registers():
    rb = RegisterBank()
    assert rb.read("S0") == 0.0
    rb.update_sensor("S0", 12.4)
    assert rb.read("S0") == 12.4

    with pytest.raises(KeyError):
        rb.update_sensor("S9", 1.0)


def test_flags_and_snapshot():
    rb = RegisterBank()
    assert not rb.get_flag("FAULT")
    rb.set_flag("FAULT", True)
    assert rb.get_flag("FAULT")

    snap = rb.snapshot()
    assert snap["flags"]["FAULT"] is True
    assert snap["sensors"]["S0"] == 0.0

    rb.reset()
    assert not rb.get_flag("FAULT")
