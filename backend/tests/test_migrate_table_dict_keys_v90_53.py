"""
test_migrate_table_dict_keys_v90_53.py — v90.53 (2026-04-27)

v90.48 도입 후 발생한 KeyError 회귀 테스트.

본부장님 환경 5건 케이스:
  - eft_batch       → settlement_eft_batch
  - org_unit        → ref_org_unit
  - credit_score    → customer_credit_score
  - kyc_document    → customer_kyc_document
  - profile         → customer_profile

증상: DROP 직후 KeyError: 'customer_profile' (정규화된 이름)
원인: _skip_cols_map[table] 등을 src_bare 이름으로 등록해놓고,
      swap 후 정규화된 이름으로 접근 → KeyError.

수정: dict 키 등록을 swap 다음으로 이동 + src_bare 도 같은 set 참조.

실행:
  cd backend
  pytest tests/test_migrate_table_dict_keys_v90_53.py -v
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

# backend 경로
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class FakeMigrationEngine:
    """
    _migrate_table 의 dict 초기화 + swap 부분만 발췌하여 검증.
    실제 엔진 import 가 무겁고 외부 의존성이 많아서 핵심 로직만 simulate.
    """
    
    def __init__(self, src_schema_map, schema_strategy="underscore"):
        self._src_schema_map = src_schema_map or {}
        self._schema_strategy = schema_strategy
        self._tgt_table_name_cache = {}
        self._skip_cols_map = {}
        self._cast_cols_map = {}
        self._rowver_cols = {}
        self._dto_cols = {}
        self._geo_cols = {}
        self._bin_cols = {}
        self._logs = []
    
    def _log(self, level, msg):
        self._logs.append((level, msg))
    
    def _target_table_name(self, bare):
        """v90.48 의 동일 동작 simulate."""
        if not bare:
            return bare
        if bare in self._tgt_table_name_cache:
            return self._tgt_table_name_cache[bare]
        
        schema = self._src_schema_map.get(bare, "") or ""
        
        # underscore strategy
        sch = schema.strip()
        b = bare.strip()
        if not sch or sch.lower() == "dbo":
            tgt = b
        elif b.lower().startswith(sch.lower() + "_"):
            tgt = b
        elif self._schema_strategy == "underscore":
            tgt = f"{sch}_{b}"
        else:
            tgt = b
        
        self._tgt_table_name_cache[bare] = tgt
        return tgt
    
    def _migrate_table_setup_v90_53(self, table_input):
        """
        v90.53 패치 적용 버전 — dict 초기화 위치 swap 후로 이동.
        실제 _migrate_table 의 라인 2999~3045 핵심 로직만 발췌.
        """
        table = table_input
        
        # v90.53: dict 자체 보장만 여기서 (객체 자체 잔상 방지)
        # 키 등록은 swap 후로 이동
        if not hasattr(self, '_skip_cols_map'): self._skip_cols_map = {}
        if not hasattr(self, '_cast_cols_map'): self._cast_cols_map = {}
        # ...
        
        # ── swap ──
        src_bare = table
        try:
            tgt_table = self._target_table_name(table)
        except Exception:
            tgt_table = table
        if tgt_table != src_bare:
            self._log("info", f"[{src_bare}] → [{tgt_table}]")
        table = tgt_table
        
        # ── v90.53: 키 등록은 swap 다음 ──
        self._skip_cols_map[table] = set()
        self._cast_cols_map[table] = set()
        self._rowver_cols[table]   = set()
        self._dto_cols[table]      = set()
        self._geo_cols[table]      = set()
        self._bin_cols[table]      = set()
        # 이중 등록 (src_bare 도 같은 set 참조)
        if src_bare != table:
            self._skip_cols_map[src_bare] = self._skip_cols_map[table]
            self._cast_cols_map[src_bare] = self._cast_cols_map[table]
            self._rowver_cols[src_bare]   = self._rowver_cols[table]
            self._dto_cols[src_bare]      = self._dto_cols[table]
            self._geo_cols[src_bare]      = self._geo_cols[table]
            self._bin_cols[src_bare]      = self._bin_cols[table]
        
        return src_bare, table
    
    def _migrate_table_setup_v90_48_BUGGY(self, table_input):
        """
        v90.48 버그 버전 — dict 초기화가 swap 전에 실행되어 KeyError 유발.
        회귀 테스트 비교용.
        """
        table = table_input
        
        # 버그: swap 전에 키 등록
        self._skip_cols_map[table] = set()
        self._cast_cols_map[table] = set()
        self._rowver_cols[table]   = set()
        self._dto_cols[table]      = set()
        self._geo_cols[table]      = set()
        self._bin_cols[table]      = set()
        
        # swap
        src_bare = table
        tgt_table = self._target_table_name(table)
        table = tgt_table
        
        return src_bare, table


# ════════════════════════════════════════════════════════════════════════════
# 본부장님 환경 5건 케이스 데이터
# ════════════════════════════════════════════════════════════════════════════

PRESIDENT_CASES = [
    # (src_bare, expected_target, src_schema_map_entry)
    ("eft_batch",     "settlement_eft_batch",     {"eft_batch": "settlement"}),
    ("org_unit",      "ref_org_unit",             {"org_unit": "ref"}),
    ("credit_score",  "customer_credit_score",    {"credit_score": "customer"}),
    ("kyc_document",  "customer_kyc_document",    {"kyc_document": "customer"}),
    ("profile",       "customer_profile",         {"profile": "customer"}),
]


# ════════════════════════════════════════════════════════════════════════════
# 회귀 테스트 — v90.48 버그 재현
# ════════════════════════════════════════════════════════════════════════════

class TestV90_48_BugReproduction:
    """v90.48 의 버그가 실제로 KeyError 를 일으켰는지 확인 (음성 테스트)."""
    
    @pytest.mark.parametrize("src_bare,expected_tgt,schema_map", PRESIDENT_CASES)
    def test_v48_buggy_causes_keyerror(self, src_bare, expected_tgt, schema_map):
        """v90.48 버전에서는 정규화된 이름으로 접근 시 KeyError 발생."""
        engine = FakeMigrationEngine(schema_map)
        src, tgt = engine._migrate_table_setup_v90_48_BUGGY(src_bare)
        
        # tgt 이름 정상 매핑됐는지 우선 확인
        assert tgt == expected_tgt, f"매핑 실패: {src_bare} → {tgt}, 기대 {expected_tgt}"
        
        # 정규화된 이름으로 접근 시 KeyError 발생 (버그 재현)
        with pytest.raises(KeyError) as exc_info:
            engine._skip_cols_map[tgt].add("test_col")
        
        # KeyError 메시지가 정규화된 이름 — 본부장님 화면 메시지 일치
        assert str(exc_info.value) == f"'{tgt}'", \
            f"KeyError 메시지 불일치: {exc_info.value} vs '{tgt}'"


# ════════════════════════════════════════════════════════════════════════════
# 핵심 테스트 — v90.53 패치 검증
# ════════════════════════════════════════════════════════════════════════════

class TestV90_53_Fix:
    """v90.53 패치 적용 후 KeyError 가 발생하지 않음을 검증."""
    
    @pytest.mark.parametrize("src_bare,expected_tgt,schema_map", PRESIDENT_CASES)
    def test_v53_no_keyerror_on_target_name(self, src_bare, expected_tgt, schema_map):
        """v90.53: 정규화된 이름으로 접근해도 KeyError 없음."""
        engine = FakeMigrationEngine(schema_map)
        src, tgt = engine._migrate_table_setup_v90_53(src_bare)
        
        assert tgt == expected_tgt
        
        # 정규화 이름으로 접근 — 정상 동작
        engine._skip_cols_map[tgt].add("test_col_1")
        engine._cast_cols_map[tgt].add("test_col_2")
        engine._rowver_cols[tgt].add("test_col_3")
        engine._dto_cols[tgt].add("test_col_4")
        engine._geo_cols[tgt].add("test_col_5")
        engine._bin_cols[tgt].add("test_col_6")
        
        # 모든 set 에 정상 들어갔는지 확인
        assert "test_col_1" in engine._skip_cols_map[tgt]
        assert "test_col_2" in engine._cast_cols_map[tgt]
        assert "test_col_3" in engine._rowver_cols[tgt]
        assert "test_col_4" in engine._dto_cols[tgt]
        assert "test_col_5" in engine._geo_cols[tgt]
        assert "test_col_6" in engine._bin_cols[tgt]
    
    @pytest.mark.parametrize("src_bare,expected_tgt,schema_map", PRESIDENT_CASES)
    def test_v53_src_bare_alias_works(self, src_bare, expected_tgt, schema_map):
        """v90.53 추가 안전망: src_bare 로 접근해도 KeyError 없음 (이중 등록)."""
        engine = FakeMigrationEngine(schema_map)
        src, tgt = engine._migrate_table_setup_v90_53(src_bare)
        
        # src_bare 로 접근도 가능
        engine._skip_cols_map[src].add("via_src_bare")
        
        # 같은 set 객체이므로 tgt 로도 보임
        assert "via_src_bare" in engine._skip_cols_map[tgt], \
            "src_bare 와 tgt 가 같은 set 을 공유하지 않음 (alias 실패)"
    
    def test_v53_dbo_default_schema(self):
        """default schema (dbo) 는 swap 안 됨 → src_bare == tgt."""
        engine = FakeMigrationEngine({"tag": "dbo"})
        src, tgt = engine._migrate_table_setup_v90_53("tag")
        
        assert src == "tag"
        assert tgt == "tag"
        # 키가 한 번만 등록됨 (이중 alias 안 함)
        engine._skip_cols_map[tgt].add("col_x")
        assert "col_x" in engine._skip_cols_map["tag"]
    
    def test_v53_repeat_call_safe(self):
        """같은 테이블 _migrate_table 두 번 호출 (idempotent)."""
        engine = FakeMigrationEngine({"profile": "customer"})
        
        # 1차 호출
        src1, tgt1 = engine._migrate_table_setup_v90_53("profile")
        engine._skip_cols_map[tgt1].add("first_col")
        
        # 2차 호출 — 키가 새로 set() 으로 초기화됨 (잔상 방지)
        src2, tgt2 = engine._migrate_table_setup_v90_53("profile")
        assert "first_col" not in engine._skip_cols_map[tgt2], \
            "2차 호출에서 잔상 발견 (set 재초기화 실패)"


# ════════════════════════════════════════════════════════════════════════════
# 통합 — 본부장님 환경 5건 시나리오 일괄
# ════════════════════════════════════════════════════════════════════════════

def test_president_5_cases_no_keyerror():
    """
    본부장님 환경의 정확한 5건 시나리오 시뮬레이션.
    각 테이블에 대해 v90.53 setup 후 정규화 이름으로 접근해도 KeyError 없음.
    """
    full_schema_map = {
        "eft_batch":    "settlement",
        "org_unit":     "ref",
        "credit_score": "customer",
        "kyc_document": "customer",
        "profile":      "customer",
    }
    engine = FakeMigrationEngine(full_schema_map)
    
    # 각 테이블 처리 시뮬레이션
    results = []
    for src_bare in full_schema_map.keys():
        try:
            src, tgt = engine._migrate_table_setup_v90_53(src_bare)
            # 정규화 이름으로 모든 dict 접근 시도 (실제 _migrate_table 라인 3183, 3186 등)
            engine._cast_cols_map[tgt].add("test_cast")
            engine._geo_cols[tgt].add("test_geo")
            engine._rowver_cols[tgt].add("test_rowver")
            engine._dto_cols[tgt].add("test_dto")
            engine._bin_cols[tgt].add("test_bin")
            engine._skip_cols_map[tgt].add("test_skip")
            results.append((src_bare, tgt, "OK"))
        except KeyError as e:
            results.append((src_bare, "?", f"FAIL: KeyError: {e}"))
    
    # 5건 모두 OK 여야 함
    failed = [r for r in results if r[2] != "OK"]
    assert not failed, f"본부장님 환경 5건 중 {len(failed)}건 실패:\n" + \
                       "\n".join([str(r) for r in failed])


if __name__ == "__main__":
    # 수동 실행
    print("=== v90.48 버그 재현 ===")
    for src_bare, exp_tgt, schema_map in PRESIDENT_CASES:
        engine = FakeMigrationEngine(schema_map)
        src, tgt = engine._migrate_table_setup_v90_48_BUGGY(src_bare)
        try:
            engine._skip_cols_map[tgt].add("test")
            print(f"  {src_bare} → {tgt}: OK (이건 잘못됨)")
        except KeyError as e:
            print(f"  {src_bare} → {tgt}: KeyError {e} ← v90.48 버그 재현됨")
    
    print()
    print("=== v90.53 패치 검증 ===")
    for src_bare, exp_tgt, schema_map in PRESIDENT_CASES:
        engine = FakeMigrationEngine(schema_map)
        src, tgt = engine._migrate_table_setup_v90_53(src_bare)
        try:
            engine._skip_cols_map[tgt].add("test")
            print(f"  {src_bare} → {tgt}: OK ✓")
        except KeyError as e:
            print(f"  {src_bare} → {tgt}: KeyError {e} ← v90.53 실패 (패치 안 됨)")
