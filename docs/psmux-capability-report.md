# psmux capability report

- Generated: 2026-04-22 10:54:22 -04:00
- Host shell: `pwsh.exe -File` on native Windows
- Repository: `C:\Users\Administrator\Desktop\ccb\claude_code_bridge`
- psmux path: `D:\psmux\psmux.exe`
- pwsh: `PowerShell 7.6.0`
- psmux: `psmux 3.3.3`

## Overall conclusion

psmux is viable for the CCB Windows namespace model, but only with explicit caveats. `-L` named server isolation works and shared-server + per-project session also works. The main gaps are `pipe-pane`, terminal-close verification depth, and the fact that `kill-session` does not clear sessions on named servers, so project teardown/rebuild should use `kill-server` per project server instead.

- Command plane: supported=10, partial=2, workaround_available=1, unsupported=0
- Semantic plane: supported=5, partial=1, workaround_available=1, unsupported=0

## Command plane

| Command | Status | Evidence | Notes |
| --- | --- | --- | --- |
| new-session | supported | main: 1 windows (created Wed Apr 22 10:54:23 2026) |  |
| split-window | supported | 0\|%1\|WIN-DBNQVHEMCKP\|0\|shell<br>1\|%4\|WIN-DBNQVHEMCKP\|0\|cmd<br>2\|%3\|WIN-DBNQVHEMCKP\|0\|cmd | Verified both -h and -v. |
| list-panes | supported | 0\|%1\|WIN-DBNQVHEMCKP\|0\|shell<br>1\|%4\|WIN-DBNQVHEMCKP\|0\|cmd<br>2\|%3\|WIN-DBNQVHEMCKP\|0\|cmd |  |
| display-message | supported | GATE_MESSAGE_OK |  |
| send-keys | supported | <br>C:\Users\Administrator\Desktop\ccb>echo SEND_KEYS_OK<br>SEND_KEYS_OK<br><br>C:\Users\Administrator\Desktop\ccb> |  |
| capture-pane | supported | <br>C:\Users\Administrator\Desktop\ccb>echo SEND_KEYS_OK<br>SEND_KEYS_OK<br><br>C:\Users\Administrator\Desktop\ccb> |  |
| set-option | supported | status-left "[gate-main] "<br>@gate-user "hello" |  |
| set-hook | supported | pane-exited -> run-shell "cmd /c echo HOOKFIRED > C:\Users\Administrator\Desktop\ccb\claude_code_bridge\.testlogs\psmux-capability-gate\pane-exited-hook.txt"<br>HOOKFIRED | pane-exited fired on natural process exit; kill-pane alone did not trigger this hook in earlier probe. |
| pipe-pane | partial | file_exists=True length=0<br> | When streaming output did not land in file, capture-pane polling remains a workaround. |
| kill-pane | supported | before:<br>0\|%1\|WIN-DBNQVHEMCKP\|0\|shell<br>1\|%4\|WIN-DBNQVHEMCKP\|0\|cmd<br>after:<br>0\|%1\|WIN-DBNQVHEMCKP\|0\|shell |  |
| kill-session | workaround_available | main: 1 windows (created Wed Apr 22 10:54:23 2026) | On `-L` named servers, kill-session returned 0 but did not remove the session. Project teardown can still fall back to kill-server per project server. |
| attach-session | supported | /dev/pts/6: s1: cmd [120x29] (utf8) [activity=2s ago] |  |
| switch-client | partial | before:<br>/dev/pts/6: s1: cmd [120x29] (utf8) [activity=2s ago]<br>after:<br>/dev/pts/6: s1: cmd [120x29] (utf8) [activity=4s ago] | On this Windows run the command returned 0, but the attached client stayed on s1. |

## Semantic plane

| Scenario | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Close terminal, session survives | partial | s1: 1 windows (created Wed Apr 22 10:54:36 2026) (attached)<br>s2: 1 windows (created Wed Apr 22 10:54:37 2026) | Automated proxy used Stop-Process on the attached pwsh client. Session survived, but a real user-driven terminal close still needs one manual spot check. |
| Pane death leaves session controllable | supported | <br>C:\Users\Administrator\Desktop\ccb>echo STILL_ALIVE<br>STILL_ALIVE<br><br>C:\Users\Administrator\Desktop\ccb> |  |
| Multi-project namespace isolation | supported | shared_server projA => status-left "[A] "<br>shared_server projB => status-left "[B] "<br>serverA:<br>main: 1 windows (created Wed Apr 22 10:54:51 2026)<br>serverB:<br>main: 1 windows (created Wed Apr 22 10:54:52 2026) | psmux -L provided separate named servers; shared-server + per-project session also worked. |
| Pane title stable and readable | supported | AGENT_cmd | Shell-level title alone did not update pane_title in earlier probe; select-pane -T did. |
| Pane marker and user option readable back | supported | @gate-marker "hello"<br>pane_marked=1 |  |
| UI contract can be reapplied after attach | supported | attached => status-left "[UI-2] "<br>after_detach => status-left "[UI-2] " |  |
| Pane id can be rediscovered after session rebuild | workaround_available | before=%1<br>session name still present after kill-session on the named server |  |

## Manual follow-up still worth doing

1. Open a fresh native Windows terminal window.
2. Run `D:\psmux\psmux.exe -L gate-manual new-session -d -s smoke -- cmd /k title MANUAL`.
3. Run `D:\psmux\psmux.exe -L gate-manual attach-session -t smoke` in that terminal.
4. Close the terminal window via the window close button, not `Stop-Process`.
5. From another `pwsh.exe`, run `D:\psmux\psmux.exe -L gate-manual list-sessions` and confirm `smoke` still exists.

## Raw artifacts

- Scratch directory: `C:\Users\Administrator\Desktop\ccb\claude_code_bridge\.testlogs\psmux-capability-gate`
- Hook artifact: `pane-exited-hook.txt`
- Pipe artifact: `pipe-pane.txt`
