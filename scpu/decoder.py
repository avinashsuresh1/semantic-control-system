"""
Semantic Decoder powered by Jev / System-1 decision architecture.
"""

from abc import ABC, abstractmethod
import math
import re
from typing import Any, Dict, List, Optional
from scpu.types import DecodedOperation, HardwareSignal, SemanticInstruction, SignalType


class BaseSemanticDecoder(ABC):
    """Abstract interface for Semantic CPU instruction decoders."""

    @abstractmethod
    def decode(
        self,
        instruction: SemanticInstruction,
        state_snapshot: Dict[str, Any],
        tactical_prior: Optional[Any] = None,
    ) -> DecodedOperation:
        """Decode a natural language instruction given the current hardware snapshot and optional System-2 prior."""
        pass


class JevSystem1Decoder(BaseSemanticDecoder):
    """
    Jev-inspired System-1 Decision Engine.
    Executes a single-pass parallel decision over typed question schemas:
    1. Action Classification (Discrete Signal Selection)
    2. Continuous Signal Parameter Estimation (e.g. PWM, Voltage)
    3. Probability/Confidence Calibration
    Optionally conditioned by System-2 TacticalPrior scenarios.
    """

    def __init__(self, default_confidence: float = 0.95) -> None:
        self.default_confidence = default_confidence

    def decode(
        self,
        instruction: SemanticInstruction,
        state_snapshot: Dict[str, Any],
        tactical_prior: Optional[Any] = None,
    ) -> DecodedOperation:
        text = instruction.text.strip().lower()
        sensors = state_snapshot.get("sensors", {})
        general = state_snapshot.get("general", {})
        signals: List[HardwareSignal] = []
        reg_updates: Dict[str, float] = {}
        flag_updates: Dict[str, bool] = {}
        confidence = self.default_confidence
        intent = "UNKNOWN"
        halt = False

        # System-1 Pattern / Decision Rules (Fuzzy sensory-motor mapping)
        
        # 1. Emergency Stop / Halt
        if "emergency stop" in text or "e-stop" in text or "abort" in text:
            intent = "EMERGENCY_STOP"
            confidence = 0.99
            flag_updates["EMERGENCY_STOP"] = True
            flag_updates["FAULT"] = True
            signals.append(HardwareSignal(pin_or_channel="OUT0", signal_type=SignalType.DIGITAL_LOW, value=0.0))
            signals.append(HardwareSignal(pin_or_channel="BRAKE", signal_type=SignalType.DIGITAL_HIGH, value=1.0))

        elif "halt" in text or "shutdown" in text:
            intent = "HALT"
            confidence = 0.98
            halt = True
            flag_updates["HALT"] = True

        # 2. Obstacle / Proximity Avoidance Reflex (Continuous fuzzy actuation)
        # e.g., "if obstacle < 30cm, decelerate motor smoothly" or "avoid obstacle"
        elif "obstacle" in text or "proximity" in text or "distance" in text:
            intent = "OBSTACLE_AVOIDANCE"
            distance = sensors.get("S0", 100.0)  # S0 = ultrasonic / lidar distance in cm
            
            # Extract threshold if mentioned (e.g. "30cm", "< 20")
            match = re.search(r"(\d+(\.\d+)?)", text)
            threshold = float(match.group(1)) if match else 30.0

            if distance < threshold:
                # Fuzzy braking curve: closer -> harder braking / lower throttle
                severity = max(0.0, min(1.0, 1.0 - (distance / threshold)))
                throttle = max(0.0, 1.0 - severity)
                signals.append(
                    HardwareSignal(
                        pin_or_channel="OUT0",  # Motor throttle
                        signal_type=SignalType.PWM,
                        value=round(throttle, 3),
                        unit="pwm_duty",
                    )
                )
                signals.append(
                    HardwareSignal(
                        pin_or_channel="OUT1",  # Brake actuator
                        signal_type=SignalType.PWM,
                        value=round(severity, 3),
                        unit="pwm_duty",
                    )
                )
                # Calibrated confidence: high when clear sensor reading
                confidence = 0.92
            else:
                # Cruising throttle
                signals.append(
                    HardwareSignal(
                        pin_or_channel="OUT0",
                        signal_type=SignalType.PWM,
                        value=0.75,
                        unit="pwm_duty",
                    )
                )
                confidence = 0.95

        # 3. Thermal Throttling / Cooling fan control
        elif "temperature" in text or "thermal" in text or "cool" in text or "fan" in text:
            intent = "THERMAL_MANAGEMENT"
            temp = sensors.get("S1", 25.0)  # S1 = Celsius
            if temp > 75.0:
                # Fan 100%, throttle CPU/motors down
                signals.append(HardwareSignal("FAN_PWM", SignalType.PWM, 1.0, "pwm_duty"))
                signals.append(HardwareSignal("OUT0", SignalType.PWM, 0.2, "throttle_reduction"))
                confidence = 0.96
            elif temp > 50.0:
                # Proportional fan curve
                fan_speed = (temp - 50.0) / 25.0  # 0.0 to 1.0
                signals.append(HardwareSignal("FAN_PWM", SignalType.PWM, round(fan_speed, 2), "pwm_duty"))
                confidence = 0.94
            else:
                signals.append(HardwareSignal("FAN_PWM", SignalType.PWM, 0.0, "pwm_duty"))
                confidence = 0.98

        # 4. Direct Actuation / Pin manipulation
        # e.g., "turn on led 2", "set motor speed to 60%"
        elif "turn on" in text or "enable" in text:
            intent = "DIRECT_ENABLE"
            pin_match = re.search(r"(out\d+|led\d*|gpio\d+|relay\d*)", text)
            pin = pin_match.group(1).upper() if pin_match else "OUT0"
            signals.append(HardwareSignal(pin_or_channel=pin, signal_type=SignalType.DIGITAL_HIGH, value=1.0))
            confidence = 0.97

        elif "turn off" in text or "disable" in text:
            intent = "DIRECT_DISABLE"
            pin_match = re.search(r"(out\d+|led\d*|gpio\d+|relay\d*)", text)
            pin = pin_match.group(1).upper() if pin_match else "OUT0"
            signals.append(HardwareSignal(pin_or_channel=pin, signal_type=SignalType.DIGITAL_LOW, value=0.0))
            confidence = 0.97

        elif "set" in text and ("speed" in text or "throttle" in text or "pwm" in text):
            intent = "SET_PWM"
            pct_match = re.search(r"(\d+(\.\d+)?)%", text)
            val_match = re.search(r"to\s+(\d+(\.\d+)?)", text)
            if pct_match:
                val = float(pct_match.group(1)) / 100.0
            elif val_match:
                val = float(val_match.group(1))
            else:
                val = 0.5
            signals.append(HardwareSignal(pin_or_channel="OUT0", signal_type=SignalType.PWM, value=val))
            confidence = 0.93

        # 5. Overcurrent / Safety Guardrail simulation
        elif "overcurrent" in text or "power limit" in text:
            intent = "POWER_LIMIT_CHECK"
            current = sensors.get("S2", 0.0)  # S2 = Amperes
            if current > 8.0:
                flag_updates["OVERCURRENT"] = True
                flag_updates["FAULT"] = True
                signals.append(HardwareSignal("OUT0", SignalType.DIGITAL_LOW, 0.0))
                confidence = 0.98
            else:
                confidence = 0.95

        # 6. Uncertain / Ambiguous semantic instructions -> Low Confidence
        elif "maybe" in text or "perhaps" in text or "guess" in text or "unclear" in text:
            intent = "AMBIGUOUS_DIRECTIVE"
            confidence = 0.40  # Trigger confidence rejection by SafetyInterlock
            signals.append(HardwareSignal("OUT0", SignalType.PWM, 0.5))

        # 7. Condition on System-2 Tactical Prior (if provided)
        if tactical_prior is not None:
            constraints = getattr(tactical_prior, "active_constraints", {})
            mode = getattr(tactical_prior, "mode", "NORMAL")

            # Ambiguity resolution: If System-2 has simulated and recommended a course of action
            if intent == "AMBIGUOUS_DIRECTIVE" and getattr(tactical_prior, "recommended_directive", ""):
                intent = f"RESOLVED_BY_SYSTEM2: {tactical_prior.recommended_directive}"
                confidence = 0.88

            # Emergency avoidance from System-2 mental simulation
            if mode == "EMERGENCY_AVOIDANCE":
                intent = f"EMERGENCY_AVOIDANCE_OVERRIDE (Risk: {getattr(tactical_prior, 'risk_factor', 1.0):.2f})"
                signals = [
                    HardwareSignal(pin_or_channel="OUT0", signal_type=SignalType.PWM, value=0.0, unit="throttle_cut"),
                    HardwareSignal(pin_or_channel="OUT1", signal_type=SignalType.PWM, value=1.0, unit="brake_clamp"),
                ]
                confidence = 0.96

            # Apply active constraints (e.g. max throttle cap from cautious mode)
            if "max_throttle" in constraints:
                max_thr = constraints["max_throttle"]
                for i, sig in enumerate(signals):
                    if sig.pin_or_channel == "OUT0" and sig.signal_type == SignalType.PWM:
                        signals[i] = HardwareSignal(
                            pin_or_channel=sig.pin_or_channel,
                            signal_type=sig.signal_type,
                            value=min(sig.value, max_thr),
                            unit=sig.unit,
                        )

            if constraints.get("brake_override") == 1.0:
                signals.append(HardwareSignal("BRAKE", SignalType.DIGITAL_HIGH, 1.0))

        return DecodedOperation(
            instruction_address=instruction.address,
            intent=intent,
            signals=signals,
            confidence=confidence,
            target_registers=reg_updates,
            flag_updates=flag_updates,
            halt=halt,
        )
