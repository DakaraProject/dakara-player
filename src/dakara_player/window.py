"""Manage a window."""

import logging
from abc import ABC, abstractmethod
from threading import Event, Thread

try:
    import tkinter

except ImportError:
    tkinter = None


logger = logging.getLogger(__name__)


class BaseWindowManager(ABC):
    """Abstract class for window manager.

    Args:
        title (str): Title of the window.
        fullscreen (bool): If true, the window is fullscreen.
        disabled (bool): If True, no window are displayed.
    """

    GREETINGS = "Abstract window manager selected"

    @staticmethod
    @abstractmethod
    def is_available():
        """Tell if this window manager can be initialized.

        Returns:
            bool: True if the window managen can be initialized.


        Raises:
            WindowManagerNotAvailableError: If no window manager is available.
        """

    def __init__(self, title="No title", fullscreen=False, disabled=False):
        if not self.is_available():
            raise WindowManagerNotAvailableError(
                "This window manager cannot be initialized"
            )

        logger.debug(self.GREETINGS)
        self.title = title
        self.fullscreen = fullscreen
        self.disabled = disabled

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    @abstractmethod
    def open(self):
        """Open the window."""

    @abstractmethod
    def close(self):
        """Close the window."""

    @abstractmethod
    def get_id(self):
        """Get window ID.

        Retuns:
            int: ID of the window.
        """


class DummyWindowManager(BaseWindowManager):
    """Dummy window manager.

    It never creates a window and is always available.

    Args:
        title (str): Title of the window.
        fullscreen (bool): If true, the window is fullscreen.
        disabled (bool): If True, no window are displayed.
    """

    GREETINGS = "Dummy window manager selected"

    @staticmethod
    def is_available():
        """Tell if this window manager can be initialized.

        Returns:
            bool: True if the window managen can be initialized.
        """
        return True

    def open(self):
        """Open the window."""

    def close(self):
        """Close the window."""

    def get_id(self):
        """Get window ID.

        Retuns:
            int: ID of the window.
        """
        return None


class TkWindowManager(BaseWindowManager):
    """Tkinter window manager.

    Uses the Python default GUI library Tkinter.

    The window is created in a separate thread and checks every
    `ACTUALIZE_INTERVAL` if it has to close (using an event set by the `close`
    method). This indirect approach works well, even if the window doesn't
    close immediately at shutdown. A more direct approach was tried using
    `generate_event`, but this messes up the destruction order and leads to a
    crash of the interpreter. Using `quit` instead of `destroy` as a workaround
    was problematic for tests, as the method doesn't cleanup after itself,
    making inpossible to close a second window.

    See: Https://stackoverflow.com/q/66529633/4584444

    Args:
        title (str): Title of the window.
        fullscreen (bool): If true, the window is fullscreen.
        disabled (bool): If True, no window are displayed.
    """

    GREETINGS = "Tk window selected"
    ACTUALIZE_INTERVAL = 1000

    @staticmethod
    def is_available():
        """Tell if this window manager can be initialized.

        Returns:
            bool: True if the window managen can be initialized.
        """
        return tkinter is not None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window_thread = Thread(target=self.create_window)
        self.stop = Event()
        self.ready = Event()
        self.id = None

    def create_window(self):
        """Create the window.

        Must be called in its own thread.
        """

        class TkWindow(tkinter.Tk):
            """Custom Tk window."""

            def __init__(self, stop, title, fullscreen, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.stop = stop
                self.title(title)
                self.configure(width=1024, height=576, bg="black", cursor="none")
                self.resizable(True, True)
                self.attributes("-fullscreen", fullscreen)
                self.after(TkWindowManager.ACTUALIZE_INTERVAL, self.actualize)

            def actualize(self):
                """Check if the window has to be closed periodically."""
                if self.stop.is_set():
                    self.destroy()
                    return

                self.after(TkWindowManager.ACTUALIZE_INTERVAL, self.actualize)

        logger.debug("Creating Tk window thread")
        window = TkWindow(self.stop, self.title, self.fullscreen)
        self.id = window.winfo_id()

        # allow to not draw the window for testing purposes
        if self.disabled:
            window.withdraw()

        self.ready.set()
        window.mainloop()

    def open(self):
        """Open the window."""
        logger.debug("Creating Tk window")
        self.window_thread.start()

    def close(self):
        """Close the window."""
        self.ready.wait()
        logger.debug("Closing Tk window")
        self.stop.set()
        self.window_thread.join()

    def get_id(self):
        """Get window ID.

        Retuns:
            int: ID of the window.
        """
        self.ready.wait()
        logger.debug("Getting Tk window ID")
        return self.id


def get_window_manager_class():
    """Give an available window manager class.

    Returns:
        BaseWindowManager: Tries to return `TkWindowManager`, fallbacks to
        `DummyWindowManager`.
    """
    if TkWindowManager.is_available():
        return TkWindowManager

    return DummyWindowManager


WindowManager = get_window_manager_class()
"""BaseWindowManager: Available window manager class.
"""


class WindowManagerNotAvailableError(Exception):
    """Error when initializing an unavailable window manager."""
