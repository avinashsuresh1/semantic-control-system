"""
Register File and Hardware State for Semantic CPU.
"""

from typing import Any, Dict, Optional


class RegisterBank:
    """
    Simulated hardware registers including:
    - R0..R7: General purpose registers
    - S0..S7: Sensor / Telemetry input registers (read-only to code, updated by hardware/sensors)
    - OUT0..OUT7: Actuator / Control output registers
    - Flags: ZERO, FAULT, OVERCURRENT, EMERGENCY_STOP, HALT
    """

    def __init__(self) -> None:
        self._general: Dict[str, float] = {f"R{i}": 0.0 for i in range(8)}
        self._sensors: Dict[str, float] = {f"S{i}": 0.0 for i in range(8)}
        self._outputs: Dict[str, float] = {f"OUT{i}": 0.0 for i in range(8)}
        self._flags: Dict[str, bool] = {
            "FAULT": False,
            "OVERCURRENT": False,
            "EMERGENCY_STOP": False,
            "HALT": False,
            "INTERRUPT": False,
        }

    def read(self, reg_name: str) -> float:
        name = reg_name.upper()
        if name in self._general:
            return self._general[name]
        if name in self._sensors:
            return self._sensors[name]
        if name in self._outputs:
            return self._outputs[name]
        raise KeyError(f"Unknown register: {reg_name}")

    def write_general(self, reg_name: str, value: float) -> None:
        name = reg_name.upper()
        if name not in self._general:
            raise KeyError(f"Register {reg_name} is not a valid general purpose register (R0-R7).")
        self._general[name] = float(value)

    def write_output(self, reg_name: str, value: float) -> None:
        name = reg_name.upper()
        if name not in self._outputs:
            raise KeyError(f"Register {reg_name} is not a valid output register (OUT0-OUT7).")
        self._outputs[name] = float(value)

    def update_sensor(self, sensor_name: str, value: float) -> None:
        """Sensors are updated by the physical environment or peripherals."""
        name = sensor_name.upper()
        if name not in self._sensors:
            raise KeyError(f"Sensor {sensor_name} is not recognized (S0-S7).")
        self._sensors[name] = float(value)

    def get_flag(self, flag_name: str) -> bool:
        return self._flags.get(flag_name.upper(), False)

    def set_flag(self, flag_name: str, val: bool) -> None:
        name = flag_name.upper()
        if name in self._flags:
            self._flags[name] = bool(val)
        else:
            self._flags[name] = bool(val)

    def snapshot(self) -> Dict[str, Any]:
        """Provides a serializable snapshot of CPU state for the Jev decoder."""
        return {
            "general": dict(self._general),
            "sensors": dict(self._sensors),
            "outputs": dict(self._outputs),
            "flags": dict(self._flags),
        }

    def reset(self) -> None:
        for k in self._general:
            self._general[k] = 0.0
        for k in self._sensors:
            self._sensors[k] = 0.0
        for k in self._outputs:
            self._outputs[k] = 0.0
        for k in self._flags:
            self._flags[k] = False
