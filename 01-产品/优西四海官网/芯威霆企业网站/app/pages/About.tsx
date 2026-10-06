import { motion } from "motion/react";
import { CheckCircle2, TrendingUp, Compass, Flag } from "lucide-react";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";

export function About() {
  return (
    <div className="w-full bg-white">
      {/* Page Header */}
      <section className="pt-24 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-3xl"
        >
          <h1 className="text-4xl md:text-6xl font-black tracking-tight mb-6">
            关于<span className="text-orange-600">芯威霆</span>
          </h1>
          <p className="text-xl text-zinc-500 leading-relaxed">
            我们不仅仅是一家跨境电商公司，更是连接中国智造与全球消费者的桥梁。以福州为起点，以亚马逊北美站为主舞台，我们将运动与活力传递到世界各地。
          </p>
        </motion.div>
      </section>

      {/* Main Image */}
      <section className="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto mb-24">
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="w-full h-[400px] md:h-[600px] rounded-3xl overflow-hidden relative"
        >
          <ImageWithFallback 
            src="https://images.unsplash.com/photo-1758873268663-5a362616b5a7?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBvZmZpY2UlMjB0ZWFtJTIwY29sbGFib3JhdGlvbnxlbnwxfHx8fDE3NzQ4Nzk1OTN8MA&ixlib=rb-4.1.0&q=80&w=1080"
            alt="Office Team"
            className="w-full h-full object-cover"
          />
        </motion.div>
      </section>

      {/* Company Info Grid */}
      <section className="py-16 bg-zinc-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-zinc-100">
              <Compass className="w-10 h-10 text-orange-600 mb-6" />
              <div className="text-3xl font-black mb-2">福州</div>
              <p className="text-zinc-500 text-sm">总部位于仓山区智能产业园，背靠福建完善的鞋服供应链体系。</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-zinc-100">
              <TrendingUp className="w-10 h-10 text-orange-600 mb-6" />
              <div className="text-3xl font-black mb-2">Amazon US</div>
              <p className="text-zinc-500 text-sm">核心主攻亚马逊美国站，积累了深厚的北美市场运营经验。</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-zinc-100">
              <Flag className="w-10 h-10 text-orange-600 mb-6" />
              <div className="text-3xl font-black mb-2">运动鞋类</div>
              <p className="text-zinc-500 text-sm">专注且垂直深耕男、女、儿童运动鞋品类，做深做透。</p>
            </div>
            <div className="bg-orange-600 text-white p-8 rounded-2xl shadow-sm">
              <div className="text-5xl font-black mb-2 mt-4">20-99</div>
              <div className="text-xl font-bold mb-4 opacity-90">人精英团队</div>
              <p className="text-orange-100 text-sm">年轻、富有激情、极具战斗力的跨境电商专业队伍。</p>
            </div>
          </div>
        </div>
      </section>

      {/* Culture */}
      <section className="py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mx-auto text-center mb-16">
            <h2 className="text-3xl font-bold mb-4">企业文化与价值观</h2>
            <p className="text-zinc-500">在芯威霆，我们推崇简单高效的沟通方式，秉持客户第一的原则，不断在跨境浪潮中奔跑。</p>
          </div>

          <div className="space-y-12 max-w-4xl mx-auto">
            {[
              { title: "敏捷创新", desc: "跨境市场瞬息万变。我们鼓励团队快速试错，敏捷迭代，用创新的运营手法打破传统壁垒。" },
              { title: "极致产品", desc: "哪怕是一双最普通的运动鞋，也要死磕舒适度与外观设计。产品力是我们立足北美市场的根本。" },
              { title: "合作共赢", desc: "无论是内部团队的协作，还是外部与供应商的携手，我们始终坚信 1+1>2 的力量，共享发展红利。" },
              { title: "活力激情", desc: "就如我们售卖的运动鞋一样，我们希望整个团队保持向上的体育精神：拼搏、坚持、超越自我。" }
            ].map((item, idx) => (
              <div key={idx} className="flex gap-4 items-start">
                <CheckCircle2 className="w-6 h-6 text-orange-600 shrink-0 mt-1" />
                <div>
                  <h3 className="text-xl font-bold mb-2">{item.title}</h3>
                  <p className="text-zinc-600 leading-relaxed">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}