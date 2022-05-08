import os
import platform
from queue import Queue
from threading import Event
from unittest import TestCase, skipIf, skipUnless
from unittest.mock import patch

from dakara_player.window import TkWindowManager


@skipUnless(TkWindowManager.is_available(), "Tkinter not available")
@patch.object(TkWindowManager, "ACTUALIZE_INTERVAL", 100)
class TkWindowManagerIntegrationTestCase(TestCase):
    @skipIf(
        platform.system() == "Linux" and "DISPLAY" not in os.environ,
        "No display detected on Linux",
    )
    # @skipIf(
    #     platform.system() == "Darwin",
    #     "Cannot be tested on Mac",
    # )
    def test_run_forever(self):
        """Test to open a Tk window."""
        stop = Event()
        errors = Queue()
        window_comm = Queue()
        stop.set()
        window = TkWindowManager(stop, errors, window_comm, disabled=True)
        window.run_forever()
        self.assertFalse(window_comm.empty())
        window_id = window_comm.get()
        self.assertIsNotNone(window_id)
