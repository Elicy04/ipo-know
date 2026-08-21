# =============================================================================
# build.ps1 — IPO Know 一键打包脚本（PyInstaller onefile）
#
# 用途:
#   基于已固化的 ipo-know.spec 构建单文件产物 dist\ipo-know.exe。
#   spec 中已包含全部收集参数（nicegui 包目录、ui/assets、sse/api YAML、
#   collect-submodules nicegui、collect-all webview/pythonnet、
#   hidden-import clr_loader、spider.ico 图标），无需在命令行重复传参。
#
# 用法:
#   .\build.ps1           增量构建（利用 PyInstaller 缓存，重建很快）
#   .\build.ps1 -Clean    构建前删除 build/ 缓存目录，强制全新构建
#
# 说明:
#   - 可从任意目录调用（内部使用 $PSScriptRoot 定位项目根）
#   - 构建失败时以非零退出码结束
# =============================================================================

[CmdletBinding()]
param(
    # 构建前删除 build/ 缓存目录，强制全新构建
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

$PythonExe   = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$SpecFile    = Join-Path $ProjectRoot 'ipo-know.spec'
$EntryFile   = Join-Path $ProjectRoot 'pack_main.py'
$BuildDir    = Join-Path $ProjectRoot 'build'
$Artifact    = Join-Path $ProjectRoot 'dist\ipo-know.exe'

# onefile 产物预期下限（MB），低于该值视为构建异常
$MinArtifactSizeMB = 20

Write-Host ''
Write-Host '===== IPO Know 一键打包 =====' -ForegroundColor Cyan
Write-Host "项目根目录: $ProjectRoot"

# -----------------------------------------------------------------------------
# 前置检查
# -----------------------------------------------------------------------------
Write-Host ''
Write-Host '[1/4] 前置检查...' -ForegroundColor Cyan

# 1. 虚拟环境
if (-not (Test-Path $PythonExe)) {
    Write-Host "错误: 未找到虚拟环境 Python: $PythonExe" -ForegroundColor Red
    Write-Host '请先创建虚拟环境并安装依赖，例如: uv sync' -ForegroundColor Yellow
    exit 1
}
Write-Host "  虚拟环境: OK ($PythonExe)"

# 2. PyInstaller 是否已安装
$PyInstallerVersion = & $PythonExe -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0 -or -not $PyInstallerVersion) {
    Write-Host '错误: 虚拟环境中未安装 PyInstaller' -ForegroundColor Red
    Write-Host '请先执行: uv pip install pyinstaller' -ForegroundColor Yellow
    exit 1
}
Write-Host "  PyInstaller: OK (v$PyInstallerVersion)"

# 3. spec 文件
if (-not (Test-Path $SpecFile)) {
    Write-Host "错误: 未找到 spec 文件: $SpecFile" -ForegroundColor Red
    exit 1
}
Write-Host "  spec 文件: OK ($SpecFile)"

# 4. 入口文件
if (-not (Test-Path $EntryFile)) {
    Write-Host "错误: 未找到入口文件: $EntryFile" -ForegroundColor Red
    exit 1
}
Write-Host "  入口文件: OK ($EntryFile)"

# -----------------------------------------------------------------------------
# 可选: 清理构建缓存
# -----------------------------------------------------------------------------
if ($Clean) {
    Write-Host ''
    Write-Host '[2/4] 清理构建缓存 (-Clean)...' -ForegroundColor Cyan
    if (Test-Path $BuildDir) {
        Remove-Item -Recurse -Force $BuildDir
        Write-Host "  已删除: $BuildDir"
    } else {
        Write-Host '  build/ 目录不存在，无需清理'
    }
} else {
    Write-Host ''
    Write-Host '[2/4] 增量构建模式（保留 build/ 缓存）' -ForegroundColor Cyan
}

# -----------------------------------------------------------------------------
# 执行构建
# -----------------------------------------------------------------------------
Write-Host ''
Write-Host '[3/4] 执行 PyInstaller 构建...' -ForegroundColor Cyan
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

# 使用 .NET Process 同步等待子进程结束并统一 UTF-8 输出，
# 避免 PowerShell 管道异步刷新导致的乱码与产物检查时序问题
$ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
$ProcessInfo.FileName = $PythonExe
$ProcessInfo.Arguments = "-m PyInstaller `"$SpecFile`" --noconfirm"
$ProcessInfo.WorkingDirectory = $ProjectRoot
$ProcessInfo.UseShellExecute = $false
$ProcessInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$ProcessInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8
$ProcessInfo.RedirectStandardOutput = $true
$ProcessInfo.RedirectStandardError = $true
$ProcessInfo.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'

$BuildProcess = [System.Diagnostics.Process]::Start($ProcessInfo)
$StdoutTask = $BuildProcess.StandardOutput.ReadToEndAsync()
$StderrTask = $BuildProcess.StandardError.ReadToEndAsync()
$BuildProcess.WaitForExit()

$Stopwatch.Stop()
$Elapsed = '{0:mm\:ss}' -f $Stopwatch.Elapsed

$BuildOutput = $StdoutTask.Result
if ($StderrTask.Result) {
    $BuildOutput = $BuildOutput + [Environment]::NewLine + $StderrTask.Result
}

if ($BuildProcess.ExitCode -ne 0) {
    Write-Host $BuildOutput
    Write-Host ''
    Write-Host "构建失败（PyInstaller 退出码: $($BuildProcess.ExitCode)，耗时 $Elapsed）" -ForegroundColor Red
    exit 1
}

Write-Host $BuildOutput
Write-Host "  PyInstaller 执行完成，耗时 $Elapsed"

# -----------------------------------------------------------------------------
# 检查产物
# -----------------------------------------------------------------------------
Write-Host ''
Write-Host '[4/4] 检查产物...' -ForegroundColor Cyan

if (-not (Test-Path $Artifact)) {
    Write-Host "错误: 未找到产物文件: $Artifact" -ForegroundColor Red
    exit 1
}

$ArtifactItem = Get-Item $Artifact
$SizeMB = [math]::Round($ArtifactItem.Length / 1MB, 1)

# 校验产物更新时间（应为本次构建刚刚写入）与体积下限，
# 防止误报旧的或不完整的产物为构建成功
$AgeSeconds = ((Get-Date) - $ArtifactItem.LastWriteTime).TotalSeconds
if ($AgeSeconds -gt 600) {
    Write-Host "错误: 产物文件未更新（最后修改时间: $($ArtifactItem.LastWriteTime)），构建可能未实际执行" -ForegroundColor Red
    exit 1
}
if ($SizeMB -lt $MinArtifactSizeMB) {
    Write-Host "错误: 产物体积异常（$SizeMB MB，预期 >= $MinArtifactSizeMB MB），构建可能不完整" -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '==============================================' -ForegroundColor Green
Write-Host ' 构建成功!' -ForegroundColor Green
Write-Host " 产物: $Artifact" -ForegroundColor Green
Write-Host " 体积: $SizeMB MB" -ForegroundColor Green
Write-Host " 更新时间: $($ArtifactItem.LastWriteTime)" -ForegroundColor Green
Write-Host " 耗时: $Elapsed" -ForegroundColor Green
Write-Host '==============================================' -ForegroundColor Green
exit 0

