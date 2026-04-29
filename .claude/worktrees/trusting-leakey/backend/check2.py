content = open('app/api/routes/schema.py', encoding='utf-8').read()

for i, line in enumerate(content.split('\n'), 1):
    if 'SERVER=' in line or 'port' in line.lower() or '1433' in line or '1434' in line:
        print(f"{i}: {line}")