#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把会议纪要生成单文件 HTML（light 主题，可折叠全文）。"""
import html
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ---------- 数据 ----------
META = {
    "title": "2026-09-23 周会纪要",
    "date": "2026-09-23",
    "start": "09:59",
    "duration": "41 分 31 秒",
    "segments": 825,
    "source": "微信语音 · 39 MB · AAC 48kHz 立体声",
    "engine": "mlx-whisper large-v3-turbo（本地推理，用时 4 分 10 秒）",
}

TLDR = "四线并行：技术侧在「把数据打通」，业务侧在「把广告做细」，视觉侧在「把品牌做统一」，管理侧在「把能力沉淀成流程」。全场的核心矛盾只有一个 —— <b>数据怎么自动、合规、可持续地流进来</b>。"

DECISIONS = [
    ("分组表不新建", "直接对接现有绩效系统里已有的那张表", "该表变更不多；双头维护必然导致两边对不上"),
    ("DSP 投在自己账号里", "不走服务商渠道", "① 数据沉淀在对方，不合作就访问不了；② 自家账号里 DSP 与广告数据打通更顺；③ 摸索出的方法易被对方复制"),
    ("费用分摊按归因", "谁受益谁分摊", "投 A 款但 30% 成交出在 B 款 → B 款也要分摊。大方向运营已同意，比例细节后续再谈"),
    ("口径不变，加一层视图", "底层仍是 SalesSKU / ASIN，新增「款式级」表", "小组级那张表要保留（每月费用分摊要用）"),
    ("知识库用 GitHub", "不用付费仓库", "对比后 GitHub 更合适"),
    ("知识库前期先用起来", "不急于出规范", "先让大家熟悉，后续再流程化"),
    ("视觉规范统一到「系列级」", "不是统一到品牌级", "不同产品线可以用不同主色调"),
    ("研究新形式 > 修修补补", "广告活动数量在 AI 加持下不再是限制", "可以做得很细，一条大链接几十到几百个活动各有作用"),
    ("预算拆小多开", "大预算 → 小额多活动", "原 $100–200 起步 → 一天 $15 开 20 个，总额相近但更可控"),
]

TODOS = [
    ("做「分摊到款式级」的表，从现有数据导出给运营", "A / B", "复用同一份数据，避免多系统各维护一份", "high"),
    ("补齐 79 个测试广告的效果结论与优化建议", "B", "报告已出，效果与建议还在 VI 那边", "high"),
    ("验证 Codex 多账号代理/中转通路（阿里云日本站）", "A", "先跑通链路再谈部署", "mid"),
    ("摸清 AMC / AWS 数据链路：能否不用外链、账号如何确认", "A", "有外链跳转，不敢直接放进资料里试", "mid"),
    ("图片生成网页管理员界面上线，放提示词给运营用", "C", "后续新增模块走管理流程加入", "mid"),
    ("研究品牌视觉规范（色彩/字体/页面），几周内出初稿", "C", "定位为未来一个月主线", "mid"),
    ("Logo 优化：字体风格不大改，只优化比例 + 颜色适配", "C", "需适配长条 / 方形 / 圆形", "low"),
    ("补写品牌故事（Brand Story）", "C", "现状：为了卖货弄了个商标，没有故事", "low"),
    ("建个人草稿库 + 公司共享库两级 GitHub 知识库", "C", "每周整理一次再上传", "mid"),
    ("研究团队级知识库的共享与检索方案（本地 vs 云端）", "全员", "Obsidian 同步是存到它自己云端；本地部署共享是难点", "mid"),
    ("确定 skills 优先级排序 + AGENTS.md 技能分级", "全员", "区分团队首要技能与个人需要技能", "low"),
]

