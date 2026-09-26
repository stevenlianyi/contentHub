# contentHub 运维定时任务运行脚本 (Windows / PowerShell; 供「计划任务」调用) —— SP4c
#
# 用途: 一次性串联调用三个运维入口(cron / Windows 计划任务用):
#   1) schedule/archive.py       归档清理(★ 默认 dry-run; 真删须 -Execute 或设 CH_ARCHIVE_EXECUTE=1)
#   2) schedule/credentialCheck.py  凭据健康巡检(单次执行; 常驻请改用 --loop)
#   3) chmonitor/dailyCheck.py   每日巡检(七项指标 -> 报告落 code/data/monitor/)
#
# ★★ 安全红线: 默认 dry-run —— 不加 -Execute 时, 归档只打印「将删除/将导出」清单, 绝不真删。
#    真删必须显式传 -Execute(或设环境变量 CH_ARCHIVE_EXECUTE=1)。
#
# 用法:
#   powershell -File code/src/tools/runOpsJobs.ps1                # 归档 dry-run + 巡检 + 每日巡检
#   powershell -File code/src/tools/runOpsJobs.ps1 -Execute       # ★ 归档真删(需确认)
#   powershell -File code/src/tools/runOpsJobs.ps1 -SkipArchive   # 只跑巡检 + 每日巡检

param(
    [switch]$Execute,
    [switch]$SkipArchive,
    [switch]$SkipCredentialCheck,
    [switch]$SkipDailyCheck
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$srcDir    = Split-Path -Parent $scriptDir
$py        = if ($env:PY) { $env:PY } else { "python" }

Set-Location $srcDir

$failCount = 0

if (-not $SkipArchive) {
    if ($Execute) {
        Write-Host "[ops] archive (★ 真删, 已显式确认)"
        & $py "schedule/archive.py" --execute
    } else {
        Write-Host "[ops] archive (dry-run 默认, 只打印清单)"
        & $py "schedule/archive.py"
    }
    if ($LASTEXITCODE -ne 0) { $failCount++ }
}

if (-not $SkipCredentialCheck) {
    Write-Host "[ops] credentialCheck (单次执行)"
    & $py "schedule/credentialCheck.py"
    if ($LASTEXITCODE -ne 0) { $failCount++ }
}

if (-not $SkipDailyCheck) {
    Write-Host "[ops] dailyCheck (每日巡检)"
    & $py "chmonitor/dailyCheck.py"
    if ($LASTEXITCODE -ne 0) { $failCount++ }
}

Write-Host ("[ops] done: fail={0}" -f $failCount)
if ($failCount -gt 0) { exit 1 }
