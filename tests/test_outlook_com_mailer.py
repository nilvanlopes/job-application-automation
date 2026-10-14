from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import job_application_automation.outlook_com_mailer as mailer


def test_resolve_windows_process_env_selects_working_interop_socket(monkeypatch, tmp_path):
    current = tmp_path / "848_interop"
    working = tmp_path / "2_interop"
    current.touch()
    working.touch()
    monkeypatch.setenv("WSL_INTEROP", str(current))
    monkeypatch.setattr(mailer, "Path", _fake_path_factory(tmp_path, current, working))

    probes = []

    def fake_run(command, **kwargs):
        probes.append((command, kwargs["env"]["WSL_INTEROP"]))
        return SimpleNamespace(returncode=0 if kwargs["env"]["WSL_INTEROP"] == str(working) else 1)

    monkeypatch.setattr(mailer.subprocess, "run", fake_run)
    result = mailer._resolve_windows_process_env("powershell.exe")

    assert result["WSL_INTEROP"] == str(working)
    assert len(probes) == 2


def _fake_path_factory(root: Path, current: Path, working: Path):
    original_path = Path

    class FakePath(type(original_path)):
        pass

    # Keep the production helper's Path API while making its socket discovery
    # deterministic for the unit test.
    def factory(value):
        path = original_path(value)
        if str(path) == "/run/WSL":
            return _InteropRoot(root, current, working)
        return path

    return factory


class _InteropRoot:
    def __init__(self, root: Path, current: Path, working: Path):
        self.root = root
        self.current = current
        self.working = working

    def exists(self):
        return True

    def glob(self, pattern):
        return [self.current, self.working]
