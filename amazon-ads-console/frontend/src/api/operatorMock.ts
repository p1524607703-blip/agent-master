const emptyRows = { daily: [], weekly: [] }

export const operatorDetails: Record<string, any> = {
  ZJ: {
    operator: 'ZJ', account: '川鹏 + AMS', range: '2026-08-29 ~ 2026-09-04',
    summary: { spend: 9452, totalOrders: 1459, adOrders: 921, organic: 538, cpo: 6.48, organicShare: 36.9, maturity: 86 },
    products: [
      {
        code: 'W8K2-', cpo: 4.40, roas: 4.86, tacos: 11.8, maturity: 100, spend: 2659.73, totalOrders: 605, adOrders: 382, adTypeSpend:{SP:1669.30,SB:940.31,SD:0,STV:50.12},
        daily: [
          {period:'9/04',spend:401.32,adOrders:58,totalOrders:91,organic:33,cpo:4.41,maturity:42,status:'归因中',change:null,yoy:null},
          {period:'9/03',spend:388.70,adOrders:61,totalOrders:94,organic:33,cpo:4.14,maturity:68,status:'归因中',change:null,yoy:null},
          {period:'9/02',spend:396.51,adOrders:63,totalOrders:97,organic:34,cpo:4.09,maturity:82,status:'归因中',change:null,yoy:null},
          {period:'9/01',spend:372.80,adOrders:57,totalOrders:89,organic:32,cpo:4.19,maturity:100,status:'已成熟',change:-4.8,yoy:6.1},
          {period:'8/31',spend:350.10,adOrders:55,totalOrders:80,organic:25,cpo:4.38,maturity:100,status:'已成熟',change:3.2,yoy:4.7},
        ],
        weekly: [
          {period:'8/24–8/30',spend:2388.4,adOrders:341,totalOrders:570,organic:229,cpo:4.19,maturity:100,status:'已成熟',change:-8.2,yoy:5.6},
          {period:'8/31–9/06',spend:1910.2,adOrders:294,totalOrders:451,organic:157,cpo:4.24,maturity:73,status:'归因中',change:null,yoy:null},
        ],
      },
      {
        code: 'W81', cpo: 5.62, roas: 4.21, tacos: 13.6, maturity: 100, spend: 1586.17, totalOrders: 282, adOrders: 201, adTypeSpend:{SP:1124.40,SB:356.77,SD:76.00,STV:28.99},
        daily: [
          {period:'9/04',spend:236.2,adOrders:28,totalOrders:43,organic:15,cpo:5.49,maturity:40,status:'归因中',change:null,yoy:null},
          {period:'9/03',spend:245.7,adOrders:30,totalOrders:45,organic:15,cpo:5.46,maturity:65,status:'归因中',change:null,yoy:null},
          {period:'9/02',spend:251.4,adOrders:31,totalOrders:46,organic:15,cpo:5.47,maturity:81,status:'归因中',change:null,yoy:null},
          {period:'9/01',spend:284.6,adOrders:36,totalOrders:49,organic:13,cpo:5.81,maturity:100,status:'已成熟',change:-3.4,yoy:3.3},
        ],
        weekly: [
          {period:'8/24–8/30',spend:1490.4,adOrders:186,totalOrders:264,organic:78,cpo:5.65,maturity:100,status:'已成熟',change:-2.7,yoy:4.1},
          {period:'8/31–9/06',spend:1017.9,adOrders:125,totalOrders:183,organic:58,cpo:5.56,maturity:70,status:'归因中',change:null,yoy:null},
        ],
      },
      {
        code: 'W63', cpo: 9.75, roas: 2.94, tacos: 18.7, maturity: 78, spend: 516.68, totalOrders: 53, adOrders: 41, adTypeSpend:{SP:402.10,SB:82.58,SD:32.00,STV:0},
        daily: [
          {period:'9/04',spend:91.4,adOrders:6,totalOrders:8,organic:2,cpo:11.43,maturity:38,status:'归因中',change:null,yoy:null},
          {period:'9/03',spend:84.7,adOrders:7,totalOrders:9,organic:2,cpo:9.41,maturity:62,status:'归因中',change:null,yoy:null},
          {period:'9/02',spend:79.1,adOrders:6,totalOrders:8,organic:2,cpo:9.89,maturity:78,status:'归因中',change:null,yoy:null},
          {period:'9/01',spend:76.0,adOrders:5,totalOrders:8,organic:3,cpo:9.50,maturity:100,status:'已成熟',change:7.3,yoy:11.8},
        ],
        weekly: [
          {period:'8/24–8/30',spend:522.2,adOrders:43,totalOrders:58,organic:15,cpo:9.00,maturity:100,status:'已成熟',change:6.1,yoy:9.4},
          {period:'8/31–9/06',spend:331.2,adOrders:24,totalOrders:33,organic:9,cpo:10.04,maturity:68,status:'归因中',change:null,yoy:null},
        ],
      },
      { code:'W51', cpo:6.21, roas:3.88, tacos:14.2, maturity:91, spend:1120.4, totalOrders:180, adOrders:124, adTypeSpend:{SP:770.2,SB:252.4,SD:72.8,STV:25.0}, ...emptyRows },
      { code:'W75V2', cpo:7.08, roas:3.44, tacos:15.6, maturity:84, spend:984.2, totalOrders:139, adOrders:92, adTypeSpend:{SP:638.1,SB:255.6,SD:70.5,STV:20.0}, ...emptyRows },
      { code:'W85', cpo:5.91, roas:4.12, tacos:13.1, maturity:100, spend:792.8, totalOrders:134, adOrders:87, adTypeSpend:{SP:545.0,SB:182.8,SD:65.0,STV:0}, ...emptyRows },
    ],
  },
  XH: {
    operator:'XH', account:'川鹏', range:'2026-08-29 ~ 2026-09-04',
    summary:{spend:8920,totalOrders:1612,adOrders:1010,organic:602,cpo:5.53,organicShare:37.3,maturity:92},
    products:[
      {code:'W8K6',cpo:5.12,roas:4.63,tacos:12.4,maturity:100,spend:2410,totalOrders:471,adOrders:300,adTypeSpend:{SP:1680,SB:530,SD:150,STV:50},...emptyRows},
      {code:'W882',cpo:5.47,roas:4.35,tacos:12.9,maturity:100,spend:1980,totalOrders:362,adOrders:228,adTypeSpend:{SP:1400,SB:430,SD:120,STV:30},...emptyRows},
      {code:'W51',cpo:6.02,roas:3.97,tacos:14.0,maturity:88,spend:1220,totalOrders:203,adOrders:141,adTypeSpend:{SP:830,SB:270,SD:90,STV:30},...emptyRows},
    ],
  },
  XM: {
    operator:'XM', account:'川鹏', range:'2026-08-29 ~ 2026-09-04',
    summary:{spend:7810,totalOrders:1386,adOrders:910,organic:476,cpo:5.64,organicShare:34.3,maturity:71},
    products:[
      {code:'Y10',cpo:5.31,roas:4.51,tacos:12.7,maturity:73,spend:2110,totalOrders:397,adOrders:261,adTypeSpend:{SP:1460,SB:420,SD:180,STV:50},...emptyRows},
      {code:'V202',cpo:6.18,roas:3.83,tacos:14.8,maturity:69,spend:1870,totalOrders:303,adOrders:196,adTypeSpend:{SP:1210,SB:460,SD:150,STV:50},...emptyRows},
      {code:'S75',cpo:5.89,roas:4.02,tacos:13.9,maturity:71,spend:990,totalOrders:168,adOrders:110,adTypeSpend:{SP:700,SB:190,SD:80,STV:20},...emptyRows},
    ],
  },
}
