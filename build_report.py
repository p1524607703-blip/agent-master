# -*- coding: utf-8 -*-
import json
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

R=json.load(open("/Users/panjinlong/Documents/agent-master/analysis_summary.json",encoding="utf-8"))
A="/Users/panjinlong/Documents/agent-master/report_assets"

doc=Document()
# CJK font
def set_cjk(style_name="Normal", font="Microsoft YaHei"):
    st=doc.styles[style_name]
    st.font.name=font
    st.element.rPr.rFonts.set(qn('w:eastAsia'),font)
set_cjk("Normal"); set_cjk("Heading 1"); set_cjk("Heading 2"); set_cjk("Heading 3"); set_cjk("Title")

NAVY=RGBColor(0x1F,0x3A,0x5F); ORANGE=RGBColor(0xE4,0x79,0x11); GREY=RGBColor(0x55,0x55,0x55)

def H1(t):
    p=doc.add_heading(t,level=1)
    for r in p.runs: r.font.color.rgb=NAVY
    return p
def H2(t):
    p=doc.add_heading(t,level=2)
    for r in p.runs: r.font.color.rgb=ORANGE
    return p
def para(t,bold=False,size=10.5,color=None,align=None,italic=False):
    p=doc.add_paragraph()
    run=p.add_run(t); run.bold=bold; run.italic=italic; run.font.size=Pt(size)
    if color: run.font.color.rgb=color
    if align: p.alignment=align
    return p
def bullet(t,bold_lead=None):
    p=doc.add_paragraph(style="List Bullet")
    if bold_lead:
        r=p.add_run(bold_lead); r.bold=True
    p.add_run(t)
    return p

def table(headers, rows, widths=None, highlight_first_col=False):
    t=doc.add_table(rows=1, cols=len(headers))
    t.style="Light Grid Accent 1"
    t.alignment=WD_TABLE_ALIGNMENT.CENTER
    for i,h in enumerate(headers):
        c=t.rows[0].cells[i]; c.text=""
        run=c.paragraphs[0].add_run(h); run.bold=True; run.font.size=Pt(9.5)
    for row in rows:
        cells=t.add_row().cells
        for i,v in enumerate(row):
            cells[i].text=""
            run=cells[i].paragraphs[0].add_run(str(v)); run.font.size=Pt(9.5)
            if highlight_first_col and i==0: run.bold=True
    if widths:
        for r in t.rows:
            for i,w in enumerate(widths):
                r.cells[i].width=Inches(w)
    return t

# ===================== COVER =====================
tp=doc.add_paragraph()
tp.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=tp.add_run("亚马逊广告投放深度分析报告"); r.bold=True; r.font.size=Pt(22); r.font.color.rgb=NAVY
sp=doc.add_paragraph(); sp.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=sp.add_run("DSP（需求方平台展示型广告） × SA（站内搜索 / 赞助广告）协同与效率诊断"); r.font.size=Pt(12); r.font.color.rgb=GREY
sp2=doc.add_paragraph(); sp2.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=sp2.add_run("品牌：WHITIN ｜ 数据来源：Amazon Marketing Cloud（AMC）探索报表 + DSP 广告活动导出（2026-09-01）"); r.font.size=Pt(9.5); r.italic=True; r.font.color.rgb=GREY
doc.add_paragraph()

# ===================== EXEC SUMMARY =====================
H1("一、核心结论摘要（Executive Summary）")
c=R["campaign"]
bullet(" 当前在投 DSP 广告活动 9 个（暂停 2 个），合计花费约 $%s，带来销售额 $%s，即时 ROAS %.1f、长期 ROAS %.1f；新客（NTB）销售额占比高达 %.0f%%，说明 DSP 拉新与品牌溢出效果显著。"%(
    format(c['cost'],',.0f'), format(c['sales'],',.0f'), c['roas'], c['lt_roas'], c['ntb_sales_share']), "投放大盘：")
