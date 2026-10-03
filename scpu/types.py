"""
Core data structures and types for the Semantic CPU (sCPU).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalType(str, Enum):
    DIGITAL_HIGH = "DIGITAL_HIGH"
    DIGITAL_LOW = "DIGITAL_LOW"
    PWM = "PWM"
    ANALOG_VOLTAGE = "ANALOG_VOLTAGE"
    BUS_COMMAND = "BUS_COMMAND"
    INTERRUPT = "INTERRUPT"
    NO_OP = "NO_OP"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    SAFETY_FAULT = "SAFETY_FAULT"
    CONFIDENCE_REJECTED = "CONFIDENCE_REJECTED"
    HALTED = "HALTED"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True)
class SemanticInstruction:
    """An instruction in natural language or semantic form."""
    address: int
    text: str
    target_device: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HardwareSignal:
    """Physical or simulated hardware signal emitted by the sCPU."""
    pin_or_channel: str
    signal_type: SignalType
    value: float  # e.g., 0.0/1.0 for digital, 0.0-1.0 for PWM duty cycle, voltage for analog
    unit: str = "raw"


@dataclass
class DecodedOperation:
    """Result of System-1 semantic decoding by Jev."""
    instruction_address: int
    intent: str
    signals: List[HardwareSignal]
    confidence: float  # Calibrated probability [0.0, 1.0] from Jev
    target_registers: Dict[str, float] = field(default_factory=dict)
    flag_updates: Dict[str, bool] = field(default_factory=dict)
    halt: bool = False


@dataclass
class ExecutionResult:
    """Cycle execution status and feedback."""
    cycle: int
    instruction_address: int
    status: ExecutionStatus
    decoded_op: Optional[DecodedOperation]
    emitted_signals: List[HardwareSignal] = field(default_factory=list)
    message: str = ""
