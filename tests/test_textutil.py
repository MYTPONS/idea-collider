from collider.textutil import first_json_object, jaccard, normalize_text


def test_first_json_object_plain():
    assert first_json_object('{"a": 1}') == {"a": 1}


def test_first_json_object_ignores_prefix_and_fence():
    raw = "```json\n{\"label\":\"pain\",\"why\":\"x\"}\n```"
    assert first_json_object(raw) == {"label": "pain", "why": "x"}


def test_first_json_object_returns_none():
    assert first_json_object("没有 JSON") is None


def test_jaccard_identical_and_disjoint():
    assert jaccard("上游随时失效", "上游随时失效") == 1.0
    assert jaccard("上游随时失效", "殡葬时间窗刚性") == 0.0


def test_normalize_strips_punctuation_and_space():
    assert normalize_text("上游 失效，账号。") == "上游失效账号"
