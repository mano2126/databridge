"""
preflight_kb_learner.py — Phase E-3 / v90.52 (2026-04-27)

preflight 가 fail 로 보고한 케이스를 자동으로 KB 에 누적.

배경:
  본부장님 환경에서 동일 패턴이 반복 발생하는 경우 (예: TVF MySQL 미지원),
  이를 KB 에 등재하여 다음 AI 변환 시 프롬프트에 힌트로 주입.
  
  v90.52 까지는 schema.py 의 13-7-kb-recorded 트레이스만 남기고
  실제 영구 저장은 본 모듈이 담당.

저장 위치:
  backend/prompts/mssql_to_mysql/auto_learned_rules.json
  backend/prompts/mssql_to_mysql/error_cases.txt   (기존 KB 와 통합)

데이터 구조 (auto_learned_rules.json):
  {
    "version": "v90.52",
    "updated_at": "2026-04-27T21:33:00",
    "patterns": [
      {
        "rule_id": "R-10",
        "obj_type": "FUNCTION",
        "obj_name_pattern": "*_tvf_*",
        "occurrence": 3,
        "first_seen": "2026-04-27T21:33:11",
        "last_seen": "2026-04-27T21:38:01",
        "issue_msg": "MySQL 은 RETURNS TABLE ...",
        "suggested_action": "VIEW 로 변환 또는 PROCEDURE OUT 사용",
      },
      ...
    ]
  }

원칙 (본부장님 메모리 정책):
  - 등재만, 자동 정정 X (수동 검토 큐로 사용)
  - 실패 N회 (기본 3회) 누적 시 fail → AI 프롬프트 강제 주입 후보
  - 프로젝트 KB 의 living asset 으로 관리
"""

from __future__ import annotations
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

_log = logging.getLogger("databridge.kb_learner")

# KB 파일 경로 — backend/prompts/mssql_to_mysql/
_KB_DIR_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / "prompts" / "mssql_to_mysql",
    Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "mssql_to_mysql",
    Path("D:/project/databridge_full/backend/prompts/mssql_to_mysql"),
    Path("./prompts/mssql_to_mysql"),
]

_AUTO_LEARNED_FILE = "auto_learned_rules.json"
_ERROR_CASES_FILE = "error_cases.txt"

# 자동 등재 임계값 — N회 누적 시 fail 후보
_PROMOTE_THRESHOLD = 3


# ════════════════════════════════════════════════════════════════════════════
# 공개 API
# ════════════════════════════════════════════════════════════════════════════

def record_fail_cases(
    obj_name: str,
    obj_type: str,
    fail_issues: List[Dict[str, Any]],
) -> bool:
    """
    preflight fail 케이스를 KB 에 누적.
    
    Args:
        obj_name: 객체명 (예: "tvf_contract_events")
        obj_type: "FUNCTION" | "PROCEDURE" | "TRIGGER" | "VIEW" | "TABLE"
        fail_issues: preflight_check 결과의 issues 중 severity=fail 만
    
    Returns:
        True if 등재 성공, False if 디스크 쓰기 실패
    """
    if not fail_issues:
        return False
    
    kb_dir = _find_kb_dir()
    if kb_dir is None:
        _log.warning("[kb_learner] KB 디렉토리를 찾지 못함 — 등재 skip")
        return False
    
    auto_file = kb_dir / _AUTO_LEARNED_FILE
    error_file = kb_dir / _ERROR_CASES_FILE
    
    # auto_learned_rules.json 갱신
    try:
        kb = _load_kb(auto_file)
        now = datetime.now().isoformat(timespec="seconds")
        
        for issue in fail_issues:
            rule_id = issue.get("rule", "?")
            msg = issue.get("msg", "")
            hint = issue.get("hint", "")
            
            # 동일 rule_id + obj_type 매칭하는 패턴 찾기
            existing = None
            for pat in kb["patterns"]:
                if (pat.get("rule_id") == rule_id
                        and pat.get("obj_type") == obj_type):
                    existing = pat
                    break
            
            if existing:
                existing["occurrence"] = existing.get("occurrence", 1) + 1
                existing["last_seen"] = now
                # last_obj_names 에 누적 (최근 5개만 유지)
                names = existing.setdefault("last_obj_names", [])
                if obj_name not in names:
                    names.append(obj_name)
                    if len(names) > 5:
                        names.pop(0)
            else:
                kb["patterns"].append({
                    "rule_id": rule_id,
                    "obj_type": obj_type,
                    "occurrence": 1,
                    "first_seen": now,
                    "last_seen": now,
                    "issue_msg": msg,
                    "suggested_action": hint,
                    "last_obj_names": [obj_name],
                })
        
        kb["updated_at"] = now
        kb["version"] = "v90.52"
        
        _save_kb(auto_file, kb)
        
    except Exception as e:
        _log.warning("[kb_learner] auto_learned_rules.json 갱신 실패: %s", e)
        return False
    
    # error_cases.txt 에 한 줄 추가 (사람이 읽기 좋은 포맷)
    try:
        with open(error_file, "a", encoding="utf-8") as f:
            f.write(
                f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                f"[{obj_type}] {obj_name}\n"
            )
            for issue in fail_issues:
                f.write(
                    f"- [{issue.get('rule', '?')}] {issue.get('msg', '')}\n"
                    f"  → {issue.get('hint', '')}\n"
                )
    except Exception as e:
        _log.warning("[kb_learner] error_cases.txt 추가 실패 (무시): %s", e)
    
    return True


