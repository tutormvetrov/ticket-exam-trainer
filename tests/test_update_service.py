from __future__ import annotations

from application.update_service import UpdateService


def test_http_error_text_for_403_is_actionable() -> None:
    text = UpdateService._http_error_text(403)
    assert "HTTP 403" in text
    assert "не ломает приложение" in text


def test_http_error_text_for_404_mentions_release_api() -> None:
    text = UpdateService._http_error_text(404)
    assert "HTTP 404" in text
    assert "release api" in text.lower()
