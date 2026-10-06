import { motion } from "motion/react";
import { ArrowRight, MoveRight, Target, Users, Zap, Globe2 } from "lucide-react";
import { NavLink } from "react-router";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";

export function Home() {
  return (
    <div className="w-full">
      {/* Hero Section */}
      <section className="relative h-[85vh] min-h-[600px] flex items-center overflow-hidden bg-zinc-950">
        <div className="absolute inset-0 w-full h-full">
          <ImageWithFallback
            src="https://images.unsplash.com/photo-1758346082653-d3e7803e4260?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxkeW5hbWljJTIwcnVubmluZyUyMHNob2VzfGVufDF8fHx8MTc3NDk0ODc5Mnww&ixlib=rb-4.1.0&q=80&w=1080"
            alt="Dynamic running shoes"
            className="w-full h-full object-cover opacity-40"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-zinc-950 via-zinc-950/80 to-transparent" />
        </div>
        
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="max-w-2xl"
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-600/10 border border-orange-600/20 text-orange-500 font-medium text-sm mb-6">
              <span className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
              专注亚马逊北美站跨境电商
            </div>
            <h1 className="text-5xl md:text-7xl font-black text-white leading-[1.1] mb-6 tracking-tight">
              赋能每一步<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-orange-600">
                驱动全球化步伐
              </span>
            </h1>
            <p className="text-lg md:text-xl text-zinc-300 mb-10 leading-relaxed font-light">
              芯威霆致力于高品质运动鞋类的跨境出海。以简约、活力的理念，将卓越的设计与舒适体验带给北美消费者。
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <NavLink 
                to="/business"
                className="bg-orange-600 text-white px-8 py-4 rounded-full font-medium flex items-center justify-center gap-2 hover:bg-orange-500 transition-all hover:gap-4"
              >
                探索我们的业务 <ArrowRight className="w-5 h-5" />
              </NavLink>
              <NavLink 
                to="/partners"
                className="bg-white/10 text-white backdrop-blur-sm border border-white/20 px-8 py-4 rounded-full font-medium flex items-center justify-center gap-2 hover:bg-white/20 transition-all"
              >
                合作与招商
              </NavLink>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Stats / Intro */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-3xl md:text-4xl font-bold mb-6 tracking-tight">不仅仅是卖鞋，<br />更是传递一种<span className="text-orange-600 italic">生活态度</span>。</h2>
              <p className="text-zinc-600 leading-relaxed mb-8">
                芯威霆自创立以来，扎根于福州仓山区智能产业园，依托强大的供应链优势和敏锐的北美市场嗅觉，迅速成长为亚马逊运动鞋类目的新锐力量。我们不仅追求销量，更追求每一次用户穿上我们鞋子时的愉悦体验。
              </p>
              
              <div className="grid grid-cols-2 gap-8">
                <div>
                  <div className="text-4xl font-black text-zinc-900 mb-2">20-99</div>
                  <div className="text-sm text-zinc-500 font-medium">精英团队规模</div>
                </div>
                <div>
                  <div className="text-4xl font-black text-zinc-900 mb-2">USA</div>
                  <div className="text-sm text-zinc-500 font-medium">核心深耕市场</div>
                </div>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <motion.div whileHover={{ y: -5 }} className="bg-zinc-50 p-6 rounded-2xl">
                <Target className="w-8 h-8 text-orange-600 mb-4" />
                <h3 className="font-bold mb-2">精准选品</h3>
                <p className="text-sm text-zinc-500">基于大数据分析，精准触达北美消费者的真实需求。</p>
              </motion.div>
              <motion.div whileHover={{ y: -5 }} className="bg-zinc-50 p-6 rounded-2xl translate-y-8">
                <Globe2 className="w-8 h-8 text-orange-600 mb-4" />
                <h3 className="font-bold mb-2">全球化视野</h3>
                <p className="text-sm text-zinc-500">主攻美国亚马逊站，未来布局更多国际市场。</p>
              </motion.div>
              <motion.div whileHover={{ y: -5 }} className="bg-zinc-50 p-6 rounded-2xl">
                <Zap className="w-8 h-8 text-orange-600 mb-4" />
                <h3 className="font-bold mb-2">高效运营</h3>
                <p className="text-sm text-zinc-500">智能化的仓储与物流管理，极致提升周转效率。</p>
              </motion.div>
              <motion.div whileHover={{ y: -5 }} className="bg-zinc-50 p-6 rounded-2xl translate-y-8">
                <Users className="w-8 h-8 text-orange-600 mb-4" />
                <h3 className="font-bold mb-2">合作共赢</h3>
                <p className="text-sm text-zinc-500">与优质供应商深度绑定，构建坚实的商业壁垒。</p>
              </motion.div>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Categories */}
      <section className="py-24 bg-zinc-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-end mb-12">
            <div>
              <h2 className="text-3xl font-bold tracking-tight mb-4">核心业务线</h2>
              <p className="text-zinc-500 max-w-xl">全面覆盖男士、女士及儿童运动鞋市场，打造多元化产品矩阵。</p>
            </div>
            <NavLink to="/business" className="hidden sm:flex items-center gap-2 text-orange-600 font-medium hover:text-orange-700">
              查看全部 <MoveRight className="w-4 h-4" />
            </NavLink>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { title: "男士运动系列", image: "https://images.unsplash.com/photo-1618153478389-b2ed8de18ed3?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtZW4lMjBzcG9ydHMlMjBzaG9lcyUyMHNuZWFrZXJzfGVufDF8fHx8MTc3NDk0ODc5Mnww&ixlib=rb-4.1.0&q=80&w=1080", desc: "力量与性能的完美结合，专为高强度运动与日常穿搭设计。" },
              { title: "女士轻跑系列", image: "https://images.unsplash.com/photo-1765109370759-efe11445d3fa?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHx3b21lbiUyMHJ1bm5pbmclMjBzaG9lcyUyMGF0aGxldGV8ZW58MXx8fHwxNzc0OTQ4NzkyfDA&ixlib=rb-4.1.0&q=80&w=1080", desc: "轻盈、透气、时尚。让每一步都优雅自如，充满活力。" },
              { title: "儿童活力系列", image: "https://images.unsplash.com/photo-1583979365152-173a8f14181b?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxraWRzJTIwc25lYWtlcnMlMjBjb2xvcmZ1bHxlbnwxfHx8fDE3NzQ5NDg3OTN8MA&ixlib=rb-4.1.0&q=80&w=1080", desc: "缤纷色彩，安全舒适。陪伴孩子健康成长的每一步。" }
            ].map((category, idx) => (
              <motion.div 
                key={idx}
                whileHover={{ y: -10 }}
                className="group relative overflow-hidden rounded-2xl bg-white shadow-sm border border-zinc-100"
              >
                <div className="aspect-[4/5] overflow-hidden">
                  <ImageWithFallback 
                    src={category.image} 
                    alt={category.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                  />
                </div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent flex flex-col justify-end p-6 text-white">
                  <h3 className="text-xl font-bold mb-2">{category.title}</h3>
                  <p className="text-sm text-zinc-300 opacity-0 group-hover:opacity-100 transition-opacity duration-300 transform translate-y-4 group-hover:translate-y-0">
                    {category.desc}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
          <div className="mt-8 text-center sm:hidden">
            <NavLink to="/business" className="inline-flex items-center gap-2 text-orange-600 font-medium">
              查看全部 <MoveRight className="w-4 h-4" />
            </NavLink>
          </div>
        </div>
      </section>

      {/* Call to Action */}
      <section className="py-20 bg-orange-600 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white opacity-5 rounded-full blur-3xl transform translate-x-1/2 -translate-y-1/2" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-black opacity-10 rounded-full blur-3xl transform -translate-x-1/2 translate-y-1/2" />
        
        <div className="relative max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl md:text-5xl font-black text-white mb-6">携手芯威霆，共创无限可能</h2>
          <p className="text-orange-100 text-lg mb-10 max-w-2xl mx-auto">
            无论您是寻找优质合作伙伴的供应商，还是充满激情渴望展现自我的电商人才，我们都期待您的加入。
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <NavLink to="/partners" className="bg-zinc-900 text-white px-8 py-4 rounded-full font-medium hover:bg-black transition-colors">
              成为供应商
            </NavLink>
            <NavLink to="/careers" className="bg-white text-orange-600 px-8 py-4 rounded-full font-medium hover:bg-zinc-50 transition-colors">
              查看热招职位
            </NavLink>
          </div>
        </div>
      </section>
    </div>
  );
}