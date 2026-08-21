from pathlib import Path
from tempfile import gettempdir
from traceback import format_tb

from dakara_base.safe_workers import Worker


def assert_no_errors(worker: Worker) -> None:
    if worker.stop.is_set():
        errors = [worker.errors.get() for _ in range(worker.errors.qsize())]
        message_bits = [
            (e[0].__name__, e[1], "\n".join(format_tb(e[2]))) for e in errors
        ]
        message = "\n".join(
            f"{i}: {name}: {msg}\n{stack}"
            for i, (name, msg, stack) in enumerate(message_bits)
        )

        raise AssertionError(f"Worker {worker} is in failed state:\n{message}")


def get_temp_dir() -> Path:
    """Return the default temporary directory.

    This function fixes the problem on Windows CI where `tempfile.gettempdir`
    would return a DOS short path, not a Windows long path.

    See:
        https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file#short-vs-long-names

    Returns:
        pathlib.Path: Long path to the default temporary directory.
    """
    return Path(gettempdir()).resolve()
