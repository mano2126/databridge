import pyodbc

try:
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=127.0.0.1,1434;'
        'DATABASE=mgtest;'
        'UID=sa;'
        'PWD=0000;'
        'TrustServerCertificate=yes;',
        timeout=10
    )
    print('연결 성공!')
    conn.close()
except Exception as e:
    print('에러:', e)