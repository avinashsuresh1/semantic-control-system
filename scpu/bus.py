"""
Hardware Bus and Device Controller.
"""

from typing import Dict, List, Optional
from scpu.types import HardwareSignal, SignalType


class HardwareBus:
    """
    Simulates physical pins, PWM timers, and actuator busses.
    """

    def __init__(self) -> None:
        self.digital_pins: Dict[str, int] = {}
        self.pwm_channels: Dict[str, float] = {}
        self.analog_lines: Dict[str, float] = {}
        self.signal_history: List[HardwareSignal] = []

    def apply_signal(self, signal: HardwareSignal) -> None:
        self.signal_history.append(signal)
        pin = signal.pin_or_channel.upper()

        if signal.signal_type in (SignalType.DIGITAL_HIGH, SignalType.DIGITAL_LOW):
            self.digital_pins[pin] = 1 if signal.signal_type == SignalType.DIGITAL_HIGH else 0
        elif signal.signal_type == SignalType.PWM:
            self.pwm_channels[pin] = float(signal.value)
        elif signal.signal_type == SignalType.ANALOG_VOLTAGE:
            self.analog_lines[pin] = float(signal.value)

    def get_digital(self, pin: str) -> int:
        return self.digital_pins.get(pin.upper(), 0)

    def get_pwm(self, channel: str) -> float:
        return self.pwm_channels.get(channel.upper(), 0.0)

    def get_analog(self, line: str) -> float:
        return self.analog_lines.get(line.upper(), 0.0)

    def clear(self) -> None:
        self.digital_pins.clear()
        self.pwm_channels.clear()
        self.analog_lines.clear()
        self.signal_history.clear()
