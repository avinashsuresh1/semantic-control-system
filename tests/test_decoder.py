"""
Unit tests for JevSystem1Decoder.
"""

from scpu.decoder import JevSystem1Decoder
from scpu.types import SemanticInstruction, SignalType


def test_decoder_direct_actuation():
    decoder = JevSystem1Decoder()
    inst = SemanticInstruction(address=0, text="turn on LED1")
    op = decoder.decode(inst, {})
    assert op.intent == "DIRECT_ENABLE"
    assert len(op.signals) == 1
    assert op.signals[0].pin_or_channel == "LED1"
    assert op.signals[0].signal_type == SignalType.DIGITAL_HIGH
    assert op.signals[0].value == 1.0
    assert op.confidence >= 0.90


def test_decoder_obstacle_avoidance_reflex():
    decoder = JevSystem1Decoder()
    # Case A: Obstacle close (distance = 10cm, threshold = 30cm)
    inst = SemanticInstruction(address=0, text="if obstacle < 30cm, decelerate motor smoothly")
    state_near = {"sensors": {"S0": 10.0}}
    op_near = decoder.decode(inst, state_near)
    assert op_near.intent == "OBSTACLE_AVOIDANCE"
    # Closer distance -> low throttle on OUT0, high brake on OUT1
    motor_sig = [s for s in op_near.signals if s.pin_or_channel == "OUT0"][0]
    brake_sig = [s for s in op_near.signals if s.pin_or_channel == "OUT1"][0]
    assert motor_sig.value < 0.5
    assert brake_sig.value > 0.5

    # Case B: Clear road (distance = 80cm)
    state_clear = {"sensors": {"S0": 80.0}}
    op_clear = decoder.decode(inst, state_clear)
    motor_sig_clear = [s for s in op_clear.signals if s.pin_or_channel == "OUT0"][0]
    assert motor_sig_clear.value == 0.75


def test_decoder_thermal_management():
    decoder = JevSystem1Decoder()
    inst = SemanticInstruction(address=0, text="monitor temperature and cool if hot")
    # Low temp
    op_cool = decoder.decode(inst, {"sensors": {"S1": 30.0}})
    fan_cool = [s for s in op_cool.signals if s.pin_or_channel == "FAN_PWM"][0]
    assert fan_cool.value == 0.0

    # Critical temp
    op_hot = decoder.decode(inst, {"sensors": {"S1": 85.0}})
    fan_hot = [s for s in op_hot.signals if s.pin_or_channel == "FAN_PWM"][0]
    assert fan_hot.value == 1.0


def test_decoder_ambiguous_low_confidence():
    decoder = JevSystem1Decoder()
    inst = SemanticInstruction(address=0, text="maybe turn something on perhaps")
    op = decoder.decode(inst, {})
    assert op.confidence < 0.60
