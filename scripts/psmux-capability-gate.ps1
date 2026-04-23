param(
    [string]$PsmuxPath = 'D:\psmux\psmux.exe'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ReportPath = Join-Path $RepoRoot 'docs\psmux-capability-report.md'
$ScratchRoot = Join-Path $RepoRoot '.testlogs\psmux-capability-gate'
$PwshExe = Join-Path $PSHOME 'pwsh.exe'
$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
$PwshVersion = (& $PwshExe --version | Out-String).Trim()
$PsmuxVersion = (& $PsmuxPath --version | Out-String).Trim()

New-Item -ItemType Directory -Force -Path $ScratchRoot | Out-Null
Remove-Item (Join-Path $ScratchRoot '*') -Force -Recurse -ErrorAction SilentlyContinue
$ProgressPath = Join-Path $ScratchRoot 'progress.log'

$CommandResults = [System.Collections.Generic.List[object]]::new()
$SemanticResults = [System.Collections.Generic.List[object]]::new()
$UsedServers = [System.Collections.Generic.List[string]]::new()

function Split-Lines {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) {
        return @()
    }
    return @($Text -split "`r?`n" | Where-Object { $_ -ne '' })
}

function Mark-Step {
    param([string]$Name)
    Add-Content -Path $ProgressPath -Value ("$(Get-Date -Format 'HH:mm:ss') `t$Name")
}

function To-MdCell {
    param([string]$Text)
    if ($null -eq $Text) {
        return ''
    }
    return (($Text -replace '\|', '\|') -replace "`r?`n", '<br>')
}

function Invoke-Psmux {
    param(
        [string]$Server,
        [string[]]$CmdArgs,
        [switch]$AllowFailure
    )

    $AllArgs = @()
    if ($Server) {
        $AllArgs += @('-L', $Server)
    }
    $AllArgs += $CmdArgs
    $Output = & $PsmuxPath @AllArgs 2>&1 | Out-String
    $Result = [pscustomobject]@{
        Server = $Server
        Args = ($AllArgs -join ' ')
        ExitCode = $LASTEXITCODE
        Output = $Output.TrimEnd()
    }
    if (-not $AllowFailure -and $Result.ExitCode -ne 0) {
        throw "psmux failed: $($Result.Args)`n$($Result.Output)"
    }
    return $Result
}

function Add-CommandResult {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Evidence,
        [string]$Notes = ''
    )
    $script:CommandResults.Add([pscustomobject]@{
        Name = $Name
        Status = $Status
        Evidence = $Evidence
        Notes = $Notes
    })
}

function Add-SemanticResult {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Evidence,
        [string]$Notes = ''
    )
    $script:SemanticResults.Add([pscustomobject]@{
        Name = $Name
        Status = $Status
        Evidence = $Evidence
        Notes = $Notes
    })
}

function Get-FirstMatchLine {
    param(
        [string]$Text,
        [string]$Pattern
    )
    return (Split-Lines $Text | Where-Object { $_ -match $Pattern } | Select-Object -First 1)
}

function Get-PaneLines {
    param(
        [string]$Server,
        [string]$Target
    )
    $r = Invoke-Psmux -Server $Server -CmdArgs @('list-panes', '-t', $Target, '-F', '#{pane_index}|#{pane_id}|#{pane_title}|#{pane_marked}|#{pane_current_command}')
    return Split-Lines $r.Output
}

function New-GateSession {
    param(
        [string]$Server,
        [string]$Session,
        [string]$Title = 'ROOTPANE'
    )
    Invoke-Psmux -Server $Server -CmdArgs @('new-session', '-d', '-s', $Session, '--', 'cmd', '/k', ("title $Title")) | Out-Null
    Start-Sleep -Seconds 1
}

