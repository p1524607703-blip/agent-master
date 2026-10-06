import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

const products = [
  { name: '无线蓝牙耳机 Pro Max', category: '电子', priceMin: 19.99, priceMax: 39.99, score: 92, status: 'recommended' },
  { name: '硅胶厨房收纳架', category: '厨房', priceMin: 8.99, priceMax: 18.99, score: 85, status: 'recommended' },
  { name: '宠物自动饮水机', category: '宠物', priceMin: 22.99, priceMax: 45.99, score: 88, status: 'recommended' },
  { name: 'LED补光灯环形灯', category: '摄影', priceMin: 15.99, priceMax: 29.99, score: 79, status: 'watching' },
  { name: '可折叠手机支架', category: '电子', priceMin: 5.99, priceMax: 12.99, score: 72, status: 'watching' },
  { name: '多功能充电宝 20000mAh', category: '电子', priceMin: 25.99, priceMax: 49.99, score: 83, status: 'recommended' },
  { name: '瑜伽垫防滑加厚', category: '运动', priceMin: 18.99, priceMax: 35.99, score: 76, status: 'watching' },
  { name: '猫咪自动喂食器', category: '宠物', priceMin: 35.99, priceMax: 69.99, score: 91, status: 'recommended' },
  { name: '美妆收纳旋转架', category: '美妆', priceMin: 12.99, priceMax: 24.99, score: 68, status: 'watching' },
  { name: '不锈钢保温杯 500ml', category: '厨房', priceMin: 14.99, priceMax: 28.99, score: 74, status: 'watching' },
  { name: '车载手机支架磁吸', category: '汽车', priceMin: 9.99, priceMax: 19.99, score: 81, status: 'recommended' },
  { name: '儿童编程机器人套件', category: '教育', priceMin: 45.99, priceMax: 89.99, score: 87, status: 'recommended' },
  { name: '睡眠眼罩遮光3D', category: '家居', priceMin: 6.99, priceMax: 14.99, score: 65, status: 'watching' },
  { name: 'USB风扇小型桌面', category: '电子', priceMin: 7.99, priceMax: 16.99, score: 58, status: 'dropped' },
  { name: '植物精油香薰机', category: '家居', priceMin: 19.99, priceMax: 39.99, score: 78, status: 'watching' },
]

const platforms = ['tiktok', 'reddit', 'google', 'facebook']
const metrics = ['views', 'mentions', 'search_volume', 'ad_count']

async function main() {
  console.log('🌱 开始播种数据...')

  await prisma.trendData.deleteMany()
  await prisma.alert.deleteMany()
  await prisma.agentTask.deleteMany()
  await prisma.product.deleteMany()

  for (const p of products) {
    const product = await prisma.product.create({ data: p })

    // 为每个商品创建趋势数据
    for (const platform of platforms.slice(0, 2 + Math.floor(Math.random() * 2))) {
      for (let i = 0; i < 7; i++) {
        await prisma.trendData.create({
          data: {
            productId: product.id,
            platform,
            metric: metrics[Math.floor(Math.random() * metrics.length)],
            value: Math.floor(1000 + Math.random() * 99000),
            deltaPercent: (Math.random() - 0.3) * 60,
            recordedAt: new Date(Date.now() - i * 24 * 3600 * 1000),
          },
        })
      }
    }
  }

  // 创建几条 Alert
  const firstProduct = await prisma.product.findFirst()
  if (firstProduct) {
    await prisma.alert.createMany({
      data: [
        { productId: firstProduct.id, type: 'surge', message: '无线蓝牙耳机 TikTok 热度暴增 +142%', severity: 'critical' },
        { productId: firstProduct.id, type: 'price_drop', message: '竞品价格下调 18%，建议关注', severity: 'warning' },
      ],
    })
  }

  // 创建 AgentTask 历史
  await prisma.agentTask.createMany({
    data: [
      { name: '全品类数据扫描', type: 'scan', status: 'completed', progress: 100, completedAt: new Date() },
      { name: 'TikTok趋势抓取', type: 'scan', status: 'completed', progress: 100, completedAt: new Date() },
      { name: '预警规则检查', type: 'alert_check', status: 'completed', progress: 100, completedAt: new Date() },
    ],
  })

  console.log(`✅ 种子数据完成：${products.length} 个商品，趋势数据，预警，任务历史`)
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect())