bullet(" 全渠道营销漏斗共 278 万意识用户、2.7 万考虑用户、419 转化用户、222 忠诚用户。DSP 触达用户最少（31.6 万，占 11.4%），却贡献 229 个转化（占全渠道 54.7%）与 126 个忠诚用户（占 56.8%）——是事实上“转化与复购”的主力引擎。", "流量结构：")
bullet(" 路径归因显示 77.7%% 的转化路径以 DSP 为首触点；马尔可夫（移除效应）归因中 DSP 权重 0.774，远高于 SP 0.160、SD 0.059、SB 0.007。DSP 并非“锦上添花”，而是转化链路的枢纽。", "DSP 是转化枢纽：")
bullet(" 54%% 的 DSP 用户仅被曝光 1 次（单触购买率 0.029%%，CPA $6.08），而曝光 3–7 次的区间 CPA 仅 $2.1–2.5、购买率提升 10–30 倍。提升有效频次是性价比最高的优化点。", "最大优化点（频次）：")
bullet(" SP（Sponsored Products）占据最大曝光（214 万意识用户，占 76.9%%），但“考虑到转化”率仅 0.65%%、路径 ROAS 仅 0.48，是效率最低的渠道——它在本账户更像“流量池/防守”，而非直接收割。", "SP 效率失衡：")
bullet(" 长期 ROAS（14.6）显著高于即时 ROAS（11.3），证明 DSP 转化存在滞后与站外品牌溢出，不应仅以 7/14 天窗口考核。", "考核口径：")
doc.add_paragraph()

# ===================== CONCEPTS =====================
H1("二、核心概念：DSP 与 SA 是什么、差在哪")
para("在开始解读数据前，先厘清两类广告的本质差异。它们并非“同一平台上的两种出价方式”，而是回答两个完全不同商业问题的工具：", size=10.5)
H2("2.1 一句话区分")
bullet("DSP = 程序化展示/视频广告平台，按受众（行为、兴趣、再营销、相似人群）在 Amazon 站内及站外（Prime Video、Fire TV、Twitch、第三方网站/App）买曝光，计价以 CPM 为主，目标是“创造需求 + 再营销”。", "Amazon DSP（需求方平台）：")
bullet("SA = 站内赞助广告，含 Sponsored Products（商品推广）、Sponsored Brands（品牌推广）、Sponsored Display（展示型定向），按关键词/ASIN/品类/情境定向，计价以 CPC 为主，目标是“收割已经存在的搜索需求”。", "Sponsored Ads（SA，站内搜索广告）：")
H2("2.2 关键差异对照")
table(["维度","Amazon DSP","Sponsored Ads（SP/SB/SD）"],
[["核心目标","创造需求、再营销、全漏斗品牌","收割已有搜索意图、直接转化"],
 ["定向逻辑","受众（行为/兴趣/再营销/相似人群）","关键词 / ASIN / 品类 / 情境"],
 ["主要计价","CPM（千次曝光成本）","CPC（点击成本，SD 也可按 vCPM）"],
 ["曝光位置","Amazon 站内 + 站外（流媒体/第三方）","主要在 Amazon 站内（搜索页/详情页）"],
 ["归因方式","点击 + 曝光（view-through）双归因","以点击归因为主"],
 ["核心指标","触达/频次/DPV/新客率/品牌搜索提升→ROAS","ACoS / ROAS / 搜索词层级"],
 ["适合阶段","拓新、防守竞品、复购、品牌资产","上新排名、守搜索词、高意图收割"],
 ["可观测性","可在 AMC 中做多触点归因/增量","报表自成体系，跨渠道需借助 AMC"]],
 widths=[1.3,2.6,2.6])
para("⚠ 常见误区：Sponsored Display（SD）不是“DSP 轻量版”。二者都买展示库存，但 SD 是自助式赞助格式（简单定向、CPC/vCPM 计费、归入 PPC 报表），DSP 才是真正的人群构建 + 频次控制 + 流媒体 + AMC 度量平台。本报告的“SA”泛指 SP+SB+SD 站内赞助广告。", size=9.5, italic=True, color=GREY)
doc.add_paragraph()

# ===================== DATA SCOPE =====================
H1("三、数据口径与样本说明")
table(["文件","内容口径","关键字段"],
[["AMC 漏斗分析","按广告类型(SB/SP/SD/DSP)的 4 层漏斗与转化率","意识/考虑/转化/忠诚用户数及阶段转化率"],
 ["AMC 站内外承接路径","标准路径到转化（按广告类型）","路径发生次数、购买、购买份额、ROAS、马尔可夫预算分配"],
 ["AMC 自定义触点","自定义路径标签（获客P+/考虑层转化P+等）","自定义路径转化与 ROAS、初始状态分布"],
 ["AMC 曝光频次","触达与频次（广告类型 × F1–F10+）","曝光量、用户、购买率、NTB、CPA、eCPM、成本占比"],
 ["AMC 分时情况","按频次的预算探索（含推荐分时）","各频次桶花费、ROAS、CPM、购买转化率"],
 ["Campaign_Sep_1_2026.csv","DSP 广告活动级导出（11 个活动，9 在投）","展示/点击/成本/销售额/ROAS/新客/品牌搜索/长期ROAS"]],
 widths=[1.7,2.6,2.2])
