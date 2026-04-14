import { motion } from "motion/react";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";
import { ArrowRight, ShoppingBag } from "lucide-react";

export function Business() {
  const categories = [
    {
      id: "men",
      title: "男士运动系列",
      subtitle: "Men's Sports Shoes",
      desc: "结合前沿缓震科技与耐磨材质，专为力量训练、户外跑步及日常通勤打造。设计风格硬朗简约，兼顾实用性与时尚感。",
      image: "https://images.unsplash.com/photo-1618153478389-b2ed8de18ed3?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtZW4lMjBzcG9ydHMlMjBzaG9lcyUyMHNuZWFrZXJzfGVufDF8fHx8MTc3NDk0ODc5Mnww&ixlib=rb-4.1.0&q=80&w=1080",
      features: ["超强抓地力", "动态缓震中底", "透气编织鞋面"]
    },
    {
      id: "women",
      title: "女士轻量系列",
      subtitle: "Women's Lightweight Running",
      desc: "专为女性脚型研发，极大地减轻了鞋身重量。清新的马卡龙配色搭配流线型设计，让运动成为一种优雅的享受。",
      image: "https://images.unsplash.com/photo-1765109370759-efe11445d3fa?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHx3b21lbiUyMHJ1bm5pbmclMjBzaG9lcyUyMGF0aGxldGV8ZW58MXx8fHwxNzc0OTQ4NzkyfDA&ixlib=rb-4.1.0&q=80&w=1080",
      features: ["超轻量化设计", "人体工学足弓支撑", "高弹力回馈"]
    },
    {
      id: "kids",
      title: "儿童成长系列",
      subtitle: "Kids Colorful Sneakers",
      desc: "选用环保无毒材料，魔术贴设计方便穿脱。鞋底采用防滑纹路，保护儿童活泼好动的每一步，色彩缤纷激发孩子想象力。",
      image: "https://images.unsplash.com/photo-1583979365152-173a8f14181b?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxraWRzJTIwc25lYWtlcnMlMjBjb2xvcmZ1bHxlbnwxfHx8fDE3NzQ5NDg3OTN8MA&ixlib=rb-4.1.0&q=80&w=1080",
      features: ["魔术贴便捷穿脱", "环保无毒亲肤材料", "防踢鞋头设计"]
    }
  ];

  return (
    <div className="w-full bg-white">
      {/* Header */}
      <section className="bg-zinc-950 text-white py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <ShoppingBag className="w-12 h-12 text-orange-500 mx-auto mb-6" />
            <h1 className="text-4xl md:text-5xl font-black mb-6 tracking-tight">我们的业务与产品矩阵</h1>
            <p className="text-zinc-400 max-w-2xl mx-auto text-lg">
              深耕北美亚马逊鞋类赛道，以数据驱动选品，以品质赢取口碑。我们专注于为您提供兼具设计感与性价比的运动鞋履。
            </p>
          </motion.div>
        </div>
      </section>

      {/* Product Lines */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="space-y-32">
          {categories.map((category, index) => (
            <div 
              key={category.id} 
              className={`flex flex-col gap-12 lg:gap-20 items-center ${
                index % 2 === 1 ? 'lg:flex-row-reverse' : 'lg:flex-row'
              }`}
            >
              <motion.div 
                initial={{ opacity: 0, x: index % 2 === 1 ? 50 : -50 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className="w-full lg:w-1/2"
              >
                <div className="relative aspect-square md:aspect-[4/3] rounded-3xl overflow-hidden shadow-2xl">
                  <ImageWithFallback 
                    src={category.image} 
                    alt={category.title}
                    className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
                  />
                  <div className="absolute inset-0 bg-black/10 mix-blend-overlay" />
                </div>
              </motion.div>

              <motion.div 
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6, delay: 0.2 }}
                className="w-full lg:w-1/2"
              >
                <div className="text-orange-600 font-bold uppercase tracking-wider mb-2 text-sm">
                  {category.subtitle}
                </div>
                <h2 className="text-3xl md:text-4xl font-black mb-6">{category.title}</h2>
                <p className="text-zinc-600 text-lg leading-relaxed mb-8">
                  {category.desc}
                </p>
                <ul className="space-y-4 mb-8">
                  {category.features.map((feature, idx) => (
                    <li key={idx} className="flex items-center gap-3 font-medium text-zinc-800">
                      <div className="w-2 h-2 rounded-full bg-orange-500" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <button className="flex items-center gap-2 text-orange-600 font-bold hover:text-orange-700 transition-colors group">
                  在 Amazon 上查看详情
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </button>
              </motion.div>
            </div>
          ))}
        </div>
      </section>

      {/* Stats / Operations */}
      <section className="bg-orange-600 text-white py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12 text-center">
            <div>
              <div className="text-5xl font-black mb-4">98%</div>
              <div className="text-orange-100 font-medium text-lg">好评满意度</div>
            </div>
            <div>
              <div className="text-5xl font-black mb-4">24h</div>
              <div className="text-orange-100 font-medium text-lg">FBA 极速发货响应</div>
            </div>
            <div>
              <div className="text-5xl font-black mb-4">100+</div>
              <div className="text-orange-100 font-medium text-lg">月度上新SKU数</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}