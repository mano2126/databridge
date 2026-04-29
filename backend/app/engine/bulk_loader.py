"""
app/engine/bulk_loader.py
============================================================
대용량 이관을 위한 bulk-load 로더 추상화 (v9 패치 #20)

목적
----
기존 pyodbc.executemany() 방식은 초당 1천~5천 rows 수준으로
500만 행 이상의 테이블은 수 시간이 걸려 판매 제품으로 부적합.

본 모듈은 타겟 DB 에 맞춰 "진짜 bulk 프로토콜"을 사용하는
로더 플러그인 구조를 제공.

로더 종류
---------
1. ExecutemanyLoader   — 기존 방식 (pyodbc.executemany + fast_executemany)
2. MssqlBcpLoader      — MSSQL bcp.exe 외부 실행 (CSV 경유, 최고속)
3. MssqlPymssqlLoader  — pymssql bulk_copy (추가 설치 불필요 옵션)
4. MysqlLoadDataLoader — MySQL LOAD DATA LOCAL INFILE (역방향 이관용)
5. 향후: PgCopyFromLoader 등

선택 전략
---------
- 테이블 행수 < BULK_THRESHOLD (기본 10만) → Executemany
- 타겟=MSSQL, 그 이상                        → BCP → 폴백 pymssql → 폴백 Executemany
- 타겟=MySQL, 그 이상                        → LOAD DATA LOCAL INFILE → 폴백 Executemany
- job.bulk_mode 설정으로 강제 지정 가능: "auto" | "executemany" | "bcp" | "pymssql" | "mysql_load"

모든 로더는 load() 메서드 구현. 반환값: 삽입 성공 행수.
실패 시 예외를 올리고 상위(migration_engine) 가 폴백 또는 오류 처리.
"""
from __future__ import annotations
import os
import csv
import time
import shutil
import tempfile
import subprocess
from abc import ABC, abstractmethod
from typing import Iterable, Sequence, Callable, Optional, List, Tuple, Any


# ─────────────────────────────────────────────────────────────
# 공통 타입
# ─────────────────────────────────────────────────────────────
LogSink = Callable[[str, str], None]   # (level, msg) -> None


class BulkLoadError(Exception):
    """Bulk 로더가 실패했지만 상위에서 fallback 가능한 예외"""
    pass


class BulkLoadFatal(Exception):
    """복구 불가능한 오류 — fallback 해도 의미 없음"""
    pass


