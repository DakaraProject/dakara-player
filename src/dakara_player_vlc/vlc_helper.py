import os
from unittest.mock import patch


def init():
    # patch for Windows with Python > 3.8
    if not hasattr(os, "add_dll_directory"):
        return

    with patch("ctypes.CDLL") as mocked_cdll:
        # at some point, vlc.py checks something in ctypes.CDLL.__name__
        mocked_cdll.__name__ = ""

        from vlc import find_lib

        # obtain plugin_path and add it to dll directories
        _, plugin_path = find_lib()
        os.add_dll_directory(plugin_path)
