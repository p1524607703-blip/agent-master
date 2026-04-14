import { motion } from "motion/react";
import { Handshake, ShieldCheck, Box, BarChart3, Mail } from "lucide-react";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";

export function Partners() {
  return (
    <div className="w-full bg-zinc-50">
      {/* Header */}
      <section className="relative py-24 px-4 sm:px-6 lg:px-8 overflow-hidden">
        <div className="absolute inset-0 z-0">
          <ImageWithFallback 
            src="https://images.unsplash.com/photo-1573552991725-c7b115591d04?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHx3YXJlaG91c2UlMjBsb2dpc3RpY3MlMjBib3hlc3xlbnwxfHx8fDE3NzQ4NTgyMDB8MA&ixlib=rb-4.1.0&q=80&w=1080"
            alt="Logistics background"
            className="w-full h-full object-cover opacity-10"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-zinc-50/80 to-zinc-50" />
        </div>
        
        <div className="relative z-10 max-w-4xl mx-auto text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <Handshake className="w-16 h-16 text-orange-600 mx-auto mb-6" />
            <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-6 text-zinc-900">
              全球招商，共赢跨境蓝海
            </h1>
            <p className="text-xl text-zinc-600 leading-relaxed">
              芯威霆正面向全国诚招优质鞋类供应商及供应链合作伙伴。基于我们的亚马逊北美站强大销售网络，助您的产品出海无忧。
            </p>
          </motion.div>
        </div>
      </section>

      {/* Why Partner With Us */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-16">为什么选择芯威霆？</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-zinc-100 hover:shadow-md transition-shadow">
            <BarChart3 className="w-10 h-10 text-orange-600 mb-6" />
            <h3 className="text-xl font-bold mb-3">稳定庞大的销量基数</h3>
            <p className="text-zinc-500 text-sm leading-relaxed">
              我们在亚马逊北美站深耕多年，拥有成熟的爆款打造能力和稳定的日订单量，能为优质供应商提供持续可观的采购需求。
            </p>
          </div>
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-zinc-100 hover:shadow-md transition-shadow">
            <ShieldCheck className="w-10 h-10 text-orange-600 mb-6" />
            <h3 className="text-xl font-bold mb-3">靠谱的资金结算</h3>
            <p className="text-zinc-500 text-sm leading-relaxed">
              资金链健康，遵守契约精神。按合同约定准时结算货款，让供应商无后顾之忧，安心做好产品研发与生产。
            </p>
          </div>
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-zinc-100 hover:shadow-md transition-shadow">
            <Box className="w-10 h-10 text-orange-600 mb-6" />
            <h3 className="text-xl font-bold mb-3">前沿的市场数据赋能</h3>
            <p className="text-zinc-500 text-sm leading-relaxed">
              实时反哺北美最新流行趋势、材质偏好及消费者痛点，与工厂共同研发改进产品，提升产品溢价与竞争力。
            </p>
          </div>
        </div>
      </section>

      {/* Supplier Requirements */}
      <section className="py-20 bg-zinc-950 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-3xl font-bold mb-8">我们寻找这样的你</h2>
              <ul className="space-y-6">
                <li className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-orange-600/20 text-orange-500 flex items-center justify-center font-bold shrink-0">1</div>
                  <div>
                    <h4 className="font-bold text-lg mb-1">自有工厂或深度合作产线</h4>
                    <p className="text-zinc-400 text-sm">具备稳定的产能与品控能力，主营运动鞋、休闲鞋品类。</p>
                  </div>
                </li>
                <li className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-orange-600/20 text-orange-500 flex items-center justify-center font-bold shrink-0">2</div>
                  <div>
                    <h4 className="font-bold text-lg mb-1">严格的质量管理体系</h4>
                    <p className="text-zinc-400 text-sm">能够满足跨境电商严格的质检要求，退货率控制在行业优秀水平。</p>
                  </div>
                </li>
                <li className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-orange-600/20 text-orange-500 flex items-center justify-center font-bold shrink-0">3</div>
                  <div>
                    <h4 className="font-bold text-lg mb-1">具备研发和推新能力</h4>
                    <p className="text-zinc-400 text-sm">能根据市场反馈快速打样迭代，具备一定的设计或改款能力优先。</p>
                  </div>
                </li>
              </ul>
            </div>
            
            <div className="bg-zinc-900 p-8 md:p-10 rounded-3xl border border-zinc-800">
              <h3 className="text-2xl font-bold mb-6">入驻意向通道</h3>
              <p className="text-zinc-400 text-sm mb-8">
                如果您符合以上条件且有意合作，请将您的公司简介、产品画册及合作意向发送至我们的招商邮箱，我们会尽快与您联系。
              </p>
              
              <div className="flex items-center gap-4 bg-zinc-950 p-4 rounded-xl border border-zinc-800 mb-6">
                <Mail className="w-6 h-6 text-orange-500" />
                <div>
                  <div className="text-xs text-zinc-500 mb-1">供应商招商专属邮箱</div>
                  <div className="font-mono text-white font-medium">supply@xinweiting.com</div>
                </div>
              </div>
              
              <button className="w-full bg-orange-600 hover:bg-orange-500 text-white font-bold py-4 rounded-xl transition-colors">
                一键复制邮箱地址
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}