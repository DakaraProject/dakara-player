import sys
import os
from importlib import reload
from unittest import TestCase, skipIf, skipUnless
from unittest.mock import patch

try:
    import tkinter

except ImportError:
    tkinter = None

from dakara_player.window import (
    DummyWindowManager,
    TkWindowManager,
    WindowManagerNotAvailableError,
)


class DummyWindowManagerTestCase(TestCase):
    """Test the dummy window manager
    """

    @patch.object(DummyWindowManager, "is_available", return_value=False)
    def test_init_not_available(self, mocked_is_available):
        """Test to init an unavailable window manager
        """
        with self.assertRaises(WindowManagerNotAvailableError):
            DummyWindowManager(None, None)

        mocked_is_available.assert_called_with()

    def test_open_close(self):
        """Test to open and close dummy window
        """
        with DummyWindowManager():
            pass

    def test_get_id(self):
        """Test to get dummy window ID
        """
        with DummyWindowManager() as window_manager:
            self.assertIsNone(window_manager.get_id())


@skipUnless(TkWindowManager.is_available(), "Tkinter not available")
@patch.object(TkWindowManager, "ACTUALIZE_INTERVAL", 100)
class TkWindowManagerTestCase(TestCase):
    """Test the Tkinter window manager
    """

    @patch("dakara_player.window.tkinter", None)
    def test_is_available_no_tkinter(self):
        """Test to check availability of Tkinter window manager without Tkinter
        """
        self.assertFalse(TkWindowManager.is_available())

    def test_open_close(self):
        """Test to open and close Tk window
        """
        reload(tkinter)
        with TkWindowManager(disabled=True):
            pass

    @skipIf(
        "linux" in sys.platform and "DISPLAY" not in os.environ,
        "No display detected on Linux",
    )
    def test_get_id(self):
        """Test to get Tk window ID
        """
        reload(tkinter)
        with TkWindowManager(disabled=True) as window_manager:
            self.assertIsNotNone(window_manager.get_id())
