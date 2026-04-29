f = open('app/api/routes/schema.py', encoding='utf-8').read()
print('Encrypt=no 포함:', 'Encrypt=no' in f)
print('1434 포함:', '1434' in f)