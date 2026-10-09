# -*- coding: utf-8 -*-
"""エスト規則の検算（ワークブックの数式と同じ計算を Python で行う）
python3 simulate.py        … 当社数量で計算
python3 simulate.py est    … エスト見積の数量に置き換えて、エストの各計と一致するか確認"""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lines as L
import est_ref as E
import pricing as P


def ru(x, n):  # ROUNDUP(x, n)
    m = 10 ** n
    return math.ceil(x * m - 1e-9) / m


def run(use_est_qty=False, include_tbd=P.INCLUDE_TBD, labor_cost=P.LABOR_COST, mat_ratio=P.MAT_RATIO, verbose=True):
    tot = {}
    cost_all = 0.0
    labor_all = 0.0
    md_all = 0.0
    for sec in L.SECTIONS:
        H, C = {}, {}
        base_sum = cost_sum = 0.0
        exp_vals = []
        for ln in sec['lines']:
            k = ln['kind']
            if k == 'head':
                continue
            if k in ('item', 'tbd'):
                qty = ln['qty']
                if use_est_qty:
                    qty = ln['est'][0] if ln.get('est') else 0
                if k == 'item':
                    h = round(qty * ln['price'])
                    mat = ln['mat']
                    if isinstance(mat, tuple):
                        mat = round(ln['price'] * mat_ratio * mat[1])
                    lab = round(ln['md'] * labor_cost)
                    c = qty * (mat + lab)
                    labor_all += qty * lab
                    md_all += qty * ln['md']
                else:
                    price = ru(ln['prov'] / (1 - P.TARGET_MARGIN), -3)
                    h = round(qty * price) if include_tbd else 0
                    c = qty * ln['prov'] if include_tbd else 0
                H[ln['key']] = h
                C[ln['key']] = c
                ln['_qty'] = qty
                base_sum += h
                cost_sum += c
            elif k == 'pct':
                h = round(sum(H[b] for b in ln['base']) * ln['rate'])
                c = round(sum(C[b] for b in ln['base']) * ln['rate'])
                H[ln['key']] = h
                C[ln['key']] = c
                base_sum += h
                cost_sum += c
            elif k == 'labor':
                md = sum(next(x for x in sec['lines'] if x.get('key') == b)['_qty'] * next(x for x in sec['lines'] if x.get('key') == b)['bug']
                         for b in ln['base'])
                rate = P.EST_LABOR_PIPE if ln['rate'] == 'EST_LABOR_PIPE' else P.EST_LABOR_ELEC
                h = ru(md * rate, -1)
                c = md * round(labor_cost)
                labor_all += c
                md_all += md
                H[ln['key']] = h
                C[ln['key']] = c
                base_sum += h
                cost_sum += c
        if use_est_qty:   # エストにだけある行（縁石 11.2-16.0 など）を加える
            base_sum += sum(a[4] for a in L.EST_ONLY if a[0] == sec['title'] and a[4] > 0)
        rates = [r for _, r in E.EST_EXP[sec['key']]]
        e1 = ru(base_sum * rates[0], -2)
        e2 = ru((base_sum + e1) * rates[1], -2)
        s3 = base_sum + e1 + e2
        total = ru(s3 + ru(s3 * rates[2], -2), -3)
        e3 = total - s3
        tot[sec['key']] = dict(base=base_sum, exp=(e1, e2, e3), total=total, cost=cost_sum)
        cost_all += cost_sum
        if verbose:
            print(f"{sec['title']}: 基礎額 {base_sum:,.0f}  経費 {e1:,.0f}/{e2:,.0f}/{e3:,.0f}  計 {total:,.0f}  原価 {cost_sum:,.0f}")
    oh = ru((tot['AC']['total'] + tot['PIPE']['total']) * E.EST_OVERHEAD, -2)
    sub = tot['AC']['total'] + tot['PIPE']['total'] + oh
    welfare = labor_all * P.WELFARE_COST
    cost_total = cost_all + welfare
    submit = math.ceil(cost_total / (1 - P.TARGET_MARGIN) / P.ROUND_UNIT - 1e-9) * P.ROUND_UNIT
    disc = submit - sub if submit < sub else 0
    final = sub + disc
    if verbose:
        print(f"工事諸経費 {oh:,.0f}  小計 {sub:,.0f}")
        print(f"人工 {md_all:.2f}  労務原価 {labor_all:,.0f}  法定福利(事業主) {welfare:,.0f}  原価合計 {cost_total:,.0f}")
        print(f"提出額(粗利{P.TARGET_MARGIN:.0%}) {submit:,.0f}  出精値引 {disc:,.0f}  合計 {final:,.0f}  粗利率 {(final - cost_total) / final:.1%}")
    return dict(sub=sub, final=final, cost=cost_total, oh=oh, tot=tot, md=md_all)


if __name__ == '__main__':
    est = len(sys.argv) > 1 and sys.argv[1] == 'est'
    r = run(use_est_qty=est)
    if est:
        print('--- エスト見積との照合: 空調 174,000 / 配管 1,112,000 / 諸経費 64,300 / 小計 1,350,300')
        print('一致' if (r['tot']['AC']['total'], r['tot']['PIPE']['total'], r['oh'], r['sub']) == (174000, 1112000, 64300, 1350300) else '不一致')
        print(f"エスト提出額 1,100,000 の粗利率（この原価モデル・エスト数量）: {(1100000 - r['cost']) / 1100000:.1%}")
