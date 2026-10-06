import openpyxl, pandas as pd, json, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ---- Chinese font ----
CN = None
for cand in ["/System/Library/Fonts/PingFang.ttc","/System/Library/Fonts/STHeiti Light.ttc",
             "/Library/Fonts/Arial Unicode.ttf","/System/Library/Fonts/Hiragino Sans GB.ttc"]:
    import os
    if os.path.exists(cand):
        CN = cand; break
if CN:
    fm.fontManager.addfont(CN)
    plt.rcParams["font.family"] = fm.FontProperties(fname=CN).get_name()
plt.rcParams["axes.unicode_minus"] = False

OUT="/Users/panjinlong/Documents/agent-master/report_assets"
import os
os.makedirs(OUT, exist_ok=True)

def money(s):
    if pd.isna(s): return None
    s=str(s).replace("US$","").replace("$","").replace(",","").strip()
    if s in ("","NaN","None"): return None
    try: return float(s)
    except: return None

R={}

# ============ 1. CAMPAIGN CSV (DSP) ============
df = pd.read_csv("/Users/panjinlong/Downloads/Campaign_Sep_1_2026.csv")
for c in ["广告活动预算金额","总成本","销售额","CPM","CPC","点击率","每千次可见展示成本 (vCPM)","可见展示量占比","展示量","点击量","用户触达量","购买量","销售额（品牌新客）","商品详情页浏览量","品牌搜索量","长期销售","长期 ROAS","ROAS","品牌新客购买占比","品牌新客销售额占比","投放率（当前投放）"]:
    if c in df.columns:
        df[c+"_n"]=df[c].apply(money)
active = df[df["状态代码"]=="DELIVERING"].copy()
def ssum(col): 
    v=active[col+"_n"].dropna().sum(); return round(v,2) if pd.notna(v) else None
camp = {
 "n_total": len(df), "n_active": len(active), "n_paused": len(df)-len(active),
 "impr": int(active["展示量_n"].sum()),
 "clicks": int(active["点击量_n"].sum()),
 "cost": ssum("总成本"),
 "sales": ssum("销售额"),
 "sales_ntb": ssum("销售额（品牌新客）"),
 "reach": ssum("用户触达量"),
 "dpv": ssum("商品详情页浏览量"),
 "brand_search": ssum("品牌搜索量"),
 "lt_sales": ssum("长期销售"),
}
camp["ctr"]=round(camp["clicks"]/camp["impr"]*100,3) if camp["impr"] else None
camp["cpc"]=round(camp["cost"]/camp["clicks"],3) if camp["clicks"] else None
camp["cpm"]=round(camp["cost"]/camp["impr"]*1000,3) if camp["impr"] else None
camp["roas"]=round(camp["sales"]/camp["cost"],3) if camp["cost"] else None
camp["lt_roas"]=round(camp["lt_sales"]/camp["cost"],3) if camp["cost"] else None
camp["ntb_sales_share"]=round(camp["sales_ntb"]/camp["sales"]*100,2) if camp["sales"] else None
R["campaign"]=camp
# per active campaign key metrics
per=[]
for _,r in active.iterrows():
    per.append({
      "name":r["广告活动名称"],"impr":int(r["展示量_n"] or 0),"clicks":int(r["点击量_n"] or 0),
      "cost":r["总成本_n"],"sales":r["销售额_n"],"roas":r["ROAS_n"],"lt_roas":r["长期 ROAS_n"],
      "cpc":r["CPC_n"],"cpm":r["CPM_n"],"ctr":r["点击率_n"],"ntb_sales_share":r["品牌新客销售额占比_n"],
      "brand_search":int(r["品牌搜索量_n"] or 0),"dpv":int(r["商品详情页浏览量_n"] or 0)
    })
R["per_campaign"]=per

# ============ 2. FUNNEL ============
wb=openpyxl.load_workbook("/Users/panjinlong/Downloads/AMCExploration_W81K漏斗分析.xlsx",read_only=True,data_only=True)
ws=wb["营销漏斗"]
fun=[]
for r in ws.iter_rows(values_only=True):
    if r[0] in ("SB","SP","SD","DSP","全部"):
        fun.append({"type":r[0],"aware":r[1],"cons":r[2],"conv":r[3],"loyal":r[4],
                    "a2c":r[5],"c2conv":r[6],"loyalty":r[7]})
