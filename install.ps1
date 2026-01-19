param(
  [Parameter(Position = 0)]
  [ValidateSet("install", "uninstall", "help")]
  [string]$Command = "help",
  [string]$InstallPrefix = "$env:LOCALAPPDATA\codex-dual",
  [switch]$Yes
)

# --- UTF-8 / BOM compatibility (Windows PowerShell 5.1) ---
# Keep this near the top so Chinese/emoji output is rendered correctly.
try {
  $script:utf8NoBom = [System.Text.UTF8Encoding]::new($false)
} catch {
  $script:utf8NoBom = [System.Text.Encoding]::UTF8
}
try { $OutputEncoding = $script:utf8NoBom } catch {}
try { [Console]::OutputEncoding = $script:utf8NoBom } catch {}
try { [Console]::InputEncoding = $script:utf8NoBom } catch {}
try { chcp 65001 | Out-Null } catch {}

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Constants
$script:CCB_START_MARKER = "<!-- CCB_CONFIG_START -->"
$script:CCB_END_MARKER = "<!-- CCB_CONFIG_END -->"
$script:CCB_WEZTERM_START_MARKER = "-- CCB_WEZTERM_START"
$script:CCB_WEZTERM_END_MARKER = "-- CCB_WEZTERM_END"

$script:SCRIPTS_TO_LINK = @(
  "ccb",
  "cask", "caskd", "cpend", "cping",
  "gask", "gaskd", "gpend", "gping",
  "oask", "oaskd", "opend", "oping",
  "lask", "laskd", "lpend", "lping"
)

$script:CLAUDE_MARKDOWN = @(
  "cpend.md", "cping.md",
  "gpend.md", "gping.md",
  "opend.md", "oping.md"
)

$script:LEGACY_SCRIPTS = @(
  "cast", "cast-w", "codex-ask", "codex-pending", "codex-ping",
  "claude-codex-dual", "claude_codex", "claude_ai", "claude_bridge"
)

# i18n support
function Get-CCBLang {
  $lang = $env:CCB_LANG
  if ($lang -in @("zh", "cn", "chinese")) { return "zh" }
  if ($lang -in @("en", "english")) { return "en" }
  # Auto-detect from system
  try {
    $culture = (Get-Culture).Name
    if ($culture -like "zh*") { return "zh" }
  } catch {}
  return "en"
}

$script:CCBLang = Get-CCBLang

function Get-Msg {
  param([string]$Key, [string]$Arg1 = "", [string]$Arg2 = "")
  $msgs = @{
    "install_complete" = @{ en = "Installation complete"; zh = "安装完成" }
    "uninstall_complete" = @{ en = "Uninstall complete"; zh = "卸载完成" }
    "python_old" = @{ en = "Python version too old: $Arg1"; zh = "Python 版本过旧: $Arg1" }
    "requires_python" = @{ en = "ccb requires Python 3.10+"; zh = "ccb 需要 Python 3.10+" }
    "confirm_windows" = @{ en = "Continue installation in Windows? (y/N)"; zh = "确认继续在 Windows 中安装？(y/N)" }
    "cancelled" = @{ en = "Installation cancelled"; zh = "安装已取消" }
    "windows_warning" = @{ en = "You are installing ccb in native Windows environment"; zh = "你正在 Windows 原生环境安装 ccb" }
    "same_env" = @{ en = "ccb/cask/cping/cpend must run in the same environment as codex/gemini."; zh = "ccb/cask/cping/cpend 必须与 codex/gemini 在同一环境运行。" }
  }
  if ($msgs.ContainsKey($Key)) {
    return $msgs[$Key][$script:CCBLang]
  }
  return $Key
}

function Show-Usage {
  Write-Host "Usage:"
  Write-Host "  .\install.ps1 install    # Install or update"
  Write-Host "  .\install.ps1 uninstall  # Uninstall"
  Write-Host ""
  Write-Host "Options:"
  Write-Host "  -InstallPrefix <path>    # Custom install location (default: $env:LOCALAPPDATA\codex-dual)"
  Write-Host ""
  Write-Host "Requirements:"
  Write-Host "  - Python 3.10+"
}

