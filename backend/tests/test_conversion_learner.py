"""
tests/test_conversion_learner.py — 변환 KB 자동 학습 엔진 테스트
v10 #21
"""
import pytest


SAMPLE_SRC_DDL = """CREATE TABLE [dbo].[Customer] (
    [cus_id] INT IDENTITY(1,1) NOT NULL,
    [cus_name] NVARCHAR(100) NOT NULL,
    [balance] MONEY DEFAULT 0,
    [created_at] DATETIME NOT NULL,
    [is_vip] BIT DEFAULT 0,
    [memo] NVARCHAR(MAX)
)"""

SAMPLE_TGT_STMT = """CREATE TABLE IF NOT EXISTS `Customer` (
    `cus_id` INT AUTO_INCREMENT NOT NULL,
    `cus_name` VARCHAR(100) CHARACTER SET utf8mb4 NOT NULL,
    `balance` DECIMAL(19,4) DEFAULT 0,
    `created_at` DATETIME(3) NOT NULL,
    `is_vip` TINYINT(1) DEFAULT 0,
    `memo` TEXT,
    PRIMARY KEY (`cus_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"""


class TestTypePairExtraction:
    def test_extract_basic_type_pairs(self, learner_clean):
        pairs = learner_clean._extract_type_pairs(SAMPLE_SRC_DDL, [SAMPLE_TGT_STMT])
        types = {(s, t) for s, t in pairs}
        assert ("NVARCHAR", "VARCHAR") in types
        assert ("MONEY", "DECIMAL") in types
        assert ("BIT", "TINYINT") in types
        assert ("NVARCHAR", "TEXT") in types
        # DATETIME 이 DATETIME(3) 로 갔으므로 정규화 후 DATETIME → DATETIME (동일 → 제외됨)
        # INT IDENTITY → INT AUTO_INCREMENT 는 단일 토큰이 아니라 파서가 안 잡음 (정상)

    def test_extract_returns_empty_for_bad_ddl(self, learner_clean):
        assert learner_clean._extract_type_pairs("", [SAMPLE_TGT_STMT]) == []
        assert learner_clean._extract_type_pairs(SAMPLE_SRC_DDL, []) == []
        assert learner_clean._extract_type_pairs(SAMPLE_SRC_DDL, ["garbage"]) == []

    def test_normalize_type(self, learner_clean):
        n = learner_clean._norm_type
        assert n("VARCHAR(100)") == "VARCHAR"
        assert n("DECIMAL(19,4)") == "DECIMAL"
        assert n("  nvarchar  ") == "NVARCHAR"
        assert n("") == ""


class TestLearnFromAIConversion:
    def test_first_learn_creates_new_rules(self, learner_clean):
        result = {"statements": [SAMPLE_TGT_STMT], "notes": ""}
        summary = learner_clean.learn_from_ai_conversion(
            SAMPLE_SRC_DDL, result, "TABLE", "Customer", "mssql", "mysql", "job_1"
        )
        assert summary["new_type_rules"] >= 4
        assert summary["updated"] == 0

    def test_duplicate_learn_increments_confidence(self, learner_clean):
        result = {"statements": [SAMPLE_TGT_STMT], "notes": ""}
        learner_clean.learn_from_ai_conversion(
            SAMPLE_SRC_DDL, result, "TABLE", "Customer", "mssql", "mysql", "job_1"
        )
        s2 = learner_clean.learn_from_ai_conversion(
            SAMPLE_SRC_DDL, result, "TABLE", "Customer", "mssql", "mysql", "job_2"
        )
        assert s2["new_type_rules"] == 0
        assert s2["updated"] >= 4

    def test_auto_promote_at_threshold(self, learner_clean):
        """confidence ≥ PROMOTE_THRESHOLD(3) 일 때 shadow → active"""
        result = {"statements": [SAMPLE_TGT_STMT], "notes": ""}
        for i in range(learner_clean.PROMOTE_THRESHOLD):
            learner_clean.learn_from_ai_conversion(
                SAMPLE_SRC_DDL, result, "TABLE", "Customer", "mssql", "mysql", f"job_{i}"
            )
        rules = [r for r in learner_clean._type_rules.values()
                 if r.get("source") == "ai_learned"]
        assert len(rules) >= 4
        active = [r for r in rules if r.get("status") == "active"]
        assert len(active) >= 4, "3회 누적 후 자동 active 승격 기대"

    def test_empty_input_safe(self, learner_clean):
        r = learner_clean.learn_from_ai_conversion(
            "", {}, "TABLE", "x", "mssql", "mysql"
        )
        assert r == {"new_type_rules": 0, "new_obj_rules": 0, "updated": 0}

    def test_none_input_safe(self, learner_clean):
        r = learner_clean.learn_from_ai_conversion(
            None, None, "TABLE", "x", "mssql", "mysql"
        )
        assert r["new_type_rules"] == 0

    def test_object_pattern_extraction(self, learner_clean):
        src_proc = """CREATE PROCEDURE sp_test AS
        SELECT GETDATE(), ISNULL(@x, 0), NEWID()
        WHERE SYSTEM_USER = 'admin'"""
        tgt_proc = ["""CREATE PROCEDURE sp_test() BEGIN
        SELECT NOW(), IFNULL(v_x, 0), UUID()
        WHERE CURRENT_USER() = 'admin'; END"""]
        hits = learner_clean._extract_obj_patterns(src_proc, tgt_proc)
        names = {h["src_syntax"] for h in hits}
        assert "GETDATE()" in names
        assert "NEWID()" in names


