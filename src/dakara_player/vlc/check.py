"""Module to check the availability of VLC."""


def is_vlc_available() -> bool:
    """Check if VLC can be imported and used.

    This is trickier than it sounds, as on some machine, importing `python-vlc`
    without having VLC installed triggers a `FileNotFoundError`, whereas on
    some others (GitHub Windows CI servers), the import is fine, but creating a
    VLC object triggers a `NameError`. On some other cases (Appveyor Windows CI
    servers?), creting objects is fine, but they are `None` (this is the case
    for `vlc.Instance()`.

    Returns:
        bool: True if VLC can be imported and used.
    """
    try:
        import vlc

        return vlc.Instance() is not None

    except (ImportError, FileNotFoundError, OSError, NameError):
        return False
