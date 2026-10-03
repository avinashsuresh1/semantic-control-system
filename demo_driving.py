"""
Autonomous Driving Demonstration:
Illustrating 'second nature' reflex driving via System-1 (Jev)
supported by System-2 (deliberative traffic scenario simulation).
"""

from scpu.cpu import SemanticCPU
from scpu.driving import DrivingReflexDecoder
from scpu.interlock import SafetyInterlock
from scpu.system2 import System2ScenarioSimulator


def run_driving_demo() -> None:
    print("=" * 75)
    print("  SEMANTIC CONTROL SYSTEM — AUTONOMOUS VEHICLE REFLEX CO-PROCESSOR")
    print("=" * 75)

    interlock = SafetyInterlock(min_voltage=-45.0, max_voltage=45.0)
    decoder = DrivingReflexDecoder()
    system2 = System2ScenarioSimulator()
    cpu = SemanticCPU(
        decoder=decoder,
        interlock=interlock,
        system2_planner=system2,
        enable_system2_supervision=True,
    )

    # Scenarios simulating driving conditions
    scenarios = [
        {
            "name": "Highway Cruise with Minor Left Lane Drift",
            "instruction": "maintain lane and cruise",
            "sensors": {"S0": 65.0, "S1": 100.0, "S2": -0.15},  # 65m ahead, 100km/h, 15cm left of center
        },
        {
            "name": "Vehicle Ahead Slows Down (Headway Compression)",
            "instruction": "follow lead vehicle and match speed",
            "sensors": {"S0": 22.0, "S1": 80.0, "S2": 0.02},   # 22m ahead (below desired 24m gap)
        },
        {
            "name": "Sudden Cut-In Obstacle (Spinal Reflex Arc)",
            "instruction": "follow lead vehicle and match speed",
            "sensors": {"S0": 7.5, "S1": 60.0, "S2": 0.0},     # 7.5m ahead! Immediate brake
        },
        {
            "name": "Complex Multi-Way Intersection (Triggers System-2 Deliberation)",
            "instruction": "complex intersection with uncertain pedestrian crossing",
            "sensors": {"S0": 30.0, "S1": 35.0, "S2": 0.0},
        },
    ]

    for step_num, scen in enumerate(scenarios, 1):
        print(f"\n[Driving State #{step_num}]: {scen['name']}")
        print(f"  Telemetry: Lead Dist={scen['sensors']['S0']}m, Speed={scen['sensors']['S1']}km/h, Lane Offset={scen['sensors']['S2']}m")

        cpu.load_program([scen["instruction"]])
        for s_key, s_val in scen["sensors"].items():
            cpu.registers.update_sensor(s_key, s_val)

        res = cpu.step()
        print(f"  System-1 Intent: {res.decoded_op.intent} (Confidence: {res.decoded_op.confidence:.1%})")
        signals = {s.pin_or_channel: (s.value, s.unit) for s in res.emitted_signals}
        print(f"  Actuation -> Steering: {signals.get('STEERING', (0.0, ''))[0]} deg | Throttle: {signals.get('THROTTLE', (0.0, ''))[0]} | Brake: {signals.get('BRAKE', (0.0, ''))[0]}")
        print(f"  Status: {res.status.value}")

    print("\n" + "=" * 75)
    print("Autonomous Driving Reflex Demonstration Complete.")
    print("=" * 75)


if __name__ == "__main__":
    run_driving_demo()
