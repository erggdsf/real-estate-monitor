# 房产监控 - Windows定时任务设置脚本
# 以管理员身份运行 PowerShell，然后执行此脚本

$TaskName = "RealEstateMonitor"
$ScriptPath = Join-Path $PSScriptRoot "main.py"
$PythonPath = "python"  # 如果python不在PATH中，请改为完整路径

# 创建触发器：每天上午9点执行
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00"

# 创建操作
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument $ScriptPath -WorkingDirectory $PSScriptRoot

# 创建设置
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# 注册任务（需要管理员权限）
Register-ScheduledTask -TaskName $TaskName -Trigger $Trigger -Action $Action -Settings $Settings -Force

Write-Host "定时任务已创建: $TaskName"
Write-Host "每天 09:00 自动执行"
Write-Host ""
Write-Host "查看任务: Get-ScheduledTask -TaskName $TaskName"
Write-Host "删除任务: Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false"
