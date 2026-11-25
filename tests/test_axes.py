from collider.axes import axis_report
from collider.schema import GateResult, Statement


def make(text: str, axis: str | None, label: str = "constraint", error: str | None = None):
    return GateResult(
        statement=Statement(id="x", text=text),
        label=label,
        axis=axis,
        why="",
        error=error,
    )


def test_single_axis_triggers_two_warnings():
    report = axis_report([make("a", "trust"), make("b", "trust")])
    assert report["constraints"] == 2
    assert len(report["warnings"]) == 2


def test_three_axes_balanced_has_no_warning():
    report = axis_report([make("a", "trust"), make("b", "cost"), make("c", "time")])
    assert report["constraints"] == 3
    assert report["warnings"] == []


def test_rejected_results_do_not_count():
    report = axis_report(
        [make("a", "trust"), make("b", None, label="pain"), make("c", None, error="bad_label")]
    )
    assert report["constraints"] == 1
