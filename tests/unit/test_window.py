from queue import Queue
from threading import Event
from unittest import TestCase
from unittest.mock import patch

try:
    import tkinter

except ImportError:
    tkinter = None

from dakara_player.window import (
    DummyWindowManager,
    TkWindowManager,
    WindowManagerNotAvailableError,
    get_window_manager_class,
)


class DummyWindowManagerTestCase(TestCase):
    @patch.object(DummyWindowManager, "is_available", return_value=False)
    def test_init_not_available(self, mocked_is_available):
        """Test to init an unavailable window manager."""
        with self.assertRaises(WindowManagerNotAvailableError):
            DummyWindowManager(Event(), Queue(), Queue())

        mocked_is_available.assert_called_with()

    def test_run_forever(self):
        """Test to open a dummy window."""
        stop = Event()
        errors = Queue()
        window_comm = Queue()
        stop.set()
        window = DummyWindowManager(stop, errors, window_comm)
        window.run_forever()
        self.assertFalse(window_comm.empty())
        window_id = window_comm.get()
        self.assertIsNone(window_id)


class TkWindowManagerTestCase(TestCase):
    @patch("dakara_player.window.tkinter", None)
    def test_is_available_no_tkinter(self):
        """Test to check availability of Tkinter window manager without Tkinter."""
        self.assertFalse(TkWindowManager.is_available())


class GetWindowManagerClassTestCase(TestCase):
    @patch.object(TkWindowManager, "is_available", return_value=True)
    def test_get_tk_window_manager(self, mocked_is_available):
        """Test to get the Tkinter window manager."""
        self.assertIs(get_window_manager_class(), TkWindowManager)

    @patch.object(TkWindowManager, "is_available", return_value=False)
    def test_get_dummy_window_manager(self, mocked_is_available):
        """Test to get the Tkinter window manager."""
        self.assertIs(get_window_manager_class(), DummyWindowManager)
