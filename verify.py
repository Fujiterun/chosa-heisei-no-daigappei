# -*- coding: utf-8 -*-
"""平成の大合併と学びの場：完成HTMLだけを読んで検証する（外部データ不要）

ビルドスクリプトは失われているため、本スクリプトは公開HTMLを唯一の入力とし、
構造・図表番号・リンク・SVG幾何・本文と表の数値整合を機械的に点検する。
    python3 verify.py
"""
import re, io, sys, math, collections, os

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), '平成の大合併と学びの場.html')
OK, WARN, ERR = [], [], []
def chk(cond, msg, hard=True):
    (OK if cond else (ERR if hard else WARN)).append(msg)

h = io.open(HTML, encoding='utf-8').read()
txt = re.sub(r'<[^>]+>', '', re.sub(r'<b>[図表]\d+</b>', '', h))

# ---------- 1. 構造 ----------
for t in ('section','figure','table','div','details','nav','button','svg','tbody','thead'):
    o = len(re.findall(r'<%s[ >]' % t, h)); c = len(re.findall(r'</%s>' % t, h))
    chk(o == c, f'<{t}> の開閉が一致（{o}/{c}）')
ids = re.findall(r'\bid="([^"]+)"', h)
dup = sorted(k for k, v in collections.Counter(ids).items() if v > 1)
chk(not dup, f'id に重複なし {dup}')
nav = h[h.index('<nav class="tabsbar"'):h.index('</nav>')]
tabs = re.findall(r'data-tab="([a-z]+)"', nav)
panels = re.findall(r'class="tabpanel" id="panel-([a-z]+)"', h)
chk(tabs == panels, f'タブとパネルが一対一（{len(tabs)}／{len(panels)}）')
nums = re.findall(r'id="tab-[a-z]+"[^>]*><span class="n">(\d+)</span>', h)
chk(nums == [f'{i:02d}' for i in range(len(tabs))], f'タブ番号が00から連番（{len(nums)}件）')

# ---------- 2. 図表番号 ----------
figs = [int(x) for x in re.findall(r'<b>図(\d+)</b>', h)]
tbs  = [int(x) for x in re.findall(r'<b>表(\d+)</b>', h)]
chk(figs == list(range(1, len(figs)+1)), f'図番号が1から連番（{len(figs)}点）')
chk(tbs  == list(range(1, len(tbs)+1)),  f'表番号が1から連番（{len(tbs)}点）')
chk(not sorted({int(x) for x in re.findall(r'図(\d+)(?![0-9])', txt)} - set(figs)), '本文の図参照に未定義なし')
chk(not sorted({int(x) for x in re.findall(r'表(\d+)(?![0-9])', txt)} - set(tbs)),  '本文の表参照に未定義なし')
chk(not re.findall(r'[図表](?:8[0-9]{2}|9[0-9]{2})', txt), '仮番号（8xx/9xx）の残骸なし')

# ---------- 3. リンク ----------
gotos  = set(re.findall(r'data-goto="([a-z0-9\-]+)"', h))
anchors = set(re.findall(r'href="#panel-([a-z0-9\-]+)"', h))
chk(not (gotos - set(tabs)),   f'data-goto の参照先が実在 {sorted(gotos-set(tabs))}')
chk(not (anchors - set(tabs)), f'#panel- アンカーが実在 {sorted(anchors-set(tabs))}')

# ---------- 4. SVGラベルの色がCSSに負けていないか ----------
FILLCLS = {'tick','tick sm','rowlab','axttl','band-lb','note-in','inbar','vsm','vtiny','vzero','callout','leg'}
lost = [m.group(0) for m in re.finditer(r'<text[^>]*>', h)
        if (c := re.search(r'class="([^"]+)"', m.group(0))) and c.group(1) in FILLCLS
        and re.search(r'\sfill="', m.group(0)) and 'style="fill' not in m.group(0)]
chk(not lost, f'SVGラベルの色がCSSに上書きされる箇所なし（{len(lost)}件）')

# ---------- 5. SVGの幾何（はみ出し） ----------
FS = {'tick':11,'tick sm':10,'slab':12.5,'ptval':10,'callout':11,'band-lb':10.5,'note-in':11,
      'vsm':10,'vtiny':9.5,'vzero':9.5,'rowlab':12.5,'axttl':12,'leg':11.5,'matval':12,
      'inbar':10.5,'panel-ttl':12.5}
def wid(s, fs): return sum(fs*(0.58 if ord(c) < 0x2E80 else 1.0) for c in s)
over = 0
for sv in re.findall(r'<svg[^>]*class="cht"[^>]*>.*?</svg>', h, re.S):
    mb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', sv)
    if not mb: continue
    W, H = float(mb.group(1)), float(mb.group(2))
    for m in re.finditer(r'<text x="([-\d.]+)" y="([-\d.]+)"([^>]*)>([^<]*)</text>', sv):
        x, y, at, s = float(m.group(1)), float(m.group(2)), m.group(3), m.group(4)
        if 'transform=' in at: continue        # 回転ラベルは軸タイトル。x/y境界では判定できない
        cls = (re.search(r'class="([^"]+)"', at) or [None,'tick'])[1]
        anc = (re.search(r'text-anchor="([^"]+)"', at) or [None,'start'])[1]
        fs = FS.get(cls, 11); w = wid(s, fs)
        x0 = x if anc == 'start' else (x-w/2 if anc == 'middle' else x-w)
        if x0 < -1 or x0+w > W+1 or y < fs*0.7 or y > H+1: over += 1
