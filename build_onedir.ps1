# =============================================================================
# build_onedir.ps1 — IPO Know 一键打包脚本（PyInstaller onedir）
#
# 用途:
#   构建 onedir 目录式产物 dist\ipo-know-crawler\（主 exe + 运行时 DLL/依赖）。
#   收集参数与 onefile 链路（ipo-know.spec）完全相同，仅打包模式不同。
#
# spec 策略:
#   - 使用独立的 ipo-know-crawler.spec，避免与 onefile 的 ipo-know.spec 冲突
#     （PyInstaller 命令行构建会重写同名 spec）。
#   - spec 不存在时，脚本用完整 CLI 参数首次构建并自动生成该 spec；
#     之后一律基于 spec 构建（与 build.ps1 同模式）。
#
# 用法:
#   .\build_onedir.ps1           增量构建（利用 PyInstaller 缓存，重建很快）
#   .\build_onedir.ps1 -Clean    构建前删除 build\ipo-know-crawler 缓存目录
#
# 说明:
#   - 可从任意目录调用（内部使用 $PSScriptRoot 定位项目根）
#   - 构建失败时以非零退出码结束
#   - onedir 产物必须整个 dist\ipo-know-crawler 目录一起分发，不可只复制 exe
# =============================================================================

[CmdletBinding()]
param(
    # 构建前删除 build\ipo-know-crawler 缓存目录，强制全新构建
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

$PythonExe     = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$SpecFile      = Join-Path $ProjectRoot 'ipo-know-crawler.spec'
$EntryFile     = Join-Path $ProjectRoot 'pack_main.py'
$BuildCacheDir = Join-Path $ProjectRoot 'build\ipo-know-crawler'
$DistDir       = Join-Path $ProjectRoot 'dist\ipo-know-crawler'
$Artifact      = Join-Path $DistDir 'ipo-know-crawler.exe'

# onedir 产物目录预期下限（MB），低于该值视为构建不完整
$MinDirSizeMB = 50

# 首次生成 spec 用的完整 CLI 参数（与 onefile 历史命令一致，仅模式为 --onedir）
$FirstBuildArgs = '-m PyInstaller --name ipo-know-crawler --windowed --onedir --noconfirm' `
    + ' --add-data ".venv\Lib\site-packages\nicegui;nicegui" --collect-submodules nicegui' `
    + ' --collect-all webview --collect-all pythonnet --hidden-import clr_loader' `
    + ' --add-data "src\ipo_know\ui\assets;ipo_know\ui\assets"' `
    + ' --add-data "src\ipo_know\clients\sse\api;ipo_know\clients\sse\api"' `
    + ' --icon "src\ipo_know\ui\assets\spider.ico" pack_main.py'

Write-Host ''
Write-Host '===== IPO Know 一键打包（onedir）=====' -ForegroundColor Cyan
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

# 3. spec 文件（允许缺失：缺失时进入首次生成流程）
$SpecExists = Test-Path $SpecFile
if ($SpecExists) {
    Write-Host "  spec 文件: OK ($SpecFile)"
} else {
    Write-Host "  spec 文件: 不存在，本次将用完整 CLI 参数首次构建并生成 $SpecFile" -ForegroundColor Yellow
}

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
    if (Test-Path $BuildCacheDir) {
        Remove-Item -Recurse -Force $BuildCacheDir
        Write-Host "  已删除: $BuildCacheDir"
    } else {
        Write-Host '  build\ipo-know-crawler 目录不存在，无需清理'
    }
} else {
    Write-Host ''
    Write-Host '[2/4] 增量构建模式（保留 build\ipo-know-crawler 缓存）' -ForegroundColor Cyan
}

# -----------------------------------------------------------------------------
# 执行构建
# -----------------------------------------------------------------------------
Write-Host ''
Write-Host '[3/4] 执行 PyInstaller 构建...' -ForegroundColor Cyan

if ($SpecExists) {
    $BuildArgs = "-m PyInstaller `"$SpecFile`" --noconfirm"
    Write-Host "  构建模式: 基于 spec ($SpecFile)"
} else {
    $BuildArgs = $FirstBuildArgs
    Write-Host '  构建模式: 完整 CLI 参数（首次生成 ipo-know-crawler.spec）'
}

$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

$BuildProcess = $null
$BuildOutput = ''
$MaxBuildAttempts = 3

