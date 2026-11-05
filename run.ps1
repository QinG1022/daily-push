# 每日推送 —— 启动器
# 用法：双击「运行.cmd」，或在 CMD 里执行  运行.cmd 预览

# 控制台统一用 UTF-8，否则 emoji 和中文会乱码
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

Set-Location -LiteralPath $PSScriptRoot

# --------------------------------------------------------------------------- #
# 找 Python：跳过 Windows 商店那个 0 字节占位符
# --------------------------------------------------------------------------- #
function Find-Python {
    $script:SawStub = $false
    $candidates = New-Object System.Collections.ArrayList

    foreach ($name in @('py', 'python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd -and $cmd.Source) { [void]$candidates.Add($cmd.Source) }
    }
    foreach ($pattern in @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe'),
            (Join-Path $env:ProgramFiles 'Python3*\python.exe'),
            'C:\Python3*\python.exe')) {
        Get-ChildItem $pattern -ErrorAction SilentlyContinue |
            ForEach-Object { [void]$candidates.Add($_.FullName) }
    }
    # 这台机器上 DSH 自带的那份 Python
    [void]$candidates.Add('C:\Users\14426\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe')

    $seen = @{}
    foreach ($exe in $candidates) {
        if (-not $exe -or $seen.ContainsKey($exe)) { continue }
        $seen[$exe] = $true
        if (-not (Test-Path -LiteralPath $exe)) { continue }
        try {
            if ((Get-Item -LiteralPath $exe).Length -eq 0) { $script:SawStub = $true; continue }
            $out = & $exe --version 2>&1
            if ($LASTEXITCODE -eq 0 -and ("$out" -match 'Python\s+3')) {
                return [pscustomobject]@{ Exe = $exe; Version = "$out".Trim() }
            }
        } catch { }
    }
    return $null
}

$script:SawStub = $false
$python = Find-Python
if (-not $python) {
    Write-Host ''
    Write-Host '  [X] 没找到可用的 Python 3。' -ForegroundColor Red
    if ($script:SawStub) { Write-Host '      系统里的 python 命令是 Windows 商店的占位符（0 字节），不能用。' -ForegroundColor Yellow }
    Write-Host ''
    Write-Host '  装一个就行：在 CMD 里执行' -ForegroundColor Gray
    Write-Host '      winget install Python.Python.3.12' -ForegroundColor White
    Write-Host '  装完关掉这个窗口重开，再双击「运行.cmd」。' -ForegroundColor Gray
    Write-Host ''
    Read-Host '按回车关闭'
    exit 1
}

Write-Host ''
Write-Host ("  使用 {0}" -f $python.Version) -ForegroundColor DarkGray
Write-Host ("  {0}" -f $python.Exe) -ForegroundColor DarkGray
if ($script:SawStub) {
    Write-Host '  （已自动跳过系统里那个用不了的 python 占位符）' -ForegroundColor DarkGray
}
Write-Host ''

# --------------------------------------------------------------------------- #
# 参数 / 菜单
# --------------------------------------------------------------------------- #
$pyArgs = @($args)

# 支持中文快捷参数
if ($pyArgs.Count -gt 0) {
    switch ("$($pyArgs[0])".Trim()) {
        '预览' { $pyArgs = @('--dry-run') }
        '测试' { $pyArgs = @('--test') }
        '发送' { $pyArgs = @('--show') }
    }
}

$interactive = ($pyArgs.Count -eq 0)

if ($interactive) {
    Write-Host '  ┌─────────────────────────────────────┐' -ForegroundColor Cyan
    Write-Host '  │  1. 预览  只看内容，不发送（安全）  │' -ForegroundColor Cyan
    Write-Host '  │  2. 测试  发一条测试消息            │' -ForegroundColor Cyan
    Write-Host '  │  3. 发送  抓取并正式推送            │' -ForegroundColor Cyan
    Write-Host '  │  4. 退出                            │' -ForegroundColor Cyan
    Write-Host '  └─────────────────────────────────────┘' -ForegroundColor Cyan
    $choice = Read-Host '  选择 [1]'
    switch ($choice.Trim()) {
        '2' { $pyArgs = @('--test') }
        '3' { $pyArgs = @('--show') }
        '4' { exit 0 }
        default { $pyArgs = @('--dry-run') }
    }
    Write-Host ''
}

# --------------------------------------------------------------------------- #
# 跑起来（每次结果都追加到 out\run.log，方便事后查有没有发成功）
# --------------------------------------------------------------------------- #
$logDir = Join-Path $PSScriptRoot 'out'
if (-not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
$logFile = Join-Path $logDir 'run.log'
$label = if ($pyArgs.Count -gt 0) { $pyArgs -join ' ' } else { 'menu' }

$body = & $python.Exe 'main.py' @pyArgs 2>&1 | Out-String
$code = $LASTEXITCODE
Write-Host $body

try {
    $header = "`n===== {0} | {1} | exit={2} =====" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $label, $code
    $header + "`n" + $body | Out-File -LiteralPath $logFile -Append -Encoding utf8
} catch { }

if ($interactive) {
    Write-Host ''
    if ($code -eq 0) {
        Write-Host '  完成。' -ForegroundColor Green
    } else {
        Write-Host ("  出错了，退出码 {0}，把上面的内容发给我。" -f $code) -ForegroundColor Red
    }
    Read-Host '按回车关闭'
}
exit $code
