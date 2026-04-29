"""
test_v90_56_matching.py — v90.56 (2026-04-28)

본부장님이 짚으신 모순:
  "타겟에 underscore 형태가 분명히 있는데 1건도 매칭 안 됨"

진짜 원인:
  MySQL 응답이 schema_name = "capital_target" (DB 이름) 으로 옴
  → _policyKey 가 "capital_target_customer_profile" 같은 잘못된 키 생성
  → 소스 "customer_profile" 과 매칭 0건

v90.56 fix:
  schema_name 이 connecting DB 이름과 같으면 schema 결합 안 함
  + fuzzy fallback (credit_credit_line ↔ credit_line 변종)

이 테스트는 Python 미러로 알고리즘 검증.

실행:
  cd backend
  pytest tests/test_v90_56_matching.py -v
"""

import sys
import os
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ════════════════════════════════════════════════════════════════════════════
# Validate.vue _policyKey 의 Python 미러 (v90.56)
# ════════════════════════════════════════════════════════════════════════════

def policy_key(t, *, schema_strategy='underscore', src_db_name='', tgt_db_name='', side='source'):
    """v90.56 _policyKey 알고리즘 미러."""
    if isinstance(t, str):
        if '.' in t:
            parts = t.split('.')
            sch = parts[0]
            bare = parts[-1]
        else:
            sch = ''
            bare = t
    else:
        sch = (t.get('schema_name') or '').strip()
        bare = (t.get('table_name') or '').strip()
    
    if not bare:
        return ''
    
    # v90.56 핵심 fix: schema_name 이 connecting DB 이름이면 schema-less
    db_name = src_db_name if side == 'source' else tgt_db_name
    if sch and db_name and sch.lower() == db_name.lower():
        return bare
    
    if not sch or sch.lower() == 'dbo':
        return bare
    if bare.lower().startswith(sch.lower() + '_'):
        return bare
    if schema_strategy == 'underscore':
        return f"{sch}_{bare}"
    return bare


def fuzzy_match(src_keys: dict, tgt_keys: dict) -> dict:
    """v90.56 fuzzy fallback — credit_line ↔ credit_credit_line 같은 변종."""
    matched_pairs = []
    common = set(src_keys.keys()) & set(tgt_keys.keys())
    for k in common:
        matched_pairs.append((k, k))
    
    src_only = set(src_keys.keys()) - common
    tgt_only = set(tgt_keys.keys()) - common
    sr_remove = set()
    tr_remove = set()
    
    for sk in list(src_only):
        for tk in list(tgt_only):
            if sk == tk or tk in tr_remove:
                continue
            if sk.endswith('_' + tk) or tk.endswith('_' + sk):
                matched_pairs.append((sk, tk))
                sr_remove.add(sk)
                tr_remove.add(tk)
                break
    
    return {
        'matched': matched_pairs,
        'src_only': sorted(src_only - sr_remove),
        'tgt_only': sorted(tgt_only - tr_remove),
    }


# ════════════════════════════════════════════════════════════════════════════
# 본부장님 환경 정확 데이터
# ════════════════════════════════════════════════════════════════════════════

PRESIDENT_SOURCES = [
    ("collection",   "activity"),
    ("collection",   "delinquency"),
    ("collection",   "legal_action"),
    ("collection",   "settlement_offer"),
    ("collection",   "write_off"),
    ("credit",       "application"),
    ("credit",       "collateral"),
    ("credit",       "contract"),
    ("credit",       "contract_event"),
    ("credit",       "contract_terms"),
    ("credit",       "credit_line"),       # 까다로운 케이스
    ("credit",       "guarantor"),
    ("credit",       "repayment_schedule"),
    ("credit",       "scoring"),
    ("customer",     "address_history"),
    ("customer",     "bank_account"),
    ("customer",     "consent"),
    ("customer",     "contact_history"),
    ("customer",     "credit_score"),
    ("customer",     "income_info"),
    ("customer",     "kyc_document"),
    ("customer",     "profile"),
    ("customer",     "tag"),
    ("customer",     "tag_map"),
    ("ref",          "branch"),
    ("ref",          "code_group"),
    ("ref",          "code_value"),
    ("ref",          "credit_grade"),
    ("ref",          "employee"),
    ("ref",          "fx_rate"),
    ("ref",          "holiday"),
    ("ref",          "industry_code"),
    ("ref",          "interest_rate"),
    ("ref",          "org_unit"),
    ("ref",          "product"),
    ("settlement",   "autopay_failure"),
    ("settlement",   "daily_settlement"),
    ("settlement",   "disbursement"),
    ("settlement",   "eft_batch"),
    ("settlement",   "fee_charge"),
    ("settlement",   "payment_log"),
    ("settlement",   "trx_history"),
]