SECTIONS = [
    {
        "id": "s1",
        "no": "4.1",
        "title": "广告数据中台",
        "who": "【A · 数据与系统】",
        "blocks": [
            ("✅ 已完成", [
                "数据库<b>已搭好并接入控制台</b>，后端 <b>FastAPI</b>，基本由 AI 维护。",
                "映射链条理清：<b>子ASIN → 父ASIN → 运营组</b>。其中 <b>子ASIN → 运营组</b> 是<b>唯一可确定</b>的边。",
                "仍有零星分不清的（举例 <b>W2030</b> 这类 ASIN）在慢慢调整 —— ⚠️ 与本地已知的 <code>B0DTK7FK2M</code> 被 1 条自指错标行污染成 <code>mixed_parent</code> 的问题<b>高度疑似同一件事</b>。",
                "<b>CPO 计算</b>：按广告类型分类后计算，对数据库脚本压力不大。",
            ]),
            ("📌 关于分组表的口径决定（重要）", [
                "A 建议<b>不要自己再建一套分组表</b>，直接用公司<b>现有绩效系统</b>里已有的那张表 → <b>已拍板</b>。",
                "原因链：运营自己创建并<b>认领 Seller SKU</b>；公司算绩效时<b>也是按 SKU 落到小组</b>（每组卖多少、利润多少、花了多少费用）。",
                "让现有表与中台对接即可，该表变更不多，避免「这个系统维护一次、那个系统再维护一次 → 对不上」。",
            ]),
            ("🆕 本周新增", [
                "做了一套 <b>DSP 分析链</b>模板。⚠️ 会上提到「之前分析成 <b>W8K</b> 了，实际上是 <b>W8K2</b>」（款号存疑），<b>W8K2 刚做完一份，数据还没上传</b>。",
            ]),
            ("🔍 待验证：数据获取链路", [
                "A 发现 <b>Codex 上可以连到 AWS 上的分析平台</b>（结合后文「AMC 容器」，疑似 <b>Amazon Marketing Cloud</b>），但会<b>跳出一个外链</b>，出于安全考虑<b>不敢直接放进资料里试</b>。",
                "会上共识：<b>核心问题就是「数据怎么获取」</b> —— 走 API，还是走某种桥接？AWS 数据分析链路与 GPT 之间「肯定是有桥接的」。",
                "<b>唯一待验证项</b>：账户确认（确认账户后第三方应该能打通）。",
                "【负责人】结论：<b>终极形态是 AI 直接从广告账户取数</b> —— 但取决于亚马逊广告平台到底开放哪些接口。",
            ]),
            ("🔧 AI 工具链 / 代理方案", [
                "<b>方案一（自家）</b>：阿里云<b>日本站服务器</b>做中转 → 代理接入 Codex 客户端 → 再分发给各处。",
                "<b>方案二（同行演示）</b>：<b>20x 账号</b>装在虚拟机上做<b>中转站</b>；一个账号对应一个中转站 + 独立隧道/代理；在 Codex 客户端里<b>选择中转站</b>再启动 Codex，即可正常使用 GPT 的 token。",
                "<b>多账号轮换</b>：某账号触达上限进入「冷静期」时，<b>切到另一个中转账户接着用</b>；公司层面理论上<b>两三个账号循环就够</b>。可统计每个用户消耗多少 token。负责人点评：「看起来也不是很复杂的样子。」",
                "<b>风险点</b>：新开账户目前<b>买不到 20 倍套餐</b>（已下架）；存在一定的<b>代理风险</b>。",
                "<b>IP 分流疑虑已澄清</b>：实际用户都在<b>日本站的电脑</b>上，出口 IP 很稳定，甚至能<b>绕开翻墙影响</b>，国内可正常访问。",
                "<b>A 自己的用法</b>：账户级<b>网页端数据</b> + <b>DeepSeek 的 agent</b>，不消耗 token；写代码时用网页端免费流量接入本地数据；<b>多 subagent 并发</b>。「把网页端当 API 用」，中间有一条<b>隧道</b>连到本地，把 agent 的工作流和 <b>skills</b> 全部注入网页端。",
            ]),
        ],
    },
    {
        "id": "s2",
        "no": "4.2",
        "title": "管理侧定调",
        "who": "【负责人】",
        "quote": "大家要解决的问题是在于说，当整个团队都要用的时候，就变成一种情况 —— 人手一个 Codex。",
        "blocks": [
            ("🎯 三阶段判断", [
                "<b>① 现在 = 探索阶段</b>：目标是<b>让大家先用起来</b>。不做各种约束，因为每个人接受程度和使用效果不一样，对 AI 熟悉程度也不够。",
                "<b>② 下一步 = 流程化</b>：真正从业务流程来讲，它是需要流程化的 —— 做什么事、调用哪个 <b>skill</b>、怎么得到结果、结果传到哪。",
                "<b>③ 终局 = 规模化 / SOP</b>：此时<b>账号和 token 必须够多</b>，不能「用着用着就触上限」。",
            ]),
            ("💸 规模化的代价（真实痛点）", [
                "举例：「让他帮我写一个功能，<b>思考了三十多分钟，卡掉五小时上限</b>。」 → 流程化以后这类等待不可接受。",
            ]),
            ("🚀 终极形态", [
                "把能力<b>沉淀成一个个 agent</b>（「这个 agent 是做什么功能的」），大家按需调用 → 公司业务流程<b>相对 SOP 化</b>，<b>不再需要人人有账号</b>，也<b>解决了技能沉淀问题</b>。",
                "更远一步：单一技能之后，可能直接在 AI 里把<b>全流程</b>跑完 —— 例如优化一个广告：从数据分析 → 调整建议 → 调整执行，<b>全在 AI 内完成</b>。",
            ]),
        ],
    },
    {
        "id": "s3",
        "no": "4.3",
        "title": "广告诊断 / DSP / 费用分摊",
        "who": "【B · 广告与运营】",
        "blocks": [
            ("📊 广告诊断", [
                "已跟运营对齐了几个<b>广告媒体</b>和<b>产品广告组</b>的分析；<b>四个账号的口子做了自动更新</b>。",
                "此前运营做测试的广告<b>共 79 个</b>：<b>川鹏 ~70 多个</b>；<b>洁博利 十几个</b>（⚠️ 转写为「接过率」，比对店铺名单判定，请核对）；其他账号较少（很多测试此前已做过，属复测）。平均<b>每个运营测 5–10 个</b>。",
                "现状：<b>分析报告基本已出</b>，但<b>效果与建议还在 VI 那边</b>，后面要给运营<b>对应策略</b>。",
            ]),
            ("💰 DSP", [
                "已摸清怎么投；服务商那边能看到的 <b>P+ 之类，我们这边基本都能看到，也能设置、能操作</b>。",
                "已在账号里做了<b>功能测试 —— 除了没有点「启用」，其他操作都过了一遍</b>。",
                "洁博利问能不能投 DSP → 结论：<b>自投，不走服务商</b>（详见决议 2）。",
                "<b>衡量标准很重要</b>：原先账号做到 2 点多的指标就觉得自己优秀，看到别人做到更高，<b>才知道差距在哪</b>。所以外部方案「就看一看」，然后<b>自己也跑一个测试框</b>验证放大效果。",
                "⚠️ 关键前提：<b>如果 DSP 没有重复计算归因</b>，那就可以<b>放开投</b>；但目前给的金额都比较小，<b>放大效果未知</b>。",
            ]),
            ("🎯 投放方法论", [
                "以前开广告活动<b>只有几个大类</b>（SP、关键词、自动、大词），往后可以<b>做得很细致</b>。",
                "对比 AMS 那边的分享，坦言<b>「我们运营这边的广告做得还没那么精细化」</b>。",
                "精细化后：<b>一条大链接可能有几十到三百个广告活动，每个各有作用</b> → 可以把<b>整体 ROI 往上提</b>。",
                "所以重点应该是<b>研究新形式</b>，而不是在原有广告上修补。",
            ]),
            ("🧮 广告费用分摊（本周进展）", [
                "之前的分摊<b>不含 SP</b>，主要是搜索广告；<b>现在把 SP 算进去</b>，并做了<b>「含 SP vs 不含 SP」的花费对比</b>，数据<b>已上传云文档</b>（⚠️ 转写为「英文单」，平台名待核）。价格波动较多，暂时未定论。",
                "<b>待办</b>：分摊目前只到<b>运营 / 小组级别</b>，<b>能否下沉到每个款式</b>？",
                "动机：运营自己核算单个款式时，「分到款式」更直观。<b>做一条链接时，肯定不是按子ASIN 算，而是按父ASIN 或单个链接/销售组算</b>。",
                "数据落脚点多为 <b>SalesSKU 或 ASIN</b> —— <b>不改变分摊口径</b>，只是多加一层视图。",
                "利润算法：销售收入 − 各项费用 = 确切数字；<b>唯一没进系统的就是广告花费</b>（原先靠手动统计，会变、归因时间不同又会变）。",
                "痛点举例：<b>投的是 A 款，但 30% 成交出在 B 款</b>；<b>B 款自己没投广告，按新分摊法也要分摊</b>。",
                "更实际的场景：<b>新款转化比不好，广告其实出在成熟链接上</b> → 只看账面会误判「新款广告亏得厉害」，反映不出这个款到底好不好。",
                "<b>结论</b>：增加<b>「分到每个产品集合」</b>的表，<b>仍按月算</b>，但能落到款式。",
            ]),
        ],
    },
    {
        "id": "s4",
        "no": "4.4",
        "title": "视觉 / 图片生成 / 知识库",
        "who": "【C · 视觉与知识库】",
        "blocks": [
            ("🖼️ 图片提示词实测", [
                "用<b>通用图片提示词</b>测试了：<b>童鞋</b>、<b>以前的两款鞋</b>、<b>冬季鞋</b>；结果<b>动态效果不错</b>，已发给对方看。",
                "<b>亚马逊那边的 agent 也可以直接生成</b> —— 图方便可以直接用那边的。",
                "主要瓶颈：<b>图片等待时间</b>。自建流程（<b>FLUX 那批</b>）也能批量生成很多个，但对时间/吞吐有要求。",
            ]),
            ("🌐 网页端", [
                "为<b>加快推出</b>做了调整：<b>增加了管理员界面</b>，仍在调整中。",
                "上线后先<b>把提示词放进去让运营使用</b>；后续<b>新增模块通过管理流程加入</b>。",
            ]),
            ("📚 知识库方案（重点讨论）", [
                "选型：<b>GitHub vs 付费仓库</b> → <b>GitHub 更合适</b>。",
                "<b>两级结构</b>：每个运营一个<b>个人草稿库</b> + 公司一个<b>整体大库</b>；核验并符合规范后<b>从个人库上传到公司库</b>；需要时（如 Codex 需要某技能）<b>从公司库拉下来用</b>。",
                "<b>Obsidian 的局限</b>：自带同步（Sync）本质是存到它自己的云端仓库；<b>它的双链是「假连接」</b>，各文档之间的链接不是真连接。因此<b>知识库本身没有检索引擎能力</b>，主要充当<b>保存链路仓库</b>。",
                "<b>现状流程</b>：本地用 AI 做一轮 → 生成一个文件 → <b>钉钉上传一份 + 本地存一份</b>。",
                "<b>关键补充</b>：<b>skills 必须有优先级排序</b>；需要一份 <b>AGENTS.md（智能体 MD 文件）</b> 区分<b>团队首要技能</b>与<b>个人需要的技能</b>。单次任务产出很杂乱，要升级为可共用的通用知识库 / skill <b>必须人工维护</b>。流程：每周做好 → 整理成可共用的 → 上传共享库 → 再拉下来。",
                "<b>本地 agent vs web 端</b>：本地 agent <b>每次对话完都会保留一份 MD</b>；<b>web 端做不到</b>（除非走隧道）。负责人：自己的仓库<b>永远只有一个 <code>agent-master</code></b>，不管用 Codex、WorkBuddy 还是 <b>DeepSeek Harness</b>，都回归到这一个本地仓库；仓库里接的是 <b>GitHub 上很火的那位（Karpathy）的三层架构</b>，<code>AGENTS.md</code> 里已定义架构，每次对话产出按架构回填。",
                "⚠️ 待解问题：<b>「你们俩的知识库没办法互相共享」</b> → Obsidian 有共享方案，但还有没有别的方案，需要再研究。",
                "<b>团队级视角</b>：不管装本地还是装集中，<b>技能最终要能在团队里顺畅流转、能沉淀</b>。目标：「同一个人或同小组做完分析，不需要别人去找他要」→ <b>直接通过 AI 调用</b>。",
                "<b>长期议题：如何给整个公司建一个知识库</b> —— 沉淀一两年后量会很大，慢慢会形成<b>标准 SOP</b>。",
            ]),
        ],
    },
    {
        "id": "s5",
        "no": "4.5",
        "title": "新增方向：品牌视觉统一（未来一个月主线）",
        "who": "【负责人】→ 交给【C】",
        "blocks": [
            ("❗ 问题", [
                "现在每个品牌、每个页面<b>五花八门</b>，设置、字体各式各样。前期没有强约束、让大家自由做，<b>到最终是需要统一起来的</b>。",
            ]),
            ("📝 任务", [
                "<b>花时间研究，逐步做出规范</b>（色彩怎么选、字体、页面设置），以后生成时按规范走；<b>同一产品线的视觉最终形成相对统一的风格</b>。",
                "<b>不要求马上落地</b>，但要<b>花几周有意识往这个方向学</b>。",
                "背后逻辑：这是<b>视觉影响 / 品牌营销</b>的概念 —— 理解概念后再回来做这些事，<b>就能选出更有影响力的方式</b>。",
            ]),
            ("🎨 C 的现状与思路", [
                "当前提示词方向：图片生成<b>往「实拍、整体清新明亮」</b>靠。",
                "每个品牌看有无自身特征 —— <b>新华姐</b>提过 <b>WHITIN</b> 那边可能更多是<b>几何型</b>，<b>logo 要往那个方向靠</b>。",
                "<b>全局视野</b>：除了 <b>A+ 页面</b>，还有 <b>Brand Story</b>、投广告时的 <b>Logo</b>，都要统一到品牌表达上。",
            ]),
            ("👟 WHITIN 品线现状", [
                "品线较多（<b>涉水/水鞋、四季、宽楦、动物鞋</b> 等，⚠️ 品线名转写存疑），但<b>各品线的视觉不统一</b>。",
                "目标：<b>根据品线特点 + AI 分析</b>，建议用<b>什么色调、什么 logo 字体</b>，最终各品牌之间能统一/呼应起来。",
            ]),
            ("🔤 Logo 三条具体要求", [
                "<b>风格不能变化太大</b> —— 要与<b>鞋子上的 logo 字体风格保持一致</b>；",
                "<b>比例上借助 AI 重新设计</b>；",
                "<b>适配多形态</b> —— 有的场景是长条、有的是正方形、甚至圆形 → <b>字体保持不变的前提下，通过颜色变化达到显示效果</b>。",
            ]),
            ("🌈 主色调与品牌故事", [
                "<b>主色调</b>：<b>不一定要统一到品牌级，统一到「系列」级即可</b> —— 针对不同产品线用不同主色调。",
                "<b>品牌故事</b>：要能在故事里<b>说服别人</b>。现状坦白：「从我们自己品牌的发展来讲是<b>没有故事</b>的，就是为了卖货弄了一个商标。」从营销角度讲，<b>必须有一个故事在那儿</b>。",
                "以上作为<b>「接下去一个月，除主要工作之外的方向」</b>。",
            ]),
        ],
    },
]

