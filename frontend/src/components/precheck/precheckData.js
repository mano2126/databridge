// ============================================================
// DataBridge 이관 전 사전점검 데이터 (풀 버전)
// ------------------------------------------------------------
// 최초 완전 구현: MSSQL → MySQL (100개 항목)
//   - DBA 실행용 SQL: 40개
//   - 네트워크 체크: 15개
//   - 권한 체크: 10개
//   - 방문 체크리스트: 35개
//
// 구조:
//   sqlBlocks      : [{ id, title, priority, target, description, sql, followUp? }]
//   networkChecks  : [{ id, title, description?, command, expected }]
//   permissionChecks: [{ id, title, target, description, sql }]
//   visitChecklist : [{ category, text, critical }]
// ============================================================

// ─────────────────────────────────────────────────────────
// 공통 체크리스트 (모든 이관에 공통)
// ─────────────────────────────────────────────────────────
const COMMON_VISIT_CHECKLIST = [
  // [사전 조율]
  { category: '사전 조율', text: '이관 담당 DBA 연락처 확보 (비상 연락 포함)', critical: true },
  { category: '사전 조율', text: '이관 가능 시간대 합의 (업무 외 시간, 주말)', critical: true },
  { category: '사전 조율', text: '이관 소요 시간 추정 및 다운타임 허용치 합의', critical: true },
  { category: '사전 조율', text: '롤백 시나리오 사전 합의 및 트리거 조건 명시', critical: true },
  { category: '사전 조율', text: '이관 후 정합성 검증 방법 합의 (row count, 샘플)', critical: true },
  { category: '사전 조율', text: 'Function/Procedure 수동 변환 범위 합의', critical: false },
  { category: '사전 조율', text: '고객사 보안팀 사전 승인 (DB 접근, VPN)', critical: true },
  { category: '사전 조율', text: '개인정보처리방침/컴플라이언스 검토 (필요 시)', critical: false },

  // [인프라]
  { category: '인프라', text: '이관 서버 접근 권한 (SSH/RDP) 계정 발급', critical: true },
  { category: '인프라', text: '소스/타겟 DB 방화벽 오픈 확인', critical: true },
  { category: '인프라', text: '이관 서버 사양 확인 (CPU 4+, RAM 8GB+, SSD)', critical: true },
  { category: '인프라', text: 'Python 3.11+ 설치 또는 설치 권한', critical: true },
  { category: '인프라', text: '임시 디스크 공간 확보 (소스 DB 크기의 2배 이상)', critical: true },
  { category: '인프라', text: '이관 서버 네트워크 안정성 (유선 필수, 무선 금지)', critical: true },
  { category: '인프라', text: 'NTP 시간 동기화 (소스/타겟/이관서버)', critical: false },

  // [이관 실행 중]
  { category: '이관 실행 중', text: '실시간 모니터링 담당자 지정', critical: true },
  { category: '이관 실행 중', text: '실패 시 즉시 연락 채널 (Slack/전화)', critical: true },
  { category: '이관 실행 중', text: 'UI Monitor 페이지 열어두고 진행률 확인', critical: true },
  { category: '이관 실행 중', text: '백엔드 로그 실시간 tail (비정상 에러 감시)', critical: false },
  { category: '이관 실행 중', text: '이관 중 소스 DB 쓰기 차단 (읽기 전용 모드)', critical: true },
]

