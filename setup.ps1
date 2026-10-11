<#
.SYNOPSIS
  Idempotent installer for the Local AI Video Editing Engine (Windows).
.DESCRIPTION
  Detect-first: never reinstalls working tools. Verifies every step,
  records versions to logs/setup_report.json, fails loudly on critical deps.
.EXAMPLE
  .\setup.ps1 -Install        # full install (Python 3.11 + FFmpeg + .venv + pip deps)
  .\setup.ps1 -PythonOnly     # only Python 3.11
  .\setup.ps1 -FfmpegOnly     # only FFmpeg
  .\setup.ps1 -Check          # verify only, install nothing
#>
[CmdletBinding()]
param(
  [switch]$Install,
  [switch]$PythonOnly,
  [switch]$FfmpegOnly,
  [switch]$Check
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$ReportPath = Join-Path $LogDir "setup_report.json"
$Report = @()

function Add-Report($tool, $version, $method, $status, $note = "") {
  $script:Report += [pscustomobject]@{
    tool = $tool; version = $version; method = $method; status = $status; note = $note
  }
}

function Get-Version([string]$cmd, [string]$verArgs = "--version") {
  try {
    $p = Get-Command $cmd -ErrorAction Stop
    $out = & $p.Source $verArgs 2>&1 | Select-Object -First 1
    return @{ path = $p.Source; version = "$out".Trim() }
  } catch { return $null }
}

function Test-RealPython {
  # MS Store shim reports "Python was not found" -- reject it.
  try {
    $p = Get-Command python -ErrorAction Stop
    $out = & $p.Source --version 2>&1 | Out-String
    if ($out -match "Python 3\.11" -and $out -notmatch "not found") { return @{ path = $p.Source; version = $out.Trim() } }
  } catch { }
  # Fallback: well-known per-user location (PATH order may still favor the
  # Store shim in stale sessions even after a real install).
  $known = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
  if (Test-Path -LiteralPath $known) {
    $out = & $known --version 2>&1 | Out-String
    if ($out -match "Python 3\.11") { return @{ path = $known; version = $out.Trim() } }
  }
  return $null
}

function Refresh-Path {
  # Merge registry PATH (Machine+User) into this process: winget registers
  # installs there, but inherited process env will not have them yet.
  # Merge-only (never replace) so parent-session entries are preserved.
  $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $user = [Environment]::GetEnvironmentVariable("Path", "User")
  foreach ($dir in (($machine + ";" + $user) -split ";" | Where-Object { $_ -and $_.Trim() -ne "" })) {
    if ($env:Path -notlike ("*" + $dir + "*")) { $env:Path = "$env:Path;$dir" }
  }
}

function Install-Python {
  $found = Test-RealPython
  if ($found) {
    Write-Host "Python OK: $($found.version) @ $($found.path) -- skipping install."
    Add-Report "python" $found.version "present" "ok"
    return $true
  }
  Write-Host "Installing Python 3.11 via winget (official Python.Python.3.11)..."
  try {
    winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
  } catch {
    Add-Report "python" "" "winget" "failed" $_.Exception.Message
    Write-Error "CRITICAL: Python install failed: $($_.Exception.Message)"
    return $false
  }
  Refresh-Path
  $found = Test-RealPython
  if (-not $found) {
    Add-Report "python" "" "winget" "failed" "installed but 'python --version' not reporting 3.11 -- open a NEW terminal (PATH refresh) and re-run."
    Write-Error "CRITICAL: Python installed but not on PATH. Open a NEW terminal and re-run .\setup.ps1 -Check."
    return $false
  }
  Write-Host "Python OK: $($found.version)"
  Add-Report "python" $found.version "winget:Python.Python.3.11" "installed"
  return $true
}

function Repair-FfmpegPath {
  # Gyan.FFmpeg winget package is portable: binaries live under
  # %LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\...\bin
  # without touching PATH. Wire that bin dir into the USER PATH.
  $pkgRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
  if (-not (Test-Path -LiteralPath $pkgRoot)) { return $null }
  $exe = Get-ChildItem -LiteralPath $pkgRoot -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "Gyan\.FFmpeg" } | Select-Object -First 1
  if (-not $exe) { return $null }
  $binDir = $exe.DirectoryName
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if ([string]::IsNullOrEmpty($userPath)) { $userPath = $binDir }
  elseif ($userPath -notlike "*$binDir*") { $userPath = "$userPath;$binDir" }
  [Environment]::SetEnvironmentVariable("Path", $userPath, "User")
  if ($env:Path -notlike "*$binDir*") { $env:Path = "$env:Path;$binDir" }
  return $binDir
}

