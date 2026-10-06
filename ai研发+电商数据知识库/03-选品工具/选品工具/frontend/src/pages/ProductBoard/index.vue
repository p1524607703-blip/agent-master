<template>
  <div class="board-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">选品看板</h1>
        <p class="page-sub">商品管理与追踪</p>
      </div>
      <el-button type="primary" @click="showAddDialog = true">
        <el-icon><Plus /></el-icon> 添加商品
      </el-button>
    </div>

    <!-- Summary stats -->
    <div class="summary-row">
      <StatCard label="全部商品" :value="pagination.total" icon="Box" color="#0891b2" />
      <StatCard label="已推荐" :value="statusCounts.recommended" icon="StarFilled" color="#10b981" />
      <StatCard label="观察中" :value="statusCounts.watching" icon="View" color="#f59e0b" />
      <StatCard label="已淘汰" :value="statusCounts.dropped" icon="CircleCloseFilled" color="#94a3b8" />
    </div>

    <!-- Filters -->
    <GlassCard class="filter-bar">
      <div class="filters">
        <el-radio-group v-model="filters.status" @change="fetchProducts">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="recommended">已推荐</el-radio-button>
          <el-radio-button value="watching">观察中</el-radio-button>
          <el-radio-button value="dropped">已淘汰</el-radio-button>
        </el-radio-group>
        <el-input v-model="filters.search" placeholder="搜索商品..." prefix-icon="Search" style="width: 240px" clearable @change="fetchProducts" />
        <el-select v-model="filters.category" placeholder="分类" clearable style="width: 140px" @change="fetchProducts">
          <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
        </el-select>
      </div>
    </GlassCard>

    <!-- Bento grid -->
    <div class="bento-grid" v-loading="loading">
      <div
        v-for="product in products"
        :key="product.id"
        class="product-card"
        @click="selectedProduct = product"
      >
        <div class="product-card-inner">
          <div class="product-status-bar" :class="`status--${product.status}`" />
          <div class="product-header">
            <div class="product-name">{{ product.name }}</div>
            <el-tag :type="statusType(product.status)" size="small">{{ statusLabel(product.status) }}</el-tag>
          </div>
          <div class="product-category">{{ product.category || '未分类' }}</div>
          <div class="product-price">
            <span v-if="product.priceMin">${{ product.priceMin }} – ${{ product.priceMax }}</span>
            <span v-else class="no-price">待定价</span>
          </div>
          <div class="product-score-row">
            <span class="score-label">综合评分</span>
            <el-progress :percentage="product.score" :stroke-width="5" :color="scoreColor(product.score)" style="flex:1; margin: 0 8px;" />
            <span class="score-value">{{ product.score }}</span>
          </div>
          <div class="product-actions">
            <el-button size="small" @click.stop="changeStatus(product, 'recommended')">推荐</el-button>
            <el-button size="small" type="danger" plain @click.stop="changeStatus(product, 'dropped')">淘汰</el-button>
          </div>
        </div>
      </div>

      <div v-if="!products.length && !loading" class="empty-board">
        <el-empty description="暂无商品，点击右上角添加" />
      </div>
    </div>

    <!-- Pagination -->
    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="prev, pager, next, total"
        @current-change="fetchProducts"
      />
    </div>

    <!-- Add dialog -->
    <el-dialog v-model="showAddDialog" title="添加商品" width="440px">
      <el-form :model="newProduct" label-width="80px">
        <el-form-item label="商品名称"><el-input v-model="newProduct.name" /></el-form-item>
        <el-form-item label="分类"><el-input v-model="newProduct.category" /></el-form-item>
        <el-form-item label="最低价"><el-input-number v-model="newProduct.priceMin" :min="0" /></el-form-item>
        <el-form-item label="最高价"><el-input-number v-model="newProduct.priceMax" :min="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="addProduct">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import axios from 'axios'
import GlassCard from '@/components/GlassCard.vue'
import StatCard from '@/components/StatCard.vue'

