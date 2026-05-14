"""
DataBridge Pattern Auto-Extraction — hotfix_031
=================================================

본부장님 16번째 비전 통찰 정면 처방:
  "지속적으로 KB 를 쌓고 쌓여진 KB 가 타겟 DB 에서 잘 수행되면 그걸로 이용"
  "누구나 이 솔루션을 가지고 전환 할 수 있도록"

자동 패턴 추출 흐름:
  1. AI 가 변환 성공 (또는 SQLGlot 등 외부 모듈)
  2. MySQL 실행 검증 통과
  3. src → tgt 의 차이 분석 → 잠재 Pattern 발견
  4. Pattern Library 에 후보 등록 (confidence 낮게 시작)
  5. 시간 갈수록 같은 패턴 발견 빈도 증가 → confidence 자동 상승
  6. confidence ≥ 0.9 → 정식 자산

본부장님 비전:
  - 본부장님 + 첫 사용자: 26 patterns
  - 사용자 100명 + 1년: 500+ patterns (자동 누적)
  - = DataBridge 만의 air-gapped 자산
"""
from __future__ import annotations
import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

_log = logging.getLogger("databridge.pattern_extractor")


# ════════════════════════════════════════════════════════════════
# 차이 분석 — 안전한 패턴 후보 추출
# ════════════════════════════════════════════════════════════════

# 후보 추출 대상: 안전하게 일반화 가능한 변환만
SAFE_EXTRACTION_PATTERNS = [
    # 1. 함수 매핑 (MSSQL 함수 → MySQL 함수)
    {
        'type': 'function_mapping',
        'src_pattern': r'\b([A-Z_]{3,15})\s*\(',  # 함수 호출 형식
        'description': '함수 매핑 후보',
    },
    # 2. 시스템 변수 (@@something)
    {
        'type': 'system_variable',
        'src_pattern': r'@@(\w+)',
        'description': '시스템 변수 매핑',
    },
    # 3. T-SQL 키워드 매핑
    {
        'type': 'keyword',
        'src_pattern': r'\b(GETDATE|SYSDATETIME|NEWID|RAND|ABS|CEILING|FLOOR)\b',
        'description': 'T-SQL 키워드',
    },
]


def find_src_only_tokens(src: str, tgt: str, min_len: int = 4) -> List[Dict]:
    """src 에 있는데 tgt 에 없는 토큰 (변환됐을 가능성 큼)."""
    # 함수/키워드 후보
    src_funcs = set(re.findall(r'\b([A-Z_]{3,20})\s*\(', src))
    tgt_funcs = set(re.findall(r'\b([A-Z_]{3,20})\s*\(', tgt))
    candidates = []
    for fn in src_funcs - tgt_funcs:
        if len(fn) >= min_len:
            candidates.append({
                'type': 'function_disappeared',
                'token': fn + '(',
                'note': f'src 에 {fn}() 있었는데 tgt 에 없음 → 다른 함수로 변환됨',
            })
    return candidates


def find_simple_token_replacements(src: str, tgt: str) -> List[Dict]:
    """src/tgt 비교로 단순 토큰 치환 발견.
    
    예: src 에 ISNULL, tgt 에 IFNULL 이 같은 위치 → ISNULL → IFNULL
    그러나 정확한 위치 매칭은 어려움 — heuristic 사용.
    """
    replacements = []
    
    # 알려진 1:1 함수 매핑 검사 (이미 패턴이면 skip)
    known_replacements = [
        ('ISNULL', 'IFNULL'),
        ('GETDATE', 'NOW'),
        ('LEN', 'LENGTH'),
        ('@@ROWCOUNT', 'ROW_COUNT'),
        ('@@IDENTITY', 'LAST_INSERT_ID'),
        ('NEWID', 'UUID'),
        ('GETUTCDATE', 'UTC_TIMESTAMP'),
        ('SYSDATETIME', 'NOW'),
        ('CHARINDEX', 'INSTR'),  # 인자 순서 다름 — 주의
        ('SUBSTRING', 'SUBSTR'),
        ('STUFF', 'INSERT'),  # 구문 다름 — 주의
        ('IIF', 'IF'),  # 구문 비슷
        ('FORMAT', 'DATE_FORMAT'),  # 인자 다름
    ]
    
    for src_fn, tgt_fn in known_replacements:
        src_count = len(re.findall(rf'\b{src_fn}\s*\(', src, re.IGNORECASE))
        tgt_count = len(re.findall(rf'\b{tgt_fn}\s*\(', tgt, re.IGNORECASE))
        src_in_tgt = len(re.findall(rf'\b{src_fn}\s*\(', tgt, re.IGNORECASE))
        
        # src 에 있던 src_fn 이 tgt 에선 없거나 줄었고, tgt_fn 이 비슷한 수 있음
        if src_count > 0 and src_in_tgt < src_count and tgt_count >= src_count - src_in_tgt:
            replacements.append({
                'type': 'function_replacement',
                'src_token': src_fn,
                'tgt_token': tgt_fn,
                'src_count': src_count,
                'tgt_count': tgt_count,
                'src_remaining_in_tgt': src_in_tgt,
                'evidence': f'{src_fn}({src_count}) → {tgt_fn}({tgt_count}, src_remaining={src_in_tgt})',
            })
    
    return replacements