SRC_DB_NAME = "capital_midsize"
TGT_DB_NAME = "capital_target"


# ════════════════════════════════════════════════════════════════════════════
# 본부장님 환경 정공법 시나리오 (재이관 후 깨끗한 상태)
# ════════════════════════════════════════════════════════════════════════════

def _build_src_response():
    return [{"schema_name": s, "table_name": b} for s, b in PRESIDENT_SOURCES]

def _build_tgt_response_normal():
    """AI 가 정직하게 schema_bare 로 변환 (credit.credit_line → credit_credit_line)"""
    out = []
    for s, b in PRESIDENT_SOURCES:
        if b.lower().startswith(s.lower() + '_'):
            tgt_table = b  # credit_line 그대로
        else:
            tgt_table = f"{s}_{b}"
        out.append({"schema_name": TGT_DB_NAME, "table_name": tgt_table})
    return out

def _build_tgt_response_simplified():
    """AI 가 credit.credit_line → credit_line 으로 단순화한 시나리오"""
    out = []
    for s, b in PRESIDENT_SOURCES:
        if s == "credit" and b == "credit_line":
            tgt_table = "credit_line"
        elif b.lower().startswith(s.lower() + '_'):
            tgt_table = b
        else:
            tgt_table = f"{s}_{b}"
        out.append({"schema_name": TGT_DB_NAME, "table_name": tgt_table})
    return out


class TestPresident41Tables:
    """본부장님 환경 42 테이블 100% 매칭 검증."""
    
    def test_v90_55_buggy_zero_match(self):
        """v90.55 (이전 버전) 의 매칭 0건 버그 재현."""
        # v90.55 알고리즘 — schema_name 이 DB 이름이어도 그냥 결합
        def buggy_policy_key(t):
            if isinstance(t, str):
                if '.' in t:
                    sch, bare = t.split('.')[0], t.split('.')[-1]
                else:
                    sch, bare = '', t
            else:
                sch = (t.get('schema_name') or '').strip()
                bare = (t.get('table_name') or '').strip()
            if not bare:
                return ''
            if not sch or sch.lower() == 'dbo':
                return bare
            if bare.lower().startswith(sch.lower() + '_'):
                return bare
            return f"{sch}_{bare}"
        
        src_keys = {buggy_policy_key(t): t for t in _build_src_response()}
        tgt_keys = {buggy_policy_key(t): t for t in _build_tgt_response_normal()}
        
        # 버그 재현: 매칭 0건
        common = set(src_keys.keys()) & set(tgt_keys.keys())
        assert len(common) == 0, \
            f"v90.55 버그 재현 실패 (매칭이 {len(common)}건 있음). " \
            f"src 샘플: {list(src_keys.keys())[:3]}, tgt 샘플: {list(tgt_keys.keys())[:3]}"
        
        # 타겟 키들이 모두 'capital_target_' prefix 갖는지 (버그 증상)
        for k in tgt_keys:
            assert k.startswith('capital_target_'), \
                f"v90.55 버그 키가 'capital_target_' 으로 시작 안 함: {k}"
    
    def test_v90_56_normal_scenario_100_percent_match(self):
        """v90.56: 정공법 시나리오 (재이관 후 정직 변환) 에서 41건 100% 매칭."""
        src_response = _build_src_response()
        tgt_response = _build_tgt_response_normal()
        
        src_keys = {policy_key(t, side='source', src_db_name=SRC_DB_NAME, tgt_db_name=TGT_DB_NAME): t 
                    for t in src_response}
        tgt_keys = {policy_key(t, side='target', src_db_name=SRC_DB_NAME, tgt_db_name=TGT_DB_NAME): t 
                    for t in tgt_response}
        
        result = fuzzy_match(src_keys, tgt_keys)
        
        assert len(result['matched']) == len(src_response), \
            f"매칭 부족: {len(result['matched'])}/{len(src_response)}.\n" \
            f"src-only: {result['src_only']}\ntgt-only: {result['tgt_only']}"
        assert not result['src_only'], f"src-only 있으면 안 됨: {result['src_only']}"
        assert not result['tgt_only'], f"tgt-only 있으면 안 됨: {result['tgt_only']}"
    
    def test_v90_56_simplified_scenario_also_works(self):
        """v90.56: AI 가 credit.credit_line 을 credit_line 으로 단순화한 시나리오도 매칭."""
        src_response = _build_src_response()
        tgt_response = _build_tgt_response_simplified()
        
        src_keys = {policy_key(t, side='source', src_db_name=SRC_DB_NAME, tgt_db_name=TGT_DB_NAME): t 
                    for t in src_response}
        tgt_keys = {policy_key(t, side='target', src_db_name=SRC_DB_NAME, tgt_db_name=TGT_DB_NAME): t 
                    for t in tgt_response}
        
        result = fuzzy_match(src_keys, tgt_keys)
        
        # 단순화 케이스에서도 fuzzy 또는 정확 매칭으로 100%
        assert len(result['matched']) == len(src_response), \
            f"매칭 부족: {len(result['matched'])}/{len(src_response)}.\n" \
            f"src-only: {result['src_only']}\ntgt-only: {result['tgt_only']}"


