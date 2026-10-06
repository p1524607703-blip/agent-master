<template>
  <div class="ai-page">
    <!-- Particle-like background -->
    <div class="ai-bg">
      <div class="particle" v-for="i in 12" :key="i" :style="particleStyle(i)" />
    </div>

    <div class="page-header">
      <div>
        <h1 class="page-title">AI 深度分析</h1>
        <p class="page-sub">MiniMax M1 驱动，SWOT + 评分报告</p>
      </div>
    </div>

    <div class="analysis-layout">
      <!-- Left: Product selector -->
      <GlassCard class="product-panel">
        <template #header><div class="card-title">选择商品</div></template>
        <div class="search-bar">
          <el-input v-model="searchQuery" placeholder="搜索商品名称..." prefix-icon="Search" clearable @input="searchProducts" />
        </div>
        <div class="product-list">
          <div
            v-for="product in filteredProducts"
            :key="product.id"
            class="product-item"
            :class="{ 'product-item--selected': selectedProduct?.id === product.id }"
            @click="selectProduct(product)"
          >
            <div class="product-item-name">{{ product.name }}</div>
            <div class="product-item-meta">{{ product.category }} · 评分 {{ product.score }}</div>
          </div>
          <div v-if="!filteredProducts.length" class="empty-state">没有找到商品</div>
        </div>
      </GlassCard>

      <!-- Center: AI Chat stream -->
      <GlassCard class="chat-panel">
        <template #header>
          <div class="card-title">
            <div class="ai-indicator">
              <span class="ai-dot" :class="{ 'ai-dot--active': analyzing }" />
              AI 分析流
            </div>
            <el-button v-if="selectedProduct" type="primary" size="small" :loading="analyzing" @click="startAnalysis">
              {{ analyzing ? '分析中...' : '开始分析' }}
            </el-button>
          </div>
        </template>

        <div class="chat-stream" ref="chatStream">
          <!-- Thinking animation -->
          <div v-if="analyzing" class="thinking-box">
            <div class="thinking-dots">
              <span /><span /><span />
            </div>
            <span class="thinking-text">AI 正在深度分析中...</span>
          </div>

          <!-- Analysis result -->
          <template v-if="analysisResult">
            <div class="ai-message">
              <div class="ai-avatar">AI</div>
              <div class="ai-bubble">
                <div class="ai-summary">{{ analysisResult.summary }}</div>

                <!-- SWOT Grid -->
                <div class="swot-grid">
                  <div class="swot-item swot--s">
                    <div class="swot-label">S 优势</div>
                    <ul><li v-for="s in analysisResult.swot.strengths" :key="s">{{ s }}</li></ul>
                  </div>
                  <div class="swot-item swot--w">
                    <div class="swot-label">W 劣势</div>
                    <ul><li v-for="w in analysisResult.swot.weaknesses" :key="w">{{ w }}</li></ul>
                  </div>
                  <div class="swot-item swot--o">
                    <div class="swot-label">O 机会</div>
                    <ul><li v-for="o in analysisResult.swot.opportunities" :key="o">{{ o }}</li></ul>
                  </div>
                  <div class="swot-item swot--t">
                    <div class="swot-label">T 威胁</div>
                    <ul><li v-for="t in analysisResult.swot.threats" :key="t">{{ t }}</li></ul>
                  </div>
                </div>

                <div class="ai-recommendation">
                  <span class="rec-label">操作建议</span>
                  <span class="rec-value" :class="`rec--${recClass}`">{{ analysisResult.recommendation }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="!selectedProduct && !analyzing" class="empty-chat">
            <div class="empty-icon">🤖</div>
            <p>选择商品后点击"开始分析"</p>
          </div>
        </div>
      </GlassCard>

      <!-- Right: Score panel -->
      <GlassCard class="score-panel" v-if="analysisResult">
        <template #header><div class="card-title">综合评分</div></template>
        <div class="score-display">
          <div class="score-number">{{ analysisResult.score }}</div>
          <div class="score-label">/ 100</div>
        </div>
        <div class="score-ring-wrap">
          <el-progress type="circle" :percentage="analysisResult.score" :stroke-width="10"
            :color="scoreGradient" :width="160" />
        </div>

        <div class="price-range">
          <div class="price-label">建议定价区间</div>
          <div class="price-value">${{ analysisResult.priceRange.min }} – ${{ analysisResult.priceRange.max }}</div>
        </div>

        <div class="target-market">
          <div class="price-label">目标受众</div>
          <div class="tags">
            <el-tag v-for="t in analysisResult.targetMarket" :key="t" size="small" type="info">{{ t }}</el-tag>
          </div>
        </div>
      </GlassCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import axios from 'axios'
import GlassCard from '@/components/GlassCard.vue'

const searchQuery = ref('')
const selectedProduct = ref<any>(null)
const products = ref<any[]>([])
const analyzing = ref(false)
const analysisResult = ref<any>(null)
const chatStream = ref<HTMLElement>()

const filteredProducts = computed(() =>
  searchQuery.value
    ? products.value.filter(p => p.name.includes(searchQuery.value))
    : products.value,
)

const recClass = computed(() => {
  const r = analysisResult.value?.recommendation || ''
  if (r.includes('强烈')) return 'green'
  if (r.includes('推荐')) return 'teal'
  if (r.includes('观望')) return 'amber'
  return 'red'
})

const scoreGradient = computed(() => {
  const s = analysisResult.value?.score || 0
  if (s >= 80) return '#10b981'
  if (s >= 60) return '#f59e0b'
  return '#f43f5e'
})

function particleStyle(i: number) {
  return {
    left: `${(i * 137) % 100}%`,
    top: `${(i * 97) % 100}%`,
    width: `${4 + (i % 3) * 3}px`,
    height: `${4 + (i % 3) * 3}px`,
    animationDelay: `${i * 0.5}s`,
    animationDuration: `${6 + (i % 4) * 2}s`,
  }
}

async function searchProducts() {
  if (!products.value.length) {
    try {
      const { data } = await axios.get('/api/products?pageSize=50')
      products.value = data.items || []
    } catch {
      products.value = Array.from({ length: 6 }, (_, i) => ({
        id: `p${i}`, name: `示例商品 ${i + 1}`, category: '家居', score: 60 + i * 5,
      }))
    }
  }
}

function selectProduct(p: any) {
  selectedProduct.value = p
  analysisResult.value = null
}

async function startAnalysis() {
  if (!selectedProduct.value) return
  analyzing.value = true
  analysisResult.value = null
  try {
    const { data } = await axios.post(`/api/analysis/${selectedProduct.value.id}`, {
      name: selectedProduct.value.name,
    })
    analysisResult.value = data
  } catch {
    // Mock result
    analysisResult.value = {
      score: 78,
      summary: '该商品在 TikTok 和 Google 上热度持续上升，受众集中于18-35岁消费群体，市场竞争适中，建议尽快入局。',
      swot: {
        strengths: ['爆款潜力高', '利润空间较大', '供应链稳定'],
        weaknesses: ['竞争对手较多', '季节性波动', '物流成本偏高'],
        opportunities: ['北美市场需求旺盛', '短视频带货红利期', '节日促销窗口'],
        threats: ['价格战风险', '平台政策变动', '仿品冲击'],
      },
      recommendation: '推荐',
      priceRange: { min: 19.99, max: 39.99 },
      targetMarket: ['18-35岁', '北美市场', '家居爱好者', '品质消费群'],
    }
  } finally {
    analyzing.value = false
    await nextTick()
    if (chatStream.value) chatStream.value.scrollTop = chatStream.value.scrollHeight
  }
}

searchProducts()
</script>

<style scoped>
.ai-page { position: relative; z-index: 1; }

.ai-bg { position: fixed; inset: 0; pointer-events: none; z-index: 0; }
.particle { position: absolute; border-radius: 50%; background: rgba(8,145,178,0.15); animation: float-particle linear infinite; }
@keyframes float-particle { 0% { transform: translateY(0) scale(1); opacity: 0.6; } 50% { opacity: 1; } 100% { transform: translateY(-100vh) scale(0.5); opacity: 0; } }

.page-header { margin-bottom: 20px; }
.page-title { font-size: 24px; font-weight: 700; color: #0c2340; }
.page-sub { font-size: 14px; color: #3d6b8a; margin-top: 4px; }

.analysis-layout { display: grid; grid-template-columns: 240px 1fr 280px; gap: 20px; min-height: 600px; }

.product-panel, .chat-panel, .score-panel { display: flex; flex-direction: column; }

.search-bar { margin-bottom: 12px; }
.product-list { flex: 1; overflow-y: auto; max-height: 500px; }
.product-item { padding: 10px 12px; border-radius: 10px; cursor: pointer; transition: background 0.15s; }
.product-item:hover, .product-item--selected { background: rgba(8,145,178,0.08); }
.product-item-name { font-size: 14px; font-weight: 500; color: #0c2340; }
.product-item-meta { font-size: 12px; color: #64748b; margin-top: 2px; }

.card-title { font-size: 15px; font-weight: 600; color: #0c2340; display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.ai-indicator { display: flex; align-items: center; gap: 8px; }
.ai-dot { width: 8px; height: 8px; border-radius: 50%; background: #94a3b8; }
.ai-dot--active { background: #0891b2; animation: blink 1s infinite; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

.chat-stream { flex: 1; overflow-y: auto; max-height: 520px; padding: 8px 0; }
.thinking-box { display: flex; align-items: center; gap: 12px; padding: 16px; background: rgba(8,145,178,0.06); border-radius: 12px; margin-bottom: 12px; }
.thinking-dots { display: flex; gap: 4px; }
.thinking-dots span { width: 8px; height: 8px; border-radius: 50%; background: #0891b2; animation: bounce 1.2s infinite; }
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%,60%,100% { transform: translateY(0); } 30% { transform: translateY(-8px); } }
.thinking-text { font-size: 13px; color: #0891b2; }

.ai-message { display: flex; gap: 12px; }
.ai-avatar { width: 32px; height: 32px; border-radius: 8px; background: linear-gradient(135deg, #0891b2, #22d3ee); color: white; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ai-bubble { flex: 1; }
.ai-summary { font-size: 14px; color: #0c2340; line-height: 1.6; margin-bottom: 16px; }

.swot-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.swot-item { padding: 10px; border-radius: 10px; }
.swot--s { background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.2); }
.swot--w { background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.15); }
.swot--o { background: rgba(8,145,178,0.06); border: 1px solid rgba(8,145,178,0.15); }
.swot--t { background: rgba(245,158,11,0.06); border: 1px solid rgba(245,158,11,0.15); }
.swot-label { font-size: 11px; font-weight: 700; margin-bottom: 6px; color: #475569; }
.swot-item ul { padding-left: 14px; }
.swot-item li { font-size: 12px; color: #334155; line-height: 1.6; }

.ai-recommendation { display: flex; align-items: center; gap: 10px; }
.rec-label { font-size: 13px; color: #64748b; }
.rec-value { font-size: 15px; font-weight: 700; padding: 4px 14px; border-radius: 20px; }
.rec--green { background: rgba(16,185,129,0.12); color: #059669; }
.rec--teal { background: rgba(8,145,178,0.12); color: #0891b2; }
.rec--amber { background: rgba(245,158,11,0.12); color: #d97706; }
.rec--red { background: rgba(244,63,94,0.12); color: #e11d48; }

.empty-chat { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 200px; color: #94a3b8; }
.empty-icon { font-size: 40px; margin-bottom: 12px; }

.score-display { display: flex; align-items: baseline; gap: 4px; margin-bottom: 12px; }
.score-number { font-size: 56px; font-weight: 800; background: linear-gradient(135deg, #0891b2, #22d3ee); -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1; }
.score-label { font-size: 18px; color: #94a3b8; }
.score-ring-wrap { display: flex; justify-content: center; margin: 12px 0; }

.price-range, .target-market { margin-top: 16px; }
.price-label { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.price-value { font-size: 18px; font-weight: 700; color: #0891b2; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }

.empty-state { text-align: center; color: #94a3b8; padding: 20px; font-size: 13px; }
</style>