function Find-Python {
  if (Get-Command py -ErrorAction SilentlyContinue) { return "py -3" }
  if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
  if (Get-Command python3 -ErrorAction SilentlyContinue) { return "python3" }
  return $null
}

function Require-Python310 {
  param([string]$PythonCmd)

  # Handle commands with arguments (e.g., "py -3")
  $cmdParts = $PythonCmd -split ' ', 2
  $fileName = $cmdParts[0]
  $baseArgs = if ($cmdParts.Length -gt 1) { $cmdParts[1] } else { "" }

  # Use ProcessStartInfo for reliable execution across different Python installations
  # (e.g., Miniconda, custom paths). The & operator can fail in some environments.
  try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $fileName
    # Combine base arguments with Python code arguments
    if ($baseArgs) {
      $psi.Arguments = "$baseArgs -c `"import sys; v=sys.version_info; print(f'{v.major}.{v.minor}.{v.micro} {v.major} {v.minor}')`""
    } else {
      $psi.Arguments = "-c `"import sys; v=sys.version_info; print(f'{v.major}.{v.minor}.{v.micro} {v.major} {v.minor}')`""
    }
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $process.Start() | Out-Null
    $process.WaitForExit()

    $vinfo = $process.StandardOutput.ReadToEnd().Trim()
    if ($process.ExitCode -ne 0 -or [string]::IsNullOrEmpty($vinfo)) {
      throw $process.StandardError.ReadToEnd()
    }

    $vparts = $vinfo -split " "
    if ($vparts.Length -lt 3) {
      throw "Unexpected version output: $vinfo"
    }

    $version = $vparts[0]
    $major = [int]$vparts[1]
    $minor = [int]$vparts[2]
  } catch {
    Write-Host "[ERROR] Failed to query Python version using: $PythonCmd"
    Write-Host "   Error details: $_"
    exit 1
  }

  if (($major -ne 3) -or ($minor -lt 10)) {
    Write-Host "[ERROR] Python version too old: $version"
    Write-Host "   ccb requires Python 3.10+"
    Write-Host "   Download: https://www.python.org/downloads/"
    exit 1
  }
  Write-Host "[OK] Python $version"
}

function Confirm-BackendEnv {
  if ($Yes -or $env:CCB_INSTALL_ASSUME_YES -eq "1") { return }

  if (-not [Environment]::UserInteractive) {
    Write-Host "[ERROR] Non-interactive environment detected, aborting to prevent Windows/WSL mismatch."
    Write-Host "   If codex/gemini will run in native Windows:"
    Write-Host "   Re-run: powershell -ExecutionPolicy Bypass -File .\install.ps1 install -Yes"
    exit 1
  }

  Write-Host ""
  Write-Host "================================================================"
  Write-Host "[WARNING] You are installing ccb in native Windows environment"
  Write-Host "================================================================"
  Write-Host "ccb/cask/cping/cpend must run in the same environment as codex/gemini."
  Write-Host ""
  Write-Host "Please confirm: You will install and run codex/gemini in native Windows (not WSL)."
  Write-Host "If you plan to run codex/gemini in WSL, exit and run in WSL:"
  Write-Host "   ./install.sh install"
  Write-Host "================================================================"
  $reply = Read-Host "Continue installation in Windows? (y/N)"
  if ($reply.Trim().ToLower() -notin @("y", "yes")) {
    Write-Host "Installation cancelled"
    exit 1
  }
}

