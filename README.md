# Semantic Control Systems (SCS) — System-1 (Jev) + System-2 Cognitive Architecture

A reference architecture and simulation framework for **Semantic Control Systems (SCS)**, where control directives operate directly in natural language semantics, decoded by a fast **System-1 decision model (Jev)** to emit deterministic hardware control signals, and supervised by a **System-2 reasoning model** for deliberative scenario simulations.

---

## 1. Architectural Overview

```
                                  +-----------------------------------------------+
                                  |         SYSTEM 2 (Reasoning LLM)              |
                                  |  - Deliberative "Mental Simulation" (0.1-1Hz) |
                                  |  - Counterfactual Scenario Rollouts           |
                                  |  - Risk Forecasting & Invariant Constraints   |
                                  +-----------------------------------------------+
                                                          |
                                      Tactical Prior (Priors, Constraints)
                                                          v
+------------------+              +-------------------------------+              +-------------------+
| Real-Time Sensor | -----------> |      SYSTEM 1 (Jev Core)      | -----------> | Hardware Control  |
| Telemetry (S0..7)|              |  - Spinal Reflex Arc (10-100Hz|              | Actuation Bus     |
| (Lidar, Current) |              |  - Single-pass decision pass  |              | (PWM, GPIO Pins)  |
+------------------+              +-------------------------------+              +-------------------+
                                                          |
                                        Low-Confidence Trap (Interrupt)
                                                          |
                                                          +-----------------------> [Wakes System 2]
```