function Install-Ffmpeg {
  $ff = Get-Version "ffmpeg" "-version"
  $fp = Get-Version "ffprobe" "-version"
  if ($ff -and $fp) {
    Write-Host "FFmpeg OK: $($ff.version) -- skipping install."
    Add-Report "ffmpeg" $ff.version "present" "ok"
    Add-Report "ffprobe" $fp.version "present" "ok"
    return $true
  }
  Write-Host "Installing FFmpeg via winget (official Gyan.FFmpeg)..."
  try {
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  } catch {
    Add-Report "ffmpeg" "" "winget" "failed" $_.Exception.Message
    Write-Error "CRITICAL: FFmpeg install failed: $($_.Exception.Message)"
    return $false
  }
  Refresh-Path
  $ff = Get-Version "ffmpeg" "-version"
  if (-not $ff) {
    $repaired = Repair-FfmpegPath
    if ($repaired) {
      Write-Host "FFmpeg found under winget packages; added to USER PATH: $repaired"
      $ff = Get-Version "ffmpeg" "-version"
    }
  }
  if (-not $ff) {
    $diag = "binary not found on PATH after install+repair"
    $foundCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($foundCmd) {
      $probeOut = ((& $foundCmd.Source -version 2>&1 | Out-String) + "").Trim()
      if ($probeOut.Length -gt 300) { $probeOut = $probeOut.Substring(0, 300) }
      $diag = "found at " + $foundCmd.Source + " but would not execute (first-run AV/SmartScreen block is a common cause). Output: " + $probeOut
    }
    Add-Report "ffmpeg" "" "winget" "failed" $diag
    Write-Error ("CRITICAL: FFmpeg verification failed: " + $diag)
    return $false
  }
  Write-Host "FFmpeg OK: $($ff.version)"
  Add-Report "ffmpeg" $ff.version "winget:Gyan.FFmpeg" "installed"
  $fp = Get-Version "ffprobe" "-version"
  if ($fp) { $fpStatus = "installed" } else { $fpStatus = "failed" }
  Add-Report "ffprobe" $fp.version "winget:Gyan.FFmpeg" $fpStatus
  return ($null -ne $fp)
}

function Install-Venv {
  $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $venvPy) {
    $v = & $venvPy --version 2>&1 | Out-String
    Write-Host "venv OK: $($v.Trim()) -- skipping creation."
    Add-Report "venv" $v.Trim() "present" "ok"
  } else {
    Write-Host "Creating .venv (Python 3.11)..."
    $pyReal = Test-RealPython
    if (-not $pyReal) {
      Add-Report "venv" "" "python -m venv" "failed" "no working Python 3.11 found for venv creation"
      Write-Error "CRITICAL: no working Python 3.11 found for venv creation."
      return $false
    }
    & $pyReal.path -m venv (Join-Path $Root ".venv")
    if (-not (Test-Path -LiteralPath $venvPy)) {
      Add-Report "venv" "" "python -m venv" "failed" ".venv creation failed"
      Write-Error "CRITICAL: .venv creation failed."
      return $false
    }
    Add-Report "venv" "created" "python -m venv" "installed"
  }
  $req = Join-Path $Root "requirements.txt"
  Write-Host "Installing pip requirements (this takes a while on first run)..."
  & $venvPy -m pip install --upgrade pip
  & $venvPy -m pip install -r $req
  if ($LASTEXITCODE -ne 0) {
    Add-Report "pip-deps" "" "pip install -r requirements.txt" "failed" "see console output"
    Write-Error "CRITICAL: pip install failed. See output above."
    return $false
  }
  $frozen = & $venvPy -m pip freeze 2>&1 | Out-String
  $pkgCount = ($frozen -split "`n").Count
  Add-Report "pip-deps" "$pkgCount packages" "pip" "installed"
  return $true
}

# ---- main ----
Refresh-Path
$doPython = $Install -or $PythonOnly -or $Check -or ((-not $FfmpegOnly) -and (-not $PythonOnly))
$doFfmpeg = $Install -or $FfmpegOnly -or $Check -or ((-not $FfmpegOnly) -and (-not $PythonOnly))

if ($Check) {
  $py = Test-RealPython; $ff = Get-Version "ffmpeg" "-version"
  if ($py) { $pyMsg = $py.version } else { $pyMsg = "MISSING" }
  if ($ff) { $ffMsg = $ff.version } else { $ffMsg = "MISSING" }
  Write-Host ("python : " + $pyMsg)
  Write-Host ("ffmpeg : " + $ffMsg)
  if ($py) { $pySt = "ok"; $pyVer = $py.version } else { $pySt = "missing"; $pyVer = "" }
  if ($ff) { $ffSt = "ok"; $ffVer = $ff.version } else { $ffSt = "missing"; $ffVer = "" }
  Add-Report "python" $pyVer "check" $pySt
  Add-Report "ffmpeg" $ffVer "check" $ffSt
} else {
  if ($doPython) { if (-not (Install-Python)) { throw "Setup aborted: Python is required." } }
  if ($doFfmpeg) { if (-not (Install-Ffmpeg)) { throw "Setup aborted: FFmpeg is required." } }
  if ($Install) { if (-not (Install-Venv)) { throw "Setup aborted: venv/pip deps failed." } }
}

$Report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
Write-Host "Report written to $ReportPath"
exit 0
