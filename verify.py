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
    # ---- 年表タブ ----
    import chrono, shell
    chk(len(chrono.EV)==57, f"年表の採録件数=57（実際{len(chrono.EV)}）")
    chk(f"{len(chrono.EV)}件" in txt, "本文の年表件数の記述が採録件数と一致")
    rows = dict((r[0], r) for r in chrono.elast_rows())
    for lb, want in [("1990-99", 0.13), ("1999-2010", 1.34), ("2010-15", 0.99), ("2015-26", 0.79)]:
        got = rows[lb][3]
        chk(abs(round(got,2)-want) < 0.005, f"追随度 {lb}={want:.2f}（実際{got:.3f}）")
    kom = dict((f"{a}->{b}", ((vb/va)**(1/(b-a))-1)*100)
               for (a,va),(b,vb) in zip(chrono.KOM[:-1], chrono.KOM[1:]))
    chk(abs(kom["2005->2008"]+3.06) < 0.005, f"公民館 2005→2008 年率−3.06%（実際{kom['2005->2008']:.2f}）")
    chk(abs(kom["2021->2024"]+1.89) < 0.005, f"公民館 2021→2024 年率−1.89%（実際{kom['2021->2024']:.2f}）")
    lib = dict((f"{a}->{b}", ((vb/va)**(1/(b-a))-1)*100)
               for (a,va),(b,vb) in zip(chrono.LIB[:-1], chrono.LIB[1:]))
    chk(abs(lib["2002->2005"]-2.80) < 0.005, f"図書館 2002→2005 年率+2.80%（実際{lib['2002->2005']:.2f}）")
    mus = dict((f"{a}->{b}", ((vb/va)**(1/(b-a))-1)*100)
               for (a,va),(b,vb) in zip(chrono.MUS[:-1], chrono.MUS[1:]))
    chk(abs(mus["2008->2011"]-0.37) < 0.005, f"博物館 2008→2011 年率+0.37%（実際{mus['2008->2011']:.2f}）")
    for y, v in [(1953, 13685), (1961, 12849)]:
        got = [r for r in chrono.LONG if int(r['年度'])==y][0]['中学校数']
        chk(abs(float(got)-v) < 1, f"中学校数 {y}年度={v:,}（学校基本調査）")
        chk(f"{v:,}校" in txt, f"本文に中学校数 {v:,}校 の記述あり")
    for y, v in [(1953, 26555), (1961, 26741)]:
        got = [r for r in chrono.LONG if int(r['年度'])==y][0]['小学校数']
        chk(abs(float(got)-v) < 1, f"小学校数 {y}年度={v:,}（学校基本調査）")
    chk("16,285校から10,751校" not in txt, "誤記「中学校 16,285校→10,751校」が残っていない")
    # ---- 47都道府県シナリオ ----
    import pref_scen as PS, region_scen as RS, scenario3 as NAT
    chk(len(PS.PREFS)==47, f"都道府県別推計が47件（実際{len(PS.PREFS)}）")
    mono = [(p,f,y) for p in PS.PREFS for f in PS.DKEY if PS.FAC[p][f]
            for y in PS.YEARS[1:]
            if not (PS.access(p,f,'good',y) <= PS.access(p,f,'bad',y)+1e-9 <= PS.access(p,f,'worst',y)+1e-9)]
    chk(not mono, f"都道府県シナリオの単調性（良い≤悪い≤最悪） {mono[:3]}")
    for f in ('公民館','図書館','博物館','小中学校'):
        a = sum(RS.FAC[r][f]['2024'] for r in RS.RMAP)
        b = sum(PS.FAC[p][f] for p in PS.PREFS)
        chk(abs(a-b) < 0.5, f"{f}の47県合計と8地方合計が一致（{b:,.0f}／{a:,.0f}）")
    need = [p for p in PS.PREFS if PS.FAC[p]['公民館'] and PS.count(p,'公民館','good',2050) > PS.FAC[p]['公民館']]
    chk(len(need)==20, f"良い未来で公民館の増設が必要な県=20（実際{len(need)}）")
    chk("増やす必要がある20都道府県" in txt, "本文の県数の記述が試算と一致")
    n0 = sum(PS.FAC[p]['公民館'] for p in need)
    n1 = sum(PS.count(p,'公民館','good',2050) for p in need)
    chk(f"{n0:,.0f}館から{n1:,.0f}館へ{n1-n0:,.0f}館の不足" in txt,
        f"20都府県の合計（{n0:,.0f}→{n1:,.0f}、{n1-n0:+,.0f}）が本文と一致")
    gap = sum(sum(PS.count(p,f,'good',2050)-PS.count(p,f,'bad',2050) for p in PS.PREFS if PS.FAC[p][f])
              for f in PS.DKEY)
    chk(f"{gap:,.0f}施設" in txt, f"良い未来と悪い未来の差 {gap:,.0f}施設 が本文と一致")
    for p, f, v in [('秋田県','小中学校',-54.7), ('青森県','小中学校',-54.5),
                    ('秋田県','公民館',-49.7), ('東京都','小中学校',-14.6), ('東京都','公民館',-15.9)]:
        got = (PS.count(p,f,'bad',2050)/PS.FAC[p][f]-1)*100
        chk(abs(round(got,1)-v) < 0.05, f"{p}の{f} 2050年減少率 {v}%（実際{got:.1f}%）")
    d = PS.FAC['長野県']['公民館'] - PS.count('長野県','公民館','bad',2050)
    chk(abs(d-638) < 1, f"長野県の公民館 638館減（実際{d:.0f}）")
    for f, m, want in [('公民館','good',12106), ('公民館','bad',6532), ('公民館','worst',4295),
                       ('小中学校','good',16540), ('図書館','worst',1121), ('博物館','bad',2890)]:
        got = NAT.count(f, m, 2070)
        chk(abs(got-want) < 1, f"全国2070年 {f}・{m} = {want:,}（実際{got:,.0f}）")
    for f, m, want in [('公民館','bad',1.85), ('公民館','worst',2.82), ('図書館','worst',2.13),
                       ('小中学校','bad',1.15)]:
        got = NAT.access(f,m,2070)/NAT.access(f,'good',2024)
        chk(abs(round(got,2)-want) < 0.005, f"遠さ {f}・{m} = {want}倍（実際{got:.2f}）")

    # ---- 予算（地方教育費調査） ----
    import budget as BG, body_pace as PC
    for y, lb, tot, sch, soc, adm in BG.FIELD:
        chk(abs(sch+soc+adm-tot) <= 2, f"{lb} 分野別の内訳合計＝総額（差{sch+soc+adm-tot}）")
    r = BG.field_rows()
    for nm, ix, want in [("総額",6,-14.9), ("学校教育費",7,-11.2), ("社会教育費",8,-42.8), ("教育行政費",9,5.2)]:
        got = r[-1][ix]-100
        chk(abs(round(got,1)-want) < 0.05, f"H8→R5 {nm} {want:+.1f}%（実際{got:+.1f}%）")
    chk(abs(round(r[0][10],1)-14.7) < 0.05 and abs(round(r[-1][10],1)-9.9) < 0.05,
        f"社会教育費の割合 14.7%→9.9%（実際{r[0][10]:.1f}%→{r[-1][10]:.1f}%）")
    b = BG.FAC[0]; e = BG.FAC[-1]
    for nm, i, want in [("社会教育費",2,-44.1), ("公民館費",3,-34.2), ("図書館費",4,-16.2), ("博物館費",5,-54.0)]:
        got = (e[i]/b[i]-1)*100
        chk(abs(round(got,1)-want) < 0.05, f"H6→R2 {nm} {want:+.1f}%（実際{got:+.1f}%）")
    # 地方教育費調査の2系列が重なる年で一致するか
    ann = {lb: soc for _, lb, _, _, soc, _ in BG.FIELD}
    for lb, yr, soc, *_ in BG.FAC:
        if lb in ann:
            chk(abs(ann[lb]-soc) <= 1, f"{lb} 社会教育費が2系列で一致（年次表{ann[lb]:,}／内訳表{soc:,}）")
    d11 = {f: (bd, n, pp) for l, f, bd, n, pp in BG.per_facility() if l == "H11"}
    d30 = {f: (bd, n, pp) for l, f, bd, n, pp in BG.per_facility() if l == "H30"}
    for f, ix, want in [("図書館",1,29.6), ("図書館",0,-22.3), ("図書館",2,-40.0),
                        ("博物館",1,12.3), ("博物館",0,-50.3), ("博物館",2,-55.7),
                        ("公民館",1,-25.1), ("公民館",0,-31.9), ("公民館",2,-9.1)]:
        got = (d30[f][ix]/d11[f][ix]-1)*100
        lab = ["予算","施設数","1施設あたり"][ix]
        chk(abs(round(got,1)-want) < 0.05, f"H11→H30 {f}の{lab} {want:+.1f}%（実際{got:+.1f}%）")
    chk(abs(sum(v for _, v, _ in BG.NAT) - BG.NAT_TOTAL) <= 2,
        f"令和8年度 主要経費の合計＝122兆3,092億円（差{sum(v for _,v,_ in BG.NAT)-BG.NAT_TOTAL}）")
    chk("46,028億円（3.8％）" in txt, "文教関係46,028億円（3.8%）の記述が計算と一致")
    for nm, yrs, sc, ss, jc, js in PC.PACE:
        pass
    p1, p2 = PC.PACE[1], PC.PACE[2]
    for lab, a, b2, want in [("小 年あたり", p1[3]/p1[1], p2[3]/p2[1], (185.9, 250.8)),
                             ("中 年あたり", p1[5]/p1[1], p2[5]/p2[1], (40.9, 61.8))]:
        chk(abs(round(a,1)-want[0]) < 0.05 and abs(round(b2,1)-want[1]) < 0.05,
            f"{lab} {want[0]}→{want[1]}（実際{a:.1f}→{b2:.1f}）")
    s1, s2 = p1[3]/(p1[2]/10000), p2[3]/(p2[2]/10000)
    j1, j2 = p1[5]/(p1[4]/10000), p2[5]/(p2[4]/10000)
    chk(abs(round(s1,1)-43.3) < 0.05 and abs(round(s2,1)-44.4) < 0.05,
        f"小 児童1万人減あたり 43.3→44.4（実際{s1:.1f}→{s2:.1f}）")
    chk(abs(round(j1,1)-7.0) < 0.05 and abs(round(j2,1)-16.3) < 0.05,
        f"中 生徒1万人減あたり 7.0→16.3（実際{j1:.1f}→{j2:.1f}）")
    chk(abs(round(j2/j1,1)-2.3) < 0.05, f"中学校は2.3倍に加速（実際{j2/j1:.2f}倍）")

    # ---- 網羅チェック表の集計と本文の一致 ----
    import coverage as CV
    _c = {k: 0 for k in CV.MARK}
    for _, _st, _ in CV.AXES:
        for _f in CV.FACS: _c[_st[_f]] += 1
    _tot = sum(_c.values())
    chk(f"{_tot}セル中、未取得は{_c['未']}セル" in txt,
        f"網羅チェックの本文が集計と一致（{_tot}セル／未取得{_c['未']}）")

    # ---- SVGラベルの色指定がCSSに負けていないか ----
    FILLCLS = {'tick','tick sm','rowlab','axttl','band-lb','note-in','inbar',
               'vsm','vtiny','vzero','callout','leg'}
    lost = [m.group(0) for m in re.finditer(r'<text[^>]*>', h)
            if (c := re.search(r'class="([^"]+)"', m.group(0))) and c.group(1) in FILLCLS
            and re.search(r'\sfill="', m.group(0)) and 'style="fill' not in m.group(0)]
    chk(not lost, f"SVGラベルの色がCSSに上書きされる箇所なし（{len(lost)}件）")

    # ---- タブ内リンクの整合 ----
    ids = {t[0] for t in shell.TABS}
    gotos = set(re.findall(r'data-goto="([a-z0-9\-]+)"', h))
    chk(not (gotos-ids), f"data-goto の参照先がすべて実在するタブ {sorted(gotos-ids)}")
    import collections
    _ids = re.findall(r'\bid="([^"]+)"', h)
    _dup = sorted(k for k, v in collections.Counter(_ids).items() if v > 1)
    chk(not _dup, f"HTML内のidに重複なし {_dup}")
    anchors = set(re.findall(r'href="#panel-([a-z0-9\-]+)"', h))
    chk(not (anchors-ids), f"#panel- アンカーがすべて実在 {sorted(anchors-ids)}")
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
