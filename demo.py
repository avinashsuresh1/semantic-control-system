"""
Interactive demonstration of the Jev-powered Semantic CPU (sCPU).
"""

from scpu.cpu import SemanticCPU


def run_demo() -> None:
    cpu = SemanticCPU()

    # Define a program using Natural Language Semantic ISA
    program = [
        "turn on LED1",
        "set throttle to 80%",
        "if obstacle < 30cm, decelerate motor smoothly",
        "monitor thermal sensors and fan",
        "emergency stop now",
    ]

    print("=" * 65)
    print("  SEMANTIC CONTROL SYSTEM (SCS) WITH SYSTEM-1 JEV DECODER")
    print("=" * 65)
    print("\nProgram Loaded:")
    for i, inst in enumerate(program):
        print(f"  [0x{i:02X}] {inst}")
    print("-" * 65)

    cpu.load_program(program)

    # Simulate environment telemetry
    cpu.registers.update_sensor("S0", 12.0)  # Obstacle distance = 12cm (within 30cm!)
    cpu.registers.update_sensor("S1", 62.0)  # Temperature = 62 C

    while not cpu.is_halted and cpu.pc < len(cpu.instruction_memory):
        curr_pc = cpu.pc
        inst_text = cpu.instruction_memory[curr_pc].text
        res = cpu.step()

        print(f"\nCycle {res.cycle} | PC: 0x{curr_pc:02X} | Instruction: \"{inst_text}\"")
        if res.decoded_op:
            print(f"  System-1 Intent: {res.decoded_op.intent} (Confidence: {res.decoded_op.confidence:.1%})")
        print(f"  Status: {res.status.value}")
        if res.emitted_signals:
            signals_str = ", ".join(
                f"{s.pin_or_channel}={s.value} ({s.signal_type.value})"
                for s in res.emitted_signals
            )
            print(f"  Signals Emitted: {signals_str}")
        print(f"  Flags: FAULT={cpu.registers.get_flag('FAULT')}, E-STOP={cpu.registers.get_flag('EMERGENCY_STOP')}")

    print("\n" + "=" * 65)
    print("Execution complete.")
    print("=" * 65)


if __name__ == "__main__":
    run_demo()