chk(over == 0, f'SVG文字のviewBoxはみ出しなし（{over}件）')

# ---------- 6. ホバー用のタイトル ----------
charts = re.findall(r'<svg[^>]*class="cht"[^>]*>.*?</svg>', h, re.S)
notitle = [i for i, s in enumerate(charts) if '<title>' not in s]
chk(not notitle, f'全チャートにホバー用<title>あり（{len(charts)}図／欠落{len(notitle)}）')

# ---------- 7. 因果を断定する表現 ----------
risky = []
for pat in [r'により[^。]{0,20}減少した', r'が原因で', r'のせいで', r'を引き起こし']:
    for m in re.finditer(pat, txt):
        risky.append(txt[max(0, m.start()-45):m.start()+35].replace('\n',''))
chk(not risky, f'因果を断定する表現 {len(risky)}件', hard=False)
for r in risky[:4]: WARN.append('   …' + r)

# ---------- 8. 表を読み取って本文と突合 ----------
def table(tid):
    i = h.index('id="' + tid + '"'); seg = h[i:h.index('</table>', i)]
    rows = []
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', seg[seg.index('<tbody>'):], re.S):
        c = [re.sub(r'<[^>]+>', '', x).strip() for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', m.group(1), re.S)]
        if c: rows.append(c)
    return rows
def f(s):
    s = s.replace(',','').replace('%','').replace('万','').replace('+','').replace('−','-').replace('△','-')
    try: return float(s)
    except ValueError: return None

TP = {r[0]: r for r in table('t-taxpref')}
FA = {r[0]: r for r in table('t-fac')}
NO = {r[0]: r for r in table('t-norm')}
P47 = [p for p in TP if p != '全国']
chk(len(P47) == 47, f'課税人口表が47都道府県（実際{len(P47)}）')
chk(len(FA) == 47 and len(NO) == 47, '施設・廃校の表が47都道府県')

tot = TP['全国']
chk('全国は373.4万円' in txt, f'本文の全国1人あたり所得が表と一致（表 {tot[3]}万円）')
chk('46.2％' in txt and abs(f(tot[2]) - 46.2) < 0.05, f'納税義務者の人口比 46.2%（表 {tot[2]}%）')
s_num = sum(f(TP[p][1]) for p in P47)
chk(abs(s_num - f(tot[1])) < 1, f'納税義務者の47都道府県合計＝全国行（{s_num:,.0f}／{f(tot[1]):,.0f}）')
s_kom = sum(f(TP[p][7]) for p in P47)
chk(abs(s_kom - 13031) < 1, f'公民館の合計＝13,031館（実際{s_kom:,.0f}）')
chk(abs(s_num/s_kom - f(tot[8])) < 1, f'公民館1館あたり納税義務者＝全国行（{s_num/s_kom:,.0f}／{f(tot[8]):,.0f}）')
chk('4,386人' in txt, f'本文の全国4,386人が表と一致（{s_num/s_kom:,.0f}）')

# 相関を表から再計算して本文と突合
def corr(xs, ys):
    n = len(xs); mx, my = sum(xs)/n, sum(ys)/n
    sx = math.sqrt(sum((x-mx)**2 for x in xs)); sy = math.sqrt(sum((y-my)**2 for y in ys))
    return sum((x-mx)*(y-my) for x, y in zip(xs, ys))/(sx*sy)
pop_d  = [f(TP[p][6]) for p in P47]
tdnum  = [f(TP[p][5]) for p in P47]
tdper  = [f(TP[p][4]) for p in P47]
kom_d  = [f(FA[p][3]) for p in P47]
extinct= [f(NO[p][4]) for p in P47]
for lab, xs, ys, want in [('納税義務者の増減×人口増減率', pop_d, tdnum, 0.914),
                          ('1人あたりの伸び×人口増減率', pop_d, tdper, -0.026)]:
    r = corr(xs, ys)
    chk(abs(round(r,3) - want) < 0.0015, f'{lab} r={want:+.3f}（表から再計算 {r:+.3f}）')
    chk(f'{want:+.3f}'.replace('+','＋').replace('＋','+') in txt or f'r={want:+.3f}' in txt or f'{abs(want):.3f}' in txt,
        f'{lab} の係数が本文に記載')
for lab, ys, want in [('公民館増減率', kom_d, 0.038), ('学校消滅率', extinct, 0.486)]:
    r = corr(tdnum, ys)
    chk(abs(round(r*r,3) - want) < 0.0015, f'{lab}×納税義務者の増減 R²={want:.3f}（再計算 {r*r:.3f}）')
# 四象限の県数
q = collections.Counter()
for p in P47:
    a, b = f(TP[p][5]) > 0, f(TP[p][4]) > 16.4
    q[('増' if a else '減') + ('厚' if b else '薄')] += 1
chk(q['増厚'] == 3 and q['減厚'] == 12 and q['増薄'] == 8 and q['減薄'] == 24,
    f'四象限の県数 3/12/8/24（再集計 {q["増厚"]}/{q["減厚"]}/{q["増薄"]}/{q["減薄"]}）')
chk('12県' in txt and '8県' in txt and '3都県' in txt, '四象限の県数が本文に記載')

print(f'■ 検証結果　OK {len(OK)}件／警告 {len(WARN)}件／エラー {len(ERR)}件\n')
if ERR:  print('【エラー】'); [print('  ✗', e) for e in ERR]
if WARN: print('【警告】');  [print('  !', w) for w in WARN]
print('\n【合格】'); [print('  ✓', o) for o in OK]
sys.exit(1 if ERR else 0)
