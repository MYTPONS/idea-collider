from collider.collide import collide_pairs
from collider.schema import Statement


class FakeModel:
    def __init__(self, interaction: bool = True, form: str = "同一个形态"):
        self.interaction = interaction
        self.form = form

    def collide(self, near_text: str, far_text: str) -> dict:
        return {
            "interaction": self.interaction,
            "must": "两边同时满足",
            "form": self.form,
            "why": "fake",
            "raw": "",
            "error": None,
        }


def statements(prefix: str, count: int) -> list[Statement]:
    return [Statement(id=f"{prefix}{i}", text=f"{prefix}{i} 文本") for i in range(count)]


def test_duplicate_forms_collapse_to_one_candidate():
    candidates, stats = collide_pairs(statements("a", 2), statements("b", 2), FakeModel())
    assert stats.pairs == 4
    assert len(candidates) == 1
    assert stats.deduped == 3


def test_interaction_flag_does_not_drop_a_form():
    candidates, stats = collide_pairs(
        statements("a", 2), statements("b", 2), FakeModel(interaction=False)
    )
    assert len(candidates) == 1
    assert stats.generated == 4


def test_same_form_with_different_must_still_dedupes():
    class Varying(FakeModel):
        def collide(self, near_text: str, far_text: str) -> dict:
            out = super().collide(near_text, far_text)
            out["must"] = far_text
            return out

    candidates, stats = collide_pairs(statements("a", 2), statements("b", 2), Varying())
    assert len(candidates) == 1
    assert stats.deduped == 3


def test_limit_caps_pairs():
    _, stats = collide_pairs(statements("a", 2), statements("b", 2), FakeModel(), limit=3)
    assert stats.pairs == 3
