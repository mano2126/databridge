"""
first_try_success_orchestrator.py — Phase H-5 (2026-04-25)

Phase H 의 모든 모듈을 통합 — 첫 이관 성공률 95%+ 달성을 위한 오케스트레이터.

이 모듈은 migration_engine.py 의 _migrate_objects 함수를 침습적으로 수정하지 않고,
"한 줄 추가" 만으로 Phase H 전체 기능을 활성화하는 통합 hook 제공.

작동 흐름:
  1) [H-1] 의존성 그래프 분석 → 안전한 실행 순서 결정
  2) [H-2] DDL 사전 검증 → auto-fix 적용 (syntax 오류 사전 잡기)
  3) [H-3] 스마트 재시도로 실행 (defer + AI 재변환)
  4) [H-4] AI 재변환 시 강화된 prompt 사용
  5) 최종 리포트

기존 migration_engine.py 의 변경:
  변경 전:
    def _migrate_objects(self, src_conn, tgt_conn, objects, do_convert):
        for name in (objects.get("functions") or []):
            ...
  
  변경 후 (3줄만 추가):
    def _migrate_objects(self, src_conn, tgt_conn, objects, do_convert):
        # Phase H 통합 시도
        from app.core.first_try_success_orchestrator import try_phase_h_migration
        if try_phase_h_migration(self, src_conn, tgt_conn, objects, do_convert):
            return  # Phase H 가 처리했으면 끝
        
        # 폴백: 기존 로직
        for name in (objects.get("functions") or []):
            ...

설계 원칙:
  - 옵션 활성화: 환경 변수 PHASE_H_ENABLED=true 일 때만 작동
  - 안전한 폴백: 어떤 단계에서든 실패하면 기존 로직으로 fallthrough
  - 비침습적: migration_engine.py 변경 최소화
  - 관찰 가능: 모든 단계 자세한 로그
  - 점진적 채택: 처음에는 dry-run 모드로 검증 가능
"""

from __future__ import annotations
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

_log = logging.getLogger("databridge.phase_h.orchestrator")


# ════════════════════════════════════════════════════════════════════════════
# 메인 오케스트레이터
# ════════════════════════════════════════════════════════════════════════════

def try_phase_h_migration(
    migration_engine,
    src_conn,
    tgt_conn,
    objects: Dict[str, List[str]],
    do_convert: bool,
) -> bool:
    """
    Phase H 통합 이관 시도.
    
    Returns:
        True: Phase H 가 모든 처리를 마침 (호출자는 더 이상 작업 안 함)
        False: Phase H 비활성화 또는 폴백 — 호출자가 기존 로직 실행
    """
    # 환경 변수로 활성화 제어 (안전 default: false)
    if not _is_phase_h_enabled(migration_engine):
        return False
    
    try:
        orchestrator = PhaseHOrchestrator(migration_engine, src_conn, tgt_conn)
        success = orchestrator.run(objects, do_convert)
        return success
    except Exception as e:
        # 어떤 이유로든 실패 시 폴백
        _log.warning(f"[Phase H] 오케스트레이터 실패 — 기존 로직으로 폴백: {e}", exc_info=True)
        return False


def _is_phase_h_enabled(engine) -> bool:
    """Phase H 활성화 여부 확인"""
    # 우선순위:
    # 1. Job 설정의 phase_h_enabled
    # 2. 환경 변수 DATABRIDGE_PHASE_H
    # 3. default: False (안전)
    
    job = getattr(engine, 'job', {}) or {}
    
    if job.get('phase_h_enabled') is True:
        return True
    if job.get('phase_h_enabled') is False:
        return False
    
    env_val = os.environ.get('DATABRIDGE_PHASE_H', '').lower()
    return env_val in ('true', '1', 'yes', 'on')


# ════════════════════════════════════════════════════════════════════════════
# Phase H 오케스트레이터 클래스
# ════════════════════════════════════════════════════════════════════════════

