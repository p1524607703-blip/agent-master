<script setup lang="ts">
import { computed, ref } from 'vue'
import { NIcon } from 'naive-ui'
import { GripVertical } from '@vicons/tabler'
import { useSessionStore } from '../stores/session'

type NavItem = [string, string]
type NavGroup = { title: string; items: NavItem[] }
type SavedLayout = { groups: Array<{ title: string; items: string[] }> }

const session = useSessionStore()
// 运营只保留「CPO 单双数据情况」一个模块，且不可拖拽/不写入本地布局缓存
const isOperator = computed(() => session.user?.roleCode === 'operator')

// v2：下架「产品明细」「广告类型」两个模块（2026-09-15 用户要求暂时隐藏）。
// 注意：布局会缓存到 localStorage，改默认值必须同时提升 STORAGE_KEY 版本，
// 否则老用户读到的仍是带这两个入口的旧布局，等于没改。
const STORAGE_KEY = 'adsight.sidebar.layout.v2'

// 已下架模块的路由路径：即使旧的本地布局里残留，渲染前也会被剔除
const RETIRED_PATHS = new Set(['/products', '/ad-types'])

const DEFAULT_GROUPS: NavGroup[] = [
  {title:'概览',items:[['/dashboard','概览看板']]},
  {title:'数据处理',items:[['/cpo-jobs','CPO处理中心'],['/issues','待确认异常']]},
  {title:'数据分析',items:[['/operator-cpo','运营单双情况']]},
  {title:'规则与数据',items:[['/product-mappings','产品映射'],['/rules','规则管理'],['/reports','报告管理']]},
]

// 运营视角的导航：只有自己的那个页面
const OPERATOR_GROUPS: NavGroup[] = [
  {title:'我的数据',items:[['/my-cpo','CPO 单双数据情况']]},
]

// 各角色允许出现的导航路径（运营只准 /my-cpo）
const allowedPaths = (): Set<string> | null =>
  isOperator.value ? new Set(['/my-cpo']) : null

const cloneDefaults = (): NavGroup[] => DEFAULT_GROUPS.map(g => ({ title:g.title, items:g.items.map(i => [...i] as NavItem) }))

/** 统一兜底：剔除已下架模块 / 角色无权访问的路径，并丢掉因此变空的导航组。 */
const stripRetired = (groups: NavGroup[]): NavGroup[] => {
  const allow = allowedPaths()
  return groups
    .map(g => ({ title: g.title, items: g.items.filter(i => !RETIRED_PATHS.has(i[0]) && (!allow || allow.has(i[0]))) }))
    .filter(g => g.items.length > 0)
}

const loadLayout = (): NavGroup[] => (isOperator.value ? OPERATOR_GROUPS : stripRetired(_loadLayout()))

const _loadLayout = (): NavGroup[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return cloneDefaults()
    const saved = JSON.parse(raw) as SavedLayout
    if (!Array.isArray(saved?.groups)) return cloneDefaults()

    const defaults = cloneDefaults()
    const defaultByTitle = new Map(defaults.map(g => [g.title, g]))
    const result: NavGroup[] = []
    const usedGroups = new Set<string>()

    for (const sg of saved.groups) {
      const base = defaultByTitle.get(sg.title)
      if (!base || usedGroups.has(base.title)) continue
      usedGroups.add(base.title)
      const byPath = new Map(base.items.map(i => [i[0], i]))
      const items: NavItem[] = []
      const usedItems = new Set<string>()
      for (const path of Array.isArray(sg.items) ? sg.items : []) {
        const item = byPath.get(path)
        if (!item || usedItems.has(path)) continue
        usedItems.add(path)
        items.push(item)
      }
      for (const item of base.items) if (!usedItems.has(item[0])) items.push(item)
      result.push({ title:base.title, items })
    }

    for (const g of defaults) if (!usedGroups.has(g.title)) result.push(g)
    return result
  } catch {
    return cloneDefaults()
  }
}

const groups = ref<NavGroup[]>(loadLayout())
// 运营视角固定单项，不参与拖拽排序；角色在登录态解析完成后才会确定，
// 所以这里用 computed 而不是初始值，避免首屏短暂渲染出管理端导航。
const visibleGroups = computed<NavGroup[]>(() => (isOperator.value ? OPERATOR_GROUPS : groups.value))
const draggingGroup = ref<number | null>(null)
const draggingItem = ref<{ group:number; item:number } | null>(null)
const overGroup = ref<number | null>(null)
const overItem = ref<{ group:number; item:number } | null>(null)

const persist = () => {
  if (isOperator.value) return  // 运营导航固定，不写本地布局
  const payload: SavedLayout = {
    groups: groups.value.map(g => ({ title:g.title, items:g.items.map(i => i[0]) })),
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

const resetLayout = () => {
  if (isOperator.value) return
  groups.value = cloneDefaults()
  localStorage.removeItem(STORAGE_KEY)
  clearDragState()
}

const clearDragState = () => {
  draggingGroup.value = null
  draggingItem.value = null
  overGroup.value = null
  overItem.value = null
}

const startGroupDrag = (event: DragEvent, index: number) => {
  draggingGroup.value = index
  draggingItem.value = null
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', `group:${index}`)
  }
}

const dropGroup = (event: DragEvent, targetIndex: number) => {
  event.preventDefault()
  const from = draggingGroup.value
  if (from == null || from === targetIndex) return clearDragState()
  const next = [...groups.value]
  const [moved] = next.splice(from, 1)
  next.splice(targetIndex, 0, moved)
  groups.value = next
  persist()
  clearDragState()
}

const startItemDrag = (event: DragEvent, groupIndex: number, itemIndex: number) => {
  event.stopPropagation()
  draggingItem.value = { group:groupIndex, item:itemIndex }
  draggingGroup.value = null
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', `item:${groupIndex}:${itemIndex}`)
  }
}

