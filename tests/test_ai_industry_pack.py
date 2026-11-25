import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_jsonl(rel):
    return [
        json.loads(line)
        for line in (ROOT / rel).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_every_far_constraint_has_a_source():
    rows = read_jsonl("data/domains/ai_compliance.jsonl")
    assert len(rows) >= 6
    for row in rows:
        assert row["source"].strip()
        assert isinstance(row["verified"], bool)


def test_far_constraints_cite_article_numbers():
    # 复核过的条目必须写清条号,否则等于没复核
    rows = read_jsonl("data/domains/ai_compliance.jsonl")
    for row in rows:
        if row["verified"]:
            assert "第" in row["source"] and "条" in row["source"], row["source"]


def test_known_products_have_specific_gaps():
    rows = read_jsonl("data/projects/ai_industry_products.jsonl")
    assert len(rows) >= 8
    for row in rows:
        assert len(row["gap"]) >= 10
        assert "体验不好" not in row["gap"]
        assert row["source"].strip()


def test_ai_industry_pack_is_registered():
    packs = json.loads((ROOT / "data/packs/index.json").read_text(encoding="utf-8"))["packs"]
    entry = next(p for p in packs if p["id"] == "ai-industry")
    assert entry["known"].endswith("ai_industry_products.jsonl")
    assert entry["evidence"].endswith("ai_industry.json")


def test_near_constraints_carry_sources():
    rows = read_jsonl("data/domains/ai_industry.jsonl")
    assert len(rows) >= 10
    for row in rows:
        assert row["source"].strip()
        assert isinstance(row["verified"], bool)


def test_evidence_entries_use_mechanism_ids_that_exist():
    from collider.mechanisms import MECHANISMS

    known_ids = {m.id for m in MECHANISMS}
    data = json.loads((ROOT / "data/evidence/ai_industry.json").read_text(encoding="utf-8"))
    for entry in data["entries"]:
        assert entry["mechanisms"], entry
        for mechanism in entry["mechanisms"]:
            assert mechanism in known_ids, mechanism
        assert len(entry["blocker"]) >= 10


def test_every_pack_points_at_files_that_exist():
    packs = json.loads((ROOT / "data/packs/index.json").read_text(encoding="utf-8"))["packs"]
    for pack in packs:
        for key in ("near", "far", "known", "evidence"):
            value = pack.get(key)
            if value:
                assert (ROOT / value).exists(), f"{pack['id']}.{key} -> {value}"
