from __future__ import annotations

import terminal


def test_extract_wsl_path_from_unc_like_path() -> None:
    f = terminal._extract_wsl_path_from_unc_like_path
    assert f("/wsl.localhost/Ubuntu-24.04/home/u/x") == "/home/u/x"
    assert f("\\\\wsl.localhost\\Ubuntu-24.04\\home\\u\\x") == "/home/u/x"
    assert f("/wsl$/Ubuntu-24.04/home/u/x") == "/home/u/x"
    assert f("/not-wsl/path") is None
    assert f("/home/user/normal/path") is None
    assert f("") is None
