"""
test_v90_58_hotfix_combined.py — v90.58 hotfix (2026-04-28)

이슈:
  v90.54 ZIP 작성 시 베이스 파일을 잘못 골라 v90.53 의 KeyError fix 가
  통째로 사라진 채 ZIP 에 들어갔음. 본부장님 환경에 v90.54 적용 시
  v90.53 fix 가 깨끗이 덮어씌워져 KeyError 재발.

증상:
  - 'ref_org_unit', 'settlement_eft_batch' 같은 정규화된 이름으로 KeyError
  - org_unit, eft_batch 테이블 이관 0초만에 오류

v90.58 hotfix:
  v90.53 정상본 베이스 + v90.54 _ensure_terminator fix 합본
  
이 테스트는 두 fix 가 모두 살아있는지 검증.
"""

import sys
import os
import re
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
ENGINE_FILE = os.path.join(_BACKEND_DIR, 'app', 'engine', 'migration_engine.py')


class TestV90_53_FixPresent:
    """v90.53 KeyError fix 가 file 에 살아있는지."""
    
    def test_v90_53_marker_present(self):
        """'v90.53 ... KeyError' 주석 마커 확인."""
        if not os.path.exists(ENGINE_FILE):
            pytest.skip(f"{ENGINE_FILE} 없음")
        content = open(ENGINE_FILE, encoding='utf-8').read()
        assert re.search(r"v90\.53.*KeyError", content), \
            "v90.53 KeyError fix 주석 마커 누락"
    
    def test_dict_key_registration_after_swap(self):
        """dict 키 등록이 swap 다음에 와야 함 (v90.53 핵심)."""
        content = open(ENGINE_FILE, encoding='utf-8').read()
        
        # src_bare = table 위치
        m_swap = re.search(r"src_bare = table", content)
        assert m_swap, "src_bare = table 라인 없음"
        swap_pos = m_swap.start()
        
        # self._skip_cols_map[table] = set() 의 모든 위치
        # _migrate_table 안의 첫 번째가 swap 후에 와야 함
        m_dict = list(re.finditer(r"self\._skip_cols_map\[table\] = set\(\)", content))
        assert m_dict, "_skip_cols_map[table] = set() 라인 없음"
        
        # 첫 번째 등록이 swap 다음 (즉 swap_pos 보다 큰 위치)
        first_dict_pos = m_dict[0].start()
        assert first_dict_pos > swap_pos, \
            f"dict 키 등록 ({first_dict_pos}) 이 swap ({swap_pos}) 보다 먼저 — v90.53 fix 무효!"
    
    def test_src_bare_alias_present(self):
        """v90.53 의 src_bare 이중 등록 안전망."""
        content = open(ENGINE_FILE, encoding='utf-8').read()
        assert re.search(
            r"_skip_cols_map\[src_bare\]\s*=\s*self\._skip_cols_map\[table\]",
            content
        ), "v90.53 src_bare alias 이중 등록 누락"


class TestV90_54_FixPresent:
    """v90.54 _ensure_terminator fix 가 file 에 살아있는지."""
    
    def test_ensure_terminator_function(self):
        content = open(ENGINE_FILE, encoding='utf-8').read()
        assert "def _ensure_terminator(s" in content, \
            "v90.54 _ensure_terminator 함수 누락"
    
    def test_v90_54_marker(self):
        content = open(ENGINE_FILE, encoding='utf-8').read()
        assert re.search(r"v90\.54.*full_ddl", content), \
            "v90.54 full_ddl 주석 마커 누락"
    
    def test_no_old_simple_join(self):
        """옛날 단순 join 코드가 남아있으면 안 됨 (주석 제외)."""
        content = open(ENGINE_FILE, encoding='utf-8').read()
        # 옛날 코드 (주석 제외): full_ddl = "\n".join(s.strip() for s in statements if s.strip())
        # 라인 시작이 # 으로 시작하지 않아야 (주석 제외)
        for line in content.splitlines():
            stripped = line.lstrip()
            if stripped.startswith('#'):
                continue  # 주석 제외 (v90.54 설명 주석은 살아있어야 함)
            # 옛날 한 줄 join 패턴 (실행 코드)
            if re.search(r'full_ddl\s*=\s*"\\n"\.join\(s\.strip\(\)\s+for\s+s\s+in\s+statements\s+if\s+s\.strip\(\)\)', stripped):
                pytest.fail(f"v90.54 옛날 join 코드 잔존: {line.strip()}")


