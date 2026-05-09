-- Q34. 감사 로그 조회 - MySQL
-- 검증 고정 조건: 2026-04-01 ~ 2026-04-02 범위
SELECT
    a.audit_id, a.table_nm, a.operation, a.pk_val,
    a.changed_by, a.audit_dt AS changed_dt,
    CASE a.operation
        WHEN 'I' THEN '등록' WHEN 'U' THEN '수정' WHEN 'D' THEN '삭제'
    END AS op_nm
FROM P01_AuditLog a
WHERE a.audit_dt >= '2026-04-01' AND a.audit_dt < '2026-04-03'
ORDER BY a.audit_id;