class PhaseHOrchestrator:
    """Phase H-1 ~ H-4 를 순서대로 실행하는 오케스트레이터"""
    
    def __init__(self, migration_engine, src_conn, tgt_conn):
        self.engine = migration_engine
        self.src_conn = src_conn
        self.tgt_conn = tgt_conn
        self.job = migration_engine.job if hasattr(migration_engine, 'job') else {}
        
    def run(self, objects: Dict[str, List[str]], do_convert: bool) -> bool:
        """전체 흐름 실행"""
        start = time.monotonic()
        self._log("info", "[Phase H] 첫 이관 성공률 모드 활성화")
        
        # ─── Step 0: DDL 수집 + AI 변환 (기존 로직 재사용) ───
        ddl_map = self._collect_ddls(objects, do_convert)
        if not ddl_map:
            self._log("warn", "[Phase H] DDL 수집 결과 없음 — 폴백")
            return False
        
        self._log("info", f"[Phase H] DDL 수집 완료: {len(ddl_map)}개")
        
        # ─── Step 1: H-1 의존성 그래프 분석 ───
        ordered_objects = self._h1_resolve_dependencies(ddl_map, objects)
        if not ordered_objects:
            self._log("warn", "[Phase H-1] 순서 결정 실패 — 폴백")
            return False
        
        self._log("info", f"[Phase H-1] 의존성 순서 결정: {len(ordered_objects)}개")
        
        # ─── Step 2: H-2 DDL 사전 검증 + auto-fix ───
        validated_objects = self._h2_validate_and_fix(ordered_objects)
        
        validation_summary = self._summarize_validation(validated_objects)
        self._log("info", 
            f"[Phase H-2] 사전 검증: {validation_summary['can_proceed']}개 실행 가능, "
            f"{validation_summary['auto_fixed']}개 자동 수정"
        )
        
        # ─── Step 3: H-3 스마트 재시도 실행 ───
        report = self._h3_execute_with_retry(validated_objects)
        
        duration = round(time.monotonic() - start, 2)
        
        # ─── Step 4: 결과 리포팅 ───
        self._log_final_report(report, duration)
        
        # job 에 리포트 저장 (UI 에서 조회용)
        self.job['phase_h_report'] = report.to_dict()
        
        return True
    
    # ─── DDL 수집 ───────────────────────────────────────────────────
    def _collect_ddls(self, objects, do_convert) -> Dict[str, Dict]:
        """오브젝트 dict → {name: {type, original_ddl, converted_ddl}}"""
        result = {}
        
        type_map = {
            'functions': 'function',
            'procedures': 'procedure',
            'views': 'view',
            'triggers': 'trigger',
        }
        
        for collection_key, type_singular in type_map.items():
            for name in (objects.get(collection_key) or []):
                ddl = self._get_source_ddl(type_singular.upper(), name)
                if not ddl:
                    continue
                
                converted = ddl
                if do_convert:
                    converted = self._convert_with_ai(name, type_singular, ddl)
                
                result[name] = {
                    'type': type_singular,
                    'original_ddl': ddl,
                    'converted_ddl': converted,
                }
        
        return result
    
    def _get_source_ddl(self, obj_type: str, name: str) -> str:
        """소스에서 DDL 가져오기 (기존 _migrate_objects 의 _get_ddl 재사용)"""
        # migration_engine 의 _get_ddl 함수 호출
        # 단, 이 함수가 _migrate_objects 안의 closure 라 직접 호출 어려움
        # → 단순화: 우리만의 SHOW CREATE 로 가져옴
        try:
            cur = self.src_conn.cursor()
            src_db_type = self.job.get('src_db', 'mysql')
            
            if src_db_type in ('mysql', 'aurora', 'mariadb', 'tidb'):
                if obj_type in ('PROCEDURE', 'FUNCTION'):
                    cur.execute(f"SHOW CREATE {obj_type} `{name}`")
                    row = cur.fetchone()
                    if row:
                        return row[2] if len(row) > 2 else ""
                elif obj_type == 'TRIGGER':
                    cur.execute(f"SHOW CREATE TRIGGER `{name}`")
                    row = cur.fetchone()
                    if row:
                        return row[2] if len(row) > 2 else ""
                elif obj_type == 'VIEW':
                    cur.execute(f"SHOW CREATE VIEW `{name}`")
                    row = cur.fetchone()
                    if row:
                        return row[1] if len(row) > 1 else ""
            elif src_db_type in ('mssql', 'azure'):
                # MSSQL: sys.sql_modules
                cur.execute("""
                    SELECT m.definition FROM sys.sql_modules m
                    JOIN sys.objects o ON m.object_id = o.object_id
                    WHERE o.name = ?
                """, [name])
                row = cur.fetchone()
                if row:
                    return row[0] or ""
        except Exception as e:
            _log.warning(f"[Phase H] DDL 가져오기 실패 [{name}]: {e}")
        
        return ""
    
    def _convert_with_ai(self, name: str, obj_type: str, ddl: str) -> str:
        """AI 변환 — H-4 강화된 prompt 사용"""
        try:
            from app.core import obj_executor
            from app.core.prompt_enhancer import enhance_conversion_prompt
            
            # error_cases 로드
            error_cases = self._load_error_cases()
            
            # 기본 prompt 생성 (obj_executor 위임)
            # obj_executor 의 _make_prompt 호출 (있으면)
            base_prompt = ""
            if hasattr(obj_executor, '_make_prompt'):
                try:
                    base_prompt = obj_executor._make_prompt(
                        src_db=self.job.get('src_db', 'mssql'),
                        tgt_db=self.job.get('tgt_db', 'mysql'),
                        obj_type=obj_type.upper(),
                        obj_name=name,
                        ddl=ddl,
                    )
                except Exception:
                    pass
            
            if not base_prompt:
                base_prompt = f"Convert {obj_type}: {ddl}"
            
            # H-4 강화
            enhanced = enhance_conversion_prompt(
                base_prompt, ddl, obj_type.upper(), error_cases
            )
            
            # AI 호출 — obj_executor 의 변환 함수 위임
            if hasattr(obj_executor, 'call_ai_for_ddl'):
                converted = obj_executor.call_ai_for_ddl(enhanced)
                if converted:
                    return converted
        except Exception as e:
            _log.warning(f"[Phase H-4] AI 변환 실패 [{name}]: {e}")
        
        # 폴백: 원본 그대로
        return ddl
    
    def _load_error_cases(self) -> str:
        """error_cases.txt 로드"""
        try:
            from pathlib import Path
            src_db = self.job.get('src_db', 'mssql')
            tgt_db = self.job.get('tgt_db', 'mysql')
            
            base = Path(__file__).resolve().parent.parent.parent / 'prompts'
            path = base / f"{src_db}_to_{tgt_db}" / "error_cases.txt"
            
            if path.exists():
                return path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            pass
        return ""
    
    # ─── H-1: 의존성 분석 ──────────────────────────────────────────
    def _h1_resolve_dependencies(self, ddl_map: Dict, objects: Dict) -> List[Dict]:
        """의존성 그래프 → 안전한 실행 순서"""
        try:
            from app.core.dependency_resolver import resolve_object_order
            
            # ddl_map → 카테고리별 dict
            functions = {}
            procedures = {}
            views = {}
            triggers = {}
            
            for name, info in ddl_map.items():
                t = info['type']
                ddl = info['converted_ddl']
                if t == 'function':
                    functions[name] = ddl
                elif t == 'procedure':
                    procedures[name] = ddl
                elif t == 'view':
                    views[name] = ddl
                elif t == 'trigger':
                    triggers[name] = ddl
            
            # 알려진 테이블 (의존성 타겟)
            known_tables = self._get_target_tables()
            
            result = resolve_object_order(
                table_names=known_tables,
                functions=functions,
                procedures=procedures,
                views=views,
                triggers=triggers,
            )
            
            # 테이블은 이미 이관됐으니 제외
            ordered = [
                {
                    'name': obj.name,
                    'type': obj.object_type.value,
                    'ddl': ddl_map[obj.name]['converted_ddl'],
                    'original_ddl': ddl_map[obj.name]['original_ddl'],
                }
                for obj in result.ordered
                if obj.object_type.value != 'table' and obj.name in ddl_map
            ]
            
            if result.cycles:
                self._log("warn", f"[Phase H-1] 순환 참조 {len(result.cycles)}건 감지")
            
            return ordered
        except Exception as e:
            _log.warning(f"[Phase H-1] 의존성 분석 실패: {e}", exc_info=True)
            return []
    
    def _get_target_tables(self) -> List[str]:
        """타겟 DB 의 기존 테이블 목록"""
        try:
            cur = self.tgt_conn.cursor()
            cur.execute("SHOW TABLES")
            return [row[0] for row in cur.fetchall()]
        except Exception:
            return []
    
    # ─── H-2: DDL 사전 검증 ─────────────────────────────────────────
    def _h2_validate_and_fix(self, ordered: List[Dict]) -> List[Dict]:
        """DDL 사전 검증 + auto-fix 적용"""
        try:
            from app.core.ddl_preflight_validator import validate_ddl
            
            validated = []
            for obj in ordered:
                result = validate_ddl(
                    obj['ddl'],
                    obj['name'],
                    obj['type'],
                    enable_auto_fix=True,
                )
                
                # auto-fix 적용
                if result.fixed_ddl:
                    obj['ddl'] = result.fixed_ddl
                    self._log("info", 
                        f"[Phase H-2] {obj['name']}: auto-fix 적용"
                    )
                
                # 검증 결과 첨부 (재시도 시 활용)
                obj['_validation'] = {
                    'can_proceed': result.can_proceed,
                    'has_errors': result.has_errors,
                    'has_warnings': result.has_warnings,
                    'issues': [
                        {'rule': i.rule_id, 'level': i.level.value, 'title': i.title}
                        for i in result.issues
                    ],
                }
                
                validated.append(obj)
            
            return validated
        except Exception as e:
            _log.warning(f"[Phase H-2] 사전 검증 실패: {e}", exc_info=True)
            return ordered
    
    def _summarize_validation(self, objs: List[Dict]) -> Dict:
        return {
            'total': len(objs),
            'can_proceed': sum(1 for o in objs 
                              if o.get('_validation', {}).get('can_proceed', True)),
            'auto_fixed': sum(1 for o in objs if 'auto-fix' in str(o)),
            'with_errors': sum(1 for o in objs 
                              if o.get('_validation', {}).get('has_errors')),
        }
    
    # ─── H-3: 스마트 재시도 실행 ────────────────────────────────────
    def _h3_execute_with_retry(self, validated: List[Dict]):
        """스마트 재시도 엔진으로 실행"""
        from app.core.smart_retry_engine import SmartRetryEngine
        
        # Executor: 실제 DDL 실행
        def executor(name, obj_type, ddl):
            return self._execute_ddl(name, obj_type, ddl)
        
        # Regenerator: AI 재변환 (H-4 강화 prompt 사용)
        def regenerator(name, obj_type, old_ddl, error):
            return self._convert_with_ai(name, obj_type, old_ddl)
        
        engine = SmartRetryEngine(
            executor=executor,
            regenerator=regenerator,
            max_attempts=3,
            retry_delay_sec=0.2,
        )
        
        # 진행 상황 콜백
        def on_progress(name, status):
            self._log("info", f"[Phase H-3] {name}: {status}")
        
        return engine.run(validated, on_progress=on_progress)
    
    def _execute_ddl(self, name: str, obj_type: str, ddl: str) -> Tuple[bool, Optional[str]]:
        """타겟 DB 에 DDL 실행"""
        try:
            cur = self.tgt_conn.cursor()
            cur.execute(ddl)
            try:
                self.tgt_conn.commit()
            except Exception:
                pass
            return True, None
        except Exception as e:
            return False, str(e)
    
    # ─── 로깅 + 리포팅 ──────────────────────────────────────────────
    def _log(self, level: str, msg: str):
        """migration_engine 의 _log 사용 (있으면)"""
        if hasattr(self.engine, '_log'):
            self.engine._log(level, msg)
        else:
            getattr(_log, level, _log.info)(msg)
    
    def _log_final_report(self, report, duration: float):
        """최종 리포트 로그"""
        from app.core.smart_retry_engine import format_retry_report
        
        report_text = format_retry_report(report)
        for line in report_text.split('\n'):
            self._log("info", line)
        
        # 핵심 지표만 한 번 더 강조
        self._log("info", "")
        self._log("info", f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self._log("info", f"  Phase H 첫 이관 성공률 모드 결과")
        self._log("info", f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self._log("info", f"    📊 첫 시도 성공률: {report.first_try_success_rate}%")
        self._log("info", f"    📊 최종 성공률:    {report.final_success_rate}%")
        self._log("info", f"    🔄 자동 복구:      {report.auto_recovered}건")
        self._log("info", f"    ❌ 최종 실패:      {report.failed}건")
        self._log("info", f"    ⏱️ 소요 시간:      {duration}초")
        self._log("info", f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


# ════════════════════════════════════════════════════════════════════════════
# 헬퍼: 외부 호출용
# ════════════════════════════════════════════════════════════════════════════

def get_phase_h_status(job: dict) -> dict:
    """UI/로그에 표시할 Phase H 상태"""
    enabled = job.get('phase_h_enabled')
    if enabled is None:
        env_val = os.environ.get('DATABRIDGE_PHASE_H', '').lower()
        enabled = env_val in ('true', '1', 'yes', 'on')
    
    report = job.get('phase_h_report', {})
    
    return {
        'enabled': bool(enabled),
        'report': report,
        'has_report': bool(report),
    }