// ─────────────────────────────────────────────────────────
// 조합: MSSQL → MySQL
// ─────────────────────────────────────────────────────────
const MSSQL_TO_MYSQL = {
  tabs: ['DBA 실행용 SQL', '네트워크 체크', '권한 체크', '방문 체크리스트'],

  // ═════════════════════════════════════════════════
  // DBA 실행용 SQL (40개)
  //   MySQL 타겟 측: 20개
  //   MSSQL 소스 측: 20개
  // ═════════════════════════════════════════════════
  sqlBlocks: [
    // ─── MySQL 타겟 (20개) ───
    {
      id: 'mysql-local-infile',
      title: 'MySQL LOCAL_INFILE 상태 확인',
      priority: 'critical',
      target: 'MySQL (타겟)',
      description: 'LOAD DATA LOCAL INFILE 은 DataBridge 의 고속 이관 경로. OFF 면 INSERT 방식으로 fallback 되어 5~10배 느려짐',
      sql: `SHOW VARIABLES LIKE 'local_infile';`,
      followUp: {
        condition: 'Value = OFF 로 나오면 DBA 에게 요청',
        note: '런타임 설정 (DB 재시작까지만 유지, 즉시 반영)',
        sql: `SET GLOBAL local_infile = 1;`,
        permanent: {
          note: '영구 설정 (my.cnf 의 [mysqld] 섹션, DB 재시작 필요)',
          sql: `[mysqld]
local_infile = 1`
        }
      }
    },
    {
      id: 'mysql-timeouts',
      title: 'MySQL 네트워크 타임아웃 변수',
      priority: 'critical',
      target: 'MySQL (타겟)',
      description: '대용량 LOAD DATA / 장시간 트랜잭션 중 연결 끊김 방지. 기본값 60초는 GB 단위 이관에서 부족',
      sql: `SHOW VARIABLES WHERE Variable_name IN (
  'net_read_timeout',
  'net_write_timeout',
  'wait_timeout',
  'interactive_timeout',
  'max_allowed_packet',
  'connect_timeout'
);`,
      followUp: {
        condition: '이관 기간 중 임시 상향 요청',
        note: '이관 완료 후 원복 가능 (세션 레벨도 가능)',
        sql: `SET GLOBAL net_read_timeout  = 600;
SET GLOBAL net_write_timeout = 600;
SET GLOBAL max_allowed_packet = 268435456;  -- 256 MB
SET GLOBAL wait_timeout = 28800;

-- 이관 완료 후 원복 예시
-- SET GLOBAL net_read_timeout  = 30;
-- SET GLOBAL net_write_timeout = 60;`
      }
    },
    {
      id: 'mysql-log-bin-trust-func',
      title: 'Function/Procedure 생성 권한 (SUPER 우회)',
      priority: 'critical',
      target: 'MySQL (타겟)',
      description: 'binary logging 활성 환경에서 Function/Procedure DDL 실행 시 SUPER 권한 필요. 이관 계정에 SUPER 가 없으면 에러 1419 발생',
      sql: `SHOW VARIABLES LIKE 'log_bin_trust_function_creators';`,
      followUp: {
        condition: 'OFF 이고 이관 계정에 SUPER 권한 없으면',
        note: '이관 기간 중에만 ON, 완료 후 원복 권장',
        sql: `SET GLOBAL log_bin_trust_function_creators = 1;

-- 이관 완료 후
-- SET GLOBAL log_bin_trust_function_creators = 0;`,
        permanent: {
          note: '영구 설정 (보안팀 리뷰 권장 — 신뢰되지 않은 Function 실행 위험)',
          sql: `[mysqld]
log_bin_trust_function_creators = 1`
        }
      }
    },
    {
      id: 'mysql-row-format',
      title: 'InnoDB 기본 행 포맷 (DYNAMIC 권장)',
      priority: 'warning',
      target: 'MySQL (타겟)',
      description: 'COMPACT 는 VARCHAR 많은 테이블에서 65535 byte 초과 시 1118 에러. DYNAMIC 은 긴 VARCHAR/TEXT 를 페이지 외부 저장하여 행 크기 제약 완화',
      sql: `SHOW VARIABLES LIKE 'innodb_default_row_format';`,
      followUp: {
        condition: 'COMPACT 면 DYNAMIC 으로 변경 권장',
        note: '기존 테이블에는 영향 없음. 새로 CREATE 되는 테이블에만 적용',
        sql: `SET GLOBAL innodb_default_row_format = 'DYNAMIC';`
      }
    },
    {
      id: 'mysql-version-edition',
      title: 'MySQL 버전 / 엔진 / 문자셋',
      priority: 'info',
      target: 'MySQL (타겟)',
      description: '버전별 기능 차이 (JSON, CTE, window function 등). 5.7 이하는 LOAD DATA 성능 낮음 — 8.0+ 권장',
      sql: `SELECT
  VERSION()                       AS mysql_version,
  @@version_compile_os            AS os_platform,
  @@default_storage_engine        AS default_engine,
  @@character_set_server          AS server_charset,
  @@character_set_database        AS db_charset,
  @@collation_server              AS server_collation,
  @@time_zone                     AS time_zone,
  @@sql_mode                      AS sql_mode;`
    },
    {
      id: 'mysql-innodb-settings',
      title: 'InnoDB 핵심 튜닝 변수',
      priority: 'info',
      target: 'MySQL (타겟)',
      description: 'Buffer pool 크기가 작으면 대용량 이관 시 디스크 I/O 병목. 최소 데이터의 50% 권장',
      sql: `SHOW VARIABLES WHERE Variable_name IN (
  'innodb_buffer_pool_size',
  'innodb_log_file_size',
  'innodb_log_buffer_size',
  'innodb_flush_log_at_trx_commit',
  'innodb_flush_method',
  'innodb_io_capacity',
  'innodb_doublewrite',
  'innodb_file_per_table'
);`
    },
    {
      id: 'mysql-max-connections',
      title: '동시 연결 한계',
      priority: 'warning',
      target: 'MySQL (타겟)',
      description: '이관 워커 수(MP 모드 4개) + 기존 애플리케이션 연결 수 합계가 max_connections 초과 시 실패',
      sql: `SHOW VARIABLES LIKE 'max_connections';
SHOW STATUS  LIKE 'Threads_connected';
SHOW STATUS  LIKE 'Max_used_connections';`
    },
    {
      id: 'mysql-sql-mode',
      title: 'sql_mode 설정 (STRICT / ZERO_DATE)',
      priority: 'warning',
      target: 'MySQL (타겟)',
      description: 'STRICT_TRANS_TABLES + NO_ZERO_DATE 있으면 MSSQL 의 0000-00-00 같은 값 INSERT 실패. 이관 기간 중 완화 고려',
      sql: `SELECT @@sql_mode;`,
      followUp: {
        condition: 'STRICT 또는 NO_ZERO_DATE 포함 시 이관 실패 가능',
        note: '이관 세션에만 sql_mode 제거 권장 (글로벌 변경은 신중)',
        sql: `-- 이관 세션에만 (DataBridge 가 연결 시 실행 가능)
SET SESSION sql_mode = '';

-- 또는 글로벌 (신중히)
-- SET GLOBAL sql_mode = 'NO_ENGINE_SUBSTITUTION';`
      }
    },
    {
      id: 'mysql-binlog-settings',
      title: 'Binary Log 상태 및 포맷',
      priority: 'info',
      target: 'MySQL (타겟)',
      description: 'binlog 활성 시 이관 속도 영향 (행마다 기록). 이관 기간 중 비활성 고려 (복제 환경 아니면)',
      sql: `SHOW VARIABLES WHERE Variable_name IN (
  'log_bin',
  'binlog_format',
  'sync_binlog',
  'binlog_row_image',
  'expire_logs_days',
  'binlog_expire_logs_seconds'
);`
    },
    {
      id: 'mysql-open-files',
      title: 'Open Files / Table Cache 한계',
      priority: 'warning',
      target: 'MySQL (타겟)',
      description: '수백 개 테이블 동시 이관 시 파일 핸들 부족 가능',
      sql: `SHOW VARIABLES LIKE 'open_files_limit';
SHOW VARIABLES LIKE 'table_open_cache';
SHOW STATUS    LIKE 'Open_tables';
SHOW STATUS    LIKE 'Opened_tables';`
    },
    {
      id: 'mysql-temp-tablespace',
      title: 'Temporary Tablespace / tmpdir',
      priority: 'info',
      target: 'MySQL (타겟)',
      description: 'ALTER TABLE / 인덱스 생성 시 임시 파일 사용. 용량 부족 시 실패',
      sql: `SHOW VARIABLES LIKE 'tmpdir';
SHOW VARIABLES LIKE 'innodb_temp_data_file_path';
SHOW VARIABLES LIKE 'tmp_table_size';
SHOW VARIABLES LIKE 'max_heap_table_size';`
    },
    {
      id: 'mysql-existing-tables',
      title: '타겟 DB 기존 테이블 / 뷰 / 프로시저',
      priority: 'info',
      target: 'MySQL (타겟)',
      description: '이관 전 기존 객체 확인. DataBridge 는 IF NOT EXISTS 로 만들지만 데이터 충돌 가능',
      sql: `SELECT
  TABLE_NAME,
  TABLE_TYPE,
  TABLE_ROWS,
  ROUND(DATA_LENGTH / 1024 / 1024, 2) AS size_mb,
  ROUND(INDEX_LENGTH / 1024 / 1024, 2) AS idx_mb,
  ENGINE,
  ROW_FORMAT,
  TABLE_COLLATION,
  CREATE_TIME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY DATA_LENGTH DESC;

-- 프로시저/함수
SELECT ROUTINE_TYPE, ROUTINE_NAME
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = DATABASE();

-- 트리거
SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE
FROM information_schema.TRIGGERS
WHERE TRIGGER_SCHEMA = DATABASE();`
    },
    {
      id: 'mysql-charset-collation',
      title: '데이터베이스 기본 charset / collation',
      priority: 'warning',
      target: 'MySQL (타겟)',
      description: 'utf8 (= utf8mb3) 은 3바이트 단위로 이모지/한자 확장문자 저장 불가. utf8mb4 권장',
      sql: `SELECT
  DEFAULT_CHARACTER_SET_NAME AS db_charset,
  DEFAULT_COLLATION_NAME     AS db_collation
FROM information_schema.SCHEMATA
WHERE SCHEMA_NAME = DATABASE();`,
      followUp: {
        condition: 'utf8 (= utf8mb3) 이면 utf8mb4 로 변경 권장',
        note: '기존 데이터 재인코딩 필요 — 빈 DB 에서만 즉시 적용 안전',
        sql: `ALTER DATABASE \`your_db\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`
      }
    },
    {
      id: 'mysql-time-zone',
      title: 'MySQL 서버 타임존',
      priority: 'warning',
      target: 'MySQL (타겟)',
      description: 'MSSQL datetime 에 저장된 시간이 KST 인데 MySQL 이 UTC 면 9시간 차이 발생',
      sql: `SELECT @@global.time_zone   AS global_tz,
       @@session.time_zone  AS session_tz,
       @@system_time_zone   AS system_tz,
       NOW()                AS mysql_now,
       UTC_TIMESTAMP()      AS mysql_utc;`
    },
    {
      id: 'mysql-replication-status',
      title: '복제 / 그룹 복제 상태',
      priority: 'info',
      target: 'MySQL (타겟)',
      description: '복제 slave 또는 그룹 복제 환경에서는 이관 방식 다름. 이관 후 지연 감시 필요',
      sql: `SHOW SLAVE STATUS;
-- 또는 MySQL 8.0.22+
SHOW REPLICA STATUS;

-- 그룹 복제
SELECT * FROM performance_schema.replication_group_members;`
    },
    {
      id: 'mysql-global-status-loading',
      title: '현재 부하 상태 (IO, Threads, Questions)',
      priority: 'info',
      target: 'MySQL (타겟)',
      description: '이관 시작 전 평시 부하 수치 기록. 이관 중/후 비교용',
      sql: `SHOW STATUS WHERE Variable_name IN (
  'Threads_running',
  'Threads_connected',
  'Queries',
  'Questions',
  'Slow_queries',
  'Innodb_buffer_pool_reads',
  'Innodb_buffer_pool_read_requests',
  'Innodb_rows_inserted',
  'Innodb_rows_read'
);`
    },
    {
      id: 'mysql-privilege-check',
      title: '이관 계정 권한 (요약)',
      priority: 'critical',
      target: 'MySQL (타겟)',
      description: 'FILE, RELOAD, PROCESS 등 특수 권한은 LOAD DATA / FLUSH 에 필요',
      sql: `SHOW GRANTS FOR CURRENT_USER();

-- 상세 조회
SELECT PRIVILEGE_TYPE, IS_GRANTABLE
FROM information_schema.USER_PRIVILEGES
WHERE GRANTEE = CONCAT("'", CURRENT_USER(), "'");`
    },
    {
      id: 'mysql-ssl-encryption',
      title: 'SSL / TLS 연결 강제 여부',
      priority: 'info',
      target: 'MySQL (타겟)',
      description: 'require_secure_transport=ON 이면 pyodbc/mysql 클라이언트도 SSL 옵션 필요',
      sql: `SHOW VARIABLES LIKE 'require_secure_transport';
SHOW VARIABLES LIKE 'have_ssl';
SHOW VARIABLES LIKE 'ssl_ca';`
    },
    {
      id: 'mysql-disk-usage',
      title: '데이터 디렉토리 디스크 여유',
      priority: 'critical',
      target: 'MySQL (타겟)',
      description: '이관 도중 디스크 full 이면 치명적. 소스 DB 크기의 2배 이상 여유 권장',
      sql: `SELECT @@datadir AS data_directory;

-- 각 테이블의 예상 크기
SELECT
  table_schema AS db,
  ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 2) AS size_gb
FROM information_schema.TABLES
GROUP BY table_schema
ORDER BY size_gb DESC;`
    },
    {
      id: 'mysql-lock-wait-timeout',
      title: 'Lock Wait Timeout / Deadlock',
      priority: 'warning',
      target: 'MySQL (타겟)',
      description: '이관 중 FK 재구성, TRUNCATE 등에서 락 경합 발생 가능',
      sql: `SHOW VARIABLES LIKE 'innodb_lock_wait_timeout';
SHOW VARIABLES LIKE 'innodb_deadlock_detect';

-- 현재 진행 중인 트랜잭션
SELECT * FROM information_schema.INNODB_TRX;`
    },

    // ─── MSSQL 소스 (20개) ───
    {
      id: 'mssql-version',
      title: 'MSSQL 버전 / 에디션 / 서비스 팩',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: '버전/에디션에 따라 사용 가능 기능 다름 (Express 에디션은 DB 크기/CPU 제한)',
      sql: `SELECT
  SERVERPROPERTY('ProductVersion')      AS version,
  SERVERPROPERTY('ProductLevel')        AS service_pack,
  SERVERPROPERTY('Edition')             AS edition,
  SERVERPROPERTY('EngineEdition')       AS engine_edition,
  SERVERPROPERTY('MachineName')         AS machine,
  @@SERVERNAME                          AS server_name,
  SERVERPROPERTY('InstanceName')        AS instance;`
    },
    {
      id: 'mssql-collation',
      title: '서버 / DB Collation (한글 인코딩 판단)',
      priority: 'critical',
      target: 'MSSQL (소스)',
      description: 'Korean_* → VARCHAR 데이터가 CP949. DataBridge v10 #14 의 CP949 디코딩이 기본 적용됨. SQL_Latin1_* 이면 UTF-8 override 필요',
      sql: `SELECT
    SERVERPROPERTY('Collation')                                  AS server_collation,
    DATABASEPROPERTYEX(DB_NAME(), 'Collation')                   AS database_collation,
    DATABASEPROPERTYEX(DB_NAME(), 'CompatibilityLevel')          AS compat_level;`,
      followUp: {
        condition: 'SQL_Latin1_* 또는 기타 비-Korean Collation 인 경우',
        note: '이관 서버에서 백엔드 기동 전 환경변수 설정',
        sql: `REM Windows CMD
set DATABRIDGE_MSSQL_VARCHAR_ENCODING=utf-8

REM 일본어
REM set DATABRIDGE_MSSQL_VARCHAR_ENCODING=cp932

REM 서유럽
REM set DATABRIDGE_MSSQL_VARCHAR_ENCODING=cp1252`
      }
    },
    {
      id: 'mssql-db-size',
      title: '데이터베이스 전체 크기',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: '이관 총 소요 시간 추정 기준 (rps × 크기)',
      sql: `SELECT
    DB_NAME()                                          AS database_name,
    SUM(CAST(size AS bigint)) * 8 / 1024               AS total_mb,
    SUM(CASE WHEN type = 0 THEN CAST(size AS bigint) ELSE 0 END) * 8 / 1024 AS data_mb,
    SUM(CASE WHEN type = 1 THEN CAST(size AS bigint) ELSE 0 END) * 8 / 1024 AS log_mb
FROM sys.database_files;`
    },
    {
      id: 'mssql-table-size',
      title: '테이블별 행수 / 크기',
      priority: 'critical',
      target: 'MSSQL (소스)',
      description: '1000만 행 이상 테이블은 MP 모드 권장. 100만 행 이상이면 야간 이관 검토',
      sql: `SELECT
    s.Name                                             AS schema_name,
    t.Name                                             AS table_name,
    p.rows                                             AS row_count,
    SUM(a.total_pages) * 8 / 1024                      AS total_mb,
    SUM(a.used_pages)  * 8 / 1024                      AS used_mb
FROM sys.tables t
INNER JOIN sys.schemas s         ON t.schema_id = s.schema_id
INNER JOIN sys.indexes i         ON t.object_id = i.object_id
INNER JOIN sys.partitions p      ON i.object_id = p.object_id AND i.index_id = p.index_id
INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
WHERE t.is_ms_shipped = 0 AND i.index_id <= 1
GROUP BY s.Name, t.Name, p.rows
ORDER BY total_mb DESC;`
    },
    {
      id: 'mssql-fk-chain',
      title: 'FK 관계 맵 (이관 순서 결정)',
      priority: 'critical',
      target: 'MSSQL (소스)',
      description: '부모→자식 순서 필수. DataBridge 는 topological sort 자동 처리하지만 순환 참조 있으면 실패',
      sql: `-- FK 관계 맵
SELECT
    OBJECT_SCHEMA_NAME(f.parent_object_id)        AS child_schema,
    OBJECT_NAME(f.parent_object_id)               AS child_table,
    OBJECT_SCHEMA_NAME(f.referenced_object_id)    AS parent_schema,
    OBJECT_NAME(f.referenced_object_id)           AS parent_table,
    f.name                                        AS fk_name,
    f.delete_referential_action_desc              AS on_delete,
    f.update_referential_action_desc              AS on_update
FROM sys.foreign_keys f
ORDER BY parent_table, child_table;

-- FK 제약조건 총 개수
SELECT COUNT(*) AS total_fk FROM sys.foreign_keys;`
    },
    {
      id: 'mssql-pk-uk',
      title: 'Primary Key / Unique Key 목록',
      priority: 'warning',
      target: 'MSSQL (소스)',
      description: 'PK 없는 테이블은 MySQL 에서도 PK 없이 생성됨. 이관 성능과 복제 영향',
      sql: `-- PK/UK 요약
SELECT
    t.name                          AS table_name,
    kc.name                         AS constraint_name,
    kc.type_desc                    AS constraint_type,
    STUFF((
        SELECT ', ' + col.name + ' (' + CAST(ic.key_ordinal AS VARCHAR) + ')'
        FROM sys.index_columns ic
        JOIN sys.columns col
          ON ic.object_id = col.object_id AND ic.column_id = col.column_id
        WHERE ic.object_id = kc.parent_object_id
          AND ic.index_id  = kc.unique_index_id
        ORDER BY ic.key_ordinal
        FOR XML PATH('')
    ), 1, 2, '')                    AS columns
FROM sys.key_constraints kc
JOIN sys.tables t ON kc.parent_object_id = t.object_id
WHERE t.is_ms_shipped = 0
ORDER BY t.name, kc.type_desc;

-- PK 없는 테이블 찾기
SELECT t.name
FROM sys.tables t
LEFT JOIN sys.key_constraints kc
  ON kc.parent_object_id = t.object_id AND kc.type = 'PK'
WHERE kc.object_id IS NULL AND t.is_ms_shipped = 0;`
    },
    {
      id: 'mssql-identity-complex-pk',
      title: 'IDENTITY 컬럼 + PK 조합 분석',
      priority: 'warning',
      target: 'MSSQL (소스)',
      description: 'MySQL 은 AUTO_INCREMENT 가 KEY 첫 번째여야 함. 복합 PK 에서 IDENTITY 가 두번째면 에러 1075. v10 #15 자동 처리됨',
      sql: `SELECT
    t.name                                          AS table_name,
    c.name                                          AS identity_column,
    STUFF((
        SELECT ', ' + col.name
        FROM sys.index_columns ic
        JOIN sys.columns col
          ON ic.object_id = col.object_id AND ic.column_id = col.column_id
        WHERE ic.object_id = t.object_id
          AND ic.index_id  = (
              SELECT index_id FROM sys.indexes
              WHERE object_id = t.object_id AND is_primary_key = 1
          )
        ORDER BY ic.key_ordinal
        FOR XML PATH('')
    ), 1, 2, '')                                    AS pk_columns,
    IDENT_CURRENT(t.name)                           AS current_identity
FROM sys.tables t
JOIN sys.columns c ON t.object_id = c.object_id
WHERE c.is_identity = 1 AND t.is_ms_shipped = 0
ORDER BY t.name;`
    },
    {
      id: 'mssql-row-size-risky',
      title: '행 크기 초과 가능 테이블 탐지',
      priority: 'warning',
      target: 'MSSQL (소스)',
      description: 'VARCHAR 길이 합 × 4 (utf8mb4) > 60000 byte 면 MySQL 1118 에러 가능. v10 #16 자동 변환됨',
      sql: `WITH tbl_bytes AS (
    SELECT
        t.name AS table_name,
        COUNT(*) AS varchar_count,
        SUM(
            CASE
                WHEN c.system_type_id IN (167, 231)   -- varchar, nvarchar
                    THEN CASE WHEN c.max_length = -1 THEN 0
                              ELSE c.max_length * 4 END
                WHEN c.system_type_id IN (175, 239)   -- char, nchar
                    THEN c.max_length * 4
                ELSE 8
            END
        ) AS est_mysql_bytes
    FROM sys.tables t
    JOIN sys.columns c ON t.object_id = c.object_id
    WHERE t.is_ms_shipped = 0
    GROUP BY t.name
)
SELECT table_name, varchar_count, est_mysql_bytes
FROM tbl_bytes
WHERE est_mysql_bytes > 60000
ORDER BY est_mysql_bytes DESC;`
    },
    {
      id: 'mssql-special-types',
      title: '특이 데이터 타입 사용 테이블',
      priority: 'warning',
      target: 'MSSQL (소스)',
      description: 'XML, hierarchyid, geography, sql_variant 등은 MySQL 에 직접 대응 없음. DataBridge 는 TEXT/LONGTEXT 로 변환',
      sql: `SELECT
    t.name                          AS table_name,
    c.name                          AS column_name,
    ty.name                         AS data_type,
    c.is_computed                   AS is_computed,
    c.is_sparse                     AS is_sparse
FROM sys.columns c
JOIN sys.tables t  ON c.object_id = t.object_id
JOIN sys.types  ty ON c.user_type_id = ty.user_type_id
WHERE t.is_ms_shipped = 0
  AND ty.name IN (
    'xml', 'hierarchyid', 'geography', 'geometry',
    'sql_variant', 'timestamp', 'rowversion',
    'datetimeoffset', 'time', 'uniqueidentifier'
  )
ORDER BY t.name, c.column_id;`
    },
    {
      id: 'mssql-computed-columns',
      title: '계산 컬럼 (Computed Column)',
      priority: 'warning',
      target: 'MSSQL (소스)',
      description: 'MSSQL AS <expression> 형 계산 컬럼은 MySQL 에서 GENERATED COLUMN 으로 변환 필요. DataBridge 는 일반 컬럼으로 이관 (값만)',
      sql: `SELECT
    t.name                  AS table_name,
    c.name                  AS column_name,
    cc.definition           AS expression,
    cc.is_persisted         AS persisted,
    cc.is_computed          AS is_computed
FROM sys.computed_columns cc
JOIN sys.tables t  ON cc.object_id = t.object_id
JOIN sys.columns c ON cc.object_id = c.object_id AND cc.column_id = c.column_id
WHERE t.is_ms_shipped = 0;`
    },
    {
      id: 'mssql-partitioned-tables',
      title: '파티션 테이블',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: 'MSSQL 파티션 함수는 MySQL 과 문법 다름. DataBridge 는 파티션 없이 단일 테이블로 이관',
      sql: `SELECT
    t.name                                  AS table_name,
    pf.name                                 AS partition_function,
    ps.name                                 AS partition_scheme,
    COUNT(*)                                AS partition_count
FROM sys.tables t
JOIN sys.indexes i         ON t.object_id = i.object_id
JOIN sys.partition_schemes ps ON i.data_space_id = ps.data_space_id
JOIN sys.partition_functions pf ON ps.function_id = pf.function_id
JOIN sys.partitions p      ON i.object_id = p.object_id AND i.index_id = p.index_id
WHERE t.is_ms_shipped = 0
GROUP BY t.name, pf.name, ps.name;`
    },
    {
      id: 'mssql-triggers',
      title: '트리거 목록',
      priority: 'warning',
      target: 'MSSQL (소스)',
      description: 'T-SQL 트리거 본문은 MySQL 과 문법 차이 큼. DataBridge 는 구조 변환 시도하나 복잡한 로직은 수동 재작성 필요',
      sql: `SELECT
    OBJECT_SCHEMA_NAME(t.object_id) AS schema_name,
    t.name                          AS trigger_name,
    OBJECT_NAME(t.parent_id)        AS table_name,
    t.is_disabled                   AS is_disabled,
    t.is_instead_of_trigger         AS instead_of,
    LEN(OBJECT_DEFINITION(t.object_id)) AS body_length
FROM sys.triggers t
WHERE t.is_ms_shipped = 0
ORDER BY table_name, trigger_name;`
    },
    {
      id: 'mssql-views',
      title: '뷰 목록 및 복잡도',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: 'T-SQL 전용 문법(CROSS APPLY, OUTPUT 등) 있는 뷰는 MySQL 에서 재작성 필요',
      sql: `SELECT
    OBJECT_SCHEMA_NAME(v.object_id)                AS schema_name,
    v.name                                         AS view_name,
    LEN(OBJECT_DEFINITION(v.object_id))            AS body_length,
    (SELECT COUNT(*) FROM sys.sql_dependencies d
        WHERE d.object_id = v.object_id)           AS dependency_count
FROM sys.views v
WHERE v.is_ms_shipped = 0
ORDER BY body_length DESC;`
    },
    {
      id: 'mssql-sp-functions',
      title: 'Stored Procedure / Function 목록',
      priority: 'warning',
      target: 'MSSQL (소스)',
      description: 'T-SQL → MySQL 자동 변환은 기본 문법만 지원. 복잡한 SP/Function 은 수동 변환 필요. AWS SCT 급 작업',
      sql: `SELECT
    OBJECT_SCHEMA_NAME(p.object_id)                AS schema_name,
    p.name                                         AS object_name,
    p.type_desc                                    AS object_type,
    LEN(OBJECT_DEFINITION(p.object_id))            AS body_length,
    p.create_date                                  AS created,
    p.modify_date                                  AS last_modified
FROM sys.objects p
WHERE p.type IN ('P', 'FN', 'IF', 'TF', 'AF', 'FS', 'FT')
  AND p.is_ms_shipped = 0
ORDER BY body_length DESC;`
    },
    {
      id: 'mssql-indexes',
      title: '인덱스 목록 및 크기',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: 'MSSQL 에만 있는 기능 (filtered index, included columns, columnstore) 은 MySQL 에서 일반 인덱스로 단순화',
      sql: `SELECT
    t.name                          AS table_name,
    i.name                          AS index_name,
    i.type_desc                     AS index_type,
    i.is_unique                     AS is_unique,
    i.is_primary_key                AS is_pk,
    i.has_filter                    AS has_filter,
    i.filter_definition             AS filter_def
FROM sys.indexes i
JOIN sys.tables t ON i.object_id = t.object_id
WHERE t.is_ms_shipped = 0 AND i.type > 0
ORDER BY t.name, i.index_id;`
    },
    {
      id: 'mssql-check-constraints',
      title: 'CHECK 제약조건',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: 'MySQL 8.0+ 는 CHECK 지원, 5.7 이하는 무시. 복잡한 표현식은 수동 변환',
      sql: `SELECT
    OBJECT_NAME(cc.parent_object_id)    AS table_name,
    cc.name                             AS constraint_name,
    cc.definition                       AS check_expression,
    cc.is_disabled                      AS is_disabled
FROM sys.check_constraints cc
JOIN sys.tables t ON cc.parent_object_id = t.object_id
WHERE t.is_ms_shipped = 0;`
    },
    {
      id: 'mssql-default-constraints',
      title: '기본값(DEFAULT) 제약',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: 'MSSQL GETDATE, NEWID 등은 MySQL 에서 NOW(), UUID() 로 변환 필요. DataBridge 자동 처리',
      sql: `SELECT
    OBJECT_NAME(dc.parent_object_id)    AS table_name,
    c.name                              AS column_name,
    dc.name                             AS constraint_name,
    dc.definition                       AS default_value
FROM sys.default_constraints dc
JOIN sys.columns c
  ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
JOIN sys.tables t ON dc.parent_object_id = t.object_id
WHERE t.is_ms_shipped = 0;`
    },
    {
      id: 'mssql-cdc-status',
      title: 'CDC (Change Data Capture) 활성 테이블',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: 'CDC 활성 테이블은 시스템 컬럼 이관 제외 필요. DataBridge CDC 이관 모드 검토',
      sql: `SELECT
    OBJECT_SCHEMA_NAME(source_object_id)    AS schema_name,
    OBJECT_NAME(source_object_id)           AS table_name,
    is_tracked_by_cdc                       AS cdc_enabled,
    create_date                             AS cdc_start
FROM sys.tables
WHERE is_tracked_by_cdc = 1
ORDER BY table_name;

-- DB 레벨 CDC 활성 여부
SELECT is_cdc_enabled FROM sys.databases WHERE name = DB_NAME();`
    },
    {
      id: 'mssql-linked-servers',
      title: 'Linked Server 참조',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: 'Linked Server 를 참조하는 뷰/SP 는 MySQL 이관 후 동작 안 함. 대안 필요',
      sql: `SELECT
    name,
    product,
    provider,
    data_source,
    is_linked,
    is_remote_login_enabled
FROM sys.servers
WHERE server_id > 0;`
    },
    {
      id: 'mssql-full-text',
      title: 'Full-Text Search 인덱스',
      priority: 'info',
      target: 'MSSQL (소스)',
      description: 'MSSQL FTS 카탈로그는 MySQL FULLTEXT INDEX 로 변환 가능하나 토크나이저 다름',
      sql: `-- Full-Text Catalog
SELECT * FROM sys.fulltext_catalogs;

-- Full-Text Index 가 있는 테이블
SELECT
    OBJECT_NAME(fi.object_id)       AS table_name,
    COL_NAME(fic.object_id, fic.column_id) AS column_name,
    fi.is_enabled                   AS enabled
FROM sys.fulltext_indexes fi
JOIN sys.fulltext_index_columns fic ON fi.object_id = fic.object_id;`
    },
  ],

  // ═════════════════════════════════════════════════
  // 네트워크 체크 (15개)
  // ═════════════════════════════════════════════════
  networkChecks: [
    {
      id: 'ping-source',
      title: 'MSSQL 소스 서버 ping',
      description: '기본 연결성. 응답시간 = 네트워크 레이턴시',
      command: `ping <MSSQL_HOST>

# Windows PowerShell (4번만)
ping -n 4 <MSSQL_HOST>

# Linux/Mac (4번만)
ping -c 4 <MSSQL_HOST>`,
      expected: '응답 평균 10ms 이내 권장 (같은 네트워크/센터). 100ms+ 는 원거리 네트워크 — 이관 속도 저하 우려'
    },
    {
      id: 'ping-target',
      title: 'MySQL 타겟 서버 ping',
      command: `ping -n 4 <MYSQL_HOST>`,
      expected: '동일 기준. 소스-타겟 간 직접 통신 없음 — 둘 다 이관 서버 기준으로 빠르면 OK'
    },
    {
      id: 'tcp-mssql-1433',
      title: 'MSSQL 포트 (1433) 접근성',
      description: '방화벽/보안그룹 오픈 확인',
      command: `# Windows PowerShell (권장)
Test-NetConnection -ComputerName <MSSQL_HOST> -Port 1433

# Linux/Mac
nc -zv <MSSQL_HOST> 1433
# 또는
timeout 3 bash -c "cat < /dev/tcp/<MSSQL_HOST>/1433"`,
      expected: 'TcpTestSucceeded: True / Connection succeeded'
    },
    {
      id: 'tcp-mysql-3306',
      title: 'MySQL 포트 (3306) 접근성',
      command: `Test-NetConnection -ComputerName <MYSQL_HOST> -Port 3306

# 커스텀 포트 시 변경 (예: 3307)
Test-NetConnection -ComputerName <MYSQL_HOST> -Port 3307`,
      expected: 'TcpTestSucceeded: True'
    },
    {
      id: 'mssql-sqlcmd-login',
      title: 'MSSQL 접속 실전 테스트',
      description: '실제 SQL 실행 가능 여부 (계정/권한까지)',
      command: `# ODBC Driver 18 설치 가정
sqlcmd -S <MSSQL_HOST>,1433 -U <user> -P <password> -d <database> -Q "SELECT 1 AS ok"

# Python 으로 (DataBridge 와 동일 경로)
python -c "import pyodbc; print(pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};SERVER=<HOST>;UID=<user>;PWD=<pw>;DATABASE=<db>;Encrypt=no;TrustServerCertificate=yes').cursor().execute('SELECT 1').fetchone())"`,
      expected: '1 반환 또는 (1,) 출력'
    },
    {
      id: 'mysql-cli-login',
      title: 'MySQL 접속 실전 테스트',
      command: `mysql -h <MYSQL_HOST> -P 3306 -u <user> -p<password> <database> -e "SELECT 1 AS ok"

# Python 으로
python -c "import pymysql; print(pymysql.connect(host='<HOST>', user='<user>', password='<pw>', database='<db>').cursor().execute('SELECT 1'))"`,
      expected: '1 반환'
    },
    {
      id: 'bandwidth-iperf3',
      title: '소스↔이관서버 대역폭 측정 (iperf3)',
      description: '대용량 이관 시간 추정. 10Gbps 이상 권장, 1Gbps 가능, 100Mbps 는 병목',
      command: `# 이관 서버에서 (서버 모드)
iperf3 -s -p 5201

# 소스 DB 서버에서 (클라이언트 모드)
iperf3 -c <이관서버_HOST> -p 5201 -t 30`,
      expected: '1Gbps 환경에서 900Mbps 이상 나오면 정상. 저하 시 네트워크 담당자 확인'
    },
    {
      id: 'traceroute',
      title: '경로 추적 (홉 개수 / 지연 지점)',
      description: '중간 네트워크 구간 문제 진단',
      command: `# Windows
tracert <MSSQL_HOST>

# Linux/Mac
traceroute <MSSQL_HOST>`,
      expected: '홉 10개 이하 권장. 특정 홉에서 지연 심하면 그 구간이 병목'
    },
    {
      id: 'mtu-check',
      title: 'MTU 확인 (패킷 단편화)',
      description: 'VPN 구간에서 MTU 감소로 패킷 드롭 발생 가능',
      command: `# Windows (단편화 없이 1472 byte 성공 = MTU 1500)
ping -l 1472 -f <MSSQL_HOST>
# 실패하면 점진적으로 줄여서 측정
ping -l 1400 -f <MSSQL_HOST>

# Linux
ping -s 1472 -M do <MSSQL_HOST>`,
      expected: '1472 byte 성공 = 표준 MTU 1500. 실패 시 MSS/MTU 튜닝 필요'
    },
    {
      id: 'dns-resolution',
      title: 'DNS 해석 확인',
      description: '호스트명 사용 시 DNS 정상 동작 여부',
      command: `# Windows
nslookup <MSSQL_HOST>
nslookup <MYSQL_HOST>

# Linux/Mac
dig <MSSQL_HOST>
host <MSSQL_HOST>`,
      expected: 'IP 주소 정상 반환. 지연 시 hosts 파일 등록 고려'
    },
    {
      id: 'ntp-sync',
      title: '시간 동기화 확인 (NTP)',
      description: '소스/타겟/이관서버 시간 차이 > 5분 이면 SSL 인증서, 로그 분석 문제',
      command: `# Windows
w32tm /query /status
w32tm /stripchart /computer:time.windows.com /samples:5

# Linux
chronyc tracking
# 또는
ntpq -p`,
      expected: '시간 오차 1초 이내'
    },
    {
      id: 'proxy-vpn-check',
      title: '프록시 / VPN 사용 여부',
      description: '기업 프록시 통과 시 DataBridge 에 설정 필요',
      command: `# Windows
netsh winhttp show proxy
# 또는 환경변수
echo %HTTP_PROXY%
echo %HTTPS_PROXY%

# Linux
env | grep -i proxy`,
      expected: '프록시 있으면 이관 서버 환경변수에 설정 필요'
    },
    {
      id: 'firewall-outbound',
      title: '이관서버 방화벽 아웃바운드 규칙',
      description: 'pip install / 패치 다운로드 등 외부 인터넷 필요 여부',
      command: `# Windows
netsh advfirewall show currentprofile
Get-NetFirewallRule -Direction Outbound -Enabled True | Where-Object {$_.Action -eq 'Block'}

# 간단 테스트
curl -I https://pypi.org
curl -I https://github.com`,
      expected: '필요한 대상(pypi, github) 접근 가능. 막혀 있으면 사전 패키지 준비'
    },
    {
      id: 'disk-iops',
      title: '이관서버 디스크 I/O 속도',
      description: '느린 디스크는 LOAD DATA 병목. SSD/NVMe 강력 권장',
      command: `# Windows (winsat)
winsat disk -drive C

# Linux (dd 간단 테스트)
dd if=/dev/zero of=/tmp/test_io bs=1M count=1024 oflag=direct
rm /tmp/test_io

# 정밀 측정 (fio — 설치 필요)
fio --name=randwrite --rw=randwrite --bs=4k --size=1G --numjobs=1 --runtime=30 --filename=/tmp/fio_test`,
      expected: 'Sequential write 500MB/s 이상 권장 (NVMe SSD). 100MB/s 이하는 HDD — 이관 속도 저하'
    },
    {
      id: 'ssl-tls-test',
      title: 'SSL/TLS 연결 테스트 (필요 시)',
      description: '타겟이 SSL 필수면 인증서/CA 경로 사전 확인',
      command: `# MSSQL SSL 테스트
openssl s_client -connect <MSSQL_HOST>:1433 -starttls mssql

# MySQL SSL 테스트
openssl s_client -connect <MYSQL_HOST>:3306 -starttls mysql

# 인증서 만료 확인
echo | openssl s_client -connect <HOST>:<PORT> 2>/dev/null | openssl x509 -noout -dates`,
      expected: 'verify return code: 0 (ok) 확인. 인증서 만료일 여유 확인'
    },
  ],

  // ═════════════════════════════════════════════════
  // 권한 체크 (10개)
  // ═════════════════════════════════════════════════
  permissionChecks: [
    {
      id: 'mysql-full-grants',
      title: 'MySQL 이관 계정 전체 권한',
      target: 'MySQL (타겟)',
      description: '이관에 필요한 권한 요약: ALL PRIVILEGES on target_db.*, FILE (전역), PROCESS (선택)',
      sql: `-- 현재 계정 전체 권한
SHOW GRANTS FOR CURRENT_USER();

-- 필요 권한 (요약)
/*
  GRANT ALL PRIVILEGES ON <target_db>.* TO '<user>'@'%';
  GRANT FILE ON *.* TO '<user>'@'%';              -- LOAD DATA 용
  GRANT PROCESS ON *.* TO '<user>'@'%';           -- SHOW PROCESSLIST
  GRANT RELOAD ON *.* TO '<user>'@'%';            -- FLUSH (선택)
  FLUSH PRIVILEGES;
*/`
    },
    {
      id: 'mysql-file-priv',
      title: 'MySQL FILE 권한 확인 (LOAD DATA)',
      target: 'MySQL (타겟)',
      description: 'LOCAL INFILE 방식에도 일부 환경에서 FILE 권한 필요',
      sql: `SELECT User, Host, File_priv
FROM mysql.user
WHERE User = SUBSTRING_INDEX(CURRENT_USER(), '@', 1);`
    },
    {
      id: 'mysql-ddl-priv',
      title: 'MySQL DDL 권한 (CREATE/ALTER/DROP)',
      target: 'MySQL (타겟)',
      description: '테이블 생성/변경/삭제 권한. 개별 권한으로 세분화된 경우 확인',
      sql: `SELECT PRIVILEGE_TYPE, IS_GRANTABLE
FROM information_schema.SCHEMA_PRIVILEGES
WHERE GRANTEE = CONCAT("'", REPLACE(CURRENT_USER(), '@', "'@'"), "'")
  AND TABLE_SCHEMA = DATABASE()
  AND PRIVILEGE_TYPE IN ('CREATE', 'ALTER', 'DROP', 'INDEX', 'REFERENCES');`
    },
    {
      id: 'mysql-routine-priv',
      title: 'MySQL 프로시저/함수 권한',
      target: 'MySQL (타겟)',
      description: 'CREATE ROUTINE / ALTER ROUTINE / EXECUTE 필요',
      sql: `SELECT PRIVILEGE_TYPE
FROM information_schema.SCHEMA_PRIVILEGES
WHERE GRANTEE = CONCAT("'", REPLACE(CURRENT_USER(), '@', "'@'"), "'")
  AND TABLE_SCHEMA = DATABASE()
  AND PRIVILEGE_TYPE IN ('CREATE ROUTINE', 'ALTER ROUTINE', 'EXECUTE');`
    },
    {
      id: 'mysql-super-priv',
      title: 'MySQL SUPER / 보조 권한',
      target: 'MySQL (타겟)',
      description: 'SUPER 는 Function 생성, SET GLOBAL, KILL 에 필요. log_bin_trust_function_creators=ON 으로 우회 가능',
      sql: `SELECT User, Host, Super_priv, Reload_priv, Process_priv
FROM mysql.user
WHERE User = SUBSTRING_INDEX(CURRENT_USER(), '@', 1);`
    },
    {
      id: 'mssql-user-context',
      title: 'MSSQL 현재 계정 컨텍스트',
      target: 'MSSQL (소스)',
      description: '접속된 로그인/사용자/역할 요약',
      sql: `SELECT
    SUSER_NAME()            AS login,
    USER_NAME()             AS db_user,
    DB_NAME()               AS database_name,
    IS_SRVROLEMEMBER('sysadmin')       AS is_sysadmin,
    IS_MEMBER('db_owner')              AS is_db_owner,
    IS_MEMBER('db_datareader')         AS is_db_datareader;`
    },
    {
      id: 'mssql-object-perms',
      title: 'MSSQL 객체별 권한 목록',
      target: 'MSSQL (소스)',
      description: '테이블별 SELECT 권한 있는지 확인. DENY 있으면 이관 실패',
      sql: `SELECT
    pr.name                     AS principal,
    pe.permission_name          AS permission,
    pe.state_desc               AS state,
    OBJECT_SCHEMA_NAME(pe.major_id) + '.' + OBJECT_NAME(pe.major_id) AS object_name
FROM sys.database_permissions pe
JOIN sys.database_principals pr
  ON pe.grantee_principal_id = pr.principal_id
WHERE pr.name = USER_NAME()
  AND pe.major_id > 0
ORDER BY object_name, permission;`
    },
    {
      id: 'mssql-schema-perms',
      title: 'MSSQL 스키마 레벨 권한',
      target: 'MSSQL (소스)',
      description: '스키마 전체 SELECT 있으면 개별 테이블 확인 불필요',
      sql: `SELECT
    pr.name                     AS principal,
    pe.permission_name          AS permission,
    pe.state_desc               AS state,
    SCHEMA_NAME(pe.major_id)    AS schema_name
FROM sys.database_permissions pe
JOIN sys.database_principals pr
  ON pe.grantee_principal_id = pr.principal_id
WHERE pr.name = USER_NAME() AND pe.class = 3  -- class=3 means schema
ORDER BY schema_name, permission;`
    },
    {
      id: 'mssql-deny-check',
      title: 'MSSQL DENY 권한 탐지',
      target: 'MSSQL (소스)',
      description: 'DENY 가 GRANT 보다 우선. 특정 테이블이 DENY 되어 있으면 이관 불가',
      sql: `SELECT
    pr.name AS principal,
    pe.permission_name,
    OBJECT_SCHEMA_NAME(pe.major_id) + '.' + OBJECT_NAME(pe.major_id) AS object_name
FROM sys.database_permissions pe
JOIN sys.database_principals pr ON pe.grantee_principal_id = pr.principal_id
WHERE pe.state = 'D'  -- Deny
  AND pr.name = USER_NAME();`
    },
    {
      id: 'mssql-system-views-access',
      title: 'MSSQL 시스템 뷰 접근 (메타데이터)',
      target: 'MSSQL (소스)',
      description: 'DataBridge 가 사용하는 INFORMATION_SCHEMA / sys.* 뷰 접근 가능 확인',
      sql: `-- 필수 뷰 접근 테스트
SELECT TOP 1 * FROM INFORMATION_SCHEMA.TABLES;
SELECT TOP 1 * FROM INFORMATION_SCHEMA.COLUMNS;
SELECT TOP 1 * FROM sys.tables;
SELECT TOP 1 * FROM sys.columns;
SELECT TOP 1 * FROM sys.foreign_keys;
SELECT TOP 1 * FROM sys.indexes;`
    },
  ],

  // ═════════════════════════════════════════════════
  // 방문 체크리스트 (35개 = 공통 20 + 조합별 15)
  // ═════════════════════════════════════════════════
  visitChecklist: [
    ...COMMON_VISIT_CHECKLIST,

    // [DB 준비 — MySQL 타겟]
    { category: 'DB 준비 (MySQL)', text: 'MySQL local_infile=ON 확인', critical: true },
    { category: 'DB 준비 (MySQL)', text: 'MySQL log_bin_trust_function_creators=ON (Function 이관용)', critical: false },
    { category: 'DB 준비 (MySQL)', text: 'MySQL net_*_timeout 상향 조정', critical: true },
    { category: 'DB 준비 (MySQL)', text: 'MySQL innodb_default_row_format=DYNAMIC', critical: false },
    { category: 'DB 준비 (MySQL)', text: 'MySQL 버퍼풀 크기 확인 (데이터 50% 이상)', critical: false },
    { category: 'DB 준비 (MySQL)', text: 'MySQL 디스크 여유 확인 (소스 크기 2배)', critical: true },
    { category: 'DB 준비 (MySQL)', text: 'MySQL 이관 계정 발급 및 권한 부여', critical: true },
    { category: 'DB 준비 (MySQL)', text: 'utf8mb4 문자셋 확인 (한글/이모지 지원)', critical: true },

    // [DB 준비 — MSSQL 소스]
    { category: 'DB 준비 (MSSQL)', text: '소스 MSSQL 최신 백업 완료 (이관 직전)', critical: true },
    { category: 'DB 준비 (MSSQL)', text: 'MSSQL Collation 확인 (한글 인코딩 결정)', critical: true },
    { category: 'DB 준비 (MSSQL)', text: '특이 타입(XML/hierarchyid 등) 사용 테이블 파악', critical: false },
    { category: 'DB 준비 (MSSQL)', text: '이관 제외 테이블 리스트 확정 (임시/로그성)', critical: false },
    { category: 'DB 준비 (MSSQL)', text: '행 크기 초과 예상 테이블 사전 확인', critical: false },
    { category: 'DB 준비 (MSSQL)', text: 'Function/Procedure 수동 변환 범위 확정', critical: false },
    { category: 'DB 준비 (MSSQL)', text: 'CDC 활성 테이블 처리 방침 결정', critical: false },

    // [이관 후 검증]
    { category: '이관 후 검증', text: '각 테이블 row count 1:1 비교 완료', critical: true },
    { category: '이관 후 검증', text: '대표 테이블 Spot check (10~20행 샘플)', critical: true },
    { category: '이관 후 검증', text: '한글 데이터 정합성 확인 (깨짐 여부)', critical: true },
    { category: '이관 후 검증', text: 'NULL/빈 문자열 처리 정합성 확인', critical: false },
    { category: '이관 후 검증', text: '숫자 컬럼 SUM/AVG 집계 비교', critical: false },
    { category: '이관 후 검증', text: '날짜 컬럼 MIN/MAX 비교 (타임존 이슈)', critical: true },
    { category: '이관 후 검증', text: '인덱스 재구축 및 통계 업데이트', critical: false },
    { category: '이관 후 검증', text: 'AUTO_INCREMENT 다음 값 세팅 확인', critical: false },
    { category: '이관 후 검증', text: '실패한 Function/Procedure 수동 변환 일정', critical: false },
    { category: '이관 후 검증', text: '애플리케이션 연결 문자열 변경 계획', critical: true },
    { category: '이관 후 검증', text: '성능 회귀 테스트 (주요 쿼리 응답시간)', critical: false },
    { category: '이관 후 검증', text: '롤백 가능 시간대 및 조건 문서화', critical: true },
  ]
}