# ─────────────────────────────────────────────────────────────
# 추상 베이스
# ─────────────────────────────────────────────────────────────
class BaseBulkLoader(ABC):
    """
    배치 한 개 (rows) 를 타겟에 적재.
    """
    name: str = "base"

    def __init__(self, table: str, col_names: List[str],
                 tgt_conn, log: Optional[LogSink] = None,
                 job_opts: Optional[dict] = None,
                 stop_check: Optional[callable] = None):
        self.table = table
        self.col_names = col_names
        self.tgt_conn = tgt_conn
        self._log = log or (lambda lv, m: None)
        self.opts = job_opts or {}
        # v9 패치 #33: 중단 체크 콜백 — True 반환 시 현재 작업 중단
        self._stop_check = stop_check or (lambda: False)

    @abstractmethod
    def load(self, rows: Sequence[Tuple[Any, ...]]) -> int:
        """rows 를 테이블에 INSERT. 삽입 성공 행수 반환."""
        ...

    # 선택적: 로더 초기화/정리 훅
    def open(self) -> None:
        pass

    def close(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────
# 1) ExecutemanyLoader — 기존 방식 (호환 + 소용량 기본)
# ─────────────────────────────────────────────────────────────
class ExecutemanyLoader(BaseBulkLoader):
    """
    pyodbc/pymysql 표준 executemany.
    pyodbc 는 fast_executemany=True 로 Parameter Array 최적화 활성.
    소용량 or BULK 로더 폴백 시 사용.
    """
    name = "executemany"

    def __init__(self, *a, insert_sql: str, tgt_is_mssql: bool = False, **kw):
        super().__init__(*a, **kw)
        self.insert_sql = insert_sql
        self.tgt_is_mssql = tgt_is_mssql
        self._cur = None  # v9 패치 #24: lazy init 지원

    def open(self) -> None:
        if self._cur is None:
            self._cur = self.tgt_conn.cursor()
            if self.tgt_is_mssql:
                try:
                    self._cur.fast_executemany = True
                except Exception:
                    pass

    def load(self, rows):
        if not rows:
            return 0
        # v9 패치 #24: open() 누락 방어 — lazy init
        if self._cur is None:
            self.open()
        self._cur.executemany(self.insert_sql, list(rows))
        self.tgt_conn.commit()
        return len(rows)

    def close(self):
        try:
            if self._cur is not None:
                self._cur.close()
        except Exception:
            pass
        self._cur = None


# ─────────────────────────────────────────────────────────────
# 2) MssqlBcpLoader — bcp.exe 외부 프로세스 (최고 속도)
# ─────────────────────────────────────────────────────────────
class MssqlBcpLoader(BaseBulkLoader):
    """
    MSSQL bcp 명령어를 이용한 bulk load.
    - 임시 디렉토리에 쿼리별 CSV 작성
    - bcp <db>.dbo.<table> in <file> -c -t<fs> -r<rs> -S <server> -U -P ...
    - TDS encoding 문제 피하려고 -w (unicode) 사용
    - 성능: 초당 5~30만 rows 가능

    필요 조건
    ---------
    - bcp.exe 가 PATH 에 있거나 cfg.bcp_path 에 경로 지정
    - MSSQL 타겟 연결 정보(host/port/user/pw/db) 가 opts 에 있음
    """
    name = "bcp"

    # 기본 필드/행 구분자 (CSV 보다 안전하게 탭 + 레코드 구분자)
    FIELD_SEP = "\x1f"   # Unit Separator (ASCII 31)
    ROW_SEP   = "\x1e\n" # Record Separator (ASCII 30) + \n

    def __init__(self, *a, tgt_host: str, tgt_port: int, tgt_user: str,
                 tgt_password: str, tgt_database: str,
                 bcp_path: Optional[str] = None, **kw):
        super().__init__(*a, **kw)
        self.tgt_host = tgt_host
        self.tgt_port = int(tgt_port or 1433)
        self.tgt_user = tgt_user
        self.tgt_password = tgt_password
        self.tgt_database = tgt_database
        self.bcp_path = bcp_path or self._detect_bcp()

    @staticmethod
    def _detect_bcp() -> Optional[str]:
        """bcp.exe 가 PATH 또는 표준 위치에 있는지 확인."""
        for cand in ("bcp", "bcp.exe"):
            p = shutil.which(cand)
            if p:
                return p
        for p in (
            r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn\bcp.exe",
            r"C:\Program Files\Microsoft SQL Server\160\Tools\Binn\bcp.exe",
            r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\180\Tools\Binn\bcp.exe",
            "/opt/mssql-tools18/bin/bcp",
            "/opt/mssql-tools/bin/bcp",
        ):
            if os.path.isfile(p):
                return p
        return None

    def open(self) -> None:
        if not self.bcp_path:
            raise BulkLoadError("bcp 실행파일을 찾을 수 없음 (PATH 에 bcp.exe 또는 cfg.bcp_path 설정 필요)")

    def load(self, rows):
        if not rows:
            return 0
        # 1) 임시 CSV 작성 (UTF-16LE, BCP 친화적)
        tmpdir = tempfile.mkdtemp(prefix="dbbridge_bcp_")
        data_file = os.path.join(tmpdir, f"{self.table}.dat")
        try:
            # BCP -w (wide unicode, UTF-16LE BOM 포함)
            # v9 패치 #29: 파일 버퍼 크기 증가 (기본 8KB → 1MB) - 대배치에서 I/O 감소
            with open(data_file, "w", encoding="utf-16", newline="", buffering=1024*1024) as f:
                # 리스트 추가 후 한 번에 write 하는 게 반복 write 보다 빠름
                lines = []
                for r in rows:
                    out_vals = [_bcp_stringify(v) for v in r]
                    lines.append(self.FIELD_SEP.join(out_vals))
                f.write(self.ROW_SEP.join(lines))
                f.write(self.ROW_SEP)  # 마지막 ROW_SEP

            # 2) bcp 실행
            # v9 패치 #35: BCP 힌트 수정
            #   -b 옵션과 -h ROWS_PER_BATCH 힌트는 **같이 쓸 수 없음** (MS 문서)
            #   → ROWS_PER_BATCH 제거, TABLOCK 만 유지
            #   -a 65535: TDS 패킷 크기 최대 (네트워크 효율 ↑)
            #   -h TABLOCK: 최소 로깅 (BULK_LOGGED recovery model 에서 효과)
            cmd = [
                self.bcp_path,
                f"[{self.tgt_database}].[dbo].[{self.table}]",
                "in",
                data_file,
                "-w",                                  # UTF-16LE unicode
                f"-t{self.FIELD_SEP}",                 # 필드 구분자
                f"-r{self.ROW_SEP}",                   # 레코드 구분자
                "-S", f"{self.tgt_host},{self.tgt_port}",
                "-U", self.tgt_user,
                "-P", self.tgt_password,
                "-b", str(len(rows)),                  # 배치 크기 = 전체 (단일 트랜잭션)
                "-a", "65535",                         # TDS 패킷 크기 (v9 #29)
                "-h", "TABLOCK",                       # 최소 로깅 힌트
                "-e", os.path.join(tmpdir, "err.log"),
                "-C", "65001",                         # 코드 페이지 UTF-8 (참고용)
            ]

            # 드라이버 TLS 검증 우회 필요 시 사용자 환경에 맞게 -u 같은 옵션 추가 가능
            # v9 패치 #33: subprocess.run → Popen 으로 변경 — 중단 체크 가능
            # v9 패치 #43: stdout/stderr 를 PIPE 가 아닌 파일로 리다이렉트 (deadlock 방지)
            # 대용량 BCP 는 수MB 의 로그를 출력 → PIPE 버퍼 (~64KB) 꽉 차면 BCP 가 write block
            # → Python proc.wait() 도 무한 대기 (pipe buffer deadlock)
            _stdout_path = os.path.join(tmpdir, "bcp.stdout")
            _stderr_path = os.path.join(tmpdir, "bcp.stderr")
            _fout = open(_stdout_path, "wb")
            _ferr = open(_stderr_path, "wb")
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=_fout,
                    stderr=_ferr,
                )
                # 0.5초마다 stop_check 확인하며 BCP 완료 대기
                _bcp_timeout = 3600
                _start = time.monotonic()
                while True:
                    try:
                        # 0.5초씩 대기, 완료되면 빠져나옴
                        proc.wait(timeout=0.5)
                        break
                    except subprocess.TimeoutExpired:
                        # 중단 요청 확인
                        if self._stop_check():
                            self._log("warn", f"  [{self.table}] BCP 중단 요청 — 프로세스 kill")
                            try:
                                proc.kill()
                            except Exception:
                                pass
                            try:
                                proc.wait(timeout=5)
                            except Exception:
                                pass
                            raise BulkLoadError("BCP 중단됨 (사용자 요청)")
                        # 타임아웃 체크
                        if time.monotonic() - _start > _bcp_timeout:
                            try: proc.kill()
                            except: pass
                            raise BulkLoadError(f"BCP 타임아웃 ({_bcp_timeout}s 초과)")
            finally:
                try: _fout.close()
                except: pass
                try: _ferr.close()
                except: pass
            # 결과 수집 - 파일에서 읽음
            try:
                with open(_stdout_path, "rb") as f: _out = f.read()
            except Exception: _out = b""
            try:
                with open(_stderr_path, "rb") as f: _err = f.read()
            except Exception: _err = b""
            if proc.returncode != 0:
                err_tail = (_err or b"").decode("utf-8", errors="replace")[-400:]
                out_tail = (_out or b"").decode("utf-8", errors="replace")[-400:]
                raise BulkLoadError(
                    f"bcp 실패 rc={proc.returncode}: {err_tail or out_tail}"
                )
            # 파싱: "xxxxx rows copied." 추출
            out = (_out or b"").decode("utf-8", errors="replace")
            copied = _parse_bcp_copied(out)
            return copied if copied > 0 else len(rows)
        finally:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


