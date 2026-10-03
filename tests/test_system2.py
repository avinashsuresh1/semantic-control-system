"""
Unit and integration tests for System-2 Deliberative Planner & Jev Co-Processor.
"""

from scpu.cpu import SemanticCPU
from scpu.decoder import JevSystem1Decoder
from scpu.system2 import System2ScenarioSimulator, TacticalPrior
from scpu.types import ExecutionStatus, SemanticInstruction, SignalType


def test_system2_scenario_simulation_branches():
    simulator = System2ScenarioSimulator()
    sensors = {"S0": 15.0, "OUT0": 0.8}
    outcomes = simulator.simulate_scenarios(sensors, "cruise")

    assert len(outcomes) == 3
    branch_names = {o.scenario_name for o in outcomes}
    assert branch_names == {"maintain_trajectory", "preemptive_slowdown", "immediate_stop"}

    maintain = [o for o in outcomes if o.scenario_name == "maintain_trajectory"][0]
    assert maintain.projected_risk > 0.80  # Stopping distance exceeds 15cm

    stop = [o for o in outcomes if o.scenario_name == "immediate_stop"][0]
    assert stop.projected_risk <= 0.10


def test_system2_deliberation_modes():
    simulator = System2ScenarioSimulator()

    # Emergency proximity (< 25cm)
    prior_emerg = simulator.deliberate({"S0": 12.0}, "mission")
    assert prior_emerg.mode == "EMERGENCY_AVOIDANCE"
    assert prior_emerg.active_constraints["max_throttle"] == 0.0

    # Cautious proximity (25cm - 50cm)
    prior_cautious = simulator.deliberate({"S0": 40.0}, "mission")
    assert prior_cautious.mode == "CAUTIOUS"
    assert prior_cautious.active_constraints["max_throttle"] == 0.35

    # Nominal clear path (> 50cm)
    prior_nominal = simulator.deliberate({"S0": 90.0}, "mission")
    assert prior_nominal.mode == "NORMAL" or prior_nominal.mode == "NOMINAL"


def test_jev_conditioned_by_system2_prior():
    decoder = JevSystem1Decoder()
    inst = SemanticInstruction(address=0, text="set throttle to 90%")
    state = {"sensors": {"S0": 35.0}, "general": {}}

    # Without System-2 prior -> Full 90% throttle
    op_unconditioned = decoder.decode(inst, state, tactical_prior=None)
    sig_raw = [s for s in op_unconditioned.signals if s.pin_or_channel == "OUT0"][0]
    assert sig_raw.value == 0.90

    # With System-2 Cautious prior (max_throttle = 0.35)
    cautious_prior = TacticalPrior(
        mode="CAUTIOUS",
        risk_factor=0.2,
        active_constraints={"max_throttle": 0.35},
    )
    op_conditioned = decoder.decode(inst, state, tactical_prior=cautious_prior)
    sig_capped = [s for s in op_conditioned.signals if s.pin_or_channel == "OUT0"][0]
    assert sig_capped.value == 0.35


def test_cpu_system2_ambiguity_resolution():
    """Verify System-2 mental simulation resolves an ambiguous instruction for Jev."""
    system2 = System2ScenarioSimulator()
    cpu = SemanticCPU(system2_planner=system2, enable_system2_supervision=True)

    program = [
        "maybe proceed forward perhaps",  # Ambiguous! Low confidence for Jev alone
    ]
    cpu.load_program(program)
    cpu.registers.update_sensor("S0", 80.0)  # Road is clear

    res = cpu.step()
    # System-2 scenario simulation should have kicked in and resolved the directive
    assert res.status == ExecutionStatus.SUCCESS
    assert "RESOLVED_BY_SYSTEM2" in res.decoded_op.intent
    assert res.decoded_op.confidence >= 0.80
    assert cpu.pc == 1
