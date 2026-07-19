# 商机雷达 · 工作日自动任务注册/取消脚本
# 计划：周一到周五 09:00 / 09:15 / 09:30 / 09:45 / 10:00 各跑一趟，周六、周日不运行
# 特性：允许电池供电时运行；到点没开机则开机后尽快补跑一次（StartWhenAvailable）
# 调用方式（由同目录 bat 启动器调用）：
#   安装每日任务.bat            → 注册并显示结果
#   安装每日任务.bat /auto      → 静默注册（安装包收尾自动调用）
#   取消每日任务.bat            → 全部取消（内部传 /remove）
$Auto   = $args -contains '/auto'
$Remove = $args -contains '/remove'
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $here 'daily_run.ps1'

$prefix = '商机雷达每日进化'
$slots  = '09:00','09:15','09:30','09:45','10:00'

# 先清掉旧版单一任务和已有的分时任务，避免重复注册
$old = @($prefix) + ($slots | ForEach-Object { "$prefix-" + ($_ -replace ':','') })
foreach ($name in $old) {
  try { Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop } catch {}
}

if ($Remove) {
  if (-not $Auto) { Write-Host "已取消全部「商机雷达」自动任务（含旧版）。" }
  exit 0
}

if (-not $Auto) {
  Write-Host "============================================================"
  Write-Host "  注册「商机雷达」工作日自动任务"
  Write-Host "  周一到周五：09:00 / 09:15 / 09:30 / 09:45 / 10:00 各跑一趟"
  Write-Host "  周六、周日不运行"
  Write-Host "============================================================"
  Write-Host ""
}

$days     = 'Monday','Tuesday','Wednesday','Thursday','Friday'
$action   = New-ScheduledTaskAction -Execute 'powershell.exe' `
              -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runner`"" `
              -WorkingDirectory $here
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$fail = 0
foreach ($t in $slots) {
  $n = $t -replace ':',''
  try {
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $t
    Register-ScheduledTask -TaskName "$prefix-$n" -Action $action -Trigger $trigger `
      -Settings $settings -Force -ErrorAction Stop | Out-Null
    if (-not $Auto) { Write-Host "  [OK] 工作日 $t 已注册" }
  } catch {
    $fail = 1
    if (-not $Auto) { Write-Host "  [失败] 工作日 $t 注册失败：$($_.Exception.Message)" }
  }
}

if (-not $Auto) {
  Write-Host ""
  if ($fail -eq 0) {
    Write-Host "✅ 全部注册成功！工作日到点自动跑（周六日不跑；到点没开机则开机后补跑）。"
    Write-Host "   查看任务：     schtasks /Query /TN `"$prefix-0900`""
    Write-Host "   立即试跑一次： schtasks /Run /TN `"$prefix-0900`""
    Write-Host "   全部取消：     双击本目录里的「取消每日任务.bat」"
    Write-Host "   运行日志在：   data\每日运行日志.txt"
  } else {
    Write-Host "❌ 有任务注册失败。请右键「安装每日任务.bat」→ 以管理员身份运行，再试一次。"
  }
  Write-Host ""
}
exit $fail
