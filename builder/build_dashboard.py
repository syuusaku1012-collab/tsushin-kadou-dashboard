#!/usr/bin/env python3
# 通信稼働 実績ダッシュボード ビルダー
# 使い方: python3 build_dashboard.py data.csv dashboard.html
#  data.csv = スプレッドシート「通信 稼働データ」をCSVエクスポートして復号したもの
import csv, json, sys, datetime, os, re
from collections import defaultdict

SRC = sys.argv[1] if len(sys.argv)>1 else 'data.csv'
OUT = sys.argv[2] if len(sys.argv)>2 else 'dashboard.html'
TPL = sys.argv[3] if len(sys.argv)>3 else 'template2.html'

# 退職者など除外リスト（excludes.txt: 1行1名、(所属)や空白は無視して照合）
def _norm(s): return re.sub(r'\s|　','',re.sub(r'\(.*?\)|（.*?）','',s or ''))
EXCLUDE=set()
if os.path.exists('excludes.txt'):
    for ln in open('excludes.txt',encoding='utf-8'):
        if ln.strip(): EXCLUDE.add(_norm(ln))

rows=list(csv.reader(open(SRC,encoding='utf-8')))
data=rows[2:]  # 0=グループ見出し,1=列見出し
def num(x):
    x=(x or '').strip()
    try:return float(x)
    except:return 0.0
ITEMS=[('乗換_端末あり',10,1.25),('乗換_SIMのみ',11,1.0),('新規',12,1.0),('機種変更',13,0.5),
 ('dカードシルバー',14,0.2),('dカードゴールド以上',15,0.5),('光Wi-Fi',16,1.5),('Amazonプライム',17,0.1),('ディズニープラス',18,0.1)]
CARRIERS={'au':19,'SB':20,'UQ':21,'YM':22,'楽天':23,'格安':24}
AGES={'若年層':32,'中年層':33,'高年層':34}
SEAT=7; DEAL=8
def blank():
    return {'稼働数':0,'総ポイント':0.0,'着座':0.0,'成約':0.0,
            'items':{k:{'件数':0.0,'ポイント':0.0} for k,_,_ in ITEMS},
            'carriers':{k:0.0 for k in CARRIERS},'ages':{k:0.0 for k in AGES}}
def add(b,r):
    b['稼働数']+=1; b['着座']+=num(r[SEAT]); b['成約']+=num(r[DEAL])
    for k,idx,pt in ITEMS:
        c=num(r[idx]); b['items'][k]['件数']+=c; b['items'][k]['ポイント']+=c*pt; b['総ポイント']+=c*pt
    for k,idx in CARRIERS.items(): b['carriers'][k]+=num(r[idx])
    for k,idx in AGES.items(): b['ages'][k]+=num(r[idx])
agg=defaultdict(lambda: defaultdict(blank))
# person: month -> name -> category(支社/代理店/総合) -> bucket
person=defaultdict(lambda: defaultdict(lambda: defaultdict(blank)))
for r in data:
    if len(r)<37: r=r+['']*(37-len(r))
    if not any(c.strip() for c in r): continue
    gen=(r[3] or '').strip(); month=(r[36] or '').strip() or '(月不明)'; name=(r[2] or '').strip()
    if _norm(name) in EXCLUDE: continue   # 退職者は集計・アプリから完全除外
    cat='代理店' if gen=='代理店' else '支社'   # 本社・本社イベントは支社に合算
    add(agg[month][cat],r); add(agg[month]['総合'],r)
    if name:
        add(person[month][name][cat],r)
        add(person[month][name]['総合'],r)
def finalize(b):
    out=dict(b); n=b['稼働数'] or 0
    out['総合生産性']=round(b['総ポイント']/n,3) if n else 0
    out['着座生産性']=round(b['着座']/n,3) if n else 0
    out['成約生産性']=round(b['成約']/n,3) if n else 0
    out['総ポイント']=round(b['総ポイント'],2)
    it={}
    for k,_,_ in ITEMS:
        p=b['items'][k]['ポイント']
        it[k]={'件数':b['items'][k]['件数'],'ポイント':round(p,2),'生産性':round(p/n,3) if n else 0}
    out['items']=it; return out
# 有効な月のみ表示（着座も獲得も0の“幻の月”＝対象月の誤入力を自動で除外。
#  実データが入った瞬間にその月が自動で出るので、翌月分の自動表示は維持される）
def is_active(m):
    t=agg[m].get('総合')
    return bool(t) and (t['着座']>0 or t['成約']>0)
ACTIVE=[m for m in sorted(agg) if is_active(m)]
result={'months':{},'persons':{}}
for m in ACTIVE:
    result['months'][m]={c:finalize(agg[m][c]) for c in ['支社','代理店','総合'] if c in agg[m]}
for m in ACTIVE:
    if m not in person: continue
    result['persons'][m]={}
    for nm in person[m]:
        result['persons'][m][nm]={c:finalize(person[m][nm][c]) for c in person[m][nm]}

now=datetime.datetime.utcnow()+datetime.timedelta(hours=9)
gen=(f"データ元：Googleスプレッドシート「通信 稼働データ」／最終更新 {now.strftime('%Y-%m-%d %H:%M')} JST（毎朝7:00 JST 自動更新）<br>"
     f"※ 依頼元「本社」「本社イベント」の稼働は支社に合算。総合＝支社＋代理店。<br>"
     f"※ ポイント：乗換端末あり1.25／乗換SIM1.0／新規1.0／機変0.5／dシルバー0.2／dゴールド以上0.5／光(ドコモ光+ホーム5G)1.5／Amazon0.1／ディズニー0.1")
tpl=open(TPL,encoding='utf-8').read()
out=tpl.replace('__DATA__',json.dumps(result,ensure_ascii=False)).replace('__GENINFO__',gen)
open(OUT,'w',encoding='utf-8').write(out)
print('OK ->',OUT,len(out),'chars ; months=',list(result['months'].keys()),'; people=',sum(len(v) for v in result['persons'].values()))