def extract_pattern_candidates(src: str, tgt: str, obj_type: str = "",
                                obj_name: str = "") -> List[Dict]:
    """변환된 src→tgt 쌍에서 자동 추출된 Pattern 후보.
    
    본부장님 비전 정면: 검증된 변환 결과에서 자동 학습.
    """
    candidates = []
    
    # 1. 단순 함수 치환 후보
    replacements = find_simple_token_replacements(src, tgt)
    for r in replacements:
        candidates.append({
            'pattern_id': f"AUTO_{r['src_token']}_TO_{r['tgt_token']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'name': f"{r['src_token']}() → {r['tgt_token']}()",
            'category': 'function',
            'priority': 100,  # 자동 추출은 낮은 우선순위
            'src_regex': rf"\b{r['src_token']}\s*\(",
            'tgt_template': f"{r['tgt_token']}(",
            'confidence': 0.6,  # 자동 추출은 낮은 신뢰도로 시작
            'auto_extracted': True,
            'discovered_from': f"{obj_type}:{obj_name}",
            'discovered_at': datetime.now().isoformat(),
            'evidence': r['evidence'],
            'use_count': 0,
        })
    
    # 2. src 에 있는데 tgt 에 없는 함수 (변환된 것으로 추정)
    disappeared = find_src_only_tokens(src, tgt)
    for d in disappeared[:5]:  # 너무 많이 추출하지 않게
        candidates.append({
            'type': 'review_candidate',
            'note': d['note'],
            'src_token': d['token'],
            'discovered_from': f"{obj_type}:{obj_name}",
        })
    
    return candidates


# ════════════════════════════════════════════════════════════════
# 외부 진입점 — Pattern KB 로 자동 등록
# ════════════════════════════════════════════════════════════════
def auto_extract_and_register(src: str, tgt: str, obj_type: str = "",
                                obj_name: str = "", verified: bool = False) -> List[Dict]:
    """변환된 쌍에서 패턴 자동 추출 + KB 등록.
    
    본부장님 비전 정면: 시간 갈수록 패턴 누적.
    
    Args:
        verified: True 면 MySQL 검증 통과한 경우 — 더 높은 confidence
    
    Returns:
        등록된 후보 패턴 리스트
    """
    candidates = extract_pattern_candidates(src, tgt, obj_type, obj_name)
    
    if not candidates:
        return []
    
    # Pattern KB 에 등록
    try:
        from app.core.pattern_kb import load_pattern_kb, save_pattern_kb
        kb = load_pattern_kb()
        
        # 기존 패턴과 중복 안 되게
        existing_ids = {p.get('pattern_id') for p in kb.get('patterns', [])}
        existing_names = {p.get('name') for p in kb.get('patterns', [])}
        
        added = []
        for c in candidates:
            if c.get('pattern_id') and c['pattern_id'] in existing_ids:
                continue
            if c.get('name') and c['name'] in existing_names:
                # 같은 이름이 이미 있으면 use_count 만 증가
                for p in kb['patterns']:
                    if p.get('name') == c['name']:
                        p['use_count'] = p.get('use_count', 0) + 1
                        # verified 면 confidence 약간 상승
                        if verified:
                            p['confidence'] = min(1.0, p.get('confidence', 0.6) + 0.05)
                        break
                continue
            
            # 새 패턴 후보 등록
            if c.get('type') == 'review_candidate':
                # 리뷰 후보 — 일단 KB 에 안 넣음 (수동 검토)
                continue
            
            if verified:
                c['confidence'] = min(1.0, c.get('confidence', 0.6) + 0.1)
            
            kb['patterns'].append(c)
            added.append(c)
        
        if added:
            save_pattern_kb(kb)
            _log.info(
                "[v95_p107-PATTERN-AUTO-EXTRACT] %s [%s] 새 Pattern %d개 자동 등록 "
                "(verified=%s): %s",
                obj_type, obj_name, len(added), verified,
                [p['name'] for p in added],
            )
        
        return added
    except Exception as e:
        _log.warning("[pattern_extractor] auto_extract 실패: %s", e)
        return []