R["funnel"]=fun

# ============ 3. PATH TO PURCHASE (standard) ============
wb2=openpyxl.load_workbook("/Users/panjinlong/Downloads/AMCExploration_W81K站内外承接路径.xlsx",read_only=True,data_only=True)
ws2=wb2["顶级转化路径标签"]
paths=[]
for r in ws2.iter_rows(values_only=True):
    if r[0] and str(r[0]).startswith("[[") :
        paths.append({"path":r[0],"occ":r[1],"rate":r[2],"buy":r[3],"buy_share":r[4],"buyers":r[5],"buyer_rate":r[6],"roas":r[7]})
R["path_standard"]=paths
ws2b=wb2["建议预算分配"]
markov_std=[]
for r in ws2b.iter_rows(values_only=True):
    if r[0] and r[0]!="漏斗":
        markov_std.append({"chan":r[0],"initial":r[1],"markov":r[2]})
R["markov_standard"]=markov_std

# ============ 4. CUSTOM TOUCHPOINTS ============
wb3=openpyxl.load_workbook("/Users/panjinlong/Downloads/AMCExploration_W81K自定义触点.xlsx",read_only=True,data_only=True)
ws3=wb3["顶级转化路径标签"]
cpaths=[]
for r in ws3.iter_rows(values_only=True):
    if r[0] and str(r[0]).startswith("[[") :
        cpaths.append({"path":r[0],"occ":r[1],"rate":r[2],"buy":r[3],"buy_share":r[4],"buyers":r[5],"buyer_rate":r[6],"roas":r[7]})
R["path_custom"]=cpaths
ws3b=wb3["建议预算分配"]
markov_cust=[]
for r in ws3b.iter_rows(values_only=True):
    if r[0] and r[0]!="漏斗":
        markov_cust.append({"chan":r[0],"initial":r[1],"markov":r[2]})
R["markov_custom"]=markov_cust

# ============ 5. REACH & FREQUENCY ============
wb4=openpyxl.load_workbook("/Users/panjinlong/Downloads/AMCExploration_W81K曝光频次.xlsx",read_only=True,data_only=True)
ws4=wb4["覆盖和曝光频率"]
freq=[]
for r in ws4.iter_rows(values_only=True):
    if r[0] in ("DSP","SB","SP","SD"):
        freq.append({"type":r[0],"freq":r[1],"impr":r[2],"users":r[3],"user_pct":r[4],
                     "buy":r[5],"buy_rate":r[6],"ntb_user":r[7],"ntb_user_pct":r[8],
                     "ntb_buy":r[9],"ntb_conv":r[10],"ntb_buy_share":r[11],"cost":r[12],
                     "sales":r[13],"cost_pct":r[14],"cpa":r[15],"ecpm":r[16]})
R["freq"]=freq

with open("/Users/panjinlong/Documents/agent-master/analysis_summary.json","w",encoding="utf-8") as f:
    json.dump(R,f,ensure_ascii=False,indent=2,default=str)

# ===================== CHARTS =====================
COL={"DSP":"#E47911","SP":"#1f77b4","SB":"#2ca02c","SD":"#9467bd","全部":"#888888"}

# Chart A: Funnel awareness->loyal by channel (log-ish grouped bar of 4 stages)
types=[f["type"] for f in fun if f["type"]!="全部"]
stages=["aware","cons","conv","loyal"]
labels=["意识","考虑","转化","忠诚"]
fig,ax=plt.subplots(figsize=(7.5,4.2))
x=range(len(types)); w=0.2
for i,s in enumerate(stages):
    vals=[next(f for f in fun if f["type"]==t)[s] for t in types]
    ax.bar([xi+w*i for xi in x],[v/1000 for v in vals],w,label=labels[i])
