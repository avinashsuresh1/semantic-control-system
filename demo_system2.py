"""
Demonstration of System-1 (Jev) supplemented by System-2 (Deliberative Scenario Simulation).
"""

from scpu.cpu import SemanticCPU
from scpu.system2 import System2ScenarioSimulator


def run_system2_demo() -> None:
    print("=" * 70)
    print("  HETEROGENEOUS SEMANTIC CONTROL SYSTEM: SYSTEM-1 (JEV) + SYSTEM-2")
    print("=" * 70)

    system2 = System2ScenarioSimulator()
    cpu = SemanticCPU(system2_planner=system2, enable_system2_supervision=True)

    # 1. System-2 Mental Simulation Phase
    sensors = {"S0": 38.0, "OUT0": 0.8}  # Obstacle 38cm away while cruising
    print("\n[Step 1: System-2 Deliberation & Counterfactual Simulation]")
    print(f"Current Telemetry: Obstacle Distance = {sensors['S0']}cm, Throttle = {sensors['OUT0']}")
    
    outcomes = system2.simulate_scenarios(sensors, "advance to checkpoint")
    for o in outcomes:
        print(f"  * Scenario Hypothesis: '{o.action_hypothesis}'")
        print(f"    -> Projected Risk: {o.projected_risk:.2f} | Rationale: {o.rationale}")

    # Synthesize Tactical Prior
    prior = system2.deliberate(sensors, "advance to checkpoint")
    print(f"\nSynthesized Tactical Prior:")
    print(f"  Mode: {prior.mode} | Risk Factor: {prior.risk_factor:.2f}")
    print(f"  Active Constraints: {prior.active_constraints}")
    print(f"  Recommended Directive: '{prior.recommended_directive}'")

    # Set prior into CPU
    cpu.current_tactical_prior = prior

    # 2. System-1 Execution conditioned on System-2 Prior
    print("\n[Step 2: System-1 Jev Execution Informed by System-2 Prior]")
    program = [
        "set throttle to 90%",           # Wants 90%, but System-2 prior clamps to 35%!
        "maybe proceed forward perhaps", # Ambiguous directive -> Escalate to System-2
    ]
    cpu.load_program(program)
    cpu.registers.update_sensor("S0", 38.0)

    for i in range(len(program)):
        res = cpu.step()
        print(f"\nInstruction: \"{cpu.instruction_memory[res.instruction_address].text}\"")
        print(f"  Decoded Intent: {res.decoded_op.intent}")
        print(f"  Confidence: {res.decoded_op.confidence:.1%}")
        signals_str = ", ".join(f"{s.pin_or_channel}={s.value} ({s.signal_type.value})" for s in res.emitted_signals)
        print(f"  Actuation Signals: {signals_str}")
        print(f"  Status: {res.status.value}")

    print("\n" + "=" * 70)
    print("Heterogeneous Dual-Core Execution Complete.")
    print("=" * 70)


if __name__ == "__main__":
    run_system2_demo()
