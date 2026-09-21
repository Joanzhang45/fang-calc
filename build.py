# -*- coding: utf-8 -*-
"""把 cases_clean.json 嵌進 index.html"""
import json, io

cases = json.load(open('cases_clean.json', encoding='utf-8'))
CASES_JSON = json.dumps(cases, ensure_ascii=False)

tpl = io.open('template.html', encoding='utf-8').read()
out = tpl.replace('__CASES__', CASES_JSON)
io.open('index.html', 'w', encoding='utf-8').write(out)
print('index.html 完成，', len(out.encode('utf-8')), 'bytes,', len(cases), '個舊案')