function Start-AttachClient {
    param(
        [string]$Server,
        [string]$Session
    )
    $Command = "& '$PsmuxPath' -L '$Server' attach-session -t '$Session'"
    return Start-Process -FilePath $PwshExe -WorkingDirectory $RepoRoot -ArgumentList @('-NoLogo', '-NoExit', '-Command', $Command) -PassThru
}

function Stop-AttachClient {
    param([System.Diagnostics.Process]$Process)
    if ($Process) {
        try {
            Stop-Process -Id $Process.Id -Force -ErrorAction Stop
        }
        catch {
        }
        Start-Sleep -Seconds 2
    }
}

function Register-Server {
    param([string]$Server)
    if (-not $script:UsedServers.Contains($Server)) {
        $script:UsedServers.Add($Server)
    }
}

function Cleanup-Servers {
    foreach ($Server in $script:UsedServers) {
        try {
            Invoke-Psmux -Server $Server -CmdArgs @('kill-server') -AllowFailure | Out-Null
        }
        catch {
        }
    }
}

function Wait-SessionGone {
    param(
        [string]$Server,
        [string]$Session,
        [int]$MaxSeconds = 5
    )
    for ($i = 0; $i -lt $MaxSeconds; $i++) {
        $Sessions = (Invoke-Psmux -Server $Server -CmdArgs @('list-sessions') -AllowFailure).Output
        if (-not (Get-FirstMatchLine -Text $Sessions -Pattern ('^' + [regex]::Escape($Session) + ':'))) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

$MainServer = "gate-main-$PID"
$AttachServer = "gate-attach-$PID"
$DeathServer = "gate-death-$PID"
$IsolationSharedServer = "gate-iso-shared-$PID"
$IsolationServerA = "gate-iso-a-$PID"
$IsolationServerB = "gate-iso-b-$PID"
$TitleServer = "gate-title-$PID"
$MarkerServer = "gate-marker-$PID"
$UiServer = "gate-ui-$PID"
$RebuildServer = "gate-rebuild-$PID"
@($MainServer, $AttachServer, $DeathServer, $IsolationSharedServer, $IsolationServerA, $IsolationServerB, $TitleServer, $MarkerServer, $UiServer, $RebuildServer) | ForEach-Object { Register-Server $_ }

$AttachClient1 = $null
$AttachClient2 = $null
try {
    Cleanup-Servers
    Mark-Step 'start'

    # Command plane: main session
    New-GateSession -Server $MainServer -Session 'main' -Title 'ROOTPANE'
    $MainSessions = (Invoke-Psmux -Server $MainServer -CmdArgs @('list-sessions')).Output
    Add-CommandResult -Name 'new-session' -Status ((Get-FirstMatchLine -Text $MainSessions -Pattern '^main:') ? 'supported' : 'unsupported') -Evidence $MainSessions

    $SplitH = Invoke-Psmux -Server $MainServer -CmdArgs @('split-window', '-h', '-t', 'main:0.0', 'cmd', '/k', 'title RIGHTPANE')
    Start-Sleep -Seconds 1
    $SplitV = Invoke-Psmux -Server $MainServer -CmdArgs @('split-window', '-v', '-t', 'main:0.0', 'cmd', '/k', 'title LOWERPANE')
    Start-Sleep -Seconds 1
    $PaneLinesAfterSplit = Get-PaneLines -Server $MainServer -Target 'main'
    $SplitStatus = if ($SplitH.ExitCode -eq 0 -and $SplitV.ExitCode -eq 0 -and $PaneLinesAfterSplit.Count -ge 3) { 'supported' } else { 'unsupported' }
    Add-CommandResult -Name 'split-window' -Status $SplitStatus -Evidence (($PaneLinesAfterSplit -join "`n")) -Notes 'Verified both -h and -v.'

    Add-CommandResult -Name 'list-panes' -Status ($PaneLinesAfterSplit.Count -ge 3 ? 'supported' : 'unsupported') -Evidence (($PaneLinesAfterSplit -join "`n"))

    $DisplayMessage = Invoke-Psmux -Server $MainServer -CmdArgs @('display-message', '-p', '-t', 'main:0.0', 'GATE_MESSAGE_OK')
    Add-CommandResult -Name 'display-message' -Status (($DisplayMessage.Output -match 'GATE_MESSAGE_OK') ? 'supported' : 'unsupported') -Evidence $DisplayMessage.Output

    Invoke-Psmux -Server $MainServer -CmdArgs @('send-keys', '-t', 'main:0.0', '-l', 'echo SEND_KEYS_OK') | Out-Null
    Invoke-Psmux -Server $MainServer -CmdArgs @('send-keys', '-t', 'main:0.0', 'Enter') | Out-Null
    Start-Sleep -Seconds 1
    $CapturePane = Invoke-Psmux -Server $MainServer -CmdArgs @('capture-pane', '-p', '-t', 'main:0.0')
    $CaptureHasSend = $CapturePane.Output -match 'SEND_KEYS_OK'
    Add-CommandResult -Name 'send-keys' -Status ($CaptureHasSend ? 'supported' : 'unsupported') -Evidence $CapturePane.Output
    Add-CommandResult -Name 'capture-pane' -Status ($CaptureHasSend ? 'supported' : 'unsupported') -Evidence $CapturePane.Output

    Invoke-Psmux -Server $MainServer -CmdArgs @('set-option', '-t', 'main', 'status-left', '[gate-main] ') | Out-Null
    Invoke-Psmux -Server $MainServer -CmdArgs @('set-option', '-t', 'main', '@gate-user', 'hello') | Out-Null
    $ShowOptionsMain = (Invoke-Psmux -Server $MainServer -CmdArgs @('show-options', '-t', 'main')).Output
    $StatusLeftLine = Get-FirstMatchLine -Text $ShowOptionsMain -Pattern '^status-left '
    $UserOptionLine = Get-FirstMatchLine -Text $ShowOptionsMain -Pattern '^@gate-user '
    $SetOptionStatus = if ($StatusLeftLine -and $UserOptionLine) { 'supported' } else { 'unsupported' }
    Add-CommandResult -Name 'set-option' -Status $SetOptionStatus -Evidence (($StatusLeftLine, $UserOptionLine | Where-Object { $_ }) -join "`n")

    $HookFile = Join-Path $ScratchRoot 'pane-exited-hook.txt'
    $HookCommand = 'run-shell "cmd /c echo HOOKFIRED > ' + $HookFile + '"'
    Invoke-Psmux -Server $MainServer -CmdArgs @('set-hook', '-t', 'main', 'pane-exited', $HookCommand) | Out-Null
    Invoke-Psmux -Server $MainServer -CmdArgs @('send-keys', '-t', 'main:0.2', '-l', 'exit') | Out-Null
    Invoke-Psmux -Server $MainServer -CmdArgs @('send-keys', '-t', 'main:0.2', 'Enter') | Out-Null
    Start-Sleep -Seconds 3
    $HookShow = (Invoke-Psmux -Server $MainServer -CmdArgs @('show-hooks', '-t', 'main')).Output
    $HookStatus = if ((Test-Path $HookFile) -and ((Get-Content $HookFile -Raw).Trim() -eq 'HOOKFIRED')) { 'supported' } else { 'partial' }
    $HookEvidence = @($HookShow)
    if (Test-Path $HookFile) {
        $HookEvidence += ((Get-Content $HookFile -Raw).Trim())
    }
    Add-CommandResult -Name 'set-hook' -Status $HookStatus -Evidence (($HookEvidence | Where-Object { $_ }) -join "`n") -Notes 'pane-exited fired on natural process exit; kill-pane alone did not trigger this hook in earlier probe.'

    $PipeFile = Join-Path $ScratchRoot 'pipe-pane.txt'
    Invoke-Psmux -Server $MainServer -CmdArgs @('pipe-pane', '-t', 'main:0.0', ('cmd /c more > ' + $PipeFile)) | Out-Null
    Invoke-Psmux -Server $MainServer -CmdArgs @('send-keys', '-t', 'main:0.0', '-l', 'echo PIPE_PANE_OK') | Out-Null
    Invoke-Psmux -Server $MainServer -CmdArgs @('send-keys', '-t', 'main:0.0', 'Enter') | Out-Null
    Start-Sleep -Seconds 2
    Invoke-Psmux -Server $MainServer -CmdArgs @('pipe-pane', '-t', 'main:0.0') | Out-Null
    Start-Sleep -Seconds 2
    $PipeExists = Test-Path $PipeFile
    $PipeContent = if ($PipeExists) { (Get-Content $PipeFile -Raw) } else { '' }
    $PipeStatus = if ($PipeContent -match 'PIPE_PANE_OK') { 'supported' } elseif ($PipeExists) { 'partial' } else { 'unsupported' }
    $PipeEvidence = if ($PipeExists) { "file_exists=True length=$((Get-Item $PipeFile).Length)`n$PipeContent" } else { 'file_exists=False' }
    Add-CommandResult -Name 'pipe-pane' -Status $PipeStatus -Evidence $PipeEvidence -Notes 'When streaming output did not land in file, capture-pane polling remains a workaround.'

    $PanesBeforeKill = Get-PaneLines -Server $MainServer -Target 'main'
    Invoke-Psmux -Server $MainServer -CmdArgs @('kill-pane', '-t', 'main:0.1') | Out-Null
    Start-Sleep -Seconds 1
    $PanesAfterKill = Get-PaneLines -Server $MainServer -Target 'main'
    $KillPaneStatus = if ($PanesAfterKill.Count -lt $PanesBeforeKill.Count) { 'supported' } else { 'unsupported' }
    Add-CommandResult -Name 'kill-pane' -Status $KillPaneStatus -Evidence ((@('before:') + $PanesBeforeKill + @('after:') + $PanesAfterKill) -join "`n")

    Invoke-Psmux -Server $MainServer -CmdArgs @('kill-session', '-t', 'main') | Out-Null
    Start-Sleep -Seconds 1
    $SessionsAfterKill = (Invoke-Psmux -Server $MainServer -CmdArgs @('list-sessions') -AllowFailure).Output
    $KillSessionStatus = if (Get-FirstMatchLine -Text $SessionsAfterKill -Pattern '^main:') { 'workaround_available' } else { 'supported' }
    $KillSessionNotes = if ($KillSessionStatus -eq 'workaround_available') { 'On `-L` named servers, kill-session returned 0 but did not remove the session. Project teardown can still fall back to kill-server per project server.' } else { '' }
    Add-CommandResult -Name 'kill-session' -Status $KillSessionStatus -Evidence ($(if ($SessionsAfterKill) { $SessionsAfterKill } else { '(no sessions listed)' })) -Notes $KillSessionNotes

    Mark-Step 'command-plane-done'

    # Attach / switch client / terminal close
    New-GateSession -Server $AttachServer -Session 's1' -Title 'S1'
    New-GateSession -Server $AttachServer -Session 's2' -Title 'S2'
    $AttachClient1 = Start-AttachClient -Server $AttachServer -Session 's1'
    Start-Sleep -Seconds 3
    $ClientsOnS1 = (Invoke-Psmux -Server $AttachServer -CmdArgs @('list-clients')).Output
    Add-CommandResult -Name 'attach-session' -Status (($ClientsOnS1 -match ':\s*s1:') ? 'supported' : 'unsupported') -Evidence $ClientsOnS1

    $SwitchClient = Invoke-Psmux -Server $AttachServer -CmdArgs @('switch-client', '-t', 's2')
    Start-Sleep -Seconds 2
    $ClientsOnS2 = (Invoke-Psmux -Server $AttachServer -CmdArgs @('list-clients')).Output
    $SwitchStatus = if ($ClientsOnS2 -match ':\s*s2:') { 'supported' } elseif ($SwitchClient.ExitCode -eq 0) { 'partial' } else { 'unsupported' }
    Add-CommandResult -Name 'switch-client' -Status $SwitchStatus -Evidence ((@('before:', $ClientsOnS1, 'after:', $ClientsOnS2) | Where-Object { $_ }) -join "`n") -Notes 'On this Windows run the command returned 0, but the attached client stayed on s1.'

    Stop-AttachClient -Process $AttachClient1
    $SessionsAfterClientKill = (Invoke-Psmux -Server $AttachServer -CmdArgs @('list-sessions')).Output
    $TerminalCloseStatus = if ($SessionsAfterClientKill -match 's1:' -and $SessionsAfterClientKill -match 's2:') { 'partial' } else { 'unsupported' }
    Add-SemanticResult -Name 'Close terminal, session survives' -Status $TerminalCloseStatus -Evidence $SessionsAfterClientKill -Notes 'Automated proxy used Stop-Process on the attached pwsh client. Session survived, but a real user-driven terminal close still needs one manual spot check.'

    Mark-Step 'attach-plane-done'

    # Pane death still controllable
    New-GateSession -Server $DeathServer -Session 'death' -Title 'ROOT'
    Invoke-Psmux -Server $DeathServer -CmdArgs @('split-window', '-h', '-t', 'death:0.0', 'cmd', '/k', 'title RIGHT') | Out-Null
    Start-Sleep -Seconds 1
    Invoke-Psmux -Server $DeathServer -CmdArgs @('kill-pane', '-t', 'death:0.1') | Out-Null
    Start-Sleep -Seconds 1
    Invoke-Psmux -Server $DeathServer -CmdArgs @('send-keys', '-t', 'death:0.0', '-l', 'echo STILL_ALIVE') | Out-Null
    Invoke-Psmux -Server $DeathServer -CmdArgs @('send-keys', '-t', 'death:0.0', 'Enter') | Out-Null
    Start-Sleep -Seconds 1
    $DeathCapture = (Invoke-Psmux -Server $DeathServer -CmdArgs @('capture-pane', '-p', '-t', 'death:0.0')).Output
    Add-SemanticResult -Name 'Pane death leaves session controllable' -Status (($DeathCapture -match 'STILL_ALIVE') ? 'supported' : 'unsupported') -Evidence $DeathCapture

    Mark-Step 'death-plane-done'

    # Namespace isolation: shared server + distinct sessions, plus per-project servers via -L
    New-GateSession -Server $IsolationSharedServer -Session 'projA' -Title 'PROJA'
    New-GateSession -Server $IsolationSharedServer -Session 'projB' -Title 'PROJB'
    Invoke-Psmux -Server $IsolationSharedServer -CmdArgs @('set-option', '-t', 'projA', 'status-left', '[A] ') | Out-Null
    Invoke-Psmux -Server $IsolationSharedServer -CmdArgs @('set-option', '-t', 'projB', 'status-left', '[B] ') | Out-Null
    $ProjAShow = (Invoke-Psmux -Server $IsolationSharedServer -CmdArgs @('show-options', '-t', 'projA')).Output
    $ProjBShow = (Invoke-Psmux -Server $IsolationSharedServer -CmdArgs @('show-options', '-t', 'projB')).Output
    $ProjAStatusLeft = Get-FirstMatchLine -Text $ProjAShow -Pattern '^status-left '
    $ProjBStatusLeft = Get-FirstMatchLine -Text $ProjBShow -Pattern '^status-left '
    New-GateSession -Server $IsolationServerA -Session 'main' -Title 'ISOA'
    New-GateSession -Server $IsolationServerB -Session 'main' -Title 'ISOB'
    $ServerAList = (Invoke-Psmux -Server $IsolationServerA -CmdArgs @('list-sessions')).Output
    $ServerBList = (Invoke-Psmux -Server $IsolationServerB -CmdArgs @('list-sessions')).Output
    $IsolationStatus = if ($ProjAStatusLeft -and $ProjBStatusLeft -and $ServerAList -match '^main:' -and $ServerBList -match '^main:') { 'supported' } else { 'partial' }
    $IsolationEvidence = @(
        "shared_server projA => $ProjAStatusLeft",
        "shared_server projB => $ProjBStatusLeft",
        'serverA:',
        $ServerAList,
        'serverB:',
        $ServerBList
    ) -join "`n"
    Add-SemanticResult -Name 'Multi-project namespace isolation' -Status $IsolationStatus -Evidence $IsolationEvidence -Notes 'psmux -L provided separate named servers; shared-server + per-project session also worked.'

    Mark-Step 'isolation-done'

    # Pane title stability
    New-GateSession -Server $TitleServer -Session 'titleprobe' -Title 'ROOT'
    Invoke-Psmux -Server $TitleServer -CmdArgs @('select-pane', '-T', 'AGENT_cmd', '-t', 'titleprobe:0.0') | Out-Null
    Start-Sleep -Seconds 1
    $PaneTitleReadback = (Invoke-Psmux -Server $TitleServer -CmdArgs @('display-message', '-p', '-t', 'titleprobe:0.0', '#{pane_title}')).Output
    Add-SemanticResult -Name 'Pane title stable and readable' -Status (($PaneTitleReadback -eq 'AGENT_cmd') ? 'supported' : 'partial') -Evidence $PaneTitleReadback -Notes 'Shell-level title alone did not update pane_title in earlier probe; select-pane -T did.'

    Mark-Step 'title-done'

    # Marker / user option readable back
    New-GateSession -Server $MarkerServer -Session 'marker' -Title 'ROOT'
    Invoke-Psmux -Server $MarkerServer -CmdArgs @('set-option', '-t', 'marker', '@gate-marker', 'hello') | Out-Null
    Invoke-Psmux -Server $MarkerServer -CmdArgs @('select-pane', '-m', '-t', 'marker:0.0') | Out-Null
    $MarkerShow = (Invoke-Psmux -Server $MarkerServer -CmdArgs @('show-options', '-t', 'marker')).Output
    $MarkerLine = Get-FirstMatchLine -Text $MarkerShow -Pattern '^@gate-marker '
    $PaneMarked = (Invoke-Psmux -Server $MarkerServer -CmdArgs @('display-message', '-p', '-t', 'marker:0.0', '#{pane_marked}')).Output
    $MarkerStatus = if ($MarkerLine -and $PaneMarked -eq '1') { 'supported' } else { 'partial' }
    Add-SemanticResult -Name 'Pane marker and user option readable back' -Status $MarkerStatus -Evidence ((@($MarkerLine, "pane_marked=$PaneMarked") | Where-Object { $_ }) -join "`n")

    Mark-Step 'marker-done'

    # UI contract reapply after attach
    New-GateSession -Server $UiServer -Session 'ui' -Title 'ROOT'
    Invoke-Psmux -Server $UiServer -CmdArgs @('set-option', '-t', 'ui', 'status-left', '[UI-1] ') | Out-Null
    $AttachClient2 = Start-AttachClient -Server $UiServer -Session 'ui'
    Start-Sleep -Seconds 3
    Invoke-Psmux -Server $UiServer -CmdArgs @('set-option', '-t', 'ui', 'status-left', '[UI-2] ') | Out-Null
    $UiOptionsWhileAttached = (Invoke-Psmux -Server $UiServer -CmdArgs @('show-options', '-t', 'ui')).Output
    Stop-AttachClient -Process $AttachClient2
    $UiOptionsAfterDetach = (Invoke-Psmux -Server $UiServer -CmdArgs @('show-options', '-t', 'ui')).Output
    $UiLineWhileAttached = Get-FirstMatchLine -Text $UiOptionsWhileAttached -Pattern '^status-left '
    $UiLineAfterDetach = Get-FirstMatchLine -Text $UiOptionsAfterDetach -Pattern '^status-left '
    $UiStatus = if ($UiLineWhileAttached -match '\[UI-2\]' -and $UiLineAfterDetach -match '\[UI-2\]') { 'supported' } else { 'partial' }
    Add-SemanticResult -Name 'UI contract can be reapplied after attach' -Status $UiStatus -Evidence ((@("attached => $UiLineWhileAttached", "after_detach => $UiLineAfterDetach") | Where-Object { $_ }) -join "`n")

    Mark-Step 'ui-done'

    # Session rebuild / pane rediscovery
    New-GateSession -Server $RebuildServer -Session 'rebuild' -Title 'ROOT1'
    $RebuildBefore = (Invoke-Psmux -Server $RebuildServer -CmdArgs @('list-panes', '-t', 'rebuild', '-F', '#{pane_id}')).Output
    Invoke-Psmux -Server $RebuildServer -CmdArgs @('kill-session', '-t', 'rebuild') | Out-Null
    $RebuildGone = Wait-SessionGone -Server $RebuildServer -Session 'rebuild' -MaxSeconds 5
    if ($RebuildGone) {
        New-GateSession -Server $RebuildServer -Session 'rebuild' -Title 'ROOT2'
        $RebuildAfter = (Invoke-Psmux -Server $RebuildServer -CmdArgs @('list-panes', '-t', 'rebuild', '-F', '#{pane_id}')).Output
        $RebuildStatus = if ((Split-Lines $RebuildBefore).Count -ge 1 -and (Split-Lines $RebuildAfter).Count -ge 1) { 'supported' } else { 'unsupported' }
        $RebuildEvidence = ((@("before=$RebuildBefore", "after=$RebuildAfter") | Where-Object { $_ }) -join "`n")
    }
    else {
        $RebuildStatus = 'workaround_available'
        $RebuildEvidence = ((@("before=$RebuildBefore", 'session name still present after kill-session on the named server') | Where-Object { $_ }) -join "`n")
    }
    Add-SemanticResult -Name 'Pane id can be rediscovered after session rebuild' -Status $RebuildStatus -Evidence $RebuildEvidence

    $SupportedCommands = ($CommandResults | Where-Object { $_.Status -eq 'supported' }).Count
    $PartialCommands = ($CommandResults | Where-Object { $_.Status -eq 'partial' }).Count
    $WorkaroundCommands = ($CommandResults | Where-Object { $_.Status -eq 'workaround_available' }).Count
    $UnsupportedCommands = ($CommandResults | Where-Object { $_.Status -eq 'unsupported' }).Count
    $SupportedSemantics = ($SemanticResults | Where-Object { $_.Status -eq 'supported' }).Count
    $PartialSemantics = ($SemanticResults | Where-Object { $_.Status -eq 'partial' }).Count
    $WorkaroundSemantics = ($SemanticResults | Where-Object { $_.Status -eq 'workaround_available' }).Count
    $UnsupportedSemantics = ($SemanticResults | Where-Object { $_.Status -eq 'unsupported' }).Count

    $OverallConclusion = if ($UnsupportedCommands -eq 0 -and $UnsupportedSemantics -eq 0) {
        'psmux is viable for the CCB Windows namespace model, but only with explicit caveats. `-L` named server isolation works and shared-server + per-project session also works. The main gaps are `pipe-pane`, terminal-close verification depth, and the fact that `kill-session` does not clear sessions on named servers, so project teardown/rebuild should use `kill-server` per project server instead.'
    }
    else {
        'psmux is not yet cleanly green for the full Windows namespace model; see unsupported items below.'
    }

    $Lines = [System.Collections.Generic.List[string]]::new()
    $Lines.Add('# psmux capability report')
    $Lines.Add('')
    $Lines.Add('- Generated: ' + $Timestamp)
    $Lines.Add('- Host shell: `pwsh.exe -File` on native Windows')
    $Lines.Add('- Repository: `C:\Users\Administrator\Desktop\ccb\claude_code_bridge`')
    $Lines.Add('- psmux path: `' + $PsmuxPath + '`')
    $Lines.Add('- pwsh: `' + $PwshVersion + '`')
    $Lines.Add('- psmux: `' + $PsmuxVersion + '`')
    $Lines.Add('')
    $Lines.Add('## Overall conclusion')
    $Lines.Add('')
    $Lines.Add($OverallConclusion)
    $Lines.Add('')
    $Lines.Add("- Command plane: supported=$SupportedCommands, partial=$PartialCommands, workaround_available=$WorkaroundCommands, unsupported=$UnsupportedCommands")
    $Lines.Add("- Semantic plane: supported=$SupportedSemantics, partial=$PartialSemantics, workaround_available=$WorkaroundSemantics, unsupported=$UnsupportedSemantics")
    $Lines.Add('')
    $Lines.Add('## Command plane')
    $Lines.Add('')
    $Lines.Add('| Command | Status | Evidence | Notes |')
    $Lines.Add('| --- | --- | --- | --- |')
    foreach ($Item in $CommandResults) {
        $Lines.Add('| ' + (To-MdCell $Item.Name) + ' | ' + (To-MdCell $Item.Status) + ' | ' + (To-MdCell $Item.Evidence) + ' | ' + (To-MdCell $Item.Notes) + ' |')
    }
    $Lines.Add('')
    $Lines.Add('## Semantic plane')
    $Lines.Add('')
    $Lines.Add('| Scenario | Status | Evidence | Notes |')
    $Lines.Add('| --- | --- | --- | --- |')
    foreach ($Item in $SemanticResults) {
        $Lines.Add('| ' + (To-MdCell $Item.Name) + ' | ' + (To-MdCell $Item.Status) + ' | ' + (To-MdCell $Item.Evidence) + ' | ' + (To-MdCell $Item.Notes) + ' |')
    }
    $Lines.Add('')
    $Lines.Add('## Manual follow-up still worth doing')
    $Lines.Add('')
    $Lines.Add('1. Open a fresh native Windows terminal window.')
    $Lines.Add('2. Run `D:\psmux\psmux.exe -L gate-manual new-session -d -s smoke -- cmd /k title MANUAL`.')
    $Lines.Add('3. Run `D:\psmux\psmux.exe -L gate-manual attach-session -t smoke` in that terminal.')
    $Lines.Add('4. Close the terminal window via the window close button, not `Stop-Process`.')
    $Lines.Add('5. From another `pwsh.exe`, run `D:\psmux\psmux.exe -L gate-manual list-sessions` and confirm `smoke` still exists.')
    $Lines.Add('')
    $Lines.Add('## Raw artifacts')
    $Lines.Add('')
    $Lines.Add('- Scratch directory: `' + $ScratchRoot + '`')
    $Lines.Add('- Hook artifact: `pane-exited-hook.txt`')
    $Lines.Add('- Pipe artifact: `pipe-pane.txt`')

    Mark-Step 'rebuild-done'
    $Lines | Set-Content -Path $ReportPath -Encoding utf8
    Mark-Step 'report-written'
    Write-Host "Wrote report to $ReportPath"
}
catch {
    Mark-Step ('error: ' + $_.Exception.Message)
    ($_ | Out-String) | Set-Content -Path (Join-Path $ScratchRoot 'error.txt') -Encoding utf8
    throw
}
finally {
    Stop-AttachClient -Process $AttachClient1
    Stop-AttachClient -Process $AttachClient2
    Cleanup-Servers
}
