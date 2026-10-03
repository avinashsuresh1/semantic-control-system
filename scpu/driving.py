"""
Autonomous Driving Domain Extension for Semantic CPU.
Models human-like driving:
- System-1 (Jev): Subconscious micro-steering, throttle modulation, reflex braking (second nature).
- System-2: Deliberative traffic hazard forecasting, overtaking simulations, route adjustments.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional
from scpu.decoder import BaseSemanticDecoder
from scpu.system2 import TacticalPrior
from scpu.types import DecodedOperation, HardwareSignal, SemanticInstruction, SignalType


@dataclass
class VehicleTelemetry:
    lead_distance_m: float       # S0: Distance to vehicle ahead
    speed_kmh: float             # S1: Vehicle current speed
    lane_offset_m: float         # S2: Lateral offset from lane center (-0.5 to +0.5m)
    lead_speed_kmh: float        # S3: Speed of lead vehicle
    adjacent_lane_clear: bool    # Flag: Blind spot / adjacent lane clear


class DrivingReflexDecoder(BaseSemanticDecoder):
    """
    System-1 driving reflex engine.
    Executes 'second-nature' muscle-memory driving actions in a single forward pass.
    """

    def __init__(self, default_confidence: float = 0.96) -> None:
        self.default_confidence = default_confidence

    def decode(
        self,
        instruction: SemanticInstruction,
        state_snapshot: Dict[str, Any],
        tactical_prior: Optional[TacticalPrior] = None,
    ) -> DecodedOperation:
        text = instruction.text.strip().lower()
        sensors = state_snapshot.get("sensors", {})
        signals: List[HardwareSignal] = []
        reg_updates: Dict[str, float] = {}
        flag_updates: Dict[str, bool] = {}
        confidence = self.default_confidence
        intent = "UNKNOWN"
        halt = False

        lead_dist = sensors.get("S0", 60.0)      # meters
        speed = sensors.get("S1", 50.0)          # km/h
        lane_offset = sensors.get("S2", 0.0)     # meters (+ = right, - = left)
        lead_speed = sensors.get("S3", speed)    # km/h

        # 1. Lane Centering Reflex (Proportional micro-steering)
        # Always emit corrective steering based on lane offset
        steering_correction = -lane_offset * 15.0  # degrees of steering
        signals.append(
            HardwareSignal(
                pin_or_channel="STEERING",
                signal_type=SignalType.ANALOG_VOLTAGE,
                value=round(steering_correction, 2),
                unit="degrees",
            )
        )

        # 2. Adaptive Cruise / Headway Reflex ("Second Nature" throttle/brake modulation)
        if "cruise" in text or "follow" in text or "match speed" in text or "maintain lane" in text:
            intent = "ADAPTIVE_HEADWAY_REFLEX"
            # Calculate Time-to-Collision (TTC) or headway gap
            desired_gap = max(15.0, (speed / 10.0) * 3.0)  # e.g. 30m at 100km/h

            if lead_dist < 10.0:
                # Urgent reflex braking
                signals.append(HardwareSignal("THROTTLE", SignalType.PWM, 0.0, "pwm_duty"))
                signals.append(HardwareSignal("BRAKE", SignalType.PWM, 0.9, "pwm_duty"))
                confidence = 0.98
            elif lead_dist < desired_gap:
                # Gentle deceleration / throttle lift
                ratio = lead_dist / desired_gap
                throttle = max(0.0, min(0.3, ratio * 0.3))
                brake = max(0.0, (1.0 - ratio) * 0.5)
                signals.append(HardwareSignal("THROTTLE", SignalType.PWM, round(throttle, 2), "pwm_duty"))
                signals.append(HardwareSignal("BRAKE", SignalType.PWM, round(brake, 2), "pwm_duty"))
                confidence = 0.95
            else:
                # Clear cruising
                signals.append(HardwareSignal("THROTTLE", SignalType.PWM, 0.65, "pwm_duty"))
                signals.append(HardwareSignal("BRAKE", SignalType.PWM, 0.0, "pwm_duty"))
                confidence = 0.97

        # 3. Emergency Stop / Collision Avoidance Reflex
        elif "emergency stop" in text or "collision avoidance" in text:
            intent = "EMERGENCY_COLLISION_REFLEX"
            signals.append(HardwareSignal("THROTTLE", SignalType.PWM, 0.0, "pwm_duty"))
            signals.append(HardwareSignal("BRAKE", SignalType.PWM, 1.0, "pwm_duty"))
            flag_updates["EMERGENCY_STOP"] = True
            flag_updates["FAULT"] = True
            confidence = 0.99

        # 4. Ambiguous driving scenario (e.g. uncertain pedestrian / erratic vehicle)
        elif "uncertain" in text or "complex intersection" in text:
            intent = "COMPLEX_SCENARIO_LOW_CONFIDENCE"
            confidence = 0.45  # System-1 doesn't know; traps to System-2
            signals.append(HardwareSignal("THROTTLE", SignalType.PWM, 0.2, "pwm_duty"))
            signals.append(HardwareSignal("BRAKE", SignalType.PWM, 0.3, "pwm_duty"))

        else:
            intent = "NOMINAL_DRIVING_REFLEX"
            signals.append(HardwareSignal("THROTTLE", SignalType.PWM, 0.5, "pwm_duty"))
            signals.append(HardwareSignal("BRAKE", SignalType.PWM, 0.0, "pwm_duty"))

        # 5. Conditioned on System-2 Tactical Prior (if System-2 ran scenario simulations)
        if tactical_prior is not None:
            constraints = getattr(tactical_prior, "active_constraints", {})
            if "max_throttle" in constraints:
                max_thr = constraints["max_throttle"]
                for i, sig in enumerate(signals):
                    if sig.pin_or_channel == "THROTTLE":
                        signals[i] = HardwareSignal(
                            pin_or_channel=sig.pin_or_channel,
                            signal_type=sig.signal_type,
                            value=min(sig.value, max_thr),
                            unit=sig.unit,
                        )
            if constraints.get("brake_override") == 1.0:
                signals.append(HardwareSignal("BRAKE", SignalType.PWM, 1.0, "pwm_duty"))

            if intent == "COMPLEX_SCENARIO_LOW_CONFIDENCE" and getattr(tactical_prior, "recommended_directive", ""):
                intent = f"RESOLVED_BY_SYSTEM2: {tactical_prior.recommended_directive}"
                confidence = 0.90

        return DecodedOperation(
            instruction_address=instruction.address,
            intent=intent,
            signals=signals,
            confidence=confidence,
            target_registers=reg_updates,
            flag_updates=flag_updates,
            halt=halt,
        )
