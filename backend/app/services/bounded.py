from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Callable, TypeVar

T = TypeVar("T")


class BoundedTimeoutError(TimeoutError):
    """Work exceeded a hard wall-clock budget; the HTTP request must not wait further."""


def run_with_timeout(func: Callable[..., T], /, *args: object, timeout: float, **kwargs: object) -> T:
    """Run ``func`` in a worker thread and raise ``BoundedTimeoutError`` if it exceeds ``timeout``.

    S0: this unblocks the caller. The worker may keep running after the timeout
    (ThreadPoolExecutor cannot kill a stuck thread). Do not use the executor as a
    context manager — ``shutdown(wait=True)`` would re-block on the hung job.
    """
    if timeout <= 0:
        raise BoundedTimeoutError("timeout must be positive")

    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="notbook-bounded")
    try:
        future = pool.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise BoundedTimeoutError(f"timed out after {timeout:g}s") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