// ─────────────────────────────────────────────────────────
// Placeholder: 아직 풀 버전 구현 안 됨
// (다음 세션에서 각각 100개 풀 버전 구현 예정)
// ─────────────────────────────────────────────────────────
const PLACEHOLDER_NOT_IMPLEMENTED = {
  tabs: ['DBA 실행용 SQL', '네트워크 체크', '권한 체크', '방문 체크리스트'],
  sqlBlocks: [
    {
      id: 'placeholder',
      title: '이 조합의 풀 버전 구현 예정',
      priority: 'info',
      target: '(N/A)',
      description: '다음 세션에서 100개 항목으로 완전 구현 예정입니다. 지금은 MSSQL→MySQL 조합만 풀 버전으로 제공됩니다.',
      sql: '-- 풀 구현은 다음 세션에서 제공됩니다\n-- 현재는 MSSQL → MySQL 조합만 완전 구현'
    }
  ],
  networkChecks: [],
  permissionChecks: [],
  visitChecklist: COMMON_VISIT_CHECKLIST
}

// ─────────────────────────────────────────────────────────
// 조합 맵
// ─────────────────────────────────────────────────────────
export const PRECHECK_CONFIGS = {
  // ✅ 풀 구현
  'mssql->mysql':      MSSQL_TO_MYSQL,

  // 🚧 차기 세션 구현 예정 (placeholder 로 대응)
  'mysql->mssql':      PLACEHOLDER_NOT_IMPLEMENTED,
  'mssql->postgresql': PLACEHOLDER_NOT_IMPLEMENTED,
  'postgresql->mssql': PLACEHOLDER_NOT_IMPLEMENTED,
  'mysql->postgresql': PLACEHOLDER_NOT_IMPLEMENTED,
  'postgresql->mysql': PLACEHOLDER_NOT_IMPLEMENTED,
}

/**
 * 특정 소스/타겟 조합의 사전점검 데이터 반환
 */
export function getPrecheckConfig(srcType, tgtType) {
  const key = `${(srcType || '').toLowerCase()}->${(tgtType || '').toLowerCase()}`
  return PRECHECK_CONFIGS[key] || null
}

/**
 * 지원되는 조합 목록
 */
export function getSupportedCombos() {
  return Object.keys(PRECHECK_CONFIGS).map(k => {
    const [src, tgt] = k.split('->')
    return { src, tgt, key: k }
  })
}
