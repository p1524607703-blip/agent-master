import { motion } from "motion/react";
import { Briefcase, ArrowRight, MapPin } from "lucide-react";

export function Careers() {
  const jobs = [
    {
      title: "亚马逊运营专员",
      department: "运营部",
      location: "福州仓山区",
      type: "全职",
      exp: "1-3年",
      desc: "负责亚马逊北美站店铺的日常运营、产品上架、Listing优化及广告投放策略制定与执行。"
    },
    {
      title: "跨境电商产品开发",
      department: "产品部",
      location: "福州仓山区",
      type: "全职",
      exp: "2年以上",
      desc: "结合美国本土市场趋势和大数据分析，开发具有爆款潜质的运动鞋类新品，跟进供应商打样进度。"
    },
    {
      title: "视觉设计师 (电商方向)",
      department: "设计部",
      location: "福州仓山区",
      type: "全职",
      exp: "1年以上",
      desc: "负责产品主图、A+页面及品牌站的设计与排版，提升产品转化率，具备一定的摄影或3D渲染能力加分。"
    },
    {
      title: "亚马逊客服支持 (英文)",
      department: "客服部",
      location: "福州仓山区",
      type: "全职",
      exp: "不限",
      desc: "处理亚马逊客户邮件，解答产品咨询，妥善处理售后问题及索赔，维护账号良好的健康指标。英语CET-4以上。"
    }
  ];

  return (
    <div className="w-full bg-white">
      {/* Header */}
      <section className="bg-orange-600 text-white py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
            <h1 className="text-4xl md:text-6xl font-black mb-6 tracking-tight">与我们一起，跑向世界</h1>
            <p className="text-xl text-orange-100 leading-relaxed mb-8 max-w-2xl mx-auto">
              加入由 20-99 位充满热情的年轻人组成的团队。在这里，你得到的不仅是一份工作，更是一片可以尽情挥洒创意与才华的跨境电商蓝海。
            </p>
          </motion.div>
        </div>
      </section>

      {/* Benefits */}
      <section className="py-20 bg-zinc-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center mb-16">我们在乎你的成长与生活</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { title: "极具竞争力的薪资", desc: "底薪 + 丰厚提成 + 年终奖，能力与回报成正比。" },
              { title: "完善的五险福利", desc: "入职即缴纳五险，保障你的基本权益无忧。" },
              { title: "透明的晋升通道", desc: "专员-主管-经理，凭实力说话，不按资排辈。" },
              { title: "丰富的团队活动", desc: "定期下午茶、节假日福利、年度旅游及团建聚餐。" }
            ].map((benefit, idx) => (
              <div key={idx} className="bg-white p-6 rounded-2xl shadow-sm text-center border border-zinc-100">
                <div className="w-12 h-12 bg-orange-50 text-orange-600 rounded-full flex items-center justify-center mx-auto mb-4 font-bold text-xl">
                  {idx + 1}
                </div>
                <h3 className="font-bold mb-2">{benefit.title}</h3>
                <p className="text-sm text-zinc-500">{benefit.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Open Positions */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-10">
          <Briefcase className="w-8 h-8 text-orange-600" />
          <h2 className="text-3xl font-bold">热招职位</h2>
        </div>

        <div className="space-y-6">
          {jobs.map((job, idx) => (
            <motion.div 
              key={idx}
              whileHover={{ scale: 1.01 }}
              className="group bg-white border border-zinc-200 rounded-2xl p-6 md:p-8 hover:border-orange-500 transition-colors shadow-sm hover:shadow-md cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-6"
            >
              <div className="flex-1">
                <h3 className="text-2xl font-bold text-zinc-900 mb-3 group-hover:text-orange-600 transition-colors">
                  {job.title}
                </h3>
                <div className="flex flex-wrap items-center gap-3 text-sm text-zinc-500 mb-4">
                  <span className="bg-zinc-100 px-3 py-1 rounded-full text-zinc-700 font-medium">{job.department}</span>
                  <span className="flex items-center gap-1"><MapPin className="w-4 h-4" /> {job.location}</span>
                  <span>{job.type}</span>
                  <span>经验要求: {job.exp}</span>
                </div>
                <p className="text-zinc-600 text-sm md:text-base leading-relaxed max-w-3xl">
                  {job.desc}
                </p>
              </div>
              <div className="shrink-0">
                <button className="bg-zinc-900 text-white px-6 py-3 rounded-xl font-medium flex items-center gap-2 hover:bg-orange-600 transition-colors w-full md:w-auto justify-center">
                  立即投递 <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          ))}
        </div>

        <div className="mt-16 text-center bg-zinc-50 p-8 rounded-2xl">
          <p className="text-zinc-600 mb-4">没有找到合适的职位？没关系！</p>
          <p className="text-sm text-zinc-500 mb-6">
            优秀的人才我们随时欢迎，请将简历发送至我们的招聘邮箱，标题请注明【自荐+应聘岗位+姓名】。
          </p>
          <a href="mailto:hr@xinweiting.com" className="inline-flex font-bold text-orange-600 hover:text-orange-700 underline underline-offset-4">
            hr@xinweiting.com
          </a>
        </div>
      </section>
    </div>
  );
}