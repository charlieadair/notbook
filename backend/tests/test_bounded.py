import time

import pytest

from app.services.bounded import BoundedTimeoutError, run_with_timeout


def _quick(value: str) -> str:
    return value


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def test_run_with_timeout_returns_result():
    assert run_with_timeout(_quick, "ok", timeout=1.0) == "ok"


def test_run_with_timeout_raises_within_budget():
    start = time.monotonic()
    with pytest.raises(BoundedTimeoutError, match="timed out"):
        run_with_timeout(_sleep, 5.0, timeout=0.25)
    elapsed = time.monotonic() - start
    assert elapsed < 1.5