ax.set_xticks([xi+1.5*w for xi in x]); ax.set_xticklabels(types)
ax.set_ylabel("用户数(千)"); ax.set_title("各广告类型营销漏斗用户规模")
ax.legend(); fig.tight_layout(); fig.savefig(f"{OUT}/funnel.png",dpi=130); plt.close(fig)

# Chart B: conversion efficiency rates (a2c, c2conv, loyalty) by channel
fig,ax=plt.subplots(figsize=(7.5,4.0))
x=range(len(types)); w=0.25
for i,key in enumerate(["a2c","c2conv","loyalty"]):
    vals=[next(f for f in fun if f["type"]==t)[key]*100 for t in types]
    ax.bar([xi+w*i for xi in x],vals,w,label={"a2c":"意识到考虑率","c2conv":"考虑到转化率","loyalty":"品牌忠诚率"}[key])
ax.set_xticks([xi+1*w for xi in x]); ax.set_xticklabels(types)
ax.set_ylabel("%"); ax.set_title("各渠道漏斗转化/留存率对比")
ax.legend(); fig.tight_layout(); fig.savefig(f"{OUT}/rates.png",dpi=130); plt.close(fig)

# Chart C: Frequency vs purchase rate (DSP) cumulative
dsp_freq=[f for f in freq if f["type"]=="DSP"]
order=["F1","F2","F3","F4","F5","F6","F7","F8","F9","F10+"]
dsp_freq=sorted(dsp_freq,key=lambda f:order.index(f["freq"]) if f["freq"] in order else 99)
fig,ax=plt.subplots(figsize=(7.5,4.2))
xs=[f["freq"] for f in dsp_freq]
ax.bar(xs,[f["buy_rate"]*100 for f in dsp_freq],color=COL["DSP"],label="单频购买率")
ax2=ax.twinx()
ax2.plot(xs,[f["user_pct"]*100 for f in dsp_freq],"o-",color="#1f77b4",label="用户占比")
ax.set_xlabel("曝光频次(F=触达次数)"); ax.set_ylabel("单频购买率(%)"); ax2.set_ylabel("用户占比(%)")
ax.set_title("DSP 曝光频次 vs 购买率（频次越高转化越强）")
ax.legend(loc="upper left"); ax2.legend(loc="upper right"); fig.tight_layout()
fig.savefig(f"{OUT}/freq.png",dpi=130); plt.close(fig)

# Chart D: ROAS by active DSP campaign
fig,ax=plt.subplots(figsize=(8,4.6))
names=[p["name"].replace("WHITIN - ","").replace(" - Total Roas","") for p in per]
roas=[p["roas"] or 0 for p in per]
bars=ax.barh(range(len(per)),roas,color=COL["DSP"])
ax.set_yticks(range(len(per))); ax.set_yticklabels(names,fontsize=8)
ax.invert_yaxis(); ax.set_xlabel("ROAS(销售额/成本)")
ax.set_title("各在投 DSP 广告活动 ROAS")
for i,v in enumerate(roas): ax.text(v+0.2,i,f"{v:.1f}",va="center",fontsize=8)
fig.tight_layout(); fig.savefig(f"{OUT}/roas_campaign.png",dpi=130); plt.close(fig)

# Chart E: Markov removal-effect budget allocation (standard)
fig,ax=plt.subplots(figsize=(7,4))
mc=[m for m in markov_std if m["markov"]]
mc=sorted(mc,key=lambda m:m["markov"],reverse=True)
ax.bar([m["chan"] for m in mc],[m["markov"]*100 for m in mc],color=[COL.get(m["chan"],"#999") for m in mc])
ax.set_ylabel("马尔可夫移除效应权重(%)"); ax.set_title("路径归因：各触点移除效应(Markov)\n数值越高=对转化贡献越大")
for i,m in enumerate(mc): ax.text(i,m["markov"]*100+0.5,f"{m['markov']*100:.1f}%",ha="center",fontsize=9)
fig.tight_layout(); fig.savefig(f"{OUT}/markov.png",dpi=130); plt.close(fig)

print(json.dumps(R,ensure_ascii=False,indent=2,default=str)[:4000])
print("\nCHARTS_WRITTEN")
