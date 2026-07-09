from pathlib import Path


def test_cross_project_handoff_is_not_active_roadmap() -> None:
    root = Path(__file__).resolve().parents[1]
    planning_doc = (root / "docs" / "planning" / "PRE_IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )
    assert "Inactive Historical Reference" in planning_doc
    assert "must not be used as this project's roadmap" in planning_doc
