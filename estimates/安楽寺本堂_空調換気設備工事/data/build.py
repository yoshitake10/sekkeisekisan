#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
御見積書の作成（安楽寺 本堂 新築工事 空調・換気設備工事）
使い方: python3 build.py [出力ディレクトリ（既定: この案件フォルダ）]
  1) job.py（明細・注記）から共通ビルダー ../../_lib_est/est_book.py でワークブックを作成
  2) recalc_cache.py で数式のキャッシュ値を埋め込み、表紙の金額を検算（simulate と一致すること）
  3) make_pdf.py で提出用 PDF（内部・参考シートを除く）を作成
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', '..', '_lib_est'))
sys.path.insert(0, HERE)
sys.path.insert(1, LIB)

import est_book as B  # noqa: E402
import job  # noqa: E402

out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(HERE)
info = B.build_book(job, out_dir)
subprocess.run([sys.executable, '-I', os.path.join(LIB, 'recalc_cache.py'), info['out']], check=True, stdout=subprocess.DEVNULL)
vpath = info['out'] + '.values.json'
v = json.load(open(vpath, encoding='utf-8'))
os.remove(vpath)

C = B.SH_COVER
cv = info['cover']
sim = B.simulate(job)
got, exp = {}, {}
for i, (kind, key) in enumerate(cv['rows']):
    cell = f"{C}!K{cv['first'] + i}"
    name = key or kind
    got[name] = v[cell]
    exp[name] = sim['oh'] if kind == 'oh' else sim['secs'][key]
for name, row in (('sub', 'sub'), ('disc', 'disc'), ('final', 'total')):
    got[name] = v[f"{C}!K{cv[row]}"]
    exp[name] = sim[name]
got['cost'], exp['cost'] = v[f"{C}!O{cv['disc']}"], sim['cost']
print('数量:', job.Q)
print('ワークブック:', got, ' 粗利率 {:.1%}'.format(v[f"{C}!Q{cv['total']}"]))
ok = all(abs(exp[k] - got[k]) <= 1 for k in got)
print('検算（simulate と一致）:', 'OK' if ok else 'NG ' + str(exp))
a0 = cv['total'] + 3
for rr in range(a0, a0 + 12):
    row = [v.get(f'{C}!{c}{rr}') for c in 'MNO']
    if any(x not in (None, '') for x in row):
        print('アラート欄:', row)
if not ok:
    sys.exit(1)
subprocess.run([sys.executable, '-I', os.path.join(LIB, 'make_pdf.py'), info['out'], out_dir], check=True)