class TestKeyErrorScenarioSimulation:
    """본부장님 환경 KeyError 케이스 시뮬레이션 (Python 미러)."""
    
    def test_org_unit_keyerror_fixed(self):
        """org_unit → ref_org_unit 케이스 시뮬레이션."""
        # v90.53 패턴: dict 등록은 swap 후
        skip_cols = {}
        cast_cols = {}
        
        # 시뮬레이션 시작
        table = "org_unit"  # 들어온 입력
        
        # swap (v90.48 정공법)
        src_bare = table
        tgt_table = "ref_org_unit"  # _target_table_name 결과 가정
        table = tgt_table  # swap
        
        # v90.53: 키 등록은 swap 후
        skip_cols[table] = set()
        cast_cols[table] = set()
        if src_bare != table:
            skip_cols[src_bare] = skip_cols[table]
            cast_cols[src_bare] = cast_cols[table]
        
        # 이후 코드가 정규화 이름으로 접근 — KeyError 안 나야 함
        try:
            skip_cols[table].add('test_col')  # table = 'ref_org_unit'
        except KeyError as e:
            pytest.fail(f"v90.53 패턴에서도 KeyError: {e}")
        
        # src_bare 로도 접근 가능 (안전망)
        try:
            skip_cols[src_bare].add('test_col_2')  # src_bare = 'org_unit'
        except KeyError as e:
            pytest.fail(f"src_bare alias 접근 실패: {e}")
        
        # 같은 set 객체 공유 확인
        assert 'test_col' in skip_cols[src_bare]
        assert 'test_col_2' in skip_cols[table]
    
    def test_eft_batch_keyerror_fixed(self):
        """eft_batch → settlement_eft_batch 케이스."""
        skip_cols = {}
        
        table = "eft_batch"
        src_bare = table
        tgt_table = "settlement_eft_batch"
        table = tgt_table
        
        skip_cols[table] = set()
        if src_bare != table:
            skip_cols[src_bare] = skip_cols[table]
        
        # 정규화 이름 접근
        skip_cols[table].add('col_a')
        # src_bare 접근
        skip_cols[src_bare].add('col_b')
        
        # 둘 다 같은 set 에 들어가야
        assert skip_cols[table] == skip_cols[src_bare]
        assert {'col_a', 'col_b'}.issubset(skip_cols[table])


if __name__ == "__main__":
    print("=== v90.58 hotfix 검증 ===")
    print(f"파일: {ENGINE_FILE}")
    print(f"존재: {os.path.exists(ENGINE_FILE)}")
    
    if os.path.exists(ENGINE_FILE):
        content = open(ENGINE_FILE, encoding='utf-8').read()
        
        v53_ok = bool(re.search(r"v90\.53.*KeyError", content))
        v54_ok = "_ensure_terminator" in content
        
        print(f"v90.53 KeyError fix: {'✓' if v53_ok else '✗'}")
        print(f"v90.54 _ensure_terminator: {'✓' if v54_ok else '✗'}")
        
        # swap 순서 확인
        m_swap = re.search(r"src_bare = table", content)
        m_dict = re.search(r"self\._skip_cols_map\[table\] = set\(\)", content)
        if m_swap and m_dict:
            order = "OK" if m_dict.start() > m_swap.start() else "FAIL"
            print(f"swap 순서 (swap 전 dict 등록 X): {order}")
