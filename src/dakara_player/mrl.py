"""Manage MRL."""

from pathlib import Path
from urllib.parse import unquote, urlparse


def mrl_to_path(file_mrl: str) -> Path:
    """Convert a MRL to a filesystem path.

    VLC stores file paths as MRL, we have to bring it back to a more classic
    looking path format.

    Args:
        file_mrl (str): Path to the resource within MRL format.

    Returns:
        pathlib.Path: Path to the resource.
    """
    # TODO Replace by pathlib.Path.from_uri() available in Python 3.13
    path_string = unquote(urlparse(file_mrl).path)

    # remove first '/' if a colon character is found like in '/C:/a/b'
    if path_string[0] == "/" and path_string[2] == ":":
        path_string = path_string[1:]

    return Path(path_string).resolve()