para("说明：AMC 报表为亚马逊官方营销云的多触点归因口径（用户可在多渠道重复计入，故各渠道“意识用户”之和 > 全渠道合计）；Campaign CSV 为 DSP 侧广告活动级实时导出。SA 侧（SP/SB/SD）仅能从 AMC 聚合口径观察，缺少独立成本明细，下文对“预算占比”的结论带有该局限。", size=9.5, italic=True, color=GREY)
doc.add_paragraph()

# ===================== FUNNEL =====================
H1("四、整体流量结构与漏斗分析")
doc.add_picture(f"{A}/funnel.png", width=Inches(6.3))
doc.add_picture(f"{A}/rates.png", width=Inches(6.3))
table(["广告类型","意识用户","考虑用户","转化用户","忠诚用户","意识到考虑率","考虑到转化率","品牌忠诚率"],
[["SB","117,433","622","37","17","0.53%","5.95%","45.9%"],
 ["SP","2,140,056","16,540","107","46","0.77%","0.65%","43.0%"],
 ["SD","637,838","6,874","46","33","1.08%","0.67%","71.7%"],
 ["DSP","316,224","3,567","229","126","1.13%","6.42%","55.0%"],
 ["全部","2,782,410","27,044","419","222","0.97%","1.55%","53.0%"]],
 widths=[0.9,1.2,1.0,0.9,0.85,1.1,1.05,1.0], highlight_first_col=True)
para("解读：", bold=True, size=10.5)
bullet("SP 是“流量入口”：意识用户 214 万（占全渠道 76.9%），但“考虑到转化”率仅 0.65%、忠诚率 43%，是典型的“广撒网、低转化”渠道——它把海量高意图搜索者拉进漏斗，却很少自己收口。")
bullet("DSP 是“转化与复购引擎”：意识用户最少（31.6 万，占 11.4%），却拿到 229 个转化（占全渠道 54.7%）和 126 个忠诚用户（占 56.8%）；“考虑到转化”率 6.42% 为全渠道最高，是 SP 的近 10 倍。")
bullet("SD 忠诚率最高（71.7%）：展示型再营销在“已考虑人群→复购”上效果突出，但绝对量级小。")
bullet("SB 体量最小、效率中等：适合品牌故事与旗舰店联动，当前更像补充角色。")
doc.add_paragraph()

# ===================== IMPRESSION / CLICK =====================
H1("五、曝光与点击表现（DSP 活动级）")
para("基于 9 个在投 DSP 活动汇总：展示量 %s、点击量 %s、混合 CTR %.2f%%、CPC $%.2f、CPM $%.2f；合计触达（reach）字段在导出中为 0，建议后续补全触达/频次去重口径。"%(
    format(c['impr'],','), format(c['clicks'],','), c['ctr'], c['cpc'], c['cpm']), size=10.5)
per=sorted(R["per_campaign"], key=lambda x:-(x["roas"] or 0))
table(["广告活动（简称）","展示量","点击","成本$","销售额$","ROAS","长期ROAS","CPC$","品牌搜索","NTB销售占比"],
[[p["name"].replace("WHITIN - ","").replace(" - Total Roas",""),
  format(p["impr"],","), p["clicks"], format(round(p["cost"],0),","), format(round(p["sales"],0),","),
  "%.1f"%(p["roas"] or 0), "%.1f"%(p["lt_roas"] or 0), "%.2f"%(p["cpc"] or 0),
  p["brand_search"], "%.0f%%"%(p["ntb_sales_share"]*100 if p["ntb_sales_share"] else 0)] for p in per],
 widths=[1.9,0.95,0.6,0.7,0.85,0.6,0.75,0.55,0.75,0.85])
doc.add_picture(f"{A}/roas_campaign.png", width=Inches(6.3))
para("解读：", bold=True, size=10.5)
bullet("高效活动：Toddler Remarketing P+（ROAS 13.1、品牌搜索 675）、All Audiences（ROAS 15.8、长期 ROAS 20.2、品牌搜索 209）、Toddler Cust Acq P+（ROAS 10.0、品牌搜索 408）表现突出，且明显带动品牌搜索量（halo 效应）。")
bullet("低效/高风险活动：Clogs CS CMP（ROAS 2.9，最低）、Remarketing P+ 的 CPC 高达 $0.40（其余多在 $0.13–0.28）；Clogs AW Mules and Clogs CPDPV（ROAS 1.9）已暂停。建议把低效活动的受众/创意向高效模板迁移。")
bullet("2 个活动处于暂停且零花费：需确认是测试遗留还是策略性暂停，避免账户结构臃肿。")
doc.add_paragraph()

