from __future__ import annotations


def start_claude(
    launcher,
    *,
    display_label: str | None = None,
    translate_fn,
    subprocess_module,
) -> int:
    del display_label
    print(f"🚀 {translate_fn('starting_claude')}")
    env = launcher._build_claude_env()

    try:
        plan = launcher.claude_start_planner.build_plan()
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    if launcher.resume:
        if plan.has_history:
            print(f"🔁 {translate_fn('resuming_claude', session_id='')}")
        else:
            print(f"ℹ️ {translate_fn('no_claude_session')}")

    print(f"📋 Session ID: {launcher.ccb_session_id}")
    print(f"📁 Runtime dir: {launcher.runtime_dir}")
    print(f"🔌 Active targets: {', '.join(launcher.target_names)}")
    print()
    print("🎯 Standard commands:")
    print('   ccb ask <agent> [from <sender>] "..."')
    print("   ccb ping <agent>")
    print("   ccb pend <agent|job_id>")
    print("   ccb watch <agent|job_id>")
    print("   ccb logs <agent>")
    print("   ccb ps")
    print("   ccb doctor")
    print()
    print(f"Executing: {' '.join(plan.cmd)}")

    try:
        return subprocess_module.run(plan.cmd, env=env, cwd=plan.run_cwd).returncode
    except KeyboardInterrupt:
        print(f"\n⚠️ {translate_fn('user_interrupted')}")
        return 130


def start_claude_pane(
    launcher,
    *,
    parent_pane: str | None,
    direction: str | None,
    display_label: str | None = None,
    translate_fn,
) -> str | None:
    print(f"🚀 {translate_fn('starting_claude')}")
    env_overrides = launcher._claude_env_overrides()
    label = launcher._display_label("claude", display_label)

    try:
        plan = launcher.claude_start_planner.build_plan()
    except FileNotFoundError as exc:
        print(str(exc))
        return None

    if launcher.resume:
        if plan.has_history:
            print(f"🔁 {translate_fn('resuming_claude', session_id='')}")
        else:
            print(f"ℹ️ {translate_fn('no_claude_session')}")

    start_cmd = " ".join(plan.cmd)
    pane_id = launcher.claude_pane_launcher.start(
        run_cwd=plan.run_cwd,
        start_cmd=start_cmd,
        env_overrides=env_overrides,
        write_local_session_fn=launcher._write_local_claude_session,
        read_local_session_id_fn=launcher._read_local_claude_session_id,
        parent_pane=parent_pane,
        direction=direction,
        display_label=label,
    )

    print(f"✅ {translate_fn('started_backend', provider=label, terminal=f'{launcher.terminal_type} pane', pane_id=pane_id)}")
    return pane_id
