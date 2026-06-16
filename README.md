# 每日商机雷达（OutBuildingDecision）

面向建筑/室内设计企业的**招投标商机自动筛选工具**。每天自动从邮箱拉取采招网等来源的项目信息邮件，结合公司资质与历史业绩打分，判断「能不能投 / 值不值得投」，并生成日报、可选推送到微信。

## 功能

- 📬 **自动收邮件**：通过 IMAP 拉取收件箱里采招网定制邮件（`fetch_email.py`）
- 🧩 **解析项目**：从邮件 HTML 中提取项目信息（`parse_email.py`）
- 🎯 **决策打分**：依据公司资质、近三年业绩、规模、价格等维度打分（`decision_engine.py`）
- 📊 **生成日报**：输出 Markdown / HTML / PDF 商机雷达日报，每条带「设计面积 / 设计造价 / 关键词」（`run_radar.py` + `scripts/md_to_pdf_edge.py`）
- 🔎 **详情页增强**：抓商机详情页正文，提取面积/造价/关键词（`fetch_detail.py` + `enrich.py`），正则免费离线，可选挂国内大模型（DeepSeek 等，OpenAI 兼容）提取更准
- 📱 **微信推送**：可选通过 pushplus / Server酱 推送重点商机摘要（`push_wechat.py`）
- ⏰ **每日任务**：一键串起全流程（`daily_job.py`、`run_radar.py`）

## 面积 / 造价 怎么来的（重要）

邮件与公开站点**列表**只给到「标题」，真正的 **设计面积 / 控制价写在详情页里**。所以分两步：

1. **抓详情页补全**（在中国境内、**最好关掉 VPN 直连**时运行，不依赖 Claude/任何外网大模型）：

   ```bash
   python enrich.py                 # 抓可投商机详情页，正则提取面积/造价/关键词
   python enrich.py --include-results   # 连竞争情报(中标价)也抓
   python enrich.py --llm           # 额外挂国内大模型(需先配 llm_config.json)，提取更准
   ```

   结果写入 `data/详情增强.json`（按项目 id 索引，带缓存，重跑只补未成功的）。

2. **出日报**：`python run_radar.py` 自动优先用增强值，抓不到的退回标题识别，`—` 表示都没取到。

数据源可抓性：
- ✅ 江苏 `jsggzy` / 安徽 `ahtba` 公开静态页 —— 直接抓，已验证能拿到面积造价。
- ⚠️ 采招网 `*.bidcenter.com.cn`（银行/证券那些）—— SPA + **需登录**，要把浏览器登录后的 Cookie
  串存到 `bidcenter_cookies.txt`（已 gitignore）才有机会抓到。用下面的小助手生成：

  ```bash
  python export_cookies.py          # 自动从 Edge/Chrome 读取（请先【完全退出浏览器】，否则文件被独占锁住）
  python export_cookies.py --paste  # 兜底：手动粘贴 Cookie（最稳，浏览器开着也行，最新版 v20 加密只能走这条）
  python export_cookies.py --test   # 用现有 cookie 自检能否抓到采招网详情页
  ```

  > 自动模式靠本机 `cryptography`+`pywin32` 解密浏览器 cookie 库（无需额外安装），但**浏览器运行时会独占
  > 锁住 Cookies 文件**，需先退出浏览器；退不了或解不开就用 `--paste`（F12→Network→刷新→复制 Cookie 请求头）。
  > 注：采招网是纯前端渲染，即便带 cookie 也未必能抓到完整正文，这部分面积/造价可能仍需人工确认。

**接国内大模型**：把 `llm_config.example.json` 复制为 `llm_config.json`，填 `api_key`、`enabled: true`。
默认 DeepSeek（`deepseek-chat`）；换智谱 GLM / 通义千问只改 `base_url`/`model`（都走 OpenAI 兼容接口）。
国内直连，关 VPN 可用——正好和「关 VPN 抓详情页」同一档网络环境。

## 快速开始

1. 安装 Python 3 依赖（标准库为主，PDF 生成依赖系统 Edge / Chromium）。
2. 复制示例配置并填入你自己的信息：

   ```bash
   cp email_config.example.json    email_config.json
   cp push_config.example.json     push_config.json
   cp company_profile.example.json company_profile.json
   ```

   - `email_config.json`：邮箱 IMAP 授权码等
   - `push_config.json`：pushplus / Server酱 token（不推送可保持 `enabled: false`）
   - `company_profile.json`：公司资质与业绩库（决策打分的核心依据）

