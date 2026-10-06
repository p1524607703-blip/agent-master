#!/usr/bin/env node
/**
 * DSP 建单页（/dsp/.../orders/new）只读现场取证器。
 *
 * 用途：诊断「转化跟踪 → 商品 → 上传文件」相关故障（含 "Error while uploading ASINs"）。
 * 只读取，不点击、不上传、不提交、不改任何投放设置。
 *
 * 用法：
 *   node dsp_page_probe.js <storeId> [entityId] [advertiserId]
 * 例：
 *   node dsp_page_probe.js 27661378824000 ENTITY1F7KI15KHQ4NT 592097575016190071
 *
 * ⚠️ 需要目标标签页已经是建单页。ziniao-cli 不能切标签页；
 *    若 CLI 挂在别的标签上，先 `ziniao-cli page visit --store-id <id> --url <建单页URL>`
 *    （会导航 CLI 当前挂着的那个标签，不要对着用户正在填的标签跑）。
 *
 * 输出要点：
 *   - 站点（亚马逊域）复选框的勾选状态 —— 默认全不勾
 *   - 页面自带告警「选择一个或多个亚马逊站点」
 *   - 上传组件的内联 props（uploadAsinApiURL / getAssociationJobStatusUrl / noAsinMsg ...）
 *   - 是否已崩（body 文本过短 / 交易无 uploadUI）
 */
const { execFileSync } = require('child_process');

const storeId = process.argv[2];
const entityId = process.argv[3] || '';
const advertiserId = process.argv[4] || '';
if (!storeId) {
  console.error('用法: node dsp_page_probe.js <storeId> [entityId] [advertiserId]');
  process.exit(2);
}

function execjs(script) {
  const out = execFileSync('ziniao-cli', ['page', 'exec', '--store-id', storeId, '--script', script],
    { encoding: 'utf8', maxBuffer: 30 * 1024 * 1024 });
  const i = out.indexOf('{'), j = out.lastIndexOf('}');
  const p = JSON.parse(out.slice(i, j + 1));
  const r = p.data && p.data.data ? p.data.data.result : p;
  return typeof r === 'string' ? JSON.parse(r) : r;
}

const PROBE = `(() => {
  const out = {};
  const all = Array.from(document.querySelectorAll('*'));
  const T = (document.body.innerText || '').replace(/\\s+/g, ' ');
  out.url = location.href;
  out.title = document.title;
  out.bodyLen = T.length;

  // 站点（亚马逊域）复选框
  out.siteCheckboxes = Array.from(document.querySelectorAll('input[type=checkbox]'))
    .filter(c => /amazon|Prime|Fresh|Whole Foods/i.test(c.name || ''))
    .map(c => ({ name: c.name, val: c.value, checked: c.checked }));

  // 页面告警
  out.alerts = Array.from(new Set(all
    .filter(e => e.children.length === 0 && /选择一个或多个亚马逊站点|请验证 ASIN|要追踪超过/i.test(e.innerText || ''))
    .map(e => (e.innerText || '').trim())));

  // 上传组件内联 props
  const hit = Array.from(document.querySelectorAll('script'))
    .map(s => s.textContent || '').find(t => t.includes('uploadAsinApiURL'));
  if (hit) {
    const g = (k) => { const m = hit.match(new RegExp(k + '\\\\s*:\\\\s*"([^"]*)"')); return m ? m[1] : null; };
    out.uploaderProps = {
      uploadAsinApiURL: g('uploadAsinApiURL'),
      getAssociationJobStatusUrl: g('getAssociationJobStatusUrl'),
      getAsinCountUrl: g('getAsinCountUrl'),
      downloadTemplateLink: g('downloadTemplateLink'),
      noAsinMsg: g('noAsinMsg'),
    };
  }

  // 转化跟踪区块是否渲染
  out.hasUploadUI = /Drop \\.csv file to upload|上传文件|添加商品/.test(T);
  out.conversionSection = all.filter(e => e.children.length === 0 && /转化跟踪|添加商品|上传文件|复制并粘贴/.test(e.innerText || ''))
    .map(e => (e.innerText || '').trim()).filter((v, i, a) => a.indexOf(v) === i).slice(0, 10);

  // 崩溃迹象
  out.looksBroken = out.bodyLen < 1500 || !out.hasUploadUI;
  return JSON.stringify(out);
})()`;

console.log(JSON.stringify(execjs(PROBE), null, 2));