UNCERTAIN = [
    ("埃局解采 / 接过率", "被推测为<b>洁博利</b>，但两处转写差异大，未 100% 确认", "核对是否确为洁博利，或另有其人/团队"),
    ("W8K / W8K2", "疑为<b>款号</b>，拼写不确定", "核对款号全称"),
    ("W2030", "与已知 <code>B0DTK7FK2M</code> → 应为 <code>W2030J</code>/AJ1 的错标问题<b>疑似同一件事</b>", "核对是否就是那条自指错标行"),
    ("「英文单」", "云文档平台名识别失败", "确认是飞书 / 钉钉 / 腾讯文档 / Excel 哪个"),
    ("「金农座」", "名词识别失败", "确认指哪个系统/表格"),
    ("「直言者」", "人名/团队名识别失败", "确认"),
    ("「第七个」", "语义不清", "确认是指第几版/第几步"),
    ("「空谷门地」", "语义失败", "听原音频确认"),
    ("「Tata」", "疑为某个<b>云端笔记/知识库服务</b>或工具简称", "确认工具名"),
    ("「四枚刀」", "已按语境改写为 Obsidian <b>Sync</b>，属推测", "确认"),
    ("「过来一家」", "语义失败", "确认"),
    ("「水旗、四组」", "疑为「涉水/水鞋」「四季」", "确认品线名"),
    ("「新华姐」", "人名", "确认写法"),
    ("「VI 那边」", "疑为视觉/VI 团队", "确认是团队还是某个系统"),
    ("「零一放假」", "已改写为<b>十一放假</b>（结合结尾「马上要过节」）", "确认"),
]

