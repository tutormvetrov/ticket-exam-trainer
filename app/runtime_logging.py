from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading


_LOG_FORMAT = "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"
_HANDLER_MARKER = "_tezis_runtime_kind"
_FILE_HANDLER_KIND = "file"
_STREAM_HANDLER_KIND = "stream"

_CONFIG_LOCK = threading.Lock()
_HOOKS_INSTALLED = False
_PREVIOUS_SYS_EXCEPTHOOK = sys.excepthook
_PREVIOUS_THREAD_EXCEPTHOOK = getattr(threading, "excepthook", None)


def get_log_path(workspace_root: Path) -> Path:
    return Path(workspace_root) / "app_data" / "tezis.log"


def setup_runtime_logging(workspace_root: Path, *, component: str) -> Path:
    log_path = get_log_path(workspace_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with _CONFIG_LOCK:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        _reconfigure_file_handler(root_logger, log_path)
        _ensure_stream_handler(root_logger)
        logging.captureWarnings(True)
        _install_exception_hooks()

    logging.getLogger(__name__).info(
        "Runtime logging ready component=%s log_path=%s",
        component,
        log_path,
    )
    return log_path


def _reconfigure_file_handler(root_logger: logging.Logger, log_path: Path) -> None:
    desired = str(log_path.resolve())
    for handler in list(root_logger.handlers):
        if getattr(handler, _HANDLER_MARKER, None) != _FILE_HANDLER_KIND:
            continue
        if getattr(handler, "baseFilename", "") == desired:
            return
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    file_handler = RotatingFileHandler(
        desired,
        maxBytes=1_048_576,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    setattr(file_handler, _HANDLER_MARKER, _FILE_HANDLER_KIND)
    root_logger.addHandler(file_handler)


def _ensure_stream_handler(root_logger: logging.Logger) -> None:
    if getattr(sys, "frozen", False):
        return
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    for handler in root_logger.handlers:
        if getattr(handler, _HANDLER_MARKER, None) == _STREAM_HANDLER_KIND:
            return

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    setattr(stream_handler, _HANDLER_MARKER, _STREAM_HANDLER_KIND)
    root_logger.addHandler(stream_handler)


def _install_exception_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return

    def _sys_hook(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            if _PREVIOUS_SYS_EXCEPTHOOK is not None:
                _PREVIOUS_SYS_EXCEPTHOOK(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger("tezis.crash").critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        if _PREVIOUS_SYS_EXCEPTHOOK is not None and _PREVIOUS_SYS_EXCEPTHOOK is not _sys_hook:
            try:
                _PREVIOUS_SYS_EXCEPTHOOK(exc_type, exc_value, exc_traceback)
            except Exception:
                pass

    sys.excepthook = _sys_hook

    if _PREVIOUS_THREAD_EXCEPTHOOK is not None:
        def _thread_hook(args) -> None:
            if issubclass(args.exc_type, KeyboardInterrupt):
                _PREVIOUS_THREAD_EXCEPTHOOK(args)
                return
            thread_name = args.thread.name if args.thread is not None else "unknown"
            logging.getLogger("tezis.crash").critical(
                "Uncaught thread exception thread=%s",
                thread_name,
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            if _PREVIOUS_THREAD_EXCEPTHOOK is not _thread_hook:
                try:
                    _PREVIOUS_THREAD_EXCEPTHOOK(args)
                except Exception:
                    pass

        threading.excepthook = _thread_hook

    _HOOKS_INSTALLED = True
