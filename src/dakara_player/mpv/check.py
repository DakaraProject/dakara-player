"""Module to check the availability of Mpv."""

ATTEMPTS = 10


def is_mpv_available() -> bool:
    """Check if Mpv can be imported and used.

    Returns:
        bool: True if Mpv can be imported and used.
    """
    # try to import
    try:
        import python_mpv_jsonipc as mpv

    except ImportError:
        return False

    # try to use
    # do it multiple times as it can be quite capricious
    for _ in range(ATTEMPTS):
        try:
            player = mpv.MPV()
            player.terminate()
            return True

        except FileNotFoundError:
            pass

    return False
