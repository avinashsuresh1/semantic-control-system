"""
Test documentation files.
"""

from pathlib import Path


def test_readme_exists_and_contains_architecture_sections():
    readme_path = Path("d:/jev-cpu/README.md")
    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8")
    assert "Semantic Control Systems (SCS)" in content
    assert "System-1 (Jev)" in content
    assert "How to Connect to Live Jev & Reasoning LLMs" in content
    assert "Hardware Safety Interlock" in content