class TestEdgeCases:
    """엣지 케이스."""
    
    def test_dbo_schema_treated_as_bare(self):
        """MSSQL dbo schema 는 bare 만 사용."""
        t = {"schema_name": "dbo", "table_name": "tag"}
        assert policy_key(t, side='source', src_db_name='mydb') == 'tag'
    
    def test_mysql_db_name_as_schema(self):
        """MySQL 의 schema_name = DB 이름이면 schema-less."""
        t = {"schema_name": "capital_target", "table_name": "customer_profile"}
        assert policy_key(t, side='target', src_db_name='capital_midsize', tgt_db_name='capital_target') == 'customer_profile'
    
    def test_credit_line_double_prefix_handled(self):
        """credit.credit_line 의 중복 prefix 처리."""
        t = {"schema_name": "credit", "table_name": "credit_line"}
        # bare 가 schema_ 로 시작 → 그대로 반환
        assert policy_key(t, side='source', src_db_name='mydb') == 'credit_line'
    
    def test_empty_schema(self):
        """빈 schema → bare 만."""
        t = {"schema_name": "", "table_name": "profile"}
        assert policy_key(t, side='source', src_db_name='mydb') == 'profile'
    
    def test_case_insensitive_db_name_match(self):
        """DB 이름 대소문자 무관 매칭."""
        t = {"schema_name": "CAPITAL_TARGET", "table_name": "x"}
        assert policy_key(t, side='target', tgt_db_name='capital_target') == 'x'


class TestFuzzyMatch:
    """fuzzy 매칭 단위 검증."""
    
    def test_credit_line_variants_match(self):
        """credit_line ↔ credit_credit_line 변종 매칭."""
        src = {'credit_line': 'src_obj'}
        tgt = {'credit_credit_line': 'tgt_obj'}
        result = fuzzy_match(src, tgt)
        assert len(result['matched']) == 1
        assert result['matched'][0] == ('credit_line', 'credit_credit_line')
    
    def test_no_false_positive_unrelated(self):
        """무관한 이름은 fuzzy 매칭하지 않아야."""
        src = {'profile': 's'}
        tgt = {'invoice': 't'}
        result = fuzzy_match(src, tgt)
        assert len(result['matched']) == 0
        assert result['src_only'] == ['profile']
        assert result['tgt_only'] == ['invoice']


if __name__ == "__main__":
    print("=== v90.55 버그 재현 ===")
    src = _build_src_response()
    tgt = _build_tgt_response_normal()
    
    def buggy(t):
        sch = (t.get('schema_name') or '').strip()
        bare = (t.get('table_name') or '').strip()
        if not sch or sch.lower() == 'dbo': return bare
        if bare.lower().startswith(sch.lower() + '_'): return bare
        return f"{sch}_{bare}"
    
    sk = {buggy(t): t for t in src}
    tk = {buggy(t): t for t in tgt}
    common = set(sk.keys()) & set(tk.keys())
    print(f"  매칭: {len(common)}건 (예상: 0건 = 버그)")
    
    print()
    print("=== v90.56 정공법 ===")
    sk = {policy_key(t, side='source', src_db_name=SRC_DB_NAME, tgt_db_name=TGT_DB_NAME): t for t in src}
    tk = {policy_key(t, side='target', src_db_name=SRC_DB_NAME, tgt_db_name=TGT_DB_NAME): t for t in tgt}
    result = fuzzy_match(sk, tk)
    print(f"  매칭: {len(result['matched'])}건 (예상: {len(src)}건)")
    if result['matched']:
        sample = [p for p in result['matched'] if p[0] != p[1]][:3]
        if sample:
            print(f"  fuzzy 페어 예시: {sample}")