for ($Attempt = 1; $Attempt -le $MaxBuildAttempts; $Attempt++) {
    if ($Attempt -gt 1) {
        Write-Host "  第 $Attempt/$MaxBuildAttempts 次重试（常见原因: 杀毒软件/索引短暂锁定刚写入的产物文件，稍候再试）" -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }

    # 使用 .NET Process 同步等待子进程结束并统一 UTF-8 输出，
    # 避免 PowerShell 管道异步刷新导致的乱码与产物检查时序问题
    $ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
    $ProcessInfo.FileName = $PythonExe
    $ProcessInfo.Arguments = $BuildArgs
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

    $BuildOutput = $StdoutTask.Result
    if ($StderrTask.Result) {
        $BuildOutput = $BuildOutput + [Environment]::NewLine + $StderrTask.Result
    }

    # 产物文件被占用（WinError 5）导致 COLLECT 清理失败时可重试，
    # 其他错误直接终止
    $LockRetryable = ($BuildProcess.ExitCode -ne 0) -and ($BuildOutput -match 'PermissionError.*WinError 5')
    if ($BuildProcess.ExitCode -eq 0 -or -not $LockRetryable) {
        break
    }
    Write-Host '  PyInstaller 因产物文件被占用而失败' -ForegroundColor Yellow
}

$Stopwatch.Stop()
$Elapsed = '{0:mm\:ss}' -f $Stopwatch.Elapsed

if ($BuildProcess.ExitCode -ne 0) {
    Write-Host $BuildOutput
    Write-Host ''
    Write-Host "构建失败（PyInstaller 退出码: $($BuildProcess.ExitCode)，耗时 $Elapsed）" -ForegroundColor Red
    exit 1
}

Write-Host $BuildOutput
Write-Host "  PyInstaller 执行完成，耗时 $Elapsed"

if (-not $SpecExists -and (Test-Path $SpecFile)) {
    Write-Host "  已生成 spec: $SpecFile（后续构建将直接基于该 spec）" -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# 检查产物
# -----------------------------------------------------------------------------
Write-Host ''
Write-Host '[4/4] 检查产物...' -ForegroundColor Cyan

# 1. 产物目录与主 exe
if (-not (Test-Path $DistDir)) {
    Write-Host "错误: 未找到产物目录: $DistDir" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Artifact)) {
    Write-Host "错误: 未找到主产物文件: $Artifact" -ForegroundColor Red
    exit 1
}
Write-Host "  主 exe: OK ($Artifact)"

# 2. 产物更新时间（应为本次构建刚刚写入），防止误报旧产物为构建成功
$ArtifactItem = Get-Item $Artifact
$AgeSeconds = ((Get-Date) - $ArtifactItem.LastWriteTime).TotalSeconds
if ($AgeSeconds -gt 600) {
    Write-Host "错误: 产物文件未更新（最后修改时间: $($ArtifactItem.LastWriteTime)），构建可能未实际执行" -ForegroundColor Red
    exit 1
}

# 3. 关键运行时 DLL（onedir 分发完整性要点）
#    优先校验主运行时 python3XX.dll（如 python311.dll，不含轻量 launcher python3.dll）；
#    PyInstaller 6.x 默认将运行时 DLL 放入 _internal\ 子目录，故递归查找
$PythonDlls = Get-ChildItem -Path $DistDir -Recurse -Filter 'python3*.dll' -File
$PythonDll = $PythonDlls | Where-Object { $_.Name -match '^python3\d+\.dll$' } | Select-Object -First 1
if (-not $PythonDll) {
    Write-Host "错误: 产物目录中未找到 Python 主运行时 DLL（python3XX.dll，如 python311.dll），onedir 产物不完整: $DistDir" -ForegroundColor Red
    exit 1
}
Write-Host "  运行时 DLL: OK ($($PythonDll.FullName))"

# 4. 产物目录总体积（onedir 主 exe 很小，体积校验针对整个目录）
$DirBytes = (Get-ChildItem -Path $DistDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$DirSizeMB = [math]::Round($DirBytes / 1MB, 1)
if ($DirSizeMB -lt $MinDirSizeMB) {
    Write-Host "错误: 产物目录体积异常（$DirSizeMB MB，预期 >= $MinDirSizeMB MB），构建可能不完整" -ForegroundColor Red
    exit 1
}

$FileCount = (Get-ChildItem -Path $DistDir -Recurse -File).Count

Write-Host ''
Write-Host '==============================================' -ForegroundColor Green
Write-Host ' 构建成功!' -ForegroundColor Green
Write-Host " 产物目录: $DistDir" -ForegroundColor Green
Write-Host " 主 exe: $Artifact" -ForegroundColor Green
Write-Host " 目录体积: $DirSizeMB MB（$FileCount 个文件）" -ForegroundColor Green
Write-Host " 更新时间: $($ArtifactItem.LastWriteTime)" -ForegroundColor Green
Write-Host " 耗时: $Elapsed" -ForegroundColor Green
Write-Host '----------------------------------------------' -ForegroundColor Green
Write-Host ' 分发提示: onedir 产物需整个 dist\ipo-know-crawler 目录一起分发，' -ForegroundColor Yellow
Write-Host '           不可只复制 exe!' -ForegroundColor Yellow
Write-Host '==============================================' -ForegroundColor Green
exit 0

