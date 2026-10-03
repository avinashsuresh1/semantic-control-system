"""
Integration tests for the full Semantic CPU execution pipeline.
"""

from scpu.cpu import SemanticCPU
from scpu.types import ExecutionStatus


def test_cpu_program_execution():
    cpu = SemanticCPU()
    program = [
        "turn on LED1",
        "set throttle to 60%",
        "if obstacle < 30cm, decelerate motor smoothly",
        "monitor thermal sensors and fan",
        "halt",
    ]
    cpu.load_program(program)

    # Set initial sensors (obstacle far, temperature normal)
    cpu.registers.update_sensor("S0", 100.0)  # distance = 100cm
    cpu.registers.update_sensor("S1", 40.0)   # temp = 40C

    results = cpu.run()
    assert len(results) == 5
    assert all(r.status == ExecutionStatus.SUCCESS for r in results)
    assert cpu.is_halted

    # Verify physical hardware bus states
    assert cpu.bus.get_digital("LED1") == 1
    assert cpu.bus.get_pwm("OUT0") == 0.75  # from clear road in obstacle instruction
    assert cpu.bus.get_pwm("FAN_PWM") == 0.0


def test_cpu_sensor_reactive_reflex():
    """Verify that changing sensor values alters hardware signals in real-time."""
    cpu = SemanticCPU()
    program = [
        "if obstacle < 30cm, decelerate motor smoothly",
    ]
    cpu.load_program(program)

    # Sensor detects close obstacle
    cpu.registers.update_sensor("S0", 6.0)  # 6cm away
    res = cpu.step()

    assert res.status == ExecutionStatus.SUCCESS
    assert cpu.bus.get_pwm("OUT0") == 0.2  # Throttled down
    assert cpu.bus.get_pwm("OUT1") == 0.8  # Braking engaged


def test_cpu_rejects_ambiguous_instruction_safely():
    cpu = SemanticCPU()
    program = [
        "maybe guess something perhaps",
        "turn on OUT2",
    ]
    cpu.load_program(program)

    res1 = cpu.step()
    # Should be rejected due to low confidence threshold (< 0.75)
    assert res1.status == ExecutionStatus.CONFIDENCE_REJECTED
    assert cpu.registers.get_flag("INTERRUPT") is True

    # Next valid instruction continues
    res2 = cpu.step()
    assert res2.status == ExecutionStatus.SUCCESS
    assert cpu.bus.get_digital("OUT2") == 1


def test_cpu_emergency_stop_halts_execution():
    cpu = SemanticCPU()
    program = [
        "turn on OUT1",
        "emergency stop now",
        "turn on OUT2",  # Should never execute
    ]
    cpu.load_program(program)

    cpu.step()
    assert cpu.bus.get_digital("OUT1") == 1

    res_estop = cpu.step()
    assert res_estop.status == ExecutionStatus.SAFETY_FAULT
    assert cpu.is_halted
    assert cpu.registers.get_flag("FAULT") is True
    assert cpu.registers.get_flag("EMERGENCY_STOP") is True

    # Stepping after halt returns HALTED status
    res_halt = cpu.step()
    assert res_halt.status == ExecutionStatus.HALTED
    assert cpu.bus.get_digital("OUT2") == 0  # not turned on
