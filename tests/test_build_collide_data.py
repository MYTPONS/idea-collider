from train.build_collide_data import build, load_experiments

FOUR = ("exp-01", "exp-02", "exp-03", "exp-04")


def test_all_four_experiments_parse():
    experiments = load_experiments(FOUR)
    assert len(experiments) == 4
    assert {experiment["name"] for experiment in experiments} == {
        "exp-01",
        "exp-02",
        "exp-03",
        "exp-04",
    }
    for experiment in experiments:
        assert experiment["a"]
        assert experiment["b"]


def test_positive_rows_cover_every_table_row():
    _, counts = build(load_experiments(FOUR))
    assert counts == {"exp-01": 9, "exp-02": 7, "exp-03": 5, "exp-04": 7}


def test_build_repeats_positive_rows():
    rows, _ = build(load_experiments(FOUR))
    positives = sum(1 for row in rows if row["output"]["interaction"])
    assert positives == 280
    assert len(rows) == 280
    for row in rows:
        assert set(row["input"]) == {"near", "far"}
        assert row["source"].startswith("docs/experiments/")
        assert row["output"]["form"]
        assert row["output"]["must"]
