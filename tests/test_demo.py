"""
Test for demo script execution.
"""

from demo import run_demo
from demo_driving import run_driving_demo
from demo_system2 import run_system2_demo


def test_demo_execution_runs_without_errors(capsys):
    run_demo()
    captured = capsys.readouterr()
    assert "SEMANTIC CONTROL SYSTEM (SCS) WITH SYSTEM-1 JEV DECODER" in captured.out
    assert "Cycle" in captured.out
    assert "Execution complete." in captured.out


def test_demo_system2_runs_without_errors(capsys):
    run_system2_demo()
    captured = capsys.readouterr()
    assert "HETEROGENEOUS SEMANTIC CONTROL SYSTEM: SYSTEM-1 (JEV) + SYSTEM-2" in captured.out
    assert "Scenario Hypothesis" in captured.out
    assert "Heterogeneous Dual-Core Execution Complete." in captured.out


def test_demo_driving_runs_without_errors(capsys):
    run_driving_demo()
    captured = capsys.readouterr()
    assert "SEMANTIC CONTROL SYSTEM — AUTONOMOUS VEHICLE REFLEX CO-PROCESSOR" in captured.out
    assert "Highway Cruise with Minor Left Lane Drift" in captured.out
    assert "Autonomous Driving Reflex Demonstration Complete." in captured.out