3. 运行：

   ```bash
   python run_radar.py
   ```

   生成的日报在 `reports/` 目录。

## 一键生成（双击即可，自动打开 PDF）

Windows 用户随时双击下面的图标就能出日报，生成完会**自动弹开 PDF**：

| 双击 | 作用 | 何时用 |
|---|---|---|
| **`一键生成日报.bat`** | 秒出：用现有邮件 + 已缓存的详情数据直接出报告 | 平时想马上看一眼，**随时点，不联网也行** |
| **`每日商机雷达.bat`** | 全量刷新：收邮件 → 抓详情页补面积/造价 → 出报告 | 想更新数据时（**最好关 VPN 国内直连**再点） |

> 想更顺手：右键 `一键生成日报.bat` →「发送到」→「桌面快捷方式」，就有个桌面按钮了；
> 也可把快捷方式拖到任务栏固定。macOS 见 `install_mac.command` 与 `安装说明.md`。
> 两个 .bat 都会调 `python run_radar.py --open`，`--open` 即生成后自动打开 PDF。

## 打包成「公司版免安装 EXE」分发到其他电脑

目标：拷到公司其他 Windows 电脑，**无需装 Python、不用开 VPN**，双击即生成日报。

1. 本机先装一次：`pip install pyinstaller`
2. 双击 **`打包EXE.bat`**（或运行里面的命令）→ 生成 `dist/商机雷达.exe`（约 40MB）。
3. 把 exe 连同 `company_profile.json`、`email_config.json`、`push_config.json`、`llm_config.json`、
   `data/`、`inbox/` 一起拷给对方（参考已打好的样例 **`商机雷达_公司安装包/`** 与
   **`商机雷达_公司安装包.zip`**）。
4. 对方机器上：双击 `商机雷达.exe`（或 `1-生成日报.bat`）即出日报；`2-更新数据并生成.bat`
   做全量刷新（建议关 VPN）；`3-导出采招网Cookie.bat` 导登录态。详见包内 `使用说明.txt`。

> 入口是 `radar_app.py`（子命令 report/update/enrich/cookies/email），`app_paths.py` 让 exe
> 把配置与产物放在 exe 旁边。大模型默认接 **MiniMax**（OpenAI 兼容，国内直连免 VPN）——
> 在 `llm_config.json` 填 `api_key` 即启用，没填则自动只用正则。

## 安全说明

以下文件包含**个人密钥与真实业务数据**，已通过 `.gitignore` 排除，不会上传：

```
email_config.json      # 邮箱授权码
push_config.json       # 推送 token
company_profile.json   # 公司资质 / 业绩
llm_config.json        # 国内大模型 API Key（DeepSeek 等）
bidcenter_cookies.txt  # 采招网登录 Cookie
inbox/ reports/ data/  # 真实邮件、日报与运行数据
```

仓库内仅提供 `*.example.json` 模板，请在本地复制后填写。

## 目录结构

```
radar_app.py              单一入口（供打包 exe；子命令 report/update/enrich/cookies/email）
app_paths.py              统一根目录（源码=脚本目录；exe=exe目录）
打包EXE.bat               一键用 PyInstaller 打包成 商机雷达.exe
fetch_email.py            收邮件
parse_email.py            解析项目
decision_engine.py        决策打分引擎
fetch_detail.py           抓商机详情页正文（公开站直连；采招网需Cookie）
export_cookies.py         采招网 Cookie 导出小助手（自动读浏览器 / 手动粘贴 / 自检）
extract.py                面积/造价/关键词提取（标题与详情页共用）
enrich.py                 详情页增强：抓正文→提取→写 data/详情增强.json（可选挂大模型）
run_radar.py              主流程：收→解析→打分→(读增强)→出日报
daily_job.py              每日任务封装
push_wechat.py            微信推送
scripts/md_to_pdf_edge.py Markdown 转 PDF
*.example.json            配置模板（含 llm_config.example.json）
安装说明.md                安装与使用说明
```
