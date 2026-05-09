import pyodbc

DSN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=127.0.0.1,1434;"
    "DATABASE=mgtest;"
    "UID=sa;"
    "PWD=0000;"
    "TrustServerCertificate=yes;"
)

print("테이블 조회 테스트...")
try:
    conn = pyodbc.connect(DSN)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.name, t.name, p2.rows
        FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id=s.schema_id
        JOIN sys.partitions p2
          ON t.object_id=p2.object_id AND p2.index_id IN(0,1)
        ORDER BY s.name, t.name
    """)
    rows = cur.fetchall()
    print(f"성공! 테이블 {len(rows)}개:")
    for r in rows:
        print(f"  {r[0]}.{r[1]} ({r[2]}행)")
    conn.close()
except Exception as e:
    print(f"실패: {e}")