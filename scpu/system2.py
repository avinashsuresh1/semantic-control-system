"""
System-2 Deliberative Planner and Scenario Simulator.
Provides deliberative scenario rollouts, risk forecasting, and tactical priors
to condition the fast System-1 (Jev) decision engine.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SimulatedOutcome:
    """Outcome of a simulated scenario branch."""
    scenario_name: str
    action_hypothesis: str
    projected_risk: float  # [0.0 = safe, 1.0 = catastrophic]
    projected_state: Dict[str, float]
    rationale: str


@dataclass
class TacticalPrior:
    """
    Context synthesized by System-2 after mental simulation of scenarios.
    Fed into Jev to condition its System-1 decisions without slowing down cycle time.
    """
    mode: str = "NORMAL"  # e.g., CAUTIOUS, AGGRESSIVE, EMERGENCY_AVOIDANCE, NOMINAL
    risk_factor: float = 0.0
    recommended_directive: str = ""
    contingency_action: str = ""
    active_constraints: Dict[str, Any] = field(default_factory=dict)


class System2ScenarioSimulator:
    """
    Simulates hypothetical scenarios ('mental simulation') using an internal world model.
    Synthesizes tactical priors and instructions for System-1 (Jev).
    """

    def __init__(self) -> None:
        pass

    def simulate_scenarios(
        self,
        current_sensors: Dict[str, float],
        mission_goal: str,
    ) -> List[SimulatedOutcome]:
        """
        Runs counterfactual scenario branches.
        For example: evaluates keeping current speed vs braking vs evasive steering.
        """
        outcomes: List[SimulatedOutcome] = []
        distance = current_sensors.get("S0", 100.0)
        speed = current_sensors.get("OUT0", 0.5)

        # Branch 1: Maintain current velocity
        stopping_distance = (speed * 50.0)
        risk_maintain = 0.95 if stopping_distance >= distance else (speed * 0.3)
        outcomes.append(
            SimulatedOutcome(
                scenario_name="maintain_trajectory",
                action_hypothesis=f"Keep throttle at {speed:.2f}",
                projected_risk=min(1.0, risk_maintain),
                projected_state={"projected_distance": max(0.0, distance - stopping_distance)},
                rationale="Fast progress but high risk if obstacle persists.",
            )
        )

        # Branch 2: Preemptive defensive deceleration
        risk_slow = 0.10 if distance > 10.0 else 0.40
        outcomes.append(
            SimulatedOutcome(
                scenario_name="preemptive_slowdown",
                action_hypothesis="Reduce throttle to 0.25 and prime brakes",
                projected_risk=risk_slow,
                projected_state={"projected_distance": distance},
                rationale="Significantly reduces kinetic hazard at minor delay cost.",
            )
        )

        # Branch 3: Hard evasive stop
        outcomes.append(
            SimulatedOutcome(
                scenario_name="immediate_stop",
                action_hypothesis="Emergency brake clamp",
                projected_risk=0.05,
                projected_state={"projected_distance": distance},
                rationale="Guaranteed collision avoidance, but halts mission progress.",
            )
        )

        return outcomes

    def deliberate(
        self,
        current_sensors: Dict[str, float],
        mission_goal: str,
    ) -> TacticalPrior:
        """
        Evaluates simulated outcomes and outputs a synthesized TacticalPrior
        to condition System-1 Jev execution.
        """
        simulations = self.simulate_scenarios(current_sensors, mission_goal)
        distance = current_sensors.get("S0", 100.0)

        # Select safest strategy that aligns with mission
        if distance < 25.0:
            best = [s for s in simulations if s.scenario_name == "immediate_stop"][0]
            return TacticalPrior(
                mode="EMERGENCY_AVOIDANCE",
                risk_factor=best.projected_risk,
                recommended_directive="emergency stop immediately to prevent collision",
                contingency_action="lock_brakes",
                active_constraints={"max_throttle": 0.0, "brake_override": 1.0},
            )
        elif distance < 50.0:
            best = [s for s in simulations if s.scenario_name == "preemptive_slowdown"][0]
            return TacticalPrior(
                mode="CAUTIOUS",
                risk_factor=best.projected_risk,
                recommended_directive="cautiously decelerate and maintain safety margin",
                contingency_action="prep_brakes",
                active_constraints={"max_throttle": 0.35, "brake_bias": 0.4},
            )
        else:
            return TacticalPrior(
                mode="NOMINAL",
                risk_factor=0.05,
                recommended_directive="maintain cruise trajectory towards target",
                contingency_action="none",
                active_constraints={"max_throttle": 1.0, "brake_bias": 0.0},
            )