def _bcp_stringify(v) -> str:
    """BCP 데이터 파일용 값 변환."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (bytes, bytearray)):
        # VARBINARY → 0x 헥사 문자열
        return "0x" + v.hex().upper()
    s = str(v)
    # 구분자 문자 제거 (혹시 데이터에 포함되어 있으면 공백으로)
    if "\x1f" in s or "\x1e" in s:
        s = s.replace("\x1f", " ").replace("\x1e", " ")
    return s


def _parse_bcp_copied(stdout: str) -> int:
    import re
    m = re.search(r"(\d+)\s+rows\s+copied", stdout, re.IGNORECASE)
    return int(m.group(1)) if m else 0


# ─────────────────────────────────────────────────────────────
# 3) MssqlPymssqlLoader — pymssql 네이티브 BULK INSERT
# ─────────────────────────────────────────────────────────────
class MssqlPymssqlLoader(BaseBulkLoader):
    """
    pymssql 의 네이티브 BULK INSERT (TDS bcp_init/bcp_bind/bcp_sendrow).

    v9 패치 #23: 실제 bulk 경로 구현
    - 1차: _mssql.MSSQLConnection.bulk_copy() 시도 (pymssql 저수준)
    - 2차: cursor.execute("SET FMTONLY OFF") + executemany (폴백)

    - 장점: 외부 bcp.exe 불필요, 메모리 직접 전송
    - 단점: pymssql 필요, 성능은 BCP 보다 낮음
    - 성능: 초당 1만~5만 rows
    """
    name = "pymssql_bulk"

    def __init__(self, *a, tgt_host: str, tgt_port: int, tgt_user: str,
                 tgt_password: str, tgt_database: str, **kw):
        super().__init__(*a, **kw)
        self.tgt_host = tgt_host
        self.tgt_port = int(tgt_port or 1433)
        self.tgt_user = tgt_user
        self.tgt_password = tgt_password
        self.tgt_database = tgt_database
        self._pm_conn = None
        self._use_native_bulk = False

    def open(self) -> None:
        try:
            import pymssql
        except ImportError:
            raise BulkLoadError("pymssql 패키지가 설치되어 있지 않음 — pip install pymssql")
        try:
            self._pm_conn = pymssql.connect(
                server=self.tgt_host, port=str(self.tgt_port),
                user=self.tgt_user, password=self.tgt_password,
                database=self.tgt_database, charset="UTF-8",
                tds_version="7.4",
                autocommit=True,
            )
        except Exception as e:
            raise BulkLoadError(f"pymssql 연결 실패: {e}")

        # 네이티브 bulk 가용성 확인 — _mssql 모듈에 bulk_copy 있는지
        try:
            inner = getattr(self._pm_conn, "_conn", None)  # _mssql.MSSQLConnection
            if inner is not None and hasattr(inner, "bulk_insert"):
                self._use_native_bulk = True
        except Exception:
            self._use_native_bulk = False

    def load(self, rows):
        if not rows:
            return 0
        if self._pm_conn is None:
            self.open()

        # 네이티브 bulk_insert 시도
        if self._use_native_bulk:
            try:
                inner = self._pm_conn._conn  # _mssql.MSSQLConnection
                # _mssql.MSSQLConnection.bulk_insert(table, rows) — 컬럼 순서대로 튜플 리스트
                inner.bulk_insert(self.table, [tuple(r) for r in rows])
                return len(rows)
            except Exception as _be:
                # 네이티브 실패 → executemany 폴백
                if self._log:
                    self._log("debug", f"pymssql native bulk 실패, executemany 폴백: {_be}")
                self._use_native_bulk = False

        # 폴백: executemany (ParameterArray)
        cur = self._pm_conn.cursor()
        try:
            placeholders = ", ".join(["%s"] * len(self.col_names))
            cols = ", ".join([f"[{c}]" for c in self.col_names])
            sql = f"INSERT INTO [{self.table}] ({cols}) VALUES ({placeholders})"
            cur.executemany(sql, [tuple(r) for r in rows])
            return len(rows)
        finally:
            try: cur.close()
            except: pass

    def close(self):
        try:
            if self._pm_conn is not None:
                self._pm_conn.close()
        except Exception:
            pass
        self._pm_conn = None


# ─────────────────────────────────────────────────────────────
# 4) MysqlLoadDataLoader — MySQL LOAD DATA LOCAL INFILE
#    역방향 이관 (MSSQL → MySQL) 대용량 처리용 (v10 패치 #1)
# ─────────────────────────────────────────────────────────────
class MysqlLoadDataLoader(BaseBulkLoader):
    """
    MySQL LOAD DATA LOCAL INFILE 를 이용한 bulk load.
    - 임시 디렉토리에 쿼리별 TSV 작성 (UTF-8)
    - LOAD DATA LOCAL INFILE '<file>' INTO TABLE ... 로 스트리밍 업로드
    - 성능: 초당 10~50만 rows (네트워크/디스크 의존)

    필요 조건
    ---------
    - MySQL 서버:   SET GLOBAL local_infile=1  (대개 기본 OFF)
    - 클라이언트:   pymysql.connect(local_infile=True)  ← 이 로더가 자체 연결

    설계 근거
    --------
    BCP 로더와 동일 패턴:
      - 외부 tgt_conn 을 건드리지 않고 로더 전용 연결을 새로 생성
      - 임시 데이터 파일에 써서 한 번에 전송 (파일 I/O + 네트워크 I/O 분리)
      - stop_check 로 중단 가능
    """
    name = "mysql_load"

    # BCP 와 동일 — 데이터에 탭/콤마가 섞여도 안전하게
    FIELD_SEP = "\x1f"   # Unit Separator (ASCII 31)
    ROW_SEP   = "\x1e\n" # Record Separator (ASCII 30) + \n
    NULL_MARK = "\\N"    # MySQL 표준 NULL 표기

    def __init__(self, *a, tgt_host: str, tgt_port: int, tgt_user: str,
                 tgt_password: str, tgt_database: str, **kw):
        super().__init__(*a, **kw)
        self.tgt_host = tgt_host
        self.tgt_port = int(tgt_port or 3306)
        self.tgt_user = tgt_user
        self.tgt_password = tgt_password
        self.tgt_database = tgt_database
        self._my_conn = None          # 로더 전용 pymysql 연결

    def open(self) -> None:
        """로더 전용 pymysql 연결 (local_infile=True) 생성.
        local_infile 은 클라이언트와 서버 양쪽에서 켜져야 동작.
        서버쪽 SET 은 권한 필요 → 여기선 클라이언트 플래그만 켜고,
        서버 쪽 OFF 인 경우 load() 에서 예외 잡아 BulkLoadError 로 올림.
        """
        try:
            import pymysql
        except Exception as e:
            raise BulkLoadError(f"pymysql 모듈 로드 실패: {e}")
        try:
            self._my_conn = pymysql.connect(
                host=self.tgt_host, port=self.tgt_port,
                user=self.tgt_user, password=self.tgt_password,
                database=self.tgt_database,
                charset="utf8mb4",
                connect_timeout=15,
                local_infile=True,                  # ★ 핵심 플래그
                autocommit=False,
            )
        except Exception as e:
            raise BulkLoadError(f"MySQL 연결 실패 (local_infile): {e}")

    def load(self, rows):
        if not rows:
            return 0
        if self._my_conn is None:
            raise BulkLoadError("로더가 open() 되지 않음")

        # 1) 임시 TSV 작성 (UTF-8)
        tmpdir = tempfile.mkdtemp(prefix="dbbridge_mysqlload_")
        data_file = os.path.join(tmpdir, f"{self.table}.dat")
        try:
            with open(data_file, "w", encoding="utf-8", newline="",
                      buffering=1024 * 1024) as f:
                lines = []
                for r in rows:
                    out_vals = [_mysql_load_stringify(v) for v in r]
                    lines.append(self.FIELD_SEP.join(out_vals))
                f.write(self.ROW_SEP.join(lines))
                f.write(self.ROW_SEP)

            # 2) 중단 체크 (파일 쓴 직후)
            if self._stop_check():
                raise BulkLoadError("MySQL LOAD DATA 중단됨 (사용자 요청)")

            # 3) LOAD DATA LOCAL INFILE 실행
            # FIELDS TERMINATED BY + LINES TERMINATED BY 를 FIELD/ROW SEP 로
            # ESCAPED BY '' : 역슬래시 해석 비활성 → \N 은 우리가 명시적으로 NULL_MARK 로 처리
            # SET foreign_key_checks=0 / unique_checks=0 / autocommit=0 → InnoDB 벌크 최적화
            col_list = ", ".join([f"`{c}`" for c in self.col_names])
            # 파일 경로: Windows 백슬래시 → 슬래시 (MySQL 파서가 이스케이프 오해 방지)
            posix_path = data_file.replace("\\", "/")
            sql = (
                f"LOAD DATA LOCAL INFILE '{posix_path}' "
                f"INTO TABLE `{self.table}` "
                f"CHARACTER SET utf8mb4 "
                f"FIELDS TERMINATED BY 0x1F ESCAPED BY '' "
                f"LINES TERMINATED BY 0x1E0A "
                f"({col_list})"
            )

            cur = self._my_conn.cursor()
            try:
                # 세션 힌트 — 실패해도 무시 (권한 없어도 치명적 아님)
                for hint in (
                    "SET foreign_key_checks=0",
                    "SET unique_checks=0",
                    "SET sql_log_bin=0",          # 바이너리 로그 부담 제거 (권한 없으면 무시됨)
                ):
                    try:
                        cur.execute(hint)
                    except Exception:
                        pass

                # 본 명령
                affected = cur.execute(sql)
                self._my_conn.commit()
                # pymysql cur.execute 는 영향 행수 반환 — LOAD DATA 는 삽입 행수
                copied = int(affected or 0)
                return copied if copied > 0 else len(rows)
            except Exception as e:
                try: self._my_conn.rollback()
                except Exception: pass
                msg = str(e)
                # 서버 쪽 local_infile 꺼진 경우의 전형적 메시지
                if "used command is not allowed" in msg.lower() \
                   or "local_infile" in msg.lower():
                    raise BulkLoadError(
                        f"MySQL 서버에서 LOCAL INFILE 비활성 "
                        f"(SET GLOBAL local_infile=1 필요): {msg}"
                    )
                raise BulkLoadError(f"LOAD DATA 실패: {msg}")
            finally:
                try: cur.close()
                except Exception: pass
        finally:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def close(self):
        try:
            if self._my_conn is not None:
                self._my_conn.close()
        except Exception:
            pass
        self._my_conn = None


def _mysql_load_stringify(v) -> str:
    """LOAD DATA 파일용 값 변환.

    MySQL LOAD DATA 규칙:
      - NULL  → \\N (ESCAPED BY '' 인 상태에서도 \\N 은 여전히 NULL 로 해석됨)
      - bool  → 0/1
      - bytes → hex 문자열 0x... (BLOB 컬럼이면 UNHEX 필요 — 아래 경고 참고)
      - 그 외 → str(v), 구분자 문자는 공백으로 치환

    주의: VARBINARY/BLOB 컬럼으로의 직접 LOAD 는 이진 안전하지 않음.
          이 경우 상위 로직에서 hex 문자열로 보낸 후, CREATE 단계에서
          컬럼을 TEXT 로 매핑하거나, 해당 테이블은 executemany 폴백을 써야 함.
          (현재 정책: _create_mysql_table 에서 varbinary → LONGBLOB 로 매핑되므로
           이진 데이터가 많은 테이블은 executemany 로 우회 권장)
    """
    if v is None:
        return "\\N"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (bytes, bytearray)):
        # BLOB 직접 삽입 시 데이터 무결성 이슈 — 상위에서 executemany 폴백 권장
        return "0x" + v.hex().upper()
    s = str(v)
    # 필드/레코드 구분자와 충돌 방지
    if "\x1f" in s or "\x1e" in s:
        s = s.replace("\x1f", " ").replace("\x1e", " ")
    # NULL 표기 충돌 방지: 데이터값 "\N" 이 진짜로 들어오는 경우는 극히 드물지만
    # 명시적으로 이스케이프 해준다 (ESCAPED BY '' 라서 역슬래시를 그대로 저장)
    # → 사용자 데이터 "\N" 은 "\\N" 두 글자 그대로 저장됨
    # MySQL 은 ESCAPED BY '' + 셀 내용이 정확히 "\N" 인 경우에만 NULL 로 해석
    if s == "\\N":
        s = "\\\\N"
    return s


# ─────────────────────────────────────────────────────────────
# 팩토리
# ─────────────────────────────────────────────────────────────
def create_loader(
    *, mode: str,
    table: str, col_names: List[str], tgt_conn,
    tgt_is_mssql: bool,
    insert_sql: str,
    log: Optional[LogSink] = None,
    job: Optional[dict] = None,
    row_count: Optional[int] = None,
    stop_check: Optional[callable] = None,
    tgt_is_mysql: bool = False,
) -> BaseBulkLoader:
    """
    mode 값:
      auto         — row_count 기준 자동 선택
      executemany  — 기존 방식 강제
      bcp          — MSSQL BCP 강제 (타겟 MSSQL 한정)
      pymssql      — pymssql bulk 강제 (타겟 MSSQL 한정)
      mysql_load   — MySQL LOAD DATA LOCAL INFILE 강제 (타겟 MySQL 한정)

    실패 시: BulkLoadError 를 올려 상위가 fallback 결정.

    v9  패치 #33: stop_check — True 반환 시 로더가 진행 중 중단
    v10 패치 #1 : tgt_is_mysql 플래그 + MysqlLoadDataLoader (역방향 이관)
                 하위호환 — 기존 호출부는 tgt_is_mysql 미지정 → False 취급
    """
    mode = (mode or "auto").lower()
    BULK_THRESHOLD = int((job or {}).get("bulk_threshold_rows", 100_000))

    if mode == "auto":
        if tgt_is_mssql and (row_count or 0) >= BULK_THRESHOLD:
            # 우선순위: bcp > pymssql > executemany
            try:
                return _build_mssql_bcp(table, col_names, tgt_conn, log, job, stop_check)
            except BulkLoadError as e:
                if log: log("warn", f"[{table}] BCP 불가 ({e}) → pymssql 시도")
            try:
                return _build_mssql_pymssql(table, col_names, tgt_conn, log, job, stop_check)
            except BulkLoadError as e:
                if log: log("warn", f"[{table}] pymssql 불가 ({e}) → executemany 폴백")
        if tgt_is_mysql and (row_count or 0) >= BULK_THRESHOLD:
            # 우선순위: mysql_load > executemany
            try:
                return _build_mysql_load(table, col_names, tgt_conn, log, job, stop_check)
            except BulkLoadError as e:
                if log: log("warn", f"[{table}] MySQL LOAD DATA 불가 ({e}) → executemany 폴백")
        # 기본
        return ExecutemanyLoader(
            table=table, col_names=col_names, tgt_conn=tgt_conn, log=log,
            insert_sql=insert_sql, tgt_is_mssql=tgt_is_mssql, job_opts=job,
            stop_check=stop_check,
        )

    if mode == "executemany":
        return ExecutemanyLoader(
            table=table, col_names=col_names, tgt_conn=tgt_conn, log=log,
            insert_sql=insert_sql, tgt_is_mssql=tgt_is_mssql, job_opts=job,
            stop_check=stop_check,
        )

    if mode == "bcp":
        if not tgt_is_mssql:
            raise BulkLoadError("BCP 는 MSSQL 타겟에서만 사용 가능")
        return _build_mssql_bcp(table, col_names, tgt_conn, log, job, stop_check)

    if mode == "pymssql":
        if not tgt_is_mssql:
            raise BulkLoadError("pymssql 로더는 MSSQL 타겟에서만 사용 가능")
        return _build_mssql_pymssql(table, col_names, tgt_conn, log, job, stop_check)

    if mode == "mysql_load":
        if not tgt_is_mysql:
            raise BulkLoadError("mysql_load 는 MySQL 타겟에서만 사용 가능")
        return _build_mysql_load(table, col_names, tgt_conn, log, job, stop_check)

    raise BulkLoadError(f"알 수 없는 bulk_mode: {mode}")


def _build_mssql_bcp(table, col_names, tgt_conn, log, job, stop_check=None) -> MssqlBcpLoader:
    j = job or {}
    loader = MssqlBcpLoader(
        table=table, col_names=col_names, tgt_conn=tgt_conn, log=log, job_opts=j,
        stop_check=stop_check,
        tgt_host=j.get("tgt_host",""), tgt_port=j.get("tgt_port",1433),
        tgt_user=j.get("tgt_username",""), tgt_password=j.get("tgt_password",""),
        tgt_database=j.get("tgt_database",""),
        bcp_path=j.get("bcp_path"),
    )
    loader.open()
    return loader


def _build_mssql_pymssql(table, col_names, tgt_conn, log, job, stop_check=None) -> MssqlPymssqlLoader:
    j = job or {}
    loader = MssqlPymssqlLoader(
        table=table, col_names=col_names, tgt_conn=tgt_conn, log=log, job_opts=j,
        stop_check=stop_check,
        tgt_host=j.get("tgt_host",""), tgt_port=j.get("tgt_port",1433),
        tgt_user=j.get("tgt_username",""), tgt_password=j.get("tgt_password",""),
        tgt_database=j.get("tgt_database",""),
    )
    loader.open()
    return loader


def _build_mysql_load(table, col_names, tgt_conn, log, job, stop_check=None) -> MysqlLoadDataLoader:
    """MySQL LOAD DATA LOCAL INFILE 로더 빌더 (v10 패치 #1)"""
    j = job or {}
    loader = MysqlLoadDataLoader(
        table=table, col_names=col_names, tgt_conn=tgt_conn, log=log, job_opts=j,
        stop_check=stop_check,
        tgt_host=j.get("tgt_host",""), tgt_port=j.get("tgt_port", 3306),
        tgt_user=j.get("tgt_username",""), tgt_password=j.get("tgt_password",""),
        tgt_database=j.get("tgt_database",""),
    )
    loader.open()
    return loader