function Install-Native {
  Confirm-BackendEnv

  $binDir = Join-Path $InstallPrefix "bin"
  $pythonCmd = Find-Python

  if (-not $pythonCmd) {
    Write-Host "Python not found. Please install Python and add it to PATH."
    Write-Host "Download: https://www.python.org/downloads/"
    exit 1
  }

  Require-Python310 -PythonCmd $pythonCmd

  Write-Host "Installing ccb to $InstallPrefix ..."
  Write-Host "Using Python: $pythonCmd"

  if (-not (Test-Path $InstallPrefix)) {
    New-Item -ItemType Directory -Path $InstallPrefix -Force | Out-Null
  }
  if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
  }

  $items = @("ccb", "lib", "bin", "commands")
  foreach ($item in $items) {
    $src = Join-Path $repoRoot $item
    $dst = Join-Path $InstallPrefix $item
    if (Test-Path $src) {
      if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
      Copy-Item -Recurse -Force $src $dst
    }
  }

  function Fix-PythonShebang {
    param([string]$TargetPath)
    if (-not $TargetPath -or -not (Test-Path $TargetPath)) { return }
    try {
      $text = [System.IO.File]::ReadAllText($TargetPath, [System.Text.Encoding]::UTF8)
      if ($text -match '^\#\!/usr/bin/env python3') {
        $text = $text -replace '^\#\!/usr/bin/env python3', '#!/usr/bin/env python'
        [System.IO.File]::WriteAllText($TargetPath, $text, $script:utf8NoBom)
      }
    } catch {
      return
    }
  }

  $scripts = @(
    "ccb",
    "cask", "caskd", "cping", "cpend",
    "gask", "gaskd", "gping", "gpend",
    "oask", "oaskd", "oping", "opend",
    "lask", "laskd", "lping", "lpend"
  )

  # In MSYS/Git-Bash, invoking the script file directly will honor the shebang.
  # Windows typically has `python` but not `python3`, so rewrite shebangs for compatibility.
  foreach ($script in $scripts) {
    if ($script -eq "ccb") {
      Fix-PythonShebang (Join-Path $InstallPrefix "ccb")
    } else {
      Fix-PythonShebang (Join-Path $InstallPrefix ("bin\\" + $script))
    }
  }

  foreach ($script in $scripts) {
    $batPath = Join-Path $binDir "$script.bat"
    $cmdPath = Join-Path $binDir "$script.cmd"
    if ($script -eq "ccb") {
      $relPath = "..\\ccb"
    } else {
      # Script is installed alongside the wrapper under $InstallPrefix\bin
      $relPath = $script
    }
    $wrapperContent = "@echo off`r`nset `"PYTHON=python`"`r`nwhere python >NUL 2>&1 || set `"PYTHON=py -3`"`r`n%PYTHON% `"%~dp0$relPath`" %*"
    [System.IO.File]::WriteAllText($batPath, $wrapperContent, $script:utf8NoBom)
    # .cmd wrapper for PowerShell/CMD users (and tools preferring .cmd over raw shebang scripts)
    [System.IO.File]::WriteAllText($cmdPath, $wrapperContent, $script:utf8NoBom)
  }

  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  $pathList = if ($userPath) { $userPath -split ";" | Where-Object { $_ } } else { @() }
  $binDirLower = $binDir.ToLower()
  $alreadyInPath = $pathList | Where-Object { $_.ToLower() -eq $binDirLower }
  if (-not $alreadyInPath) {
    $newPath = ($pathList + $binDir) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added $binDir to user PATH"
  }

  # Git version injection
  function Get-GitVersionInfo {
    param([string]$RepoRoot)

    $commit = ""
    $date = ""

    # 方法1: 本地 Git
    if (Get-Command git -ErrorAction SilentlyContinue) {
      if (Test-Path (Join-Path $RepoRoot ".git")) {
        try {
          $commit = (git -C $RepoRoot log -1 --format='%h' 2>$null)
          $date = (git -C $RepoRoot log -1 --format='%cs' 2>$null)
        } catch {}
      }
    }

    # 方法2: 环境变量
    if (-not $commit -and $env:CCB_GIT_COMMIT) {
      $commit = $env:CCB_GIT_COMMIT
      $date = $env:CCB_GIT_DATE
    }

    # 方法3: GitHub API
    if (-not $commit) {
      try {
        $api = "https://api.github.com/repos/bfly123/claude_code_bridge/commits/main"
        $response = Invoke-RestMethod -Uri $api -TimeoutSec 5 -ErrorAction Stop
        $commit = $response.sha.Substring(0,7)
        $date = $response.commit.committer.date.Substring(0,10)
      } catch {}
    }

    return @{Commit=$commit; Date=$date}
  }

  # 注入版本信息到 ccb 文件
  $verInfo = Get-GitVersionInfo -RepoRoot $repoRoot
  if ($verInfo.Commit) {
    $ccbPath = Join-Path $InstallPrefix "ccb"
    if (Test-Path $ccbPath) {
      try {
        $content = Get-Content $ccbPath -Raw -Encoding UTF8
        $content = $content -replace 'GIT_COMMIT = ""', "GIT_COMMIT = `"$($verInfo.Commit)`""
        $content = $content -replace 'GIT_DATE = ""', "GIT_DATE = `"$($verInfo.Date)`""
        [System.IO.File]::WriteAllText($ccbPath, $content, [System.Text.UTF8Encoding]::new($false))
        Write-Host "Injected version info: $($verInfo.Commit) $($verInfo.Date)"
      } catch {
        Write-Warning "Failed to inject version info: $_"
      }
    }
  }
  Install-CodexSkills
  Install-ClaudeConfig

  try {
    Set-WezTermDefaultShellToPowerShell
  } catch {
    Write-Warning "WezTerm configuration skipped: $_"
  }

  Write-Host ""
  Write-Host "Installation complete!"
  Write-Host "Restart your terminal (WezTerm) for PATH changes to take effect."
  Write-Host ""
  Write-Host "Quick start:"
  Write-Host "  ccb             # Start providers from ccb.config (default: all four)"
  Write-Host "  ccb codex       # Start with Codex backend"
  Write-Host "  ccb gemini      # Start with Gemini backend"
  Write-Host "  ccb opencode    # Start with OpenCode backend"
  Write-Host "  ccb claude      # Start with Claude backend"
}

