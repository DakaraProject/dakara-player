"""Manage MRL."""

import pathlib
from urllib.parse import unquote, urlparse

from path import Path


def mrl_to_path(file_mrl):
    """Convert a MRL to a filesystem path.

    File path is stored as MRL inside a media object, we have to bring it back
    to a more classic looking path format.

    Args:
        file_mrl (str): Path to the resource within MRL format.

    Returns:
        path.Path: Path to the resource.
    """
    path_string = unquote(urlparse(file_mrl).path)

    # remove first '/' if a colon character is found like in '/C:/a/b'
    if path_string[0] == "/" and path_string[2] == ":":
        path_string = path_string[1:]

    return Path(path_string).normpath()


def path_to_mrl(file_path):
    """Convert a filesystem path to MRL.

    Args:
        file_path (path.Path or str): Path to the resource.

    Returns:
        str: Path to the resource within MRL format.
    """
    return pathlib.Path(file_path).as_uri()
