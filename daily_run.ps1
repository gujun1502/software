# 商机雷达 · 每日自动运行实际执行脚本（由计划任务或 _每日自动运行.bat 调用）
# 优先用打包好的 商机雷达.exe；没有则用 python 跑源码。日志追加到 data\每日运行日志.txt
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
New-Item -ItemType Directory -Force data | Out-Null
$log = "data\每日运行日志.txt"

Add-Content -Path $log -Encoding UTF8 -Value "`r`n======== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 每日自动运行开始 ========"

if (Test-Path "商机雷达.exe") {
  $out = & ".\商机雷达.exe" auto 2>&1 | Out-String
} else {
  $out = & python radar_app.py auto 2>&1 | Out-String
}
$rc = $LASTEXITCODE

if ($out) { Add-Content -Path $log -Encoding UTF8 -Value $out }
Add-Content -Path $log -Encoding UTF8 -Value "======== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 结束（退出码 $rc） ========"
exit $rc
