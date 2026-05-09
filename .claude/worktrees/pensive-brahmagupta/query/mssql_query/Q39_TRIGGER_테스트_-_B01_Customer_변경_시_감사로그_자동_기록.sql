-- Q39. 감사 로그 확인 - MSSQL
SELECT TOP 5 audit_id, table_nm, operation, pk_val, changed_by, audit_dt
FROM P01_AuditLog
WHERE table_nm = 'B01_Customer'
ORDER BY audit_dt DESC;
