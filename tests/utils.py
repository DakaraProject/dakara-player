from pathlib import Path
from tempfile import gettempdir


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
