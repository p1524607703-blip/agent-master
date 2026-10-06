'use strict';
const fs = require('fs');
const path = require('path');

// 配置加载：优先级 = 环境变量 > config.json > 默认值
// 注意：本脚本只做只读提取，不含任何店铺凭据。
module.exports = function requireConfig() {
  const cfgPath = path.join(__dirname, 'config.json');
  let fileCfg = {};
  if (fs.existsSync(cfgPath)) {
    try { fileCfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8')); } catch (e) { /* ignore */ }
  }
  const e = process.env;
  const cfg = {
    storeId: e.PROMO_STORE_ID || fileCfg.storeId || '27661378824000',
    storeName: e.PROMO_STORE_NAME || fileCfg.storeName || '川鹏2号',
    cliPath: e.PROMO_CLI_PATH || fileCfg.cliPath || '/opt/homebrew/bin/ziniao-cli',
    mcid: e.PROMO_MCID || fileCfg.mcid || 'amzn1.merchant.d.AA4JMO27LSSIDRXDJKUFNHDF6SRA',
    mkid: e.PROMO_MKID || fileCfg.mkid || 'ATVPDKIKX0DER'
  };
  return cfg;
};
