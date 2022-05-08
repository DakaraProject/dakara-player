"""Manage a window."""

import logging
import platform
from abc import ABC, abstractmethod

try:
    import tkinter

except ImportError:
    tkinter = None

from dakara_base.safe_workers import wait

from dakara_player.mac import load_get_ns_view

logger = logging.getLogger(__name__)


class BaseWindowManager(ABC):
    """Abstract class for window manager.

    When ready, the window will send its ID through the window queue, so that
    other parts of the program can access it.

    Args:
        stop (threading.Event): Stop event to close the program.
        errors (queue.Queue): Errors queue.
        comm (queue.Queue): Communication queue for the window.
        title (str): Title of the window.
        fullscreen (bool): If `True`, the window is fullscreen.
        disabled (bool): If `True`, no window are displayed.
    """

    GREETINGS = "Abstract window manager selected"

    @staticmethod
    @abstractmethod
    def is_available():
        """Tell if this window manager can be initialized.

        Returns:
            bool: `True` if the window managen can be initialized.
        """

    def __init__(
        self, stop, errors, comm, title="No title", fullscreen=False, disabled=False
    ):
        if not self.is_available():
            raise WindowManagerNotAvailableError(
                "This window manager cannot be initialized"
            )

        logger.debug(self.GREETINGS)
        self.stop = stop
        self.errors = errors
        self.comm = comm
        self.title = title
        self.fullscreen = fullscreen
        self.disabled = disabled

    @abstractmethod
    def run_forever(self):
        """Open the window indefinitely.

        It will close by itself or if reqested by the program when the stop
        event is set."""


class DummyWindowManager(BaseWindowManager):
    """Dummy window manager.

    It never creates a window and is always available. The window ID sent
    through the window queue is always `None`.

    Args:
        stop (threading.Event): Stop event to close the program.
        errors (queue.Queue): Errors queue.
        comm (queue.Queue): Communication queue for the window.
        title (str): Title of the window.
        fullscreen (bool): If `True`, the window is fullscreen.
        disabled (bool): If `True`, no window are displayed.
    """

    GREETINGS = "Dummy window manager selected"

    @staticmethod
    def is_available():
        return True

    def run_forever(self):
        # sending dummy ID to communication queue
        self.comm.put(None)

        # blocking loop
        wait(self.stop)


class TkWindowManager(BaseWindowManager):
    """Tkinter window manager.

    Uses the Python default GUI library Tkinter.

    The window is created in the same thread and checks every
    `ACTUALIZE_INTERVAL` if it has to close. This indirect approach works well,
    even if the window doesn't close immediately at shutdown. A more direct
    approach was tried using `generate_event`, but this messes up the
    destruction order and leads to a crash of the interpreter. Using `quit`
    instead of `destroy` as a workaround was problematic for tests, as the
    method doesn't cleanup after itself, making impossible to close a second
    window.

    The window has to be run in the main thread for Mac support, as AppKit
    requires it for the GUI.

    See:
        https://stackoverflow.com/q/66529633/4584444

    Args:
        stop (threading.Event): Stop event to close the program.
        errors (queue.Queue): Errors queue.
        comm (queue.Queue): Communication queue for the window.
        title (str): Title of the window.
        fullscreen (bool): If `True`, the window is fullscreen.
        disabled (bool): If `True`, no window are displayed.
    """

    GREETINGS = "Tk window selected"
    ACTUALIZE_INTERVAL = 1000

    @staticmethod
    def is_available():
        return tkinter is not None

    def run_forever(self):
        system = platform.system()

        if system == "Darwin":
            # load the function to get NSView from window ID and also load the
            # appropriate Tk library
            get_ns_view, found = load_get_ns_view()

            if not found:
                logger.error("Failed to load the Tk library")

        class TkWindow(tkinter.Tk):
            """Custom Tk window."""

            def __init__(self2, stop, errors, title, fullscreen, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self2.stop = stop
                self2.errors = errors
                self2.title(title)
                self2.configure(width=1024, height=576, bg="black", cursor="none")
                self2.resizable(True, True)
                self2.attributes("-fullscreen", fullscreen)
                self2.after(self.ACTUALIZE_INTERVAL, self2.actualize)

                # if the window is closed
                self2.protocol("WM_DELETE_WINDOW", self2.on_close)

            def actualize(self2):
                """Check if the window has to be closed periodically."""
                if self2.stop.is_set():
                    self2.destroy()
                    return

                self2.after(self.ACTUALIZE_INTERVAL, self2.actualize)

            def on_close(self2):
                """Signal the application to close if the window is closed."""
                self2.errors.put(None)
                self2.stop.set()
                self2.destroy()

            def destroy(self2):
                logger.debug("Closing Tk window")
                super().destroy()

        logger.debug("Creating Tk window")
        window = TkWindow(self.stop, self.errors, self.title, self.fullscreen)

        # sending ID to communication queue
        if platform.system() == "Darwin":
            self.comm.put(get_ns_view(window.winfo_id()))

        else:
            self.comm.put(window.winfo_id())

        # allow to not draw the window for testing purposes
        if self.disabled:
            window.withdraw()

        # blocking loop
        window.mainloop()


def get_window_manager_class():
    """Give an available window manager class.

    Returns:
        BaseWindowManager: Tries to return `TkWindowManager`, fallbacks to
        `DummyWindowManager`.
    """
    if TkWindowManager.is_available():
        return TkWindowManager

    return DummyWindowManager


class WindowManagerNotAvailableError(Exception):
    """Error when initializing an unavailable window manager."""
