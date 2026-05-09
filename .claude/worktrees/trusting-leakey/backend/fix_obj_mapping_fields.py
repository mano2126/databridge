"""
fix_obj_mapping_fields.py
backend 폴더에서 실행: python fix_obj_mapping_fields.py

backend/data/obj_mapping_rules.json 의 필드명을
src_pattern/tgt_pattern → src_syntax/tgt_syntax 로 마이그레이션합니다.
"""
import json, os, shutil
from datetime import datetime

DATA_FILE = 'data/obj_mapping_rules.json'

if not os.path.exists(DATA_FILE):
    print(f'{DATA_FILE} 없음 — 마이그레이션 불필요 (신규 생성됩니다)')
    exit(0)

# 백업
bak = DATA_FILE + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(DATA_FILE, bak)
print(f'백업: {bak}')

with open(DATA_FILE, encoding='utf-8') as f:
    data = json.load(f)

changed = 0
for key, rule in data.items():
    # src_pattern → src_syntax
    if 'src_pattern' in rule and 'src_syntax' not in rule:
        rule['src_syntax'] = rule.pop('src_pattern')
        changed += 1
    # tgt_pattern → tgt_syntax
    if 'tgt_pattern' in rule and 'tgt_syntax' not in rule:
        rule['tgt_syntax'] = rule.pop('tgt_pattern')

with open(DATA_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'필드명 마이그레이션 완료: {changed}개 규칙')
print('백엔드 재시작: python -m uvicorn main:app --port 8000')
