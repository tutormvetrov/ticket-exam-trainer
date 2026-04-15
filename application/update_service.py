from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.meta import APP_VERSION, GITHUB_RELEASES_URL, GITHUB_REPOSITORY


@dataclass(slots=True)
class UpdateInfo:
    current_version: str = APP_VERSION
    latest_version: str = APP_VERSION
    checked_at: datetime | None = None
    update_available: bool = False
    release_url: str = GITHUB_RELEASES_URL
    asset_url: str = ""
    asset_name: str = ""
    error_text: str = ""

    @property
    def checked_label(self) -> str:
        if self.checked_at is None:
            return "Проверка ещё не выполнялась"
        return self.checked_at.strftime("%d.%m.%Y %H:%M")


class UpdateService:
    def __init__(self, repository: str = GITHUB_REPOSITORY) -> None:
        self.repository = repository

    def check(self, timeout_seconds: float = 6.0) -> UpdateInfo:
        try:
            request = Request(
                f"https://api.github.com/repos/{self.repository}/releases",
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "TezisDesktopUpdater",
                },
            )
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return UpdateInfo(error_text=self._http_error_text(exc.code), checked_at=datetime.now())
        except URLError as exc:
            return UpdateInfo(
                error_text=f"Не удалось проверить обновления: нет ответа от сети или GitHub ({exc.reason}).",
                checked_at=datetime.now(),
            )
        except Exception as exc:  # noqa: BLE001
            return UpdateInfo(error_text=f"Не удалось проверить обновления: {exc}", checked_at=datetime.now())

        release = next((item for item in payload if not item.get("draft")), None)
        if release is None:
            return UpdateInfo(error_text="На GitHub не найден опубликованный релиз.", checked_at=datetime.now())

        tag_name = str(release.get("tag_name", APP_VERSION)).removeprefix("v")
        assets = release.get("assets") or []
        asset = next((item for item in assets if str(item.get("name", "")).endswith(".zip")), assets[0] if assets else {})
        return UpdateInfo(
            current_version=APP_VERSION,
            latest_version=tag_name,
            checked_at=datetime.now(),
            update_available=tag_name != APP_VERSION,
            release_url=str(release.get("html_url") or GITHUB_RELEASES_URL),
            asset_url=str(asset.get("browser_download_url") or ""),
            asset_name=str(asset.get("name") or ""),
        )

    @staticmethod
    def _http_error_text(status_code: int) -> str:
        if status_code == 403:
            return (
                "GitHub временно ограничил проверку обновлений (HTTP 403). "
                "Это не ломает приложение: повторите позже или откройте страницу релизов вручную."
            )
        if status_code == 404:
            return "GitHub не нашёл опубликованный release API для этого репозитория (HTTP 404)."
        if status_code >= 500:
            return f"GitHub сейчас недоступен (HTTP {status_code}). Повторите проверку позже."
        return f"GitHub вернул ошибку {status_code}."
