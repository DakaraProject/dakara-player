"""Module to check the availability of VLC."""


def is_vlc_available() -> bool:
    try:
        import vlc

        return vlc.Instance() is not None

    except (ImportError, FileNotFoundError, OSError, NameError):
        return False
