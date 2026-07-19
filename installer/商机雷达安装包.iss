; 商机雷达 Windows 安装包脚本（Inno Setup 6）
; 编译：ISCC.exe 商机雷达安装包.iss  → 输出 setup exe 到桌面
; 由 打包EXE.bat 先产出 dist\商机雷达.exe，再编译本脚本

#define MyAppName "商机雷达"
#define MyAppVersion "2026.07.19.1"
#define MyAppPublisher "上海同济建筑室内设计工程有限公司"
#define MyAppExeName "商机雷达.exe"
#define SrcRoot "C:\Users\Jun\OutBuildingDecision"
#define SrcPkg SrcRoot + "\商机雷达_公司安装包"

[Setup]
AppId={{7C4E9A31-5B8D-4F2E-9C6A-1D3B8E5F7A20}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\商机雷达
DefaultGroupName=商机雷达
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=C:\Users\Jun\Desktop
OutputBaseFilename=商机雷达安装包_v{#MyAppVersion}
SetupIconFile={#SrcRoot}\radar.ico
UninstallDisplayIcon={app}\radar.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式（双击即生成日报并打开）"; GroupDescription: "附加任务："

[Files]
; 主程序与图标
Source: "{#SrcRoot}\dist\商机雷达.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcRoot}\radar.ico"; DestDir: "{app}"; Flags: ignoreversion
; 操作入口 bat（自动按相对路径找 exe，可直接用）
Source: "{#SrcPkg}\1-生成日报.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcPkg}\2-更新数据并生成.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcPkg}\3-导出采招网Cookie.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcPkg}\4-导出上海平台Cookie.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcRoot}\_每日自动运行.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcRoot}\daily_run.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcRoot}\install_tasks.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcRoot}\安装每日任务.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcRoot}\取消每日任务.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcRoot}\安装本地大模型.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcPkg}\使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion
; 配置文件：首次安装写入，升级不覆盖用户已改内容，卸载保留
Source: "{#SrcRoot}\company_profile.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SrcRoot}\email_config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SrcRoot}\push_config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SrcRoot}\llm_config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SrcRoot}\keywords.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SrcRoot}\sources.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
; 初始数据：历史中标做决策参考；推送历史从空开始
Source: "{#SrcRoot}\data\历史中标.json"; DestDir: "{app}\data"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SrcPkg}\data\推送历史.json"; DestDir: "{app}\data"; Flags: onlyifdoesntexist uninsneveruninstall
; 打包当天的抓取数据快照：让新电脑装完第一次生成日报就有内容
; （7天时间窗会自动过滤过旧条目；装完勾选"立即全量刷新"可拿到最新数据）
Source: "{#SrcRoot}\data\*_projects.json"; DestDir: "{app}\data"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SrcRoot}\data\详情增强.json"; DestDir: "{app}\data"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SrcPkg}\inbox\把采招网邮件_html_放这里.txt"; DestDir: "{app}\inbox"; Flags: onlyifdoesntexist

[Dirs]
Name: "{app}\data"
Name: "{app}\inbox"
Name: "{app}\reports"

[Icons]
Name: "{autodesktop}\商机雷达"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\radar.ico"; Comment: "生成商机日报并打开"; Tasks: desktopicon
; 工具箱=直达安装文件夹（全量刷新/Cookie导出/注册每日任务等 bat 都在里面），
; 不依赖 Win11 开始菜单「所有应用」——不熟的人在开始菜单找不到快捷方式
Name: "{autodesktop}\商机雷达工具箱"; Filename: "{app}"; Comment: "更新数据、导出Cookie、注册每日任务、日报文件夹都在这里"; Tasks: desktopicon
Name: "{group}\商机雷达 - 生成日报"; Filename: "{app}\1-生成日报.bat"; WorkingDir: "{app}"; IconFilename: "{app}\radar.ico"
Name: "{group}\商机雷达 - 全量刷新并生成"; Filename: "{app}\2-更新数据并生成.bat"; WorkingDir: "{app}"; IconFilename: "{app}\radar.ico"
Name: "{group}\导出采招网Cookie"; Filename: "{app}\3-导出采招网Cookie.bat"; WorkingDir: "{app}"
Name: "{group}\导出上海平台Cookie"; Filename: "{app}\4-导出上海平台Cookie.bat"; WorkingDir: "{app}"
Name: "{group}\重新注册工作日自动任务"; Filename: "{app}\安装每日任务.bat"; WorkingDir: "{app}"
Name: "{group}\取消工作日自动任务"; Filename: "{app}\取消每日任务.bat"; WorkingDir: "{app}"
Name: "{group}\安装本地大模型(可选)"; Filename: "{app}\安装本地大模型.bat"; WorkingDir: "{app}"
Name: "{group}\日报文件夹"; Filename: "{app}\reports"
Name: "{group}\使用说明"; Filename: "{app}\使用说明.txt"

[Run]
; 安装时自动注册工作日计划任务：周一至周五 09:00/09:15/09:30/09:45/10:00 各一趟，周六日不跑
Filename: "{app}\安装每日任务.bat"; Parameters: "/auto"; StatusMsg: "正在注册工作日自动任务（周一至周五 9:00-10:00 五趟）..."; Flags: runhidden
Filename: "{app}\2-更新数据并生成.bat"; Description: "立即全量刷新并生成第一份日报（联网抓取，约几分钟）"; Flags: postinstall skipifsilent
Filename: "{app}\使用说明.txt"; Description: "查看使用说明"; Flags: postinstall shellexec skipifsilent

[UninstallRun]
Filename: "{app}\取消每日任务.bat"; Parameters: "/auto"; Flags: runhidden; RunOnceId: "RemoveRadarTasks"
