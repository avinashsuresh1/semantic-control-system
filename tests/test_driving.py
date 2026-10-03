"""
Tests for autonomous vehicle second-nature driving reflexes and System-2 interaction.
"""

from scpu.cpu import SemanticCPU
from scpu.driving import DrivingReflexDecoder
from scpu.interlock import SafetyInterlock
from scpu.system2 import System2ScenarioSimulator, TacticalPrior
from scpu.types import ExecutionStatus, SemanticInstruction, SignalType


def test_lane_centering_micro_steering_reflex():
    decoder = DrivingReflexDecoder()
    inst = SemanticInstruction(address=0, text="maintain lane and cruise")

    # Drifting right by 0.2m -> expect corrective left steering (-3.0 degrees)
    state_drift_right = {"sensors": {"S0": 60.0, "S1": 80.0, "S2": 0.2}}
    op_right = decoder.decode(inst, state_drift_right)
    steering_sig = [s for s in op_right.signals if s.pin_or_channel == "STEERING"][0]
    assert steering_sig.value == -3.0

    # Drifting left by -0.3m -> expect corrective right steering (+4.5 degrees)
    state_drift_left = {"sensors": {"S0": 60.0, "S1": 80.0, "S2": -0.3}}
    op_left = decoder.decode(inst, state_drift_left)
    steering_sig_left = [s for s in op_left.signals if s.pin_or_channel == "STEERING"][0]
    assert steering_sig_left.value == 4.5


def test_adaptive_headway_reflex_throttle_and_brake():
    decoder = DrivingReflexDecoder()
    inst = SemanticInstruction(address=0, text="follow lead vehicle and match speed")

    # Ample distance (70m away at 60km/h) -> Cruising throttle
    state_clear = {"sensors": {"S0": 70.0, "S1": 60.0, "S2": 0.0}}
    op_clear = decoder.decode(inst, state_clear)
    throttle_clear = [s for s in op_clear.signals if s.pin_or_channel == "THROTTLE"][0]
    brake_clear = [s for s in op_clear.signals if s.pin_or_channel == "BRAKE"][0]
    assert throttle_clear.value == 0.65
    assert brake_clear.value == 0.0

    # Urgent cut-in: lead vehicle only 8m ahead! -> Immediate reflex braking
    state_cut_in = {"sensors": {"S0": 8.0, "S1": 60.0, "S2": 0.0}}
    op_cut_in = decoder.decode(inst, state_cut_in)
    throttle_cut = [s for s in op_cut_in.signals if s.pin_or_channel == "THROTTLE"][0]
    brake_cut = [s for s in op_cut_in.signals if s.pin_or_channel == "BRAKE"][0]
    assert throttle_cut.value == 0.0
    assert brake_cut.value == 0.9
    assert op_cut_in.confidence >= 0.95


def test_driving_cpu_integration_with_system2_supervision():
    interlock = SafetyInterlock(max_voltage=50.0)  # Allow steering degrees on analog line
    decoder = DrivingReflexDecoder()
    system2 = System2ScenarioSimulator()
    cpu = SemanticCPU(
        decoder=decoder,
        interlock=interlock,
        system2_planner=system2,
        enable_system2_supervision=True,
    )

    program = [
        "maintain lane and cruise",
        "complex intersection with uncertain pedestrian crossing",
    ]
    cpu.load_program(program)
    cpu.registers.update_sensor("S0", 45.0)  # lead distance 45m
    cpu.registers.update_sensor("S1", 40.0)  # speed 40 km/h
    cpu.registers.update_sensor("S2", 0.05)  # slight offset 0.05m

    # Cycle 1: Second-nature cruising reflex
    res1 = cpu.step()
    assert res1.status == ExecutionStatus.SUCCESS
    assert res1.decoded_op.intent == "ADAPTIVE_HEADWAY_REFLEX"

    # Cycle 2: Complex uncertain scenario triggers System-2 mental simulation
    res2 = cpu.step()
    assert res2.status == ExecutionStatus.SUCCESS
    assert "RESOLVED_BY_SYSTEM2" in res2.decoded_op.intent
    assert res2.decoded_op.confidence >= 0.85
