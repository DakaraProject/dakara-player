import logging
from abc import ABC, abstractmethod
from threading import Thread, Event

try:
    import tkinter

except ImportError:
    tkinter = None


logger = logging.getLogger(__name__)


def get_window_manager_class():
    if TkWindowManager.is_available():
        return TkWindowManager

    return DummyWindowManger


class BaseWindowManager(ABC):
    GREETINGS = "Abstract window manager selected"

    @staticmethod
    @abstractmethod
    def is_available():
        pass

    def __init__(self, stop, errors, title="No title", fullscreen=False):
        if not self.is_available():
            raise Exception("not available")

        logger.debug(self.GREETINGS)

        self.stop = stop
        self.errors = errors

    @abstractmethod
    def open(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def get_id(self):
        pass


class DummyWindowManger(BaseWindowManager):
    GREETINGS = "Dummy window manager selected"

    @staticmethod
    def is_available():
        return True

    def open(self):
        pass

    def close(self):
        pass

    def get_id(self):
        return None


class TkWindowManager(BaseWindowManager):
    GREETINGS = "Tk window selected"
    STOP_PROGRAM_EVENT = "<<stop_program>>"

    class TkWindow:
        def __init__(self, title, fullscreen):
            self.root = tkinter.Tk()
            self.root.title(title)
            self.root.configure(width=800, height=600, bg="black", cursor="none")
            self.root.resizable(True, True)
            self.root.attributes("-fullscreen", fullscreen)
            self.root.bind(TkWindowManager.STOP_PROGRAM_EVENT, self.close)
            self.id = self.root.winfo_id()

        def close(self, event):
            self.root.destroy()

    @staticmethod
    def is_available():
        return tkinter is not None

    def __init__(self, *args, title="No title", fullscreen=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.fullscreen = fullscreen
        self.window = None
        self.window_thread = Thread(target=self.create_window)
        self.ready = Event()

    def create_window(self):
        logger.debug("Creating Tk window thread")
        self.window = self.TkWindow(self.title, self.fullscreen)
        self.ready.set()
        self.window.root.mainloop()

    def open(self):
        logger.debug("Creating Tk window")
        self.window_thread.start()

    def close(self):
        self.ready.wait()
        logger.debug("Closing Tk window")
        self.window.root.event_generate(self.STOP_PROGRAM_EVENT)
        self.window_thread.join()

    def get_id(self):
        self.ready.wait()
        logger.debug("Getting Tk window ID")
        return self.window.id
