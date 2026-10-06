import { motion } from "motion/react";
import { MapPin, Phone, Mail, Clock } from "lucide-react";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";

export function Contact() {
  return (
    <div className="w-full bg-white">
      {/* Header */}
      <section className="bg-zinc-50 py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-4">联系我们</h1>
            <p className="text-xl text-zinc-500 max-w-2xl mx-auto">
              期待与您的每一次沟通。无论是业务合作、产品咨询还是加入我们，随时欢迎联络。
            </p>
          </motion.div>
        </div>
      </section>

      {/* Main Content */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
          
          {/* Contact Info */}
          <div>
            <h2 className="text-3xl font-bold mb-8">联络方式</h2>
            <div className="space-y-8 mb-12">
              <div className="flex gap-4">
                <div className="w-12 h-12 bg-orange-50 text-orange-600 rounded-xl flex items-center justify-center shrink-0">
                  <MapPin className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-lg mb-1">公司地址</h3>
                  <p className="text-zinc-600 leading-relaxed">福州市仓山区智能产业园</p>
                  <p className="text-sm text-zinc-400 mt-1">福建省, 中国</p>
                </div>
              </div>
              
              <div className="flex gap-4">
                <div className="w-12 h-12 bg-orange-50 text-orange-600 rounded-xl flex items-center justify-center shrink-0">
                  <Mail className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-lg mb-1">电子邮箱</h3>
                  <p className="text-zinc-600">商务合作: supply@xinweiting.com</p>
                  <p className="text-zinc-600">人才招聘: hr@xinweiting.com</p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-orange-50 text-orange-600 rounded-xl flex items-center justify-center shrink-0">
                  <Clock className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-lg mb-1">工作时间</h3>
                  <p className="text-zinc-600">周一至周五: 09:00 - 18:00 (北京时间)</p>
                  <p className="text-zinc-600">周末及法定节假日休息</p>
                </div>
              </div>
            </div>

            <div className="rounded-2xl overflow-hidden h-64 bg-zinc-200">
              {/* Decorative map placeholder or building image */}
              <ImageWithFallback 
                src="https://images.unsplash.com/photo-1771678041346-a2a2290cc4a4?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBzbWFydCUyMGluZHVzdHJpYWwlMjBwYXJrJTIwYnVpbGRpbmd8ZW58MXx8fHwxNzc0OTQ4NzkzfDA&ixlib=rb-4.1.0&q=80&w=1080"
                alt="Industrial Park Building"
                className="w-full h-full object-cover"
              />
            </div>
          </div>

          {/* Form */}
          <div className="bg-white border border-zinc-200 p-8 md:p-10 rounded-3xl shadow-sm">
            <h2 className="text-2xl font-bold mb-6">在线留言</h2>
            <form className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-700">姓名</label>
                  <input type="text" className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all" placeholder="您的称呼" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-700">联系电话 / 微信</label>
                  <input type="text" className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all" placeholder="您的联系方式" />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-700">电子邮箱</label>
                <input type="email" className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all" placeholder="example@domain.com" />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-700">留言内容</label>
                <textarea rows={5} className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all resize-none" placeholder="请简述您的需求或合作意向..."></textarea>
              </div>

              <button type="button" className="w-full bg-zinc-900 text-white font-bold py-4 rounded-xl hover:bg-orange-600 transition-colors">
                提交留言
              </button>
              
              <p className="text-xs text-center text-zinc-500">
                我们会在收到留言后的 1-2 个工作日内与您联系
              </p>
            </form>
          </div>
        </div>
      </section>
    </div>
  );
}