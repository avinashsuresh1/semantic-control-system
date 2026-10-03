"""
Live Network Adapters for TypeSafe Jev API and System-2 Reasoning LLMs.
Allows the Semantic CPU to switch seamlessly from local emulation to live cloud endpoints.
"""

import json
import os
from typing import Any, Callable, Dict, List, Optional
import urllib.error
import urllib.request

from scpu.decoder import BaseSemanticDecoder
from scpu.system2 import TacticalPrior
from scpu.types import DecodedOperation, HardwareSignal, SemanticInstruction, SignalType


class LiveTypeSafeJevDecoder(BaseSemanticDecoder):
    """
    Live adapter connecting the sCPU directly to TypeSafe's Jev API.
    Jev takes (Input State + Instruction + Question Schemas) and executes a single
    parallel pass returning typed categorical decisions and calibrated confidence.
    """

    DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/decide"

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_seconds: float = 0.5,
        http_requester: Optional[Callable[[str, Dict[str, str], Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
        self.endpoint = endpoint or os.environ.get("TYPESAFE_ENDPOINT", self.DEFAULT_ENDPOINT)
        self.timeout_seconds = timeout_seconds
        # Allows dependency injection for deterministic testing without external network
        self._http_requester = http_requester or self._default_requester

    def _default_requester(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def decode(
        self,
        instruction: SemanticInstruction,
        state_snapshot: Dict[str, Any],
        tactical_prior: Optional[TacticalPrior] = None,
    ) -> DecodedOperation:
        if not self.api_key:
            # Fallback when key is missing: raise trap with 0 confidence
            return DecodedOperation(
                instruction_address=instruction.address,
                intent="MISSING_API_KEY",
                signals=[],
                confidence=0.0,
            )

        # Build Jev Question & Schema Payload
        payload = {
            "instruction": instruction.text,
            "telemetry": state_snapshot.get("sensors", {}),
            "flags": state_snapshot.get("flags", {}),
            "constraints": tactical_prior.active_constraints if tactical_prior else {},
            "prior_mode": tactical_prior.mode if tactical_prior else "NORMAL",
            "schema": {
                "intent": "string",
                "signals": "list<{pin: string, type: string, value: float}>",
                "confidence": "float",
            },
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp_data = self._http_requester(self.endpoint, headers, payload)
            
            raw_signals = resp_data.get("signals", [])
            signals = []
            for s in raw_signals:
                sig_type_str = s.get("type", "PWM").upper()
                sig_type = getattr(SignalType, sig_type_str, SignalType.PWM)
                signals.append(
                    HardwareSignal(
                        pin_or_channel=s.get("pin", "OUT0"),
                        signal_type=sig_type,
                        value=float(s.get("value", 0.0)),
                    )
                )

            return DecodedOperation(
                instruction_address=instruction.address,
                intent=resp_data.get("intent", "JEV_LIVE_ACTION"),
                signals=signals,
                confidence=float(resp_data.get("confidence", 0.5)),
                target_registers=resp_data.get("registers", {}),
                flag_updates=resp_data.get("flags", {}),
                halt=bool(resp_data.get("halt", False)),
            )

        except Exception as ex:
            # Hardware safety: any network failure or timeout degrades confidence to 0.0
            return DecodedOperation(
                instruction_address=instruction.address,
                intent=f"JEV_NETWORK_FAULT: {str(ex)}",
                signals=[],
                confidence=0.0,
            )


class LiveLLMSystem2Planner:
    """
    Connects System-2 to a reasoning LLM (OpenAI, Anthropic, Gemini, or local Ollama).
    Runs deliberative scenario simulations and synthesizes TacticalPriors.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: str = "https://api.openai.com/v1/chat/completions",
        model: str = "gpt-4o",
        timeout_seconds: float = 3.0,
        http_requester: Optional[Callable[[str, Dict[str, str], Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.endpoint = endpoint
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._http_requester = http_requester or self._default_requester

    def _default_requester(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def deliberate(
        self,
        current_sensors: Dict[str, float],
        mission_goal: str,
    ) -> TacticalPrior:
        if not self.api_key:
            # Safe nominal default when key not provided
            return TacticalPrior(
                mode="NOMINAL",
                risk_factor=0.0,
                recommended_directive=mission_goal,
            )

        system_prompt = (
            "You are the System-2 Deliberative Planner of a Semantic CPU. "
            "Given sensory telemetry and the mission goal, mentally simulate alternative scenario "
            "hypotheses and output a JSON object with keys: "
            "mode (NORMAL|CAUTIOUS|EMERGENCY_AVOIDANCE), risk_factor (float 0-1), "
            "recommended_directive (string), active_constraints (dict)."
        )

        user_content = json.dumps({
            "current_sensors": current_sensors,
            "mission_goal": mission_goal,
        })

        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = self._http_requester(self.endpoint, headers, payload)
            content_str = resp["choices"][0]["message"]["content"]
            parsed = json.loads(content_str)
            return TacticalPrior(
                mode=parsed.get("mode", "NORMAL"),
                risk_factor=float(parsed.get("risk_factor", 0.1)),
                recommended_directive=parsed.get("recommended_directive", mission_goal),
                contingency_action=parsed.get("contingency_action", "none"),
                active_constraints=parsed.get("active_constraints", {}),
            )
        except Exception:
            # Fall back to safe cautious prior on error
            return TacticalPrior(
                mode="CAUTIOUS",
                risk_factor=0.5,
                recommended_directive="cautiously hold current position",
                active_constraints={"max_throttle": 0.2},
            )
