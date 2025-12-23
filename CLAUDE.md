- This is the claude_code_bridge (ccb) development folder. Pay attention to compatibility. When modifying code, also update install scripts. Use install.sh/install.ps1 to install. After completion, git commit and push.

- Cross-platform compatibility notes:
  - subprocess.run with text=True MUST include encoding="utf-8", errors="replace" (Windows defaults to GBK)
  - Avoid #!/usr/bin/env python3 shebang on Windows (triggers App Store stub, exit 49). Use python or sys.executable
  - Always test on both Linux and Windows when modifying install scripts or terminal-related code