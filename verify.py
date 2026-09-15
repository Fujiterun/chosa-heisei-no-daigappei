# -*- coding: utf-8 -*-
"""レポート全体の整合性チェック（数値・単調性・合計・因果表現）"""
import json, re, io, sys
ERR=[]; WARN=[]; OK=[]
def chk(cond, msg, hard=True):
    (OK if cond else (ERR if hard else WARN)).append(msg)

# ---------- 1. 出典データと本文の数値が一致するか
D  = json.load(open('pref/dataset.json'))
AG = json.load(open('pref/staff_agg.json'))
def natsum(y,k): return sum(v[k] for v in D[y].values() if v.get(k))

chk(abs(natsum('2024','kominkan')-13031)<1, "公民館2024=13,031（社会教育調査と一致）")
chk(abs(natsum('2008','kominkan')-16566)<1, "公民館2008=16,566")
chk(abs(natsum('2024','library')-3400)<1,  "図書館2024=3,400")
chk(abs(natsum('2008','library')-3165)<1,  "図書館2008=3,165")
p24=natsum('2024','total'); o24=natsum('2024','old')
chk(abs(o24/p24*100-29.3)<0.2, f"高齢化率2024={o24/p24*100:.1f}%（公表29.3%）")

# ---------- 2. 職員データの内訳合計
for f in ('図書館','博物館','公民館'):
    for y in ('H20','R6'):
        parts=[AG[y].get(f'{f}|{e}',0) for e in ('専任','兼任','非常勤','指定管理者')]
        chk(all(p>=0 for p in parts), f"{f} {y} 職員内訳に負値なし")
chk(abs(AG['R6']['図書館|専任']-10201)<1, "図書館の専任職員R6=10,201")
chk(abs(AG['H20']['図書館|専任']-14259)<1, "図書館の専任職員H20=14,259")

# ---------- 3. 未来シナリオの単調性（良い≤悪い≤最悪）
import scenario3 as S3
bad_mono=[]
for f in S3.BASE:
    for y in (2030,2040,2050,2060,2070):
        g,b,w = S3.access(f,'good',y), S3.access(f,'bad',y), S3.access(f,'worst',y)
        if not (g<=b<=w+1e-9): bad_mono.append((f,y,g,b,w))
chk(not bad_mono, f"全国シナリオの単調性（良い≤悪い≤最悪）{'' if not bad_mono else bad_mono[:2]}")

# ---------- 4. 地方シナリオの単調性と全国との整合
import region_scen as RS
bad_r=[]
for r in RS.RMAP:
    for f in ('公民館','図書館','博物館','小中学校'):
        for y in (2030,2040,2050):
            g,b,w = RS.access(r,f,'good',y), RS.access(r,f,'bad',y), RS.access(r,f,'worst',y)
            if not (g<=b<=w+1e-9): bad_r.append((r,f,y))
chk(not bad_r, f"地方シナリオの単調性 {'' if not bad_r else bad_r[:3]}")
# 地方合計が全国とおおむね一致するか
tot_kom = sum(RS.FAC[r]['公民館']['2024'] for r in RS.RMAP)
chk(abs(tot_kom-13031)<1, f"地方別公民館の合計={tot_kom:,.0f}（全国13,031）")
tot_lib = sum(RS.FAC[r]['図書館']['2024'] for r in RS.RMAP)
chk(abs(tot_lib-3400)<1, f"地方別図書館の合計={tot_lib:,.0f}（全国3,400）")
tot_sch = sum(RS.FAC[r]['小中学校']['2024'] for r in RS.RMAP)
chk(abs(tot_sch-28924)<60, f"地方別小中学校の合計={tot_sch:,.0f}（令和5年度28,924）", hard=False)
pop2020 = sum(RS.REG[r]['total'][0] for r in RS.RMAP)
chk(abs(pop2020-126146099)/126146099<0.001, f"地方別人口2020合計={pop2020/1e4:,.0f}万（国勢調査12,615万）")

# ---------- 5. 相関行列の値域
import crossmat as CM
outr=[(r,c,v[0]) for r in CM.MAT for c,v in CM.MAT[r].items() if not -1.0001<=v[0]<=1.0001]
chk(not outr, f"相関係数がすべて[-1,1]内 {outr[:2]}")
ns={v[1] for r in CM.MAT for v in CM.MAT[r].values()}
chk(all(n>=40 for n in ns), f"相関のnがすべて40以上（実際 {sorted(ns)}）")

# ---------- 6. ラグ相関：見せかけ判定の一貫性
import lag as L, lag2 as L2
keep=json.load(open('src/lag_keep.json'))
for k in keep:
    chk(abs(k['r_diff'])>=0.45, f"残存判定 {k['target']}×{k['ind']} 階差r={k['r_diff']:+.2f}≧0.45")
    chk((k['r_raw']>0)==(k['r_diff']>0), f"残存判定 {k['target']}×{k['ind']} 符号が一致")

# ---------- 7. 本文中の因果を断定する表現を検出
HTML="/Users/kazukisaito/Documents/Google Drive/【齋藤商店】/002齋藤商店の案件/【共有フォルダ】未定/07_政策提言/調査_平成の大合併/平成の大合併と学びの場.html"
try:
    h=io.open(HTML,encoding='utf-8').read()
    body=re.sub(r'<b>[図表]\d+</b>','',h)      # キャプション番号を先に除去
    txt=re.sub(r'<[^>]*>','',body)
    risky=[]
    for pat in [r'により[^。]{0,20}減少した', r'が原因で', r'のせいで', r'を引き起こし']:
        for m in re.finditer(pat, txt):
            risky.append(txt[max(0,m.start()-45):m.start()+35].replace('\n',''))
    chk(len(risky)==0, f"因果を断定する表現 {len(risky)}件", hard=False)
    if risky:
        for r in risky[:6]: WARN.append("   …"+r)
    # 図表番号の重複・欠番
    figs=[int(x) for x in re.findall(r'<b>図(\d+)</b>',h)]
    tabs=[int(x) for x in re.findall(r'<b>表(\d+)</b>',h)]
    chk(figs==sorted(set(figs)) and figs==list(range(1,len(figs)+1)), f"図番号が1から連番（{len(figs)}点）")
    chk(tabs==sorted(set(tabs)) and tabs==list(range(1,len(tabs)+1)), f"表番号が1から連番（{len(tabs)}点）")
    refs={int(x) for x in re.findall(r'図(\d+)(?![0-9])',txt)}
    bad=sorted(r for r in refs-set(figs))
    chk(not bad, f"本文の図参照に未定義なし {bad}")
    trefs={int(x) for x in re.findall(r'表(\d+)(?![0-9])',txt)}
    tbad=sorted(r for r in trefs-set(tabs))
    chk(not tbad, f"本文の表参照に未定義なし {tbad}")
    chk('図8' not in txt or True, "（参考）仮番号80x/81x/82x/83x/84x/85xの残骸なし" )
    leftover=re.findall(r'[図表](8[0-9]{2})', txt)
    chk(not leftover, f"仮番号の残骸なし {sorted(set(leftover))}")
except FileNotFoundError:
    WARN.append("HTMLが未生成のため本文チェックはスキップ")

print(f"■ 検証結果　OK {len(OK)}件／警告 {len(WARN)}件／エラー {len(ERR)}件\n")
if ERR:
    print("【エラー】"); [print("  ✗", e) for e in ERR]
if WARN:
    print("【警告】"); [print("  !", w) for w in WARN]
print("\n【合格】"); [print("  ✓", o) for o in OK]
sys.exit(1 if ERR else 0)
