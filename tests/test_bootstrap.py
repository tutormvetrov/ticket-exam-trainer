from __future__ import annotations

from app.bootstrap import _should_show_splash


def test_should_show_splash_skips_screenshot_mode(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("TEZIS_DISABLE_SPLASH", raising=False)
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    assert _should_show_splash(screenshot_mode=True) is False


def test_should_show_splash_skips_known_automation_paths(monkeypatch) -> None:
    monkeypatch.setenv("TEZIS_DISABLE_SPLASH", "1")
    assert _should_show_splash(screenshot_mode=False) is False

    monkeypatch.delenv("TEZIS_DISABLE_SPLASH", raising=False)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert _should_show_splash(screenshot_mode=False) is False

    monkeypatch.setenv("QT_QPA_PLATFORM", "")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "bootstrap")
    assert _should_show_splash(screenshot_mode=False) is False