class TestCoverageEstimation:
    def test_coverage_empty_db(self, learner_clean):
        # 안전 가드: 이 테스트는 빈 상태 가정 — 명시적으로 확인
        assert len(learner_clean._type_rules) == 0, \
            "fixture 격리 실패 — _type_rules 에 이전 테스트 데이터 남음"
        cov = learner_clean.estimate_local_coverage(SAMPLE_SRC_DDL, "mssql", "mysql")
        assert cov["total"] >= 5
        assert cov["covered"] == 0
        assert cov["coverage"] == 0.0

    def test_coverage_after_learning(self, learner_clean):
        # 3회 학습해서 active 로 승격시킴
        result = {"statements": [SAMPLE_TGT_STMT], "notes": ""}
        for i in range(3):
            learner_clean.learn_from_ai_conversion(
                SAMPLE_SRC_DDL, result, "TABLE", "Customer", "mssql", "mysql", f"j{i}"
            )
        cov = learner_clean.estimate_local_coverage(SAMPLE_SRC_DDL, "mssql", "mysql")
        assert cov["coverage"] > 0.5


class TestMetricsAndOverview:
    def test_metrics_accumulate(self, learner_clean):
        result = {"statements": [SAMPLE_TGT_STMT], "notes": ""}
        learner_clean.learn_from_ai_conversion(
            SAMPLE_SRC_DDL, result, "TABLE", "C", "mssql", "mysql", "j1"
        )
        m = learner_clean.get_metrics(days=7)
        assert m["summary"]["ai_calls"] >= 1
        assert m["summary"]["patterns_learned"] >= 4

    def test_overview_reflects_source(self, learner_clean):
        result = {"statements": [SAMPLE_TGT_STMT], "notes": ""}
        learner_clean.learn_from_ai_conversion(
            SAMPLE_SRC_DDL, result, "TABLE", "C", "mssql", "mysql", "j1"
        )
        ov = learner_clean.get_kb_overview()
        assert ov["type_mapping"]["ai_learned"] >= 4
        assert ov["type_mapping"]["manual"] == 0  # 빈 DB 였으므로

    def test_set_rule_status(self, learner_clean):
        result = {"statements": [SAMPLE_TGT_STMT], "notes": ""}
        learner_clean.learn_from_ai_conversion(
            SAMPLE_SRC_DDL, result, "TABLE", "C", "mssql", "mysql", "j1"
        )
        rules = list(learner_clean._type_rules.values())
        assert rules
        rid = rules[0]["id"]
        assert learner_clean.set_rule_status("type", rid, "rejected") is True
        assert learner_clean._type_rules.get(rid)["status"] == "rejected"
        # 잘못된 status
        assert learner_clean.set_rule_status("type", rid, "garbage") is False
        # 없는 rule
        assert learner_clean.set_rule_status("type", "nonexistent", "active") is False
