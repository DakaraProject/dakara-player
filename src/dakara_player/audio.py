"""Manage audio files independently of the media player."""

import filetype


def get_audio_files(filepath):
    """Get audio files with the same name as provided file.

    Args:
        filepath (pathlib.Path): Path of the initial file.

    Returns:
        list of pathlib.Path: List of paths of audio files.
    """
    # list files with similar stem
    items = filepath.parent.glob(f"{filepath.stem}.*")
    return [item for item in items if item != filepath and is_audio_file(item)]


def is_audio_file(file_path):
    """Detect if a file is audio file based on standard magic numbers.

    Args:
        file_path (pathlib.Path): Path of the file to investigate.

    Returns:
        bool: `True` if the file is an audio file, `False` otherwise.
    """
    kind = filetype.guess(str(file_path))
    if not kind:
        return False

    maintype, _ = kind.mime.split("/")

    return maintype == "audio"