const dropItem = (event: DragEvent, groupIndex: number, targetIndex: number) => {
  event.preventDefault()
  event.stopPropagation()
  const from = draggingItem.value
  if (!from || from.group !== groupIndex || from.item === targetIndex) return clearDragState()
  const next = groups.value.map(g => ({ ...g, items:[...g.items] }))
  const [moved] = next[groupIndex].items.splice(from.item, 1)
  next[groupIndex].items.splice(targetIndex, 0, moved)
  groups.value = next
  persist()
  clearDragState()
}
</script>

<template>
  <aside class="sidebar draggable-sidebar">
    <div class="brand">
      <span class="logo">A</span>
      <span>AdSight</span>
    </div>

    <div class="sidebar-layout-hint">
      <span>导航</span>
      <span v-if="!isOperator" class="hint-drag"><NIcon :size="13"><GripVertical /></NIcon>拖动排序</span>
    </div>

    <div class="nav-groups">
      <section
        v-for="(g, groupIndex) in visibleGroups"
        :key="g.title"
        class="nav-group"
        :class="{
          'dragging': draggingGroup === groupIndex,
          'drag-over': overGroup === groupIndex && draggingGroup !== null && draggingGroup !== groupIndex,
        }"
        @dragover.prevent="overGroup = groupIndex"
        @dragleave="overGroup = null"
        @drop="dropGroup($event, groupIndex)"
      >
        <div class="nav-title draggable-title">
          <span>{{ g.title }}</span>
          <span
            v-if="!isOperator"
            class="drag-handle group-handle"
            draggable="true"
            title="拖动分组"
            aria-label="拖动分组"
            @dragstart="startGroupDrag($event, groupIndex)"
            @dragend="clearDragState"
          ><NIcon :size="15"><GripVertical /></NIcon></span>
        </div>

        <div class="nav-items">
          <div
            v-for="(item, itemIndex) in g.items"
            :key="item[0]"
            class="nav-item-row"
            :class="{
              'dragging': draggingItem?.group === groupIndex && draggingItem?.item === itemIndex,
              'drag-over': overItem?.group === groupIndex && overItem?.item === itemIndex && draggingItem?.item !== itemIndex,
            }"
            @dragover.prevent.stop="overItem = { group:groupIndex, item:itemIndex }"
            @dragleave.stop="overItem = null"
            @drop="dropItem($event, groupIndex, itemIndex)"
          >
            <span
              v-if="!isOperator"
              class="drag-handle item-handle"
              draggable="true"
              title="拖动模块"
              aria-label="拖动模块"
              @dragstart="startItemDrag($event, groupIndex, itemIndex)"
              @dragend="clearDragState"
            ><NIcon :size="15"><GripVertical /></NIcon></span>
            <router-link :to="item[0]" class="nav-item">{{ item[1] }}</router-link>
          </div>
        </div>
      </section>
    </div>

    <button v-if="!isOperator" class="reset-layout" type="button" @click="resetLayout">恢复默认顺序</button>
  </aside>
</template>

<style scoped>
.draggable-sidebar{display:flex;flex-direction:column;overflow-y:auto;overflow-x:hidden;user-select:none}
.sidebar-layout-hint{display:flex;justify-content:space-between;align-items:center;padding:0 8px 5px;color:#a1a8b4;font-size:10px;border-bottom:1px solid rgba(231,234,240,.72)}
.sidebar-layout-hint span:last-child{opacity:.75}.hint-drag{display:inline-flex;align-items:center;gap:2px}
.nav-groups{display:flex;flex-direction:column;gap:1px;padding-top:3px}
.nav-group{position:relative;border-radius:9px;transition:opacity .14s ease,transform .14s ease,background .14s ease,box-shadow .14s ease}
.nav-group.dragging{opacity:.42;transform:scale(.985)}
.nav-group.drag-over{background:#f1f6fd;box-shadow:inset 0 0 0 1px #cfe0f8}
.draggable-title{display:flex;align-items:center;justify-content:space-between;gap:8px}
.drag-handle{display:inline-flex;align-items:center;justify-content:center;color:#b2bac6;cursor:grab;padding:4px;border-radius:5px;transition:color .14s ease,background .14s ease,opacity .14s ease;opacity:.18}.drag-handle .n-icon{pointer-events:none}
.nav-group:hover>.draggable-title .group-handle,.nav-item-row:hover>.item-handle{opacity:1}
.drag-handle:hover{color:#687386;background:#eef2f7}
.drag-handle:active{cursor:grabbing}
.nav-items{display:flex;flex-direction:column}
.nav-item-row{position:relative;display:flex;align-items:center;border-radius:7px;transition:opacity .14s ease,transform .14s ease,background .14s ease}
.nav-item-row.dragging{opacity:.38;transform:scale(.985)}
.nav-item-row.drag-over::before{content:"";position:absolute;left:9px;right:7px;top:-2px;height:2px;background:var(--blue);border-radius:99px;box-shadow:0 0 0 2px rgba(22,119,255,.10)}
.nav-item-row .nav-item{flex:1;min-width:0;margin-left:0;padding-left:4px}
.item-handle{width:22px;min-width:22px;padding:5px 3px;margin-left:2px}
.reset-layout{margin:auto 4px 4px;border:0;background:transparent;color:#9aa3b0;font-size:10px;padding:9px 8px;border-radius:7px;cursor:pointer;transition:background .14s,color .14s}
.reset-layout:hover{background:#f0f3f7;color:#5f6977}
@media(max-width:760px){.sidebar-layout-hint,.drag-handle,.reset-layout{display:none}.nav-item-row .nav-item{padding-left:10px}.nav-group{border-radius:0}}
</style>