function Install-CodexSkills {
  $skillsSrc = Join-Path $repoRoot "codex_skills"
  $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
  $skillsDst = Join-Path $codexHome "skills"

  if (-not (Test-Path $skillsSrc)) {
    return
  }

  if (-not (Test-Path $skillsDst)) {
    New-Item -ItemType Directory -Path $skillsDst -Force | Out-Null
  }

  Write-Host "Installing Codex skills (PowerShell SKILL.md templates)..."
  Get-ChildItem -Path $skillsSrc -Directory | ForEach-Object {
    $skillName = $_.Name
    $srcDir = $_.FullName
    $dstDir = Join-Path $skillsDst $skillName
    $dstSkillMd = Join-Path $dstDir "SKILL.md"

    if (-not (Test-Path $dstDir)) {
      New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    }

    $srcSkillMd = Join-Path $srcDir "SKILL.md.powershell"
    if (-not (Test-Path $srcSkillMd)) {
      $srcSkillMd = Join-Path $srcDir "SKILL.md"
    }
    if (-not (Test-Path $srcSkillMd)) {
      return
    }

    Copy-Item -Force $srcSkillMd $dstSkillMd
    Write-Host "  Updated Codex skill: $skillName"
  }
  Write-Host "Updated Codex skills directory: $skillsDst"
}

function Install-ClaudeConfig {
  $claudeDir = Join-Path $env:USERPROFILE ".claude"
  $commandsDir = Join-Path $claudeDir "commands"
  $claudeMd = Join-Path $claudeDir "CLAUDE.md"
  $settingsJson = Join-Path $claudeDir "settings.json"

  if (-not (Test-Path $claudeDir)) {
    New-Item -ItemType Directory -Path $claudeDir -Force | Out-Null
  }
  if (-not (Test-Path $commandsDir)) {
    New-Item -ItemType Directory -Path $commandsDir -Force | Out-Null
  }

  $srcCommands = Join-Path $repoRoot "commands"
  if (Test-Path $srcCommands) {
    Get-ChildItem -Path $srcCommands -Filter "*.md" | ForEach-Object {
      Copy-Item -Force $_.FullName (Join-Path $commandsDir $_.Name)
    }
  }

  # Install skills
  $skillsDir = Join-Path $claudeDir "skills"
  $srcSkills = Join-Path $repoRoot "skills"
  if (Test-Path $srcSkills) {
    if (-not (Test-Path $skillsDir)) {
      New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null
    }
    Write-Host "Installing Claude skills (PowerShell SKILL.md templates)..."
    Get-ChildItem -Path $srcSkills -Directory | ForEach-Object {
      if ($_.Name -eq "docs") { return }

      $skillName = $_.Name
      $srcDir = $_.FullName
      $dstDir = Join-Path $skillsDir $skillName
      $dstSkillMd = Join-Path $dstDir "SKILL.md"

      if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
      }

      $srcSkillMd = Join-Path $srcDir "SKILL.md.powershell"
      if (-not (Test-Path $srcSkillMd)) {
        $srcSkillMd = Join-Path $srcDir "SKILL.md"
      }
      if (-not (Test-Path $srcSkillMd)) {
        return
      }

      Copy-Item -Force $srcSkillMd $dstSkillMd
      Write-Host "  Updated skill: $skillName"
    }

    $srcDocs = Join-Path $srcSkills "docs"
    if (Test-Path $srcDocs) {
      $dstDocs = Join-Path $skillsDir "docs"
      if (Test-Path $dstDocs) { Remove-Item -Recurse -Force $dstDocs }
      Copy-Item -Recurse -Force $srcDocs $dstDocs
      Write-Host "  Installed skills docs: docs/"
    }
  }

  $codexRules = @"
