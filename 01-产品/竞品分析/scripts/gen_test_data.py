"""生成测试数据，验证 Obsidian 输出管道"""
import sys
sys.path.insert(0, '.')
from models import ProductItem
from output.to_obsidian import save_to_obsidian
from datetime import datetime, timezone

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

test_items = [
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="工厂直供无核山楂片500g散装蜜饯休闲零食酸甜山楂干",
        商品链接="https://detail.1688.com/offer/701234560001.html",
        商品ID="701234560001",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test1.jpg",
        采集时间=now, 售价=8.5, 原价=12.0, 起订量MOQ=500, 月销量=3200,
        评分=4.8, 评价数=1560, 商品分类="食品>休闲食品>山楂制品",
        店铺名称="河北鑫农食品厂", 发货地="河北 保定", 是否包邮=True,
    ),
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="无核山楂卷儿片250g山楂糕条独立包装学生儿童零食整箱批发",
        商品链接="https://detail.1688.com/offer/701234560002.html",
        商品ID="701234560002",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test2.jpg",
        采集时间=now, 售价=5.9, 起订量MOQ=1000, 月销量=5600,
        评分=4.7, 评价数=2280, 商品分类="食品>休闲食品>山楂制品",
        店铺名称="保定市满城区聚丰山楂食品厂", 发货地="河北 保定", 是否包邮=True,
    ),
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="精品无核山楂球200g独立包装蜜饯果脯零食满减包邮散装批发",
        商品链接="https://detail.1688.com/offer/701234560003.html",
        商品ID="701234560003",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test3.jpg",
        采集时间=now, 售价=11.8, 原价=15.0, 起订量MOQ=200, 月销量=980,
        评分=4.9, 评价数=430, 品牌="红果情", 商品分类="食品>休闲食品>山楂制品",
        店铺名称="红果情食品旗舰店", 发货地="河北 石家庄", 是否包邮=True,
    ),
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="无核山楂去核山楂片整箱5斤批发散装酸甜蜜饯厂家直销",
        商品链接="https://detail.1688.com/offer/701234560004.html",
        商品ID="701234560004",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test4.jpg",
        采集时间=now, 售价=32.0, 起订量MOQ=100, 月销量=420,
        评分=4.6, 评价数=198, 商品分类="食品>休闲食品>山楂制品",
        店铺名称="顺平县金农产品加工厂", 发货地="河北 保定", 是否包邮=False, 运费=10.0,
    ),
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="无核山楂糕原味500g老北京风味山楂年糕条切糕传统工艺",
        商品链接="https://detail.1688.com/offer/701234560005.html",
        商品ID="701234560005",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test5.jpg",
        采集时间=now, 售价=9.9, 原价=13.5, 起订量MOQ=300, 月销量=2100,
        评分=4.8, 评价数=876, 品牌="老北京", 商品分类="食品>休闲食品>山楂制品",
        店铺名称="北京三元食品有限公司", 发货地="北京", 是否包邮=True,
    ),
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="天然无核山楂干片原味无添加健康零食500g可泡水泡茶养生",
        商品链接="https://detail.1688.com/offer/701234560006.html",
        商品ID="701234560006",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test6.jpg",
        采集时间=now, 售价=14.5, 起订量MOQ=100, 月销量=1560,
        评分=4.9, 评价数=723, 品牌="山里源", 商品分类="食品>健康食品>干果炒货",
        店铺名称="山里源食品旗舰店", 发货地="陕西 西安", 是否包邮=True,
    ),
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="无核山楂饼山楂果丹皮100gx10包装整箱批发儿童零食小吃",
        商品链接="https://detail.1688.com/offer/701234560007.html",
        商品ID="701234560007",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test7.jpg",
        采集时间=now, 售价=18.0, 原价=22.0, 起订量MOQ=200, 月销量=3400,
        评分=4.7, 评价数=1890, 商品分类="食品>休闲食品>山楂制品",
        店铺名称="保定果丹皮食品厂", 发货地="河北 保定", 是否包邮=True,
    ),
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="精选大粒无核山楂整颗500g蜜饯糖葫芦专用原料厂家批发",
        商品链接="https://detail.1688.com/offer/701234560008.html",
        商品ID="701234560008",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test8.jpg",
        采集时间=now, 售价=22.0, 起订量MOQ=50, 月销量=760,
        评分=4.8, 评价数=345, 商品分类="食品>休闲食品>山楂制品",
        店铺名称="兴隆县鑫达山楂专业合作社", 发货地="河北 承德", 是否包邮=True,
    ),
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="无核山楂片红糖口味250g散装多口味可选儿童零食蜜饯礼包",
        商品链接="https://detail.1688.com/offer/701234560009.html",
        商品ID="701234560009",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test9.jpg",
        采集时间=now, 售价=7.5, 原价=10.0, 起订量MOQ=500, 月销量=4200,
        评分=4.6, 评价数=2100, 商品分类="食品>休闲食品>山楂制品",
        店铺名称="满城县宏盛食品加工厂", 发货地="河北 保定", 是否包邮=True,
    ),
    ProductItem(
        平台="1688", 搜索关键词="无核山楂",
        商品名称="网红爆款无核山楂罐头425g酸甜可口糖水山楂罐头整件批发",
        商品链接="https://detail.1688.com/offer/701234560010.html",
        商品ID="701234560010",
        主图="https://cbu01.alicdn.com/img/ibank/O1CN01test10.jpg",
        采集时间=now, 售价=6.8, 起订量MOQ=1000, 月销量=8900,
        评分=4.7, 评价数=4320, 品牌="御食园", 商品分类="食品>休闲食品>罐头",
        店铺名称="御食园食品官方旗舰店", 发货地="北京", 是否包邮=True, 是否官方店=True,
    ),
]

saved = save_to_obsidian(test_items)
print(f"写入 {saved} 条笔记")
prices = [i.售价 for i in test_items]
sales = [i.月销量 for i in test_items if i.月销量]
revenues = [i.月销售额估算 for i in test_items if i.月销售额估算]
print(f"价格区间: {min(prices):.1f} ~ {max(prices):.1f} 元")
print(f"月销量区间: {min(sales):,} ~ {max(sales):,}")
print(f"最高月销售额估算: {max(revenues):,.0f} 元")
print(f"输出目录: {__import__('config').DATA_OUTPUT_DIR}/1688/")
