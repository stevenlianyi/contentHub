# contentHub 表定义批量生成脚本 (Windows / PowerShell 等效写法)
#
# 用途: 对 database/ch_*.txt 逐表执行 mysqlCodeGenerator.py, 产出
#       database/auto_generated/auto_gen_code_ch_*.py 与 word_table_ch_*.csv
#
# ★★ 表名陷阱(务必保留本段说明) ★★
#   mysqlCodeGenerator.readFromFile() 用 fileName.split(".")[0] 取表名, 而产物目录
#   AUTO_GENERATE_OUTPUT_DIR="auto_generated" 是相对路径。若在 code/src 下执行
#   `-i database/ch_topic.txt`, 表名会变成 "database/ch_topic", 建表名与产物名全部错误。
#   因此本脚本必须先 Set-Location 到 database 目录, 再传裸文件名(-i ch_topic.txt)。
#   请勿改成带路径调用。
#
# 用法: powershell -File code/src/tools/genTableCode.ps1

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$srcDir    = Split-Path -Parent $scriptDir
$dbDir     = Join-Path $srcDir "database"
$py        = if ($env:PY) { $env:PY } else { "python" }

Set-Location $dbDir

$okCount   = 0
$failList  = @()
Get-ChildItem -Path (Join-Path $dbDir "ch_*.txt") | Sort-Object Name | ForEach-Object {
    $tableName = $_.BaseName                    # ch_topic
    # cmdTitle 必须与 config/basicSettings.py 的 _CRUD_TITLES 一致: 去 ch_ 前缀 + 去全部下划线
    # (否则会生成 funcAudit_logAdd 这类带下划线的处理器名, 与权限配置的 CMD 名对不上)
    $title     = ($tableName -replace "^ch_", "") -replace "_", "" # ch_audit_log -> auditlog
    Write-Host ("[gen] {0} -t {1}" -f $_.Name, $title)
    & $py "mysqlCodeGenerator.py" -i $_.Name -t $title
    if ($LASTEXITCODE -eq 0) { $okCount++ } else { $failList += $_.Name }
}

Write-Host ("[gen] done: ok={0}, fail={1}" -f $okCount, $failList.Count)
if ($failList.Count -gt 0) {
    Write-Host ("[gen] failed files: {0}" -f ($failList -join ", "))
    exit 1
}
