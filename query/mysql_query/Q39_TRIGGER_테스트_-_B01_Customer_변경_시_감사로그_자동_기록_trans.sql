SELECT audit_id, table_nm, operation, pk_val, changed_by, audit_dt
FROM P01_AuditLog
WHERE table_nm = 'B01_Customer'
ORDER BY audit_dt DESC
LIMIT 5;