# ===================== CONVERSION EFFICIENCY =====================
H1("六、转化效率：频次、路径与 ROAS")
H2("6.1 曝光频次 × 购买率（DSP）")
doc.add_picture(f"{A}/freq.png", width=Inches(6.3))
table(["频次","用户占比","购买量","单频购买率","CPA$","成本占比"],
[["F1（仅 1 次）","54.1%","50","0.029%","6.08","18.1%"],
 ["F2","25.4%","108","0.135%","3.10","20.0%"],
 ["F3","5.6%","56","0.314%","2.36","7.9%"],
 ["F4","4.5%","75","0.526%","1.95","8.7%"],
 ["F5–F7","4.7%","124","0.50–0.90%","2.1–2.6","9.0%"],
 ["F8–F10+","4.7%","121","0.66–0.88%","3.7–4.3","25.3%"]],
 widths=[1.2,1.0,0.9,1.2,0.8,1.0])
para("解读：单触（F1）用户占了一半以上，却只贡献极低购买率且 CPA 最高（$6.08）；购买率随频次陡增，在 F3–F7 区间达到最优性价比（CPA $2.1–2.5、购买率提升 10–30 倍）。当前预算大量“浪费”在只触达一次的用户上，是首要优化杠杆。", size=10.5)
H2("6.2 路径到转化 ROAS（站内外承接）")
table(["转化路径","路径发生次数","购买","购买份额","路径ROAS"],
[["[DSP] 首触 DSP","308,054","275","77.7%","6.40"],
 ["[SP] 首触 SP","3,018","48","13.6%","0.48"],
 ["[SD] 首触 SD","2,683","14","4.0%","99.57"],
 ["[SP→DSP]","5,616","4","1.1%","0.02"],
 ["[DSP→SD]","28","7","2.0%","79.78"],
 ["[DSP→SB]","8","3","0.9%","7.12"]],
 widths=[1.8,1.5,0.8,1.0,1.0])
para("解读：以 DSP 为首触的路径贡献了 77.7% 的购买量；SD 首触 ROAS 高达 99.6（量级小但重定向极强）；SP 首触 ROAS 仅 0.48，单独收割能力弱。多触点路径（SP→DSP、DSP→SB）印证“SA 引流 + DSP 收口/再营销”的协同形态。", size=10.5)
doc.add_paragraph()

# ===================== BUDGET =====================
H1("七、预算消耗与归因分配")
doc.add_picture(f"{A}/markov.png", width=Inches(6.0))
para("马尔可夫（移除效应）归因：若移除某触点后转化大幅下降，说明该触点对转化贡献最大。结果 DSP 0.774 > SP 0.160 > SD 0.059 > SB 0.007——DSP 是当之无愧的转化枢纽，SP 次之（守住搜索收口），SB 贡献极小。", size=10.5)
mc=R["markov_custom"]
para("自定义触点模型的“初始状态分布”显示约 87.8% 的路径流量首触落在 SA_SP，考虑层转化P+/获客P+ 各约 4.3%——即绝大多数用户先经由 SP 进入，再由 DSP/自定义 P+ 路径完成转化，进一步印证“SP 引流、DSP 转化”的分工。", size=10.5)
para("当前预算现状（DSP 侧）：9 个在投活动单日预算多为 $10/活动，合计日预算约 $90、本期花费约 $2,588。由于缺少 SA 侧独立成本，无法精确计算 DSP:SA 实际预算比；但结合归因权重，若 DSP 实际预算占比明显低于其 0.774 的移除效应权重，则存在“预算错配”，应上调 DSP 占比、压缩 SB。", size=10.5)
doc.add_paragraph()

