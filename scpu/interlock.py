"""
Hardware Safety Interlock and Confidence Guardrail Unit.
"""

from typing import Dict, List, Tuple
from scpu.types import DecodedOperation, ExecutionStatus, HardwareSignal, SignalType


class SafetyInterlock:
    """
    Enforces hardware bounds and confidence gating on decoded System-1 operations.
    """

    def __init__(
        self,
        min_confidence: float = 0.75,
        min_voltage: float = -24.0,
        max_voltage: float = 24.0,
        max_pwm: float = 1.0,
        max_current_threshold: float = 10.0,
    ) -> None:
        self.min_confidence = min_confidence
        self.min_voltage = min_voltage
        self.max_voltage = max_voltage
        self.max_pwm = max_pwm
        self.max_current_threshold = max_current_threshold

    def validate(
        self,
        op: DecodedOperation,
        current_flags: Dict[str, bool],
    ) -> Tuple[ExecutionStatus, str, List[HardwareSignal]]:
        """
        Validates the operation against safety rules.
        Returns:
            (status, explanation, sanitized_signals)
        """
        # Rule 1: Emergency Stop or Active Fault Locks System
        is_estop = (
            current_flags.get("EMERGENCY_STOP", False)
            or op.flag_updates.get("EMERGENCY_STOP", False)
        )
        is_fault = (
            current_flags.get("FAULT", False)
            or op.flag_updates.get("FAULT", False)
        )

        if is_estop or is_fault:
            # Safe fall-back: all signals neutralized to safe state
            safe_signals = [
                HardwareSignal(
                    pin_or_channel=sig.pin_or_channel,
                    signal_type=SignalType.DIGITAL_LOW,
                    value=0.0,
                    unit="safe_off",
                )
                for sig in op.signals
            ]
            return ExecutionStatus.SAFETY_FAULT, "E-Stop/Fault active. Actuation locked down.", safe_signals

        # Rule 2: Calibrated Confidence Threshold Gate
        if op.confidence < self.min_confidence:
            return (
                ExecutionStatus.CONFIDENCE_REJECTED,
                f"Confidence {op.confidence:.3f} below threshold {self.min_confidence:.3f}.",
                [],
            )

        # Rule 3: Physical Signal Range Validation & Clamping
        sanitized_signals: List[HardwareSignal] = []
        for sig in op.signals:
            val = sig.value
            if sig.signal_type == SignalType.PWM:
                val = max(0.0, min(val, self.max_pwm))
            elif sig.signal_type == SignalType.ANALOG_VOLTAGE:
                if val < self.min_voltage or val > self.max_voltage:
                    return (
                        ExecutionStatus.SAFETY_FAULT,
                        f"Voltage {val}V out of physical bounds [{self.min_voltage}V, {self.max_voltage}V].",
                        [],
                    )
            elif sig.signal_type in (SignalType.DIGITAL_HIGH, SignalType.DIGITAL_LOW):
                val = 1.0 if sig.signal_type == SignalType.DIGITAL_HIGH else 0.0

            sanitized_signals.append(
                HardwareSignal(
                    pin_or_channel=sig.pin_or_channel,
                    signal_type=sig.signal_type,
                    value=val,
                    unit=sig.unit,
                )
            )

        return ExecutionStatus.SUCCESS, "Safety checks passed.", sanitized_signals
