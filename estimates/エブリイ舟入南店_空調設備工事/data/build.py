#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
御見積書の作成（エブリイ舟入南店 リニューアル工事 空調設備工事）
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
got = dict(ac=v[C + '!K23'], pipe=v[C + '!K24'], oh=v[C + '!K25'], sub=v[C + '!K26'], disc=v[C + '!K27'],
           final=v[C + '!K28'], cost=v[C + '!O27'])
sim = B.simulate(job)
print('数量:', job.Q)
print('ワークブック:', got, ' 粗利率 {:.1%}'.format(v[C + '!Q28']))
ok = all(abs(sim[k] - got[k]) <= 1 for k in got)
print('検算（simulate と一致）:', 'OK' if ok else 'NG ' + str({k: sim[k] for k in got}))
alerts = {k: v[k] for k in v if k.startswith(C + '!N3') or k.startswith(C + '!O3')}
print('アラート欄:', alerts)
if not ok:
    sys.exit(1)
subprocess.run([sys.executable, '-I', os.path.join(LIB, 'make_pdf.py'), info['out'], out_dir], check=True)