def get_promoted_rules() -> List[Dict[str, Any]]:
    """
    누적 N회 이상인 룰 패턴 반환 — AI 프롬프트 강제 주입 후보.
    
    Returns:
        [{rule_id, obj_type, occurrence, suggested_action}, ...]
    """
    kb_dir = _find_kb_dir()
    if kb_dir is None:
        return []
    
    auto_file = kb_dir / _AUTO_LEARNED_FILE
    if not auto_file.exists():
        return []
    
    try:
        kb = _load_kb(auto_file)
        promoted = [
            p for p in kb.get("patterns", [])
            if p.get("occurrence", 0) >= _PROMOTE_THRESHOLD
        ]
        # 빈도 내림차순 정렬
        promoted.sort(key=lambda x: x.get("occurrence", 0), reverse=True)
        return promoted
    except Exception as e:
        _log.warning("[kb_learner] promoted rules 조회 실패: %s", e)
        return []


def build_prompt_injection() -> str:
    """
    promoted rules 를 AI 프롬프트에 주입할 텍스트로 변환.
    schema.py 의 _ai_convert_ddl 시작부에서 호출 가능.
    """
    promoted = get_promoted_rules()
    if not promoted:
        return ""
    
    lines = [
        "\nIMPORTANT — 다음 패턴은 과거 변환에서 반복 실패한 사례입니다. "
        "절대 동일하게 만들지 마세요:"
    ]
    for p in promoted:
        lines.append(
            f"- [{p['rule_id']}] {p.get('obj_type', '*')}: "
            f"{p.get('issue_msg', '')} → {p.get('suggested_action', '')}"
        )
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# 내부 헬퍼
# ════════════════════════════════════════════════════════════════════════════

def _find_kb_dir() -> Optional[Path]:
    """KB 디렉토리 후보 중 존재하는 것 반환."""
    for candidate in _KB_DIR_CANDIDATES:
        try:
            if candidate.exists() and candidate.is_dir():
                return candidate
        except Exception:
            continue
    
    # 후보 중 첫 번째 부모 디렉토리가 존재하면 자동 생성
    for candidate in _KB_DIR_CANDIDATES:
        try:
            if candidate.parent.exists():
                candidate.mkdir(parents=True, exist_ok=True)
                _log.info("[kb_learner] KB 디렉토리 자동 생성: %s", candidate)
                return candidate
        except Exception:
            continue
    
    return None


def _load_kb(path: Path) -> Dict[str, Any]:
    """auto_learned_rules.json 로드 (없으면 빈 구조)."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                kb = json.load(f)
            if "patterns" not in kb:
                kb["patterns"] = []
            return kb
        except Exception as e:
            _log.warning("[kb_learner] %s 파싱 실패, 빈 KB 로 시작: %s", path, e)
    
    return {
        "version": "v90.52",
        "updated_at": "",
        "patterns": [],
    }


def _save_kb(path: Path, kb: Dict[str, Any]) -> None:
    """auto_learned_rules.json 저장 (atomic write)."""
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ════════════════════════════════════════════════════════════════════════════
# 단독 실행 (KB 상태 조회)
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    kb_dir = _find_kb_dir()
    print(f"KB 디렉토리: {kb_dir}")
    
    promoted = get_promoted_rules()
    print(f"\nPromoted rules ({_PROMOTE_THRESHOLD}회 이상): {len(promoted)}개")
    for p in promoted:
        print(f"  [{p['rule_id']}] {p.get('obj_type')} × {p.get('occurrence')} — "
              f"{p.get('issue_msg', '')[:50]}")
    
    print(f"\n프롬프트 주입 텍스트:\n{build_prompt_injection() or '(없음)'}")
