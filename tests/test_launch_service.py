import applauncher.services.launch_service as launch_module
from applauncher.services.launch_service import LaunchService


def test_launch_returns_error_for_disabled_item() -> None:
    service = LaunchService()

    success, error = service.launch({"disabled": True, "disabled_reason": "blocked"})

    assert not success
    assert error is not None
    assert "blocked" in error


def test_launch_executable_with_args_uses_subprocess(monkeypatch) -> None:
    service = LaunchService()
    popen_calls: list[list[str]] = []

    monkeypatch.setattr(launch_module.os.path, "exists", lambda _: True)
    monkeypatch.setattr(launch_module.subprocess, "Popen", lambda args: popen_calls.append(args))

    success, error = service.launch(
        {
            "type": "exe",
            "path": r"C:\Tools\my_app.exe",
            "args": ["--silent"],
        }
    )

    assert success
    assert error is None
    assert popen_calls == [[r"C:\Tools\my_app.exe", "--silent"]]


def test_launch_url_falls_back_to_webbrowser(monkeypatch) -> None:
    service = LaunchService()
    opened_urls: list[str] = []

    class _DesktopServicesStub:
        @staticmethod
        def openUrl(_):
            return False

    monkeypatch.setattr(launch_module, "QDesktopServices", _DesktopServicesStub)
    monkeypatch.setattr(
        launch_module.webbrowser,
        "open",
        lambda url: opened_urls.append(url) or True,
    )

    success, error = service.launch({"type": "url", "path": "example.com"})

    assert success
    assert error is None
    assert opened_urls == ["https://example.com"]


def test_launch_folder_accepts_unc_path(monkeypatch) -> None:
    service = LaunchService()
    opened_paths: list[str] = []

    monkeypatch.setattr(launch_module, "is_unc_path", lambda _: True)
    monkeypatch.setattr(service, "_open_path", lambda value: opened_paths.append(str(value)))

    success, error = service.launch({"type": "folder", "path": r"\\server\share\folder"})

    assert success
    assert error is None
    assert opened_paths == [r"\\server\share\folder"]