TERMS = [
    ("直A生 / 此A生 / 之A生 / A森", "子ASIN"), ("副A生", "父ASIN"), ("印射", "映射"),
    ("传门", "川鹏（川鹏2号）"), ("接过率 / 埃局解采", "洁博利（存疑）"),
    ("CPU 的计算", "CPO 的计算"), ("Divisic / Dithaseek", "DeepSeek"),
    ("Deep Thick Harness", "DeepSeek Harness"), ("Cotex / codec", "Codex"),
    ("LockerBody", "WorkBuddy"), ("冷守一个 Codex", "人手一个 Codex"),
    ("Fast API", "FastAPI"), ("丁丁", "钉钉"), ("OBSIDI", "Obsidian"),
    ("四枚刀 / 四刀", "同步（Sync）"), ("藏库", "仓库"), ("flow 那笔", "FLUX 那批"),
    ("气图型", "几何型"), ("无称的字体", "无衬线字体"), ("广告花费喷摊", "广告费用分摊"),
    ("口袍费", "广告费"), ("亚马军广告牌", "亚马逊广告平台"), ("零一放假", "十一放假"),
    ("STL", "Skill"), ("Roy 做到死", "ROI 做到极致（存疑）"),
]


def esc(s):
    return s


def build():
    # 转写全文
    tr_lines = (BASE / "meeting_timed_fixed.txt").read_text(encoding="utf-8").splitlines()
    tr_html = []
    for ln in tr_lines:
        m = ln.split("] ", 1)
        if len(m) == 2:
            stamp = m[0].lstrip("[")
            body = html.escape(m[1])
            short = stamp.split(" -> ")[0]
            tr_html.append(
                f'<div class="tl"><span class="ts">{short[:8]}</span><span class="tx">{body}</span></div>'
            )
        else:
            tr_html.append(f'<div class="tl"><span class="tx">{html.escape(ln)}</span></div>')
    tr_html = "\n".join(tr_html)

    dec = "\n".join(
        f'<div class="dec"><div class="dec-h"><span class="num">{i+1:02d}</span>'
        f'<span class="dec-t">{t}</span></div>'
        f'<div class="dec-b">{d}</div><div class="why">{w}</div></div>'
        for i, (t, d, w) in enumerate(DECISIONS)
    )

    todo = "\n".join(
        f'<tr class="p-{p}"><td class="tid">{i+1}</td><td>{t}</td>'
        f'<td class="who">{who}</td><td class="note">{n}</td></tr>'
        for i, (t, who, n, p) in enumerate(TODOS)
    )

    secs = []
    for s in SECTIONS:
        blocks = []
        if s.get("quote"):
            blocks.append(f'<blockquote class="quote">{s["quote"]}</blockquote>')
        for bt, items in s["blocks"]:
            lis = "".join(f"<li>{x}</li>" for x in items)
            blocks.append(f'<div class="blk"><div class="blk-t">{bt}</div><ul>{lis}</ul></div>')
        secs.append(
            f'<section class="sec" id="{s["id"]}">'
            f'<h3><span class="sno">{s["no"]}</span>{s["title"]}'
            f'<span class="who-tag">{s["who"]}</span></h3>{"".join(blocks)}</section>'
        )
    secs = "\n".join(secs)

    unc = "\n".join(
        f"<tr><td class='ut'>{a}</td><td>{b}</td><td class='note'>{c}</td></tr>"
        for a, b, c in UNCERTAIN
    )

    terms = "\n".join(
        f'<div class="chip"><span class="bad">{html.escape(a)}</span>'
        f'<span class="arrow">→</span><span class="good">{b}</span></div>'
        for a, b in TERMS
    )

    nav = "\n".join(
        f'<a href="#{s["id"]}">{s["no"]} {s["title"]}</a>' for s in SECTIONS
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{META["title"]}</title>
<style>
:root {{
  --bg:#f6f7f9; --panel:#fff; --ink:#1a1d21; --ink2:#5b6472; --ink3:#8b95a5;
  --line:#e4e7ec; --line2:#eef0f3; --accent:#c0392b; --accent-bg:#fdf2f0;
  --blue:#1d6fd0; --blue-bg:#eff5fd; --green:#1f8a55; --green-bg:#eef8f2;
  --amber:#a8720a; --amber-bg:#fdf6e7; --grey-bg:#f3f4f6;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:0 24px 80px; }}
header {{ background:linear-gradient(180deg,#fff 0%,#fbfcfd 100%); border-bottom:1px solid var(--line);
  padding:40px 0 28px; }}
.eyebrow {{ font-size:12px; letter-spacing:.14em; color:var(--accent); font-weight:700;
  text-transform:uppercase; margin-bottom:10px; }}
h1 {{ font-size:30px; margin:0 0 18px; letter-spacing:-.02em; }}
.meta {{ display:flex; flex-wrap:wrap; gap:8px; }}
.pill {{ background:var(--grey-bg); border:1px solid var(--line); color:var(--ink2);
  font-size:12.5px; padding:5px 11px; border-radius:999px; }}
.pill b {{ color:var(--ink); font-weight:600; }}
.tldr {{ background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--accent);
  border-radius:10px; padding:20px 22px; margin:28px 0; }}
.tldr .lbl {{ font-size:11.5px; letter-spacing:.1em; color:var(--accent); font-weight:700;
  text-transform:uppercase; margin-bottom:8px; }}
.tldr p {{ margin:0; font-size:16px; line-height:1.8; }}
nav {{ position:sticky; top:0; z-index:20; background:rgba(246,247,249,.94);
  backdrop-filter:blur(10px); border-bottom:1px solid var(--line); padding:10px 0; margin-bottom:28px; }}
nav a {{ color:var(--ink2); text-decoration:none; font-size:13px; padding:5px 10px;
  border-radius:6px; display:inline-block; }}
nav a:hover {{ background:var(--grey-bg); color:var(--ink); }}
h2 {{ font-size:20px; margin:44px 0 16px; padding-bottom:10px;
  border-bottom:1px solid var(--line); letter-spacing:-.01em; }}
h2 .em {{ color:var(--accent); }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:16px 18px; margin-bottom:12px; }}
.dec {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:15px 18px; margin-bottom:10px; }}
.dec-h {{ display:flex; align-items:baseline; gap:10px; margin-bottom:5px; }}
.num {{ font-size:11px; font-weight:700; color:var(--accent); background:var(--accent-bg);
  border-radius:5px; padding:2px 7px; flex:none; }}
.dec-t {{ font-size:15.5px; font-weight:650; }}
.dec-b {{ color:var(--ink2); font-size:14.5px; }}
.why {{ color:var(--ink3); font-size:13px; margin-top:6px; padding-left:12px;
  border-left:2px solid var(--line); }}
table {{ width:100%; border-collapse:collapse; background:var(--panel);
  border:1px solid var(--line); border-radius:12px; overflow:hidden; font-size:14.5px; }}
th {{ background:#fafbfc; text-align:left; font-weight:600; font-size:12.5px;
  color:var(--ink2); letter-spacing:.04em; padding:11px 14px; border-bottom:1px solid var(--line); }}
td {{ padding:12px 14px; border-bottom:1px solid var(--line2); vertical-align:top; }}
tr:last-child td {{ border-bottom:none; }}
.tid {{ color:var(--ink3); font-size:12px; width:34px; }}
.who {{ white-space:nowrap; color:var(--blue); font-weight:600; font-size:13px; width:80px; }}
.note {{ color:var(--ink3); font-size:13px; }}
tr.p-high .tid {{ color:var(--accent); font-weight:700; }}
.sec {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:20px 22px 22px; margin-bottom:16px; }}
.sec h3 {{ font-size:17px; margin:0 0 14px; display:flex; align-items:center;
  gap:10px; flex-wrap:wrap; }}
