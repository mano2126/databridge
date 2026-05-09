# check.py - backend 폴더에서 실행: python check.py
import os

def check(label, condition):
    print(f'{"OK" if condition else "XX"} {label}')

try:
    c = open('app/api/routes/jobs.py', encoding='utf-8').read()
    print('=== jobs.py ===')
    check('objects 저장', 'j["objects"]' in c)
    check('src_port 저장', 'j["src_port"]' in c)
    check('port=3306 하드코딩 없음', 'port=3306' not in c)
    check('_rule_based_ddl_convert', '_rule_based_ddl_convert' in c)
    check('autocommit=True', 'autocommit=True' in c)
    check('bulk-delete 순서', c.find('/bulk-delete') < c.find('/{jid}'))

    idx = c.find('def _connect_src')
    print('\n_connect_src 앞부분:')
    print(c[idx:idx+200])
except Exception as e:
    print(f'jobs.py 읽기 실패: {e}')

try:
    s = open('app/api/routes/schema.py', encoding='utf-8').read()
    print('\n=== schema.py ===')
    check('MSSQL->MySQL 분기', 'if is_src_mssql and is_tgt_mysql' in s)
    check('DROP PROCEDURE IF EXISTS', 'DROP PROCEDURE IF EXISTS' in s)
    check('autocommit=True', 'autocommit=True' in s)
except Exception as e:
    print(f'schema.py 읽기 실패: {e}')
