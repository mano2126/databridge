"""
tests/test_mapping_seed.py — 타입 매핑 seed-defaults 엔드포인트 테스트
v10 #21
"""
import pytest


@pytest.fixture
def mapping(tmp_data_dir):
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("app.api.routes.mapping"):
            del sys.modules[mod]
    from app.api.routes import mapping as m
    yield m


class TestInitialSeed:
    def test_builtin_defaults_not_empty(self, mapping):
        assert len(mapping._BUILTIN_DEFAULTS) > 100, "카탈로그가 충분히 크다"
        # 샘플 검증
        sample = mapping._BUILTIN_DEFAULTS[0]
        assert "src_db" in sample
        assert "tgt_db" in sample
        assert "src_type" in sample
        assert "tgt_type" in sample

    def test_empty_store_gets_seeded(self, mapping):
        assert len(mapping._rules) == len(mapping._BUILTIN_DEFAULTS)


class TestSeedEndpoint:
    def test_seed_skip_when_all_exist(self, mapping):
        result = mapping.seed_defaults(overwrite=False)
        # 초기 시드로 이미 283개 들어있음
        assert result["inserted"] == 0
        assert result["skipped"] == len(mapping._BUILTIN_DEFAULTS)
        assert result["total_after"] == len(mapping._BUILTIN_DEFAULTS)

    def test_seed_adds_missing(self, mapping):
        # 전부 삭제 후 10개만 남기기
        all_rules = list(mapping._rules.all().items())
        for rid, _ in all_rules[10:]:
            mapping._rules.delete(rid)
        assert len(mapping._rules) == 10

        result = mapping.seed_defaults(overwrite=False)
        assert result["inserted"] + 10 == len(mapping._BUILTIN_DEFAULTS)
        assert result["total_after"] == len(mapping._BUILTIN_DEFAULTS)

    def test_seed_preserves_custom_flag(self, mapping):
        # 한 규칙을 custom=True 로 표시
        first_rule = next(iter(mapping._rules.values()))
        rid = first_rule["id"]
        first_rule["custom"] = True
        first_rule["note"] = "내가 수정한 노트"
        mapping._rules.set(rid, first_rule)

        result = mapping.seed_defaults(overwrite=True)
        assert result["overwritten"] >= 1
        # custom 플래그 보존 확인
        after = mapping._rules.get(rid)
        assert after["custom"] is True
        # note 는 빌트인 값으로 교체됨 (정상)


class TestCRUDEndpoints:
    def test_list_rules_returns_all(self, mapping):
        rules = mapping.list_rules()
        assert len(rules) == len(mapping._BUILTIN_DEFAULTS)

    def test_filter_by_src_db(self, mapping):
        rules = mapping.list_rules(src_db="mysql")
        assert all(r["src_db"] == "mysql" for r in rules)
        assert len(rules) > 0

    def test_create_rule(self, mapping):
        before = len(mapping._rules)
        new_rule = mapping.create_rule({
            "src_db": "mysql", "tgt_db": "mssql",
            "src_type": "TEST_TYPE", "tgt_type": "TEST_TYPE_TGT",
            "category": "테스트", "note": "", "warning": False,
        })
        assert new_rule["custom"] is True
        assert len(mapping._rules) == before + 1

    def test_update_rule(self, mapping):
        first = next(iter(mapping._rules.values()))
        rid = first["id"]
        updated = mapping.update_rule(rid, {"note": "updated"})
        assert updated["note"] == "updated"
        assert updated["id"] == rid

    def test_update_nonexistent_raises(self, mapping):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            mapping.update_rule("nonexistent_id", {"note": "x"})
        assert exc.value.status_code == 404

    def test_delete_rule(self, mapping):
        first = next(iter(mapping._rules.values()))
        rid = first["id"]
        before = len(mapping._rules)
        mapping.delete_rule(rid)
        assert len(mapping._rules) == before - 1

    def test_delete_nonexistent_raises(self, mapping):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            mapping.delete_rule("nope")
        assert exc.value.status_code == 404


class TestStatsAndCategories:
    def test_stats_structure(self, mapping):
        s = mapping.get_stats()
        assert "total" in s
        assert "pairs" in s
        assert "by_category" in s
        assert s["total"] > 0

    def test_categories_sorted(self, mapping):
        cats = mapping.get_categories()
        assert len(cats) > 0
        assert cats == sorted(cats)
