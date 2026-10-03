"""
Tests for LiveTypeSafeJevDecoder and LiveLLMSystem2Planner adapters.
Verifies network request formatting, response schema parsing, and graceful error handling.
"""

from scpu.adapters import LiveLLMSystem2Planner, LiveTypeSafeJevDecoder
from scpu.cpu import SemanticCPU
from scpu.types import ExecutionStatus, SemanticInstruction, SignalType


def test_live_jev_missing_api_key_returns_zero_confidence():
    decoder = LiveTypeSafeJevDecoder(api_key="")
    inst = SemanticInstruction(address=0, text="turn on LED1")
    op = decoder.decode(inst, {})
    assert op.intent == "MISSING_API_KEY"
    assert op.confidence == 0.0


def test_live_jev_successful_response_parsing():
    def mock_jev_requester(url, headers, payload):
        assert "Authorization" in headers
        assert "Bearer test_key" in headers["Authorization"]
        assert payload["instruction"] == "set throttle to 75%"
        return {
            "intent": "SET_THROTTLE",
            "confidence": 0.94,
            "signals": [
                {"pin": "OUT0", "type": "PWM", "value": 0.75},
            ],
            "registers": {"R0": 0.75},
            "flags": {},
            "halt": False,
        }

    decoder = LiveTypeSafeJevDecoder(
        api_key="test_key",
        http_requester=mock_jev_requester,
    )
    inst = SemanticInstruction(address=0, text="set throttle to 75%")
    op = decoder.decode(inst, {"sensors": {"S0": 50.0}})

    assert op.intent == "SET_THROTTLE"
    assert op.confidence == 0.94
    assert len(op.signals) == 1
    assert op.signals[0].pin_or_channel == "OUT0"
    assert op.signals[0].value == 0.75


def test_live_jev_network_failure_degrades_confidence():
    def failing_requester(url, headers, payload):
        raise ConnectionResetError("Connection refused by host")

    decoder = LiveTypeSafeJevDecoder(
        api_key="test_key",
        http_requester=failing_requester,
    )
    inst = SemanticInstruction(address=0, text="maintain speed")
    op = decoder.decode(inst, {})

    assert "JEV_NETWORK_FAULT" in op.intent
    assert op.confidence == 0.0  # Safe degradation


def test_live_llm_system2_successful_scenario_deliberation():
    def mock_llm_requester(url, headers, payload):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"mode": "CAUTIOUS", "risk_factor": 0.25, '
                            '"recommended_directive": "slow down to 30km/h", '
                            '"active_constraints": {"max_throttle": 0.3}}'
                        )
                    }
                }
            ]
        }

    planner = LiveLLMSystem2Planner(
        api_key="test_llm_key",
        http_requester=mock_llm_requester,
    )
    prior = planner.deliberate(current_sensors={"S0": 25.0}, mission_goal="cruise")

    assert prior.mode == "CAUTIOUS"
    assert prior.risk_factor == 0.25
    assert prior.recommended_directive == "slow down to 30km/h"
    assert prior.active_constraints["max_throttle"] == 0.3


def test_live_adapters_integrated_into_semantic_cpu():
    def mock_jev(url, headers, payload):
        return {
            "intent": "ACTUATE_PIN",
            "confidence": 0.98,
            "signals": [{"pin": "OUT1", "type": "DIGITAL_HIGH", "value": 1.0}],
            "halt": True,
        }

    decoder = LiveTypeSafeJevDecoder(api_key="test_key", http_requester=mock_jev)
    cpu = SemanticCPU(decoder=decoder)
    cpu.load_program(["activate relay 1"])

    res = cpu.step()
    assert res.status == ExecutionStatus.SUCCESS
    assert cpu.bus.get_digital("OUT1") == 1
    assert cpu.is_halted