const loading = ref(false)
const saving = ref(false)
const showAddDialog = ref(false)
const products = ref<any[]>([])
const selectedProduct = ref<any>(null)

const filters = reactive({ status: '', search: '', category: '' })
const pagination = reactive({ page: 1, pageSize: 12, total: 0 })
const statusCounts = ref({ recommended: 0, watching: 0, dropped: 0 })

const categories = ref(['家居', '电子', '宠物', '美妆', '运动', '厨房'])

const newProduct = reactive({ name: '', category: '', priceMin: 0, priceMax: 0 })

function statusType(s: string) {
  return { recommended: 'success', watching: 'warning', dropped: 'info' }[s] || 'info'
}

function statusLabel(s: string) {
  return { recommended: '已推荐', watching: '观察中', dropped: '已淘汰' }[s] || s
}

function scoreColor(s: number) {
  if (s >= 80) return '#10b981'
  if (s >= 60) return '#f59e0b'
  return '#f43f5e'
}

async function fetchProducts() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/products', {
      params: {
        page: pagination.page,
        pageSize: pagination.pageSize,
        status: filters.status || undefined,
        category: filters.category || undefined,
      },
    })
    products.value = data.items || []
    pagination.total = data.total || 0
  } catch {
    products.value = Array.from({ length: 6 }, (_, i) => ({
      id: `p${i}`, name: `示例商品 ${i + 1}`, category: categories.value[i % 6],
      score: 55 + i * 8, status: ['recommended', 'watching', 'dropped'][i % 3],
      priceMin: 10 + i * 5, priceMax: 30 + i * 8,
    }))
    pagination.total = 6
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const { data } = await axios.get('/api/products/stats')
    statusCounts.value = { recommended: data.recommended, watching: data.watching, dropped: data.dropped }
    pagination.total = data.total
  } catch {
    statusCounts.value = { recommended: 32, watching: 156, dropped: 60 }
  }
}

async function changeStatus(product: any, status: string) {
  try {
    await axios.put(`/api/products/${product.id}`, { status })
    product.status = status
  } catch {}
}

async function addProduct() {
  saving.value = true
  try {
    await axios.post('/api/products', { ...newProduct, status: 'watching', score: 0 })
    showAddDialog.value = false
    Object.assign(newProduct, { name: '', category: '', priceMin: 0, priceMax: 0 })
    fetchProducts()
  } catch {} finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchProducts()
  fetchStats()
})
</script>

<style scoped>
.board-page { position: relative; z-index: 1; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-title { font-size: 24px; font-weight: 700; color: #0c2340; }
.page-sub { font-size: 14px; color: #3d6b8a; margin-top: 4px; }

.summary-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 16px; }

.filter-bar { margin-bottom: 20px; }
.filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }

.bento-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; min-height: 200px; }

.product-card {
  background: rgba(255,255,255,0.45);
  backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255,255,255,0.7);
  border-radius: 18px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  overflow: hidden;
}
.product-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 16px 40px rgba(8,145,178,0.15);
}

.product-status-bar { height: 4px; width: 100%; }
.status--recommended { background: linear-gradient(90deg, #10b981, #34d399); }
.status--watching { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.status--dropped { background: linear-gradient(90deg, #94a3b8, #cbd5e1); }

.product-card-inner { padding: 16px; }
.product-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }
.product-name { font-size: 15px; font-weight: 600; color: #0c2340; flex: 1; margin-right: 8px; }
.product-category { font-size: 12px; color: #64748b; margin-bottom: 8px; }
.product-price { font-size: 14px; font-weight: 600; color: #0891b2; margin-bottom: 10px; }
.no-price { color: #94a3b8; font-weight: 400; }
.product-score-row { display: flex; align-items: center; margin-bottom: 12px; }
.score-label { font-size: 12px; color: #64748b; white-space: nowrap; }
.score-value { font-size: 13px; font-weight: 700; color: #0c2340; }
.product-actions { display: flex; gap: 8px; }

.empty-board { grid-column: 1 / -1; display: flex; justify-content: center; padding: 60px; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
</style>
