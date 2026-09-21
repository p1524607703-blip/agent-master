export const dashboardOverview = {
  ad_spend: 48260, total_orders: 8420, ad_orders: 5170, estimated_organic_orders: 3250, cpo: 5.73, estimated_organic_share: 0.386,
  ad_types: [
    { l1: 'SP', spend: 31800, orders: 3950, organicOrders: null, cpo: 8.05, children: [{name:'SP_MANUAL',spend:17250,orders:2030,cpo:8.50},{name:'SP_AUTO',spend:14550,orders:1920,cpo:7.58}] },
    { l1: 'SB', spend: 10460, orders: 930, organicOrders: null, cpo: 11.25, children: [{name:'SB_HEADLINE',spend:5820,orders:515,cpo:11.30},{name:'SB_VIDEO',spend:4640,orders:415,cpo:11.18}] },
    { l1: 'SD', spend: 4820, orders: 270, organicOrders: null, cpo: 17.85, children: [{name:'SD_DISPLAY',spend:4820,orders:270,cpo:17.85}] },
    { l1: 'STV', spend: 1180, orders: 20, organicOrders: null, cpo: 59, children: [{name:'STV_STREAMING',spend:1180,orders:20,cpo:59}] },
  ],
  performance: [
    {name:'ZJ',spend:9452,adOrders:921,totalOrders:1459,organic:538,cpo:6.48,share:'36.9%',maturity:100,change:-5.2,status:'正常'},
    {name:'XH',spend:8920,adOrders:1010,totalOrders:1612,organic:602,cpo:5.53,share:'37.3%',maturity:100,change:2.1,status:'正常'},
    {name:'XM',spend:7810,adOrders:910,totalOrders:1386,organic:476,cpo:5.64,share:'34.3%',maturity:71,change:null,status:'关注'},
  ]
}
export const dashboardTrend = [
  {date:'8/22',cpo:6.90,adOrders:318,organicOrders:null},
  {date:'8/23',cpo:6.70,adOrders:326,organicOrders:null},
  {date:'8/24',cpo:6.75,adOrders:334,organicOrders:null},
  {date:'8/25',cpo:6.40,adOrders:352,organicOrders:null},
  {date:'8/26',cpo:6.50,adOrders:347,organicOrders:null},
  {date:'8/27',cpo:6.15,adOrders:371,organicOrders:null},
  {date:'8/28',cpo:6.25,adOrders:365,organicOrders:null},
  {date:'8/29',cpo:6.00,adOrders:382,organicOrders:null},
  {date:'8/30',cpo:6.10,adOrders:376,organicOrders:null},
  {date:'8/31',cpo:5.85,adOrders:401,organicOrders:null},
  {date:'9/01',cpo:5.92,adOrders:394,organicOrders:null},
  {date:'9/02',cpo:5.68,adOrders:417,organicOrders:null},
  {date:'9/03',cpo:5.76,adOrders:409,organicOrders:null},
  {date:'9/04',cpo:5.73,adOrders:421,organicOrders:null},
]
export const cpoJobs = [{ id: 1042, data_date: '2026-09-02', owner: 'ZJ', status: 'NEEDS_REVIEW', issues: 3, products: 14, updated_at: '09-04 09:12' }]
export const issues = [
  {id:1,code:'UNCLASSIFIED',campaign:'ZJ1-W81 AUTO 9.4',problem:'新 Campaign 广告类型',suggestion:'SP / SP_AUTO',status:'待确认'},
  {id:2,code:'operator_unresolved',campaign:'W75V2 Z32 头条',problem:'产品归属冲突',suggestion:'W75V2 / Z32',status:'待确认'},
  {id:3,code:'ad_units_field_missing',campaign:'AMS-W81-Video',problem:'广告单量字段缺失',suggestion:'检查报告字段',status:'阻断'},
]
export const productRules = [
  {campaign:'479537915429061',name:'ZJ1-W85816351 头条 target W882 1.9',method:'fixed_equal_split',scope:'W85 / W81 / W63 / W51男',status:'active'},
  {campaign:'19027149623806',name:'ZJ1-W8K2- WK102 school 广泛动态 7.21',method:'mixed_split',scope:'W8K2- / WK102',status:'active'},
]
export const adTypeRules = [
  {campaign:'123456',name:'ZJ1-W81 AUTO 0.5',l1:'SP',l2:'SP_AUTO',source:'confirmed',status:'active'},
  {campaign:'345678',name:'ZJ1-W81 头条',l1:'SB',l2:'SB_HEADLINE',source:'confirmed',status:'active'},
  {campaign:'678901',name:'ZJ1-W8K2 流媒体',l1:'STV',l2:'STV_STREAMING',source:'confirmed',status:'active'},
]
export const reports = [
  {account:'川鹏',type:'业务报告',date:'2026-09-02',status:'READY'},
  {account:'欧德思',type:'业务报告',date:'2026-09-02',status:'READY'},
  {account:'川鹏',type:'广告报告',date:'2026-09-02',status:'READY'},
  {account:'AMS',type:'推广的商品',date:'2026-09-02',status:'READY'},
  {account:'STV',type:'Streaming TV',date:'2026-09-02',status:'READY'},
]
