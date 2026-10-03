"""
Unit tests for SafetyInterlock and Confidence Guardrails.
"""

from scpu.interlock import SafetyInterlock
from scpu.types import DecodedOperation, ExecutionStatus, HardwareSignal, SignalType


def test_confidence_rejection():
    interlock = SafetyInterlock(min_confidence=0.80)
    op = DecodedOperation(
        instruction_address=0,
        intent="TEST",
        signals=[HardwareSignal("OUT0", SignalType.DIGITAL_HIGH, 1.0)],
        confidence=0.65,  # Below 0.80
    )
    status, msg, signals = interlock.validate(op, {})
    assert status == ExecutionStatus.CONFIDENCE_REJECTED
    assert "below threshold" in msg
    assert len(signals) == 0


def test_emergency_stop_lockdown():
    interlock = SafetyInterlock()
    op = DecodedOperation(
        instruction_address=0,
        intent="TEST",
        signals=[HardwareSignal("OUT0", SignalType.PWM, 0.9)],
        confidence=0.99,
    )
    status, msg, signals = interlock.validate(op, {"EMERGENCY_STOP": True})
    assert status == ExecutionStatus.SAFETY_FAULT
    assert "E-Stop/Fault active" in msg
    # Signal should be forced to safe low
    assert len(signals) == 1
    assert signals[0].signal_type == SignalType.DIGITAL_LOW
    assert signals[0].value == 0.0


def test_pwm_clamping_and_voltage_validation():
    interlock = SafetyInterlock(max_voltage=12.0, max_pwm=1.0)

    # Over-range PWM gets clamped to 1.0
    op_pwm = DecodedOperation(
        instruction_address=0,
        intent="PWM_TEST",
        signals=[HardwareSignal("OUT0", SignalType.PWM, 1.4)],
        confidence=0.95,
    )
    status, _, signals = interlock.validate(op_pwm, {})
    assert status == ExecutionStatus.SUCCESS
    assert signals[0].value == 1.0

    # Over-voltage gets rejected
    op_volt = DecodedOperation(
        instruction_address=1,
        intent="VOLT_TEST",
        signals=[HardwareSignal("VCC", SignalType.ANALOG_VOLTAGE, 24.0)],
        confidence=0.95,
    )
    status_v, msg_v, _ = interlock.validate(op_volt, {})
    assert status_v == ExecutionStatus.SAFETY_FAULT
    assert "Voltage 24.0V out of physical bounds" in msg_v
