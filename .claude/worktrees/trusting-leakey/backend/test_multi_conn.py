import pyodbc

DSN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=127.0.0.1,1434;"
    "DATABASE=mgtest;"
    "UID=sa;"
    "PWD=0000;"
    "TrustServerCertificate=yes;"
)

print("=== 연속 연결 테스트 ===")
for i in range(1, 4):
    try:
        print(f"\n[{i}번째 연결 시도]")
        conn = pyodbc.connect(DSN)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.tables")
        row = cur.fetchone()
        print(f"[{i}번째 연결 성공] 테이블 수: {row[0]}")
        conn.close()
        print(f"[{i}번째 연결 종료]")
    except Exception as e:
        print(f"[{i}번째 연결 실패] {e}")