.sno {{ font-size:12px; color:var(--accent); background:var(--accent-bg);
  padding:2px 8px; border-radius:5px; font-weight:700; }}
.who-tag {{ font-size:12px; color:var(--ink2); background:var(--grey-bg);
  padding:3px 9px; border-radius:999px; font-weight:500; margin-left:auto; }}
.blk {{ margin-bottom:16px; }}
.blk:last-child {{ margin-bottom:0; }}
.blk-t {{ font-size:13.5px; font-weight:650; color:var(--ink); margin-bottom:7px; }}
.blk ul {{ margin:0; padding-left:20px; }}
.blk li {{ margin-bottom:6px; color:#2b3038; }}
.blk li b {{ color:var(--ink); font-weight:650; }}
code {{ background:var(--grey-bg); border:1px solid var(--line2); border-radius:4px;
  padding:1px 5px; font-size:12.5px; font-family:"SF Mono",Menlo,monospace; }}
.quote {{ margin:0 0 16px; padding:14px 18px; background:var(--blue-bg);
  border-left:3px solid var(--blue); border-radius:0 8px 8px 0; color:#173a63;
  font-size:15px; font-style:italic; }}
.chip {{ display:inline-flex; align-items:center; gap:6px; background:var(--panel);
  border:1px solid var(--line); border-radius:999px; padding:5px 12px; margin:0 6px 8px 0;
  font-size:13px; }}
.bad {{ color:var(--ink3); text-decoration:line-through; }}
.arrow {{ color:var(--accent); font-weight:700; }}
.good {{ color:var(--green); font-weight:650; }}
.ut {{ font-weight:600; color:var(--amber); white-space:nowrap; }}
details {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:4px 18px; }}
summary {{ cursor:pointer; font-weight:650; padding:14px 0; font-size:15px;
  list-style:none; display:flex; align-items:center; gap:8px; }}
summary::-webkit-details-marker {{ display:none; }}
summary::before {{ content:"▸"; color:var(--accent); transition:transform .18s; display:inline-block; }}
details[open] summary::before {{ transform:rotate(90deg); }}
.tl {{ display:flex; gap:14px; padding:4px 0; border-bottom:1px dashed var(--line2);
  font-size:14px; }}
.tl:last-child {{ border-bottom:none; }}
.ts {{ color:var(--ink3); font-family:"SF Mono",Menlo,monospace; font-size:12px;
  flex:none; padding-top:3px; }}
.tx {{ color:#2b3038; }}
.tr-box {{ max-height:620px; overflow-y:auto; padding:6px 0 16px; }}
footer {{ color:var(--ink3); font-size:12.5px; text-align:center; padding-top:32px; }}
.warn {{ background:var(--amber-bg); border:1px solid #f0e0b8; border-radius:10px;
  padding:14px 18px; color:#6b4a10; font-size:14px; margin-bottom:16px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="eyebrow">Meeting Minutes</div>
    <h1>{META["title"]}</h1>
    <div class="meta">
      <span class="pill">日期 <b>{META["date"]} {META["start"]}</b></span>
      <span class="pill">时长 <b>{META["duration"]}</b></span>
      <span class="pill">转写片段 <b>{META["segments"]}</b></span>
      <span class="pill">素材 {META["source"]}</span>
      <span class="pill">引擎 {META["engine"]}</span>
    </div>
  </div>
</header>

<div class="wrap">
  <div class="tldr">
    <div class="lbl">一句话总结</div>
    <p>{TLDR}</p>
  </div>

  <div class="warn">
    <b>发言人识别说明：</b>本机未做声纹分离（Whisper 不输出 speaker label）。
    文中的【负责人】【A·数据与系统】【B·广告与运营】【C·视觉与知识库】是<b>按发言内容推断</b>的，
    非机器判定，请人工核对后再对外引用。
  </div>

  <nav>
    <div class="wrap" style="padding:0 24px;">{nav}</div>
  </nav>

  <h2>二 · 决议事项（已拍板）</h2>
  {dec}

  <h2>三 · 待办清单</h2>
  <table>
    <thead><tr><th>#</th><th>待办</th><th>责任人</th><th>备注 / 阻塞</th></tr></thead>
    <tbody>{todo}</tbody>
  </table>

  <h2>四 · 分板块详情</h2>
  {secs}

  <h2>五 · <span class="em">⚠️ 存疑点</span>（务必人工核对）</h2>
  <table>
    <thead><tr><th>转写内容</th><th>问题</th><th>建议</th></tr></thead>
    <tbody>{unc}</tbody>
  </table>

  <h2>六 · 术语纠错表（机器已自动修正）</h2>
  <div class="card" style="padding:18px 18px 10px;">{terms}</div>

  <h2>七 · 转写全文（术语修正版）</h2>
  <details>
    <summary>展开 825 段带时间戳全文</summary>
    <div class="tr-box">{tr_html}</div>
  </details>

  <footer>原始音频 41 分 31 秒 · 本地 Whisper 转写 · 术语修正 32 处 · 生成于 2026-09-23</footer>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    out = BASE / "会议纪要-2026-09-23-周会.html"
    out.write_text(build(), encoding="utf-8")
    print(f"[out] {out}  ({out.stat().st_size:,} bytes)")
