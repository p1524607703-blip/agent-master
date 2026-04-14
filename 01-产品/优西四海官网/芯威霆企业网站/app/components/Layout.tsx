import { Outlet, NavLink, useLocation } from "react-router";
import { motion, AnimatePresence } from "motion/react";
import { Menu, X, ArrowUpRight, Globe } from "lucide-react";
import { useState } from "react";
import { clsx } from "clsx";

export function Layout() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();

  const navLinks = [
    { name: "首页", path: "/" },
    { name: "关于我们", path: "/about" },
    { name: "业务板块", path: "/business" },
    { name: "合作招商", path: "/partners" },
    { name: "加入我们", path: "/careers" },
    { name: "联系我们", path: "/contact" },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-zinc-50 text-zinc-900 font-sans selection:bg-orange-500 selection:text-white overflow-x-hidden">
      {/* Navigation */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-zinc-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            {/* Logo */}
            <NavLink to="/" className="flex items-center gap-2 group">
              <div className="w-10 h-10 bg-orange-600 text-white flex items-center justify-center rounded-xl font-black text-xl italic tracking-tighter group-hover:bg-orange-500 transition-colors">
                XW
              </div>
              <div>
                <span className="font-bold text-xl tracking-tight block leading-tight">芯威霆</span>
                <span className="text-[10px] text-zinc-500 font-medium uppercase tracking-widest block leading-none">Xinweiting</span>
              </div>
            </NavLink>

            {/* Desktop Nav */}
            <nav className="hidden md:flex items-center gap-8">
              {navLinks.map((link) => (
                <NavLink
                  key={link.path}
                  to={link.path}
                  className={({ isActive }) =>
                    clsx(
                      "text-sm font-medium transition-colors hover:text-orange-600 relative py-2",
                      isActive ? "text-orange-600" : "text-zinc-600"
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {link.name}
                      {isActive && (
                        <motion.div
                          layoutId="navbar-indicator"
                          className="absolute bottom-0 left-0 right-0 h-0.5 bg-orange-600"
                          initial={false}
                          transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        />
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </nav>

            {/* Language/Action */}
            <div className="hidden md:flex items-center gap-4">
              <button className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-900 transition-colors">
                <Globe className="w-4 h-4" /> EN / 中文
              </button>
              <NavLink 
                to="/contact" 
                className="bg-zinc-900 text-white px-5 py-2.5 rounded-full text-sm font-medium hover:bg-orange-600 transition-colors flex items-center gap-2"
              >
                联系合作
                <ArrowUpRight className="w-4 h-4" />
              </NavLink>
            </div>

            {/* Mobile Menu Button */}
            <button
              className="md:hidden p-2 text-zinc-600 hover:text-zinc-900"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Nav */}
        <AnimatePresence>
          {isMobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden bg-white border-b border-zinc-200 overflow-hidden"
            >
              <div className="px-4 py-6 flex flex-col gap-4">
                {navLinks.map((link) => (
                  <NavLink
                    key={link.path}
                    to={link.path}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={({ isActive }) =>
                      clsx(
                        "text-lg font-medium transition-colors",
                        isActive ? "text-orange-600" : "text-zinc-600"
                      )
                    }
                  >
                    {link.name}
                  </NavLink>
                ))}
                <div className="h-px w-full bg-zinc-100 my-2" />
                <NavLink 
                  to="/contact" 
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="bg-orange-600 text-white text-center py-3 rounded-xl font-medium"
                >
                  联系合作
                </NavLink>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Footer */}
      <footer className="bg-zinc-950 text-zinc-400 py-16 border-t border-zinc-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-12 lg:gap-8 mb-12">
            <div className="md:col-span-1">
              <div className="flex items-center gap-2 mb-6">
                <div className="w-8 h-8 bg-orange-600 text-white flex items-center justify-center rounded-lg font-black text-sm italic tracking-tighter">
                  XW
                </div>
                <div>
                  <span className="font-bold text-lg text-white tracking-tight block leading-tight">芯威霆</span>
                </div>
              </div>
              <p className="text-sm leading-relaxed mb-6">
                专注跨境电商亚马逊平台，致力于将优质的运动鞋类产品带给全球消费者。简约、活力、创新。
              </p>
            </div>
            
            <div>
              <h4 className="text-white font-semibold mb-6">快速导航</h4>
              <ul className="space-y-3 text-sm">
                <li><NavLink to="/" className="hover:text-orange-500 transition-colors">首页</NavLink></li>
                <li><NavLink to="/about" className="hover:text-orange-500 transition-colors">关于我们</NavLink></li>
                <li><NavLink to="/business" className="hover:text-orange-500 transition-colors">业务板块</NavLink></li>
                <li><NavLink to="/partners" className="hover:text-orange-500 transition-colors">合作招商</NavLink></li>
              </ul>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-6">业务覆盖</h4>
              <ul className="space-y-3 text-sm">
                <li><span className="text-zinc-500">主力市场：</span> 美国站 (Amazon US)</li>
                <li><span className="text-zinc-500">主营品类：</span> 男士/女士/儿童运动鞋</li>
                <li><span className="text-zinc-500">团队规模：</span> 20-99人精英团队</li>
              </ul>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-6">联系方式</h4>
              <ul className="space-y-3 text-sm">
                <li><span className="text-zinc-500">地址：</span> 福州市仓山区智能产业园</li>
                <li><span className="text-zinc-500">邮箱：</span> contact@xinweiting.com</li>
                <li>
                  <NavLink to="/careers" className="inline-flex items-center text-orange-500 hover:text-orange-400 font-medium mt-2">
                    加入我们团队 <ArrowUpRight className="w-3 h-3 ml-1" />
                  </NavLink>
                </li>
              </ul>
            </div>
          </div>
          
          <div className="pt-8 border-t border-zinc-800 text-sm flex flex-col md:flex-row justify-between items-center gap-4">
            <p>© 2026 福州芯威霆电子商务有限公司. All rights reserved.</p>
            <div className="flex gap-4">
              <a href="#" className="hover:text-white transition-colors">隐私政策</a>
              <a href="#" className="hover:text-white transition-colors">服务条款</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}