# ===================== SYNERGY =====================
H1("八、DSP 与 SA 的协同与差异")
bullet("本质分工：SA（尤其 SP）是“需求收割机”，坐在搜索框里抢高意图流量；DSP 是“需求制造机 + 再营销机”，在站内站外按人群种草并把离开详情页的人拉回来。本账户两者不是替代关系，而是上下游关系。", "分工：")
bullet("数据印证：SP 贡献 76.9% 的意识用户（流量原料），DSP 贡献 54.7% 的转化与 56.8% 的忠诚用户（收口与复购）；路径中 [SP→DSP] 与 [DSP→SP] 并存，说明二者在用户旅程中交替出现。","互补：")
bullet("品牌溢出：DSP 活动显著拉动品牌搜索量（合计 1,590 次；Toddler 系列占 1,100+），而品牌搜索量正是“种草→日后主动搜品牌词”的滞后信号，无法在 DSP 直接转化里体现，却在 SP 效率上兑现。","溢出：")
bullet("差异结论：用同一把 ROAS 尺子量两类广告会误判——DSP 应考核长期 ROAS + 新客率 + 品牌搜索提升；SP 应考核“防守词占比/ACoS 红线”而非绝对 ROAS。","考核：")
doc.add_paragraph()

# ===================== PROBLEMS / OPTIMIZATION =====================
H1("九、问题诊断与优化空间")
items=[
 ("1. 提升 DSP 有效频次（最高优先级）","54% 用户仅曝光 1 次、CPA $6.08。将目标频次抬到 3–6，用频次上限/频次优化与再营销受众叠加，把单触预算转移到 F3–F7 区间，预计同等花费可显著降低 CPA、提升购买量。"),
 ("2. 重估 SP 预算与结构","SP 曝光最大但转化效率最低（考虑到转化 0.65%、路径 ROAS 0.48）。建议：① 用搜索词报告做负向隔离，把纯防守/泛词预算释放；② 对高意图词用更激进出价、对低效词降预算或否词；③ 不按统一 ROAS 考核 SP，改看“防守份额 + ACoS 红线”。"),
 ("3. 校准预算分配至归因权重","马尔可夫显示 DSP 移除效应 0.774。若 DSP 实际预算占比偏低，应上调 DSP、压缩 SB（移除效应仅 0.7%）。需先补全 SA 侧成本数据以测算真实 DSP:SA 比。"),
 ("4. 复制高效活动模板、清理低效活动","把 Clogs CS CMP（ROAS 2.9）、Remarketing P+（CPC $0.40）向 All Audiences / Toddler Remarketing（ROAS 13–16）的受众与创意靠拢；暂停且零花费的 2 个活动确认后清理，减少结构噪声。"),
 ("5. 放大 SB 品牌价值","SB 体量最小但忠诚率尚可，建议结合品牌旗舰店/视频创意强化“考虑层”种草，提升其在漏斗考虑阶段的贡献。"),
 ("6. 用长期口径考核 DSP","长期 ROAS 14.6 > 即时 11.3。把 DSP 核心 KPI 设为“长期 ROAS + NTB 新客率 + 品牌搜索量提升”，避免因短期窗口低估其价值而错砍预算。"),
 ("7. 数据补齐","当前缺 SA 侧独立成本与 DSP reach 去重口径。补全后可做真正的 DSP:SA 预算配比与增量（incrementality）分析，把本报告结论从“归因”推向“因果”。"),
]
for t,d in items:
    p=doc.add_paragraph(style="List Number")
    r=p.add_run(t+"："); r.bold=True
    p.add_run(d)
doc.add_paragraph()

# ===================== APPENDIX =====================
H1("附录：关键指标汇总")
table(["指标","数值"],
[["在投 / 暂停 DSP 活动数","9 / 2"],
 ["DSP 合计展示量","%s"%format(c['impr'],',')],
 ["DSP 合计点击量 / CTR","%s / %.2f%%"%(format(c['clicks'],','),c['ctr'])],
 ["DSP 合计成本 / 销售额","$%s / $%s"%(format(c['cost'],',.0f'),format(c['sales'],',.0f'))],
 ["DSP 即时 ROAS / 长期 ROAS","%.1f / %.1f"%(c['roas'],c['lt_roas'])],
 ["DSP NTB 新客销售额占比","%.0f%%"%c['ntb_sales_share']],
 ["全渠道转化用户 / 忠诚用户","419 / 222"],
 ["DSP 占全渠道转化 / 忠诚","54.7% / 56.8%"],
 ["首触 DSP 路径购买份额","77.7%"],
 ["马尔可夫移除效应 DSP/SP/SD/SB","0.774 / 0.160 / 0.059 / 0.007"],
 ["DSP 最优频次区间（CPA 最低）","F3–F7（CPA $2.1–2.5）"]],
 widths=[3.2,3.0], highlight_first_col=True)

doc.save("/Users/panjinlong/Documents/agent-master/亚马逊广告投放深度分析报告_W81K.docx")
print("REPORT_SAVED")
