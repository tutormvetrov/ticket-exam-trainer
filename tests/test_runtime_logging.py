from __future__ import annotations

import logging


def test_setup_runtime_logging_creates_file_and_writes_message(tmp_path) -> None:
    from app.runtime_logging import get_log_path, setup_runtime_logging

    log_path = setup_runtime_logging(tmp_path, component="pytest")
    message = "runtime logging smoke marker"

    logging.getLogger("tests.runtime_logging").info(message)
    for handler in logging.getLogger().handlers:
        flush = getattr(handler, "flush", None)
        if callable(flush):
            flush()

    assert log_path == get_log_path(tmp_path)
    assert log_path.exists()
    assert message in log_path.read_text(encoding="utf-8")
