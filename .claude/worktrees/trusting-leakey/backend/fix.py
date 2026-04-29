files = [
    'app/api/routes/schema.py',
    'app/api/routes/validate.py',
    'app/api/routes/jobs.py',
    'app/api/routes/connector.py',
]

for f in files:
    content = open(f, encoding='utf-8').read()
    
    # TrustServerCertificate=yes 뒤에 Encrypt=no 추가
    content = content.replace(
        'TrustServerCertificate=yes;"',
        'TrustServerCertificate=yes;Encrypt=no;"'
    )
    content = content.replace(
        "TrustServerCertificate=yes;'",
        "TrustServerCertificate=yes;Encrypt=no;'"
    )
    # 포트도 1434로 통일
    content = content.replace(',1433;', ',1434;')
    
    open(f, 'w', encoding='utf-8').write(content)
    print(f'{f} 완료')