<!-- CCB_CONFIG_START -->
## Collaboration Rules (Codex / Gemini / OpenCode)
Codex, Gemini, and OpenCode are other AI assistants running in separate terminal sessions (WezTerm or tmux).

### Common Rules (all assistants)
Trigger (any match):
- User explicitly asks to consult one of them (e.g. "ask codex ...", "let gemini ...")
- User uses an assistant prefix (see table)
- User asks about that assistant's status (e.g. "is codex alive?")

Fast path (minimize latency):
- If the user message starts with a prefix: treat the rest as the question and dispatch immediately.
- If the user message is only the prefix (no question): ask a 1-line clarification for what to send.

Actions:
- Ask a question (default) -> ``Bash(@"`n<question>`n"@ | <cask|gask|oask>, run_in_background=true)``, tell user "ASSISTANT processing (task: xxx)", then END your turn
- Check connectivity -> run ``PING_CMD``
- Use blocking/wait or "show previous reply" commands ONLY if the user explicitly requests them

Important restrictions:
- After starting a background ask, do NOT poll for results; wait for ``bash-notification``
- Do NOT use ``*-w`` / ``*pend`` / ``*end`` unless the user explicitly requests

### Command Map
| Assistant | Prefixes | ASK (background) | PING_CMD | Explicit-request-only |
|---|---|---|---|---|
| Codex | ``@codex``, ``codex:``, ``ask codex``, ``let codex``, ``/cask`` | ``@"`n<question>`n"@ | cask`` | ``cping`` | ``cpend`` |
| Gemini | ``@gemini``, ``gemini:``, ``ask gemini``, ``let gemini``, ``/gask`` | ``@"`n<question>`n"@ | gask`` | ``gping`` | ``gpend`` |
| OpenCode | ``@opencode``, ``opencode:``, ``ask opencode``, ``let opencode``, ``/oask`` | ``@"`n<question>`n"@ | oask`` | ``oping`` | ``opend`` |

