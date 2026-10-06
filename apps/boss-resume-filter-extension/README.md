# Boss Resume Filter

一个 Chrome MV3 插件，用于在 Boss 直聘页面上根据岗位相关条件辅助筛查当前可见简历。第一版完全在本地浏览器运行，不上传简历，不调用外部接口。

## 功能

- 在插件弹窗中配置职位方向、工作年限、学历要求和推荐阈值。
- 在 Boss 直聘页面中为疑似简历卡片打分、标记推荐/复核/较低/排除。
- 右下角浮层支持重新筛查、只看推荐、导出 CSV、清除标记。
- 对年龄、性别、婚育等疑似敏感筛选条件给出合规提示。

## 安装插件

### 方式 A：开发者模式加载目录，最稳

1. 打开 Chrome：`chrome://extensions/`
2. 打开右上角“开发者模式”
3. 点击“加载已解压的扩展程序”
4. 选择本插件目录：

当前 macOS 路径：

- `/Users/panjinlong/Documents/agent-master/apps/boss-resume-filter-extension`

Windows 示例路径：

- `C:\path\to\agent-master\apps\boss-resume-filter-extension`

Linux 示例路径：

- `/path/to/agent-master/apps/boss-resume-filter-extension`

### 方式 B：打包后拖入 Chrome，适合快速试用

生成安装包：

```bash
cd /Users/panjinlong/Documents/agent-master/apps/boss-resume-filter-extension
npm install
npm run package
```

Windows PowerShell：

```powershell
cd C:\path\to\agent-master\apps\boss-resume-filter-extension
npm install
npm run package
```

生成文件：

- `dist/boss-resume-filter-extension-unpacked`：干净的可加载目录
- `dist/boss-resume-filter-extension.zip`：可上传 Chrome Web Store 的压缩包
- `dist/boss-resume-filter-extension.crx`：可拖到 `chrome://extensions` 尝试安装的 CRX
- `dist/boss-resume-filter-extension.pem`：CRX 签名私钥，保留在本机，不要公开分享

> [!warning]
> Chrome 对商店外 CRX 有平台限制。Google 官方文档说明，Windows 从 Chrome 33 起、macOS 从 Chrome 44 起不再允许从本地 CRX 路径做外部安装；Linux 可以通过本地 CRX/偏好文件安装。也就是说，`.crx` 拖入法不保证在所有 Windows/macOS 正式版 Chrome 上可用。

### 方式 C：真正的一键分发

如果要给公司人事团队长期使用，推荐两条路：

- **Chrome Web Store 非公开发布**：把 `dist/boss-resume-filter-extension.zip` 上传到 Chrome Web Store，设置为非公开/指定用户可见。用户打开链接即可安装。
- **企业策略/GPO/MDM 分发**：适合公司统一管控电脑。Windows/macOS 上更建议配合 Chrome Web Store 托管扩展和企业策略安装。

### Windows 注意事项

- 推荐在 Windows 原生 PowerShell / CMD 中运行测试，不要在 WSL 里直接调用 Windows Chrome。
- 如果没有 Chrome，可以先安装 Chrome，再加载插件目录：

```powershell
winget install --id Google.Chrome -e
```

- 如果公司电脑禁用了 `winget`，也可以从 Chrome 官网下载安装，然后在 `chrome://extensions/` 里加载插件目录。

## 使用

1. 登录并打开 Boss 直聘的简历列表或简历详情页。
2. 点击浏览器工具栏里的 `Boss Resume Filter`。
3. 填写岗位相关筛选条件。
4. 点击“保存并筛查”。
5. 在页面右下角查看统计，必要时导出 CSV。

默认岗位画像为：职位方向 `鞋类供应链开发`、工作年限 `5年以上`、学历要求 `大专及以上`。
年龄范围只作为人工备注展示，不参与自动筛查、打分或隐藏。

## 合规边界

- 仅用于辅助人事复核，不应作为自动录用或淘汰决定。
- 条件应与岗位职责直接相关，例如技能、项目经验、平台经验、证书、工作地点等。
- 不要使用年龄、性别、婚育、民族、户籍、宗教、照片/外貌等敏感或受保护属性。
- 使用前请确认符合 Boss 直聘平台规则、公司招聘制度和适用的个人信息保护要求。
- 插件只处理当前页面可见内容，不绕过登录、权限、分页限制，也不批量抓取。

## 调试

先安装 Node 依赖：

macOS / Linux：

```bash
cd /Users/panjinlong/Documents/agent-master/apps/boss-resume-filter-extension
npm install
```

Windows PowerShell：

```powershell
cd C:\path\to\agent-master\apps\boss-resume-filter-extension
npm install
```

运行规则测试：

```bash
npm test
```

运行真实 Chrome 加载扩展的烟测：

```bash
npm run test:e2e
```

运行完整测试：

```bash
npm run test:all
```

如果测试机器没有 Chrome，先运行：

```bash
npm run setup:browsers
```

烟测会按这个顺序寻找浏览器：

1. `CHROME_EXECUTABLE_PATH` 指定的路径
2. Playwright 下载的 Chromium / Chrome for Testing
3. 当前系统的常见 Chrome/Chromium 安装路径

Windows PowerShell 指定浏览器路径示例：

```powershell
$env:CHROME_EXECUTABLE_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
npm run test:e2e
```

macOS / Linux 指定浏览器路径示例：

```bash
CHROME_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" npm run test:e2e
```

如果 Boss 页面结构变化导致识别不到卡片，优先调整 [src/content.js](/Users/panjinlong/Documents/agent-master/apps/boss-resume-filter-extension/src/content.js) 里的 `CANDIDATE_SELECTORS` 和 `MARKER_WORDS`。