### Key Differences from Traditional Architectures
1. **No Token-by-Token Generation in the Reflex Loop:** Traditional LLMs generate conversational text token-by-token (taking seconds). Jev operates as a single-pass decision engine with calibrated probabilities in tens of milliseconds, matching physical control loop deadlines.
2. **Deterministic Safety Gating:** Hardware never acts on uncalibrated guesses. The **Hardware Safety Interlock Unit (SIU)** evaluates Jev’s calibrated confidence $P$. If $P < \tau$ (e.g. $0.75$), the CPU gates execution and raises an interrupt.
3. **Cognitive Co-Processing:** System 2 performs "mental simulations" (e.g. projecting obstacle trajectories or braking distance envelopes) and synthesizes a [`TacticalPrior`](file:///d:/jev-cpu/scpu/system2.py#L19-L27) down to System 1. Jev executes the conditioned reflexes without having to simulate futures on the clock.

---

## 2. Directory Structure

- [`scpu/types.py`](file:///d:/jev-cpu/scpu/types.py): Core data models ([`SemanticInstruction`](file:///d:/jev-cpu/scpu/types.py#L24-L30), [`HardwareSignal`](file:///d:/jev-cpu/scpu/types.py#L32-L39), [`DecodedOperation`](file:///d:/jev-cpu/scpu/types.py#L41-L52), [`ExecutionResult`](file:///d:/jev-cpu/scpu/types.py#L54-L63)).
- [`scpu/registers.py`](file:///d:/jev-cpu/scpu/registers.py): Hardware register file (`R0..R7`, sensor telemetry `S0..S7`, output lines `OUT0..OUT7`, flags).
- [`scpu/decoder.py`](file:///d:/jev-cpu/scpu/decoder.py): Base decoder interface and local [`JevSystem1Decoder`](file:///d:/jev-cpu/scpu/decoder.py#L26-L215) emulator.
- [`scpu/interlock.py`](file:///d:/jev-cpu/scpu/interlock.py): Hardware safety guardrail and confidence gating ([`SafetyInterlock`](file:///d:/jev-cpu/scpu/interlock.py#L9-L78)).
- [`scpu/bus.py`](file:///d:/jev-cpu/scpu/bus.py): Actuator bus, PWM timers, and digital pin controller ([`HardwareBus`](file:///d:/jev-cpu/scpu/bus.py#L9-L38)).
- [`scpu/cpu.py`](file:///d:/jev-cpu/scpu/cpu.py): Execution pipeline ([`SemanticCPU`](file:///d:/jev-cpu/scpu/cpu.py#L14-L148)) running Fetch $\to$ Decode $\to$ Guardrail $\to$ Execute $\to$ Writeback.
- [`scpu/system2.py`](file:///d:/jev-cpu/scpu/system2.py): System-2 Deliberative Planner & Scenario Simulator ([`System2ScenarioSimulator`](file:///d:/jev-cpu/scpu/system2.py#L29-L113)).
- [`scpu/driving.py`](file:///d:/jev-cpu/scpu/driving.py): Autonomous vehicle second-nature driving reflexes and adaptive headway control ([`DrivingReflexDecoder`](file:///d:/jev-cpu/scpu/driving.py#L25-L127)).
- [`scpu/adapters.py`](file:///d:/jev-cpu/scpu/adapters.py): Live network adapters for TypeSafe Jev API and System-2 Reasoning LLMs ([`LiveTypeSafeJevDecoder`](file:///d:/jev-cpu/scpu/adapters.py#L17-L113), [`LiveLLMSystem2Planner`](file:///d:/jev-cpu/scpu/adapters.py#L116-L192)).
- [`tests/`](file:///d:/jev-cpu/tests/): Automated test suite (30 passing tests).

---

## 3. How to Connect to Live Jev & Reasoning LLMs

The architecture uses an abstract interface: [`BaseSemanticDecoder`](file:///d:/jev-cpu/scpu/decoder.py#L12-L23). You can switch between offline deterministic emulation and live cloud APIs with a single configuration parameter.

### Step 1: Configure Environment Variables

```bash
# TypeSafe Jev API Configuration (System-1 Decision Core)
export TYPESAFE_API_KEY="your_typesafe_jev_key"
export TYPESAFE_ENDPOINT="https://api.typesafe.ai/v1/decide"

# Reasoning LLM Configuration (System-2 Scenario Planner)
export LLM_API_KEY="your_openai_or_gemini_or_anthropic_key"
```

### Step 2: Instantiating the Live Pipeline in Python

```python
from scpu.cpu import SemanticCPU
from scpu.adapters import LiveTypeSafeJevDecoder, LiveLLMSystem2Planner
from scpu.interlock import SafetyInterlock

# 1. Instantiate the live TypeSafe Jev decoder (System 1)
jev_decoder = LiveTypeSafeJevDecoder(
    api_key="your_typesafe_jev_key",
    endpoint="https://api.typesafe.ai/v1/decide",
    timeout_seconds=0.25  # 250ms deadline
)

# 2. Instantiate the live Reasoning LLM planner (System 2)
system2_planner = LiveLLMSystem2Planner(
    api_key="your_llm_key",
    endpoint="https://api.openai.com/v1/chat/completions",
    model="gpt-4o"  # Or your preferred reasoning model
)

# 3. Instantiate the sCPU with Safety Interlocks
cpu = SemanticCPU(
    decoder=jev_decoder,
    system2_planner=system2_planner,
    interlock=SafetyInterlock(min_confidence=0.80),
    enable_system2_supervision=True,
)

# 4. Load a natural language program and run
cpu.load_program([
    "maintain lane and match lead vehicle speed",
    "if obstacle < 20cm, apply regenerative brake smoothly",
    "emergency stop immediately",
])

# Run CPU cycles
results = cpu.run()
```

### Step 3: Payload Schema Sent to TypeSafe Jev

[`LiveTypeSafeJevDecoder`](file:///d:/jev-cpu/scpu/adapters.py#L17-L113) sends the following structured decision request to the Jev endpoint:

```json
{
  "instruction": "maintain lane and cruise",
  "telemetry": {
    "S0": 65.0,
    "S1": 100.0,
    "S2": -0.15
  },
  "flags": {
    "FAULT": false,
    "EMERGENCY_STOP": false
  },
  "constraints": {
    "max_throttle": 0.35,
    "brake_bias": 0.4
  },
  "schema": {
    "intent": "string",
    "signals": "list<{pin: string, type: string, value: float}>",
    "confidence": "float"
  }
}
```

And expects Jev's typed single-pass response:

```json
{
  "intent": "ADAPTIVE_HEADWAY_REFLEX",
  "confidence": 0.96,
  "signals": [
    {"pin": "STEERING", "type": "ANALOG_VOLTAGE", "value": 2.25},
    {"pin": "THROTTLE", "type": "PWM", "value": 0.35},
    {"pin": "BRAKE", "type": "PWM", "value": 0.0}
  ],
  "halt": false
}
```

If network latency exceeds the deadline or an error occurs, [`LiveTypeSafeJevDecoder`](file:///d:/jev-cpu/scpu/adapters.py#L17-L113) automatically degrades confidence to $0.0$, causing [`SafetyInterlock`](file:///d:/jev-cpu/scpu/interlock.py#L9-L78) to trigger a safe hold rather than allowing uncontrolled hardware movement.

---

## 4. Running Tests and Demos

### Run the Test Suite
The repository includes 30 unit and integration tests verifying register banks, decoders, interlocks, dual-process escalation, driving reflexes, and live network adapters:

```bash
python -m pytest -v
```

### Run Interactive Demos
1. **Robotic Actuation Reflex:**
   ```bash
   python demo.py
   ```
2. **Heterogeneous System-1 (Jev) + System-2 Scenario Simulation:**
   ```bash
   python demo_system2.py
   ```
3. **Autonomous Vehicle Second-Nature Driving:**
   ```bash
   python demo_driving.py
   ```