Examples:
- ``codex: review this code`` -> ``Bash(@"`nreview this code`n"@ | cask, run_in_background=true)``, END turn
- ``is gemini alive?`` -> ``gping``
<!-- CCB_CONFIG_END -->
"@

  if (Test-Path $claudeMd) {
    $content = Get-Content -Raw $claudeMd

    if ($content -match [regex]::Escape($script:CCB_START_MARKER)) {
      # Replace existing CCB config block (keep rest of file intact)
      $pattern = '(?s)<!-- CCB_CONFIG_START -->.*?<!-- CCB_CONFIG_END -->'
      $newContent = [regex]::Replace($content, $pattern, $codexRules)
      $newContent | Out-File -Encoding UTF8 -FilePath $claudeMd
      Write-Host "Updated CLAUDE.md with collaboration rules"
    } elseif ($content -match '##\s+(Codex|Gemini|OpenCode)\s+Collaboration Rules' -or $content -match '##\s+(Codex|Gemini|OpenCode)\s+协作规则') {
      # Remove legacy rule blocks then append the new unified block
      $patterns = @(
        '(?s)## Codex Collaboration Rules.*?(?=\n## (?!Gemini)|\Z)',
        '(?s)## Codex 协作规则.*?(?=\n## |\Z)',
        '(?s)## Gemini Collaboration Rules.*?(?=\n## |\Z)',
        '(?s)## Gemini 协作规则.*?(?=\n## |\Z)',
        '(?s)## OpenCode Collaboration Rules.*?(?=\n## |\Z)',
        '(?s)## OpenCode 协作规则.*?(?=\n## |\Z)'
      )
      foreach ($p in $patterns) {
        $content = [regex]::Replace($content, $p, '')
      }
      $content = ($content.TrimEnd() + "`n")
      ($content + $codexRules + "`n") | Out-File -Encoding UTF8 -FilePath $claudeMd
      Write-Host "Updated CLAUDE.md with collaboration rules"
    } else {
      Add-Content -Path $claudeMd -Value $codexRules
      Write-Host "Updated CLAUDE.md with collaboration rules"
    }
  } else {
    $codexRules | Out-File -Encoding UTF8 -FilePath $claudeMd
    Write-Host "Created CLAUDE.md with collaboration rules"
  }

  $allowList = @(
    "Bash(cask:*)", "Bash(cpend)", "Bash(cping)",
    "Bash(gask:*)", "Bash(gpend)", "Bash(gping)",
    "Bash(oask:*)", "Bash(opend)", "Bash(oping)"
  )

  if (Test-Path $settingsJson) {
    try {
      $settings = Get-Content -Raw $settingsJson | ConvertFrom-Json
    } catch {
      $settings = @{}
    }
  } else {
    $settings = @{}
  }

  if (-not $settings.permissions) {
    $settings | Add-Member -NotePropertyName "permissions" -NotePropertyValue @{} -Force
  }
  if (-not $settings.permissions.allow) {
    $settings.permissions | Add-Member -NotePropertyName "allow" -NotePropertyValue @() -Force
  }

  $currentAllow = [System.Collections.ArrayList]@($settings.permissions.allow)
  $updated = $false
  foreach ($item in $allowList) {
    if ($currentAllow -notcontains $item) {
      $currentAllow.Add($item) | Out-Null
      $updated = $true
    }
  }

  if ($updated) {
    $settings.permissions.allow = $currentAllow.ToArray()
    $settings | ConvertTo-Json -Depth 10 | Out-File -Encoding UTF8 -FilePath $settingsJson
    Write-Host "Updated settings.json with permissions"
  }
}

function Set-WezTermDefaultShellToPowerShell {
  $weztermCandidates = @(
    (Join-Path $env:USERPROFILE ".wezterm.lua"),
    (Join-Path $env:USERPROFILE ".config\\wezterm\\wezterm.lua")
  )
  $weztermConfig = $weztermCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $weztermConfig) {
    Write-Host "WezTerm config not found; skipping default shell configuration."
    Write-Host "  Checked:"
    $weztermCandidates | ForEach-Object { Write-Host "   - $_" }
    return
  }

  $pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
  $powershell = Get-Command powershell.exe -ErrorAction SilentlyContinue
  if ($pwsh) {
    $shellExe = "pwsh.exe"
    $fallbackExe = "powershell.exe"
  } elseif ($powershell) {
    $shellExe = "powershell.exe"
    $fallbackExe = "pwsh.exe"
  } else {
    Write-Warning "PowerShell not found; skipping WezTerm configuration."
    return
  }

  $content = Get-Content -Raw -Path $weztermConfig
  $hasConfigVar = ($content -match "(?m)^\\s*(local\\s+)?config\\s*=") -or ($content -match "(?m)^\\s*return\\s+config\\s*$")
  if (-not $hasConfigVar) {
    Write-Warning "WezTerm config doesn't appear to use a 'config' variable; skipping automatic edit."
    Write-Host "Suggested snippet to add before your return statement:"
    Write-Host "  config.default_prog = { '$shellExe' }"
    return
  }

  $block = @"
