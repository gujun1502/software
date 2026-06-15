# 每日商机雷达（OutBuildingDecision）

面向建筑/室内设计企业的**招投标商机自动筛选工具**。每天自动从邮箱拉取采招网等来源的项目信息邮件，结合公司资质与历史业绩打分，判断「能不能投 / 值不值得投」，并生成日报、可选推送到微信。

## 功能

- 📬 **自动收邮件**：通过 IMAP 拉取收件箱里采招网定制邮件（`fetch_email.py`）
- 🧩 **解析项目**：从邮件 HTML 中提取项目信息（`parse_email.py`）
- 🎯 **决策打分**：依据公司资质、近三年业绩、规模、价格等维度打分（`decision_engine.py`）
- 📊 **生成日报**：输出 Markdown / HTML / PDF 商机雷达日报（`run_radar.py` + `scripts/md_to_pdf_edge.py`）
- 📱 **微信推送**：可选通过 pushplus / Server酱 推送重点商机摘要（`push_wechat.py`）
- ⏰ **每日任务**：一键串起全流程（`daily_job.py`、`run_radar.py`）

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

> Windows 用户可直接双击 `每日商机雷达.bat`；macOS 见 `install_mac.command` 与 `安装说明.md`。

## 安全说明

以下文件包含**个人密钥与真实业务数据**，已通过 `.gitignore` 排除，不会上传：

```
email_config.json      # 邮箱授权码
push_config.json       # 推送 token
company_profile.json   # 公司资质 / 业绩
inbox/ reports/ data/  # 真实邮件、日报与运行数据
```

仓库内仅提供 `*.example.json` 模板，请在本地复制后填写。

## 目录结构

```
fetch_email.py            收邮件
parse_email.py            解析项目
decision_engine.py        决策打分引擎
run_radar.py              主流程：收→解析→打分→出日报
daily_job.py              每日任务封装
push_wechat.py            微信推送
scripts/md_to_pdf_edge.py Markdown 转 PDF
*.example.json            配置模板
安装说明.md                安装与使用说明
```
