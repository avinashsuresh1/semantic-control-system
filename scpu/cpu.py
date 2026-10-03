"""
Semantic CPU Core (sCPU).
Executes instructions written in natural language Semantic ISA using System-1 decoding.
"""

from typing import Any, List, Optional
from scpu.bus import HardwareBus
from scpu.decoder import BaseSemanticDecoder, JevSystem1Decoder
from scpu.interlock import SafetyInterlock
from scpu.registers import RegisterBank
from scpu.types import ExecutionResult, ExecutionStatus, SemanticInstruction


class SemanticCPU:
    """
    Semantic Central Processing Unit (sCPU).
    """

    def __init__(
        self,
        decoder: Optional[BaseSemanticDecoder] = None,
        interlock: Optional[SafetyInterlock] = None,
        bus: Optional[HardwareBus] = None,
        system2_planner: Optional[Any] = None,
        enable_system2_supervision: bool = True,
    ) -> None:
        self.decoder = decoder or JevSystem1Decoder()
        self.interlock = interlock or SafetyInterlock()
        self.bus = bus or HardwareBus()
        self.registers = RegisterBank()
        self.system2_planner = system2_planner
        self.enable_system2_supervision = enable_system2_supervision
        self.current_tactical_prior: Optional[Any] = None

        self.instruction_memory: List[SemanticInstruction] = []
        self.pc: int = 0
        self.cycle_count: int = 0
        self.is_halted: bool = False

    def simulate_and_update_prior(self, mission_goal: str = "nominal") -> Optional[Any]:
        """Runs System-2 mental simulation to forecast scenarios and update tactical prior."""
        if self.system2_planner is not None:
            snapshot = self.registers.snapshot()
            self.current_tactical_prior = self.system2_planner.deliberate(
                current_sensors=snapshot["sensors"],
                mission_goal=mission_goal,
            )
        return self.current_tactical_prior

    def load_program(self, instructions: List[str]) -> None:
        """Loads natural language instructions into instruction memory."""
        self.instruction_memory = [
            SemanticInstruction(address=idx, text=inst)
            for idx, inst in enumerate(instructions)
        ]
        self.pc = 0
        self.is_halted = False

    def step(self) -> ExecutionResult:
        """Executes a single CPU cycle (Fetch -> Decode -> Guardrail -> Execute -> Writeback)."""
        if self.is_halted:
            return ExecutionResult(
                cycle=self.cycle_count,
                instruction_address=self.pc,
                status=ExecutionStatus.HALTED,
                decoded_op=None,
                message="CPU is halted.",
            )

        if self.pc >= len(self.instruction_memory):
            self.is_halted = True
            return ExecutionResult(
                cycle=self.cycle_count,
                instruction_address=self.pc,
                status=ExecutionStatus.HALTED,
                decoded_op=None,
                message="End of instruction memory reached.",
            )

        # 1. Fetch
        inst = self.instruction_memory[self.pc]

        # 2. Decode (System-1 parallel pass conditioned on System-2 prior)
        snapshot = self.registers.snapshot()
        decoded_op = self.decoder.decode(inst, snapshot, self.current_tactical_prior)

        # 3. Guardrail / Safety Interlock
        status, reason, sanitized_signals = self.interlock.validate(
            decoded_op, snapshot["flags"]
        )

        # 3b. Deliberative System-2 Escalation (if low confidence)
        if (
            status == ExecutionStatus.CONFIDENCE_REJECTED
            and self.system2_planner is not None
            and self.enable_system2_supervision
        ):
            # System-2 performs mental simulation of scenarios
            self.simulate_and_update_prior(mission_goal=inst.text)
            # Re-decode conditioned on System-2's tactical prior
            decoded_op = self.decoder.decode(inst, snapshot, self.current_tactical_prior)
            status, reason, sanitized_signals = self.interlock.validate(
                decoded_op, snapshot["flags"]
            )

        # 4. Execute & Actuate (if allowed)
        emitted_signals = []
        if status == ExecutionStatus.SUCCESS:
            for sig in sanitized_signals:
                self.bus.apply_signal(sig)
                emitted_signals.append(sig)

            # Update general registers
            for reg, val in decoded_op.target_registers.items():
                self.registers.write_general(reg, val)

            # Update flags
            for flag, val in decoded_op.flag_updates.items():
                self.registers.set_flag(flag, val)

            if decoded_op.halt:
                self.is_halted = True

            self.pc += 1

        elif status == ExecutionStatus.CONFIDENCE_REJECTED:
            # Low confidence persists despite System-2 or System-2 disabled
            self.registers.set_flag("INTERRUPT", True)
            self.pc += 1

        elif status == ExecutionStatus.SAFETY_FAULT:
            self.registers.set_flag("FAULT", True)
            for flag, val in decoded_op.flag_updates.items():
                self.registers.set_flag(flag, val)
            # Route safe-mode signals if any
            for sig in sanitized_signals:
                self.bus.apply_signal(sig)
                emitted_signals.append(sig)
            self.is_halted = True

        self.cycle_count += 1

        return ExecutionResult(
            cycle=self.cycle_count,
            instruction_address=inst.address,
            status=status,
            decoded_op=decoded_op,
            emitted_signals=emitted_signals,
            message=reason,
        )

    def run(self, max_cycles: int = 100) -> List[ExecutionResult]:
        """Runs the CPU until halted or max cycles reached."""
        results: List[ExecutionResult] = []
        while not self.is_halted and len(results) < max_cycles:
            results.append(self.step())
        return results

    def reset(self) -> None:
        """Hard reset of the CPU registers, bus, and state."""
        self.pc = 0
        self.cycle_count = 0
        self.is_halted = False
        self.registers.reset()
        self.bus.clear()