$($script:CCB_WEZTERM_START_MARKER)
-- Set default shell to PowerShell (installed by ccb)
config.default_prog = { '$shellExe' }
-- Fallback (if '$shellExe' is not available): config.default_prog = { '$fallbackExe' }
$($script:CCB_WEZTERM_END_MARKER)
"@

  $alreadyPowerShell = $content -match "default_prog\\s*=\\s*\\{\\s*'?(pwsh\\.exe|powershell\\.exe)'?\\s*\\}"
  $hasDefaultProg = $content -match "default_prog\\s*="

  $shouldApply = $false
  if ($content -match [regex]::Escape($script:CCB_WEZTERM_START_MARKER)) {
    $shouldApply = $true
  } elseif (-not $hasDefaultProg) {
    $shouldApply = $true
  } elseif ($alreadyPowerShell) {
    Write-Host "WezTerm default_prog already configured for PowerShell."
    return
  } else {
    if ($Yes -or $env:CCB_INSTALL_ASSUME_YES -eq "1") {
      $shouldApply = $true
    } elseif ([Environment]::UserInteractive) {
      $reply = Read-Host "WezTerm default_prog is already configured. Override to '$shellExe'? (y/N)"
      if ($reply.Trim().ToLower() -in @("y", "yes")) {
        $shouldApply = $true
      }
    }
  }

  if ($shouldApply) {
    if ($content -match [regex]::Escape($script:CCB_WEZTERM_START_MARKER)) {
      $pattern = "(?s)\\Q$($script:CCB_WEZTERM_START_MARKER)\\E.*?\\Q$($script:CCB_WEZTERM_END_MARKER)\\E"
      $newContent = [regex]::Replace($content, $pattern, $block)
    } elseif ($content -match "(?m)^\\s*return\\s+config\\s*$") {
      $newContent = [regex]::Replace($content, "(?m)^\\s*return\\s+config\\s*$", ($block + "`r`nreturn config"))
    } else {
      $newContent = ($content.TrimEnd() + "`r`n`r`n" + $block + "`r`n")
    }

    [System.IO.File]::WriteAllText($weztermConfig, $newContent, $script:utf8NoBom)
    Write-Host "✓ WezTerm configured to use $shellExe ($weztermConfig)"
  } else {
    if ($hasDefaultProg -and -not $alreadyPowerShell -and ($content -notmatch "(?m)^\\s*--\\s*ccb:\\s*To use PowerShell as default shell")) {
      $hint = @"
-- ccb: To use PowerShell as default shell, set:
-- config.default_prog = { '$shellExe' }
"@
      if ($content -match "(?m)^\\s*return\\s+config\\s*$") {
        $newContent = [regex]::Replace($content, "(?m)^\\s*return\\s+config\\s*$", ($hint + "`r`nreturn config"))
      } else {
        $newContent = ($content.TrimEnd() + "`r`n`r`n" + $hint + "`r`n")
      }
      [System.IO.File]::WriteAllText($weztermConfig, $newContent, $script:utf8NoBom)
      Write-Host "WezTerm default_prog not changed; added a comment hint to $weztermConfig"
      return
    }
    Write-Host "WezTerm default_prog not changed."
  }
}

function Uninstall-Native {
  $binDir = Join-Path $InstallPrefix "bin"

  if (Test-Path $InstallPrefix) {
    Remove-Item -Recurse -Force $InstallPrefix
    Write-Host "Removed $InstallPrefix"
  }

  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if ($userPath) {
    $pathList = $userPath -split ";" | Where-Object { $_ }
    $binDirLower = $binDir.ToLower()
    $newPathList = $pathList | Where-Object { $_.ToLower() -ne $binDirLower }
    if ($newPathList.Count -ne $pathList.Count) {
      $newPath = $newPathList -join ";"
      [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
      Write-Host "Removed $binDir from user PATH"
    }
  }

  Write-Host "Uninstall complete."
}

if ($Command -eq "help") {
  Show-Usage
  exit 0
}

if ($Command -eq "install") {
  Install-Native
  exit 0
}

if ($Command -eq "uninstall") {
  Uninstall-Native
  exit 0
}
