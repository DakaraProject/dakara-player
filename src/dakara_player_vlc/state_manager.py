from threading import Event


class State:
    """State object based on events

    The State object consists in two events: when the state starts and when it
    finishes. When the state has neither started, nor finished, it is not
    active, when it has started but not finished, it is active, and when it has
    started, and finished, it is not active. A state cannot finish before it
    started.

    The start and finish events can be waited.

    Attributes:
        started (threading.Event): Start event.
        finished (threading.Event): Finish event.
    """

    def __init__(self):
        self.started = Event()
        self.finished = Event()

    def __str__(self):
        return "started: {}, finished: {}, active: {}".format(
            self.has_started(), self.has_finished(), self.is_active()
        )

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self)

    def start(self):
        """Start the state

        It resets the state in case.
        """
        self.reset()
        self.started.set()

    def finish(self):
        """Finish the state
        """
        assert self.has_started(), "The state must have started"
        self.finished.set()

    def reset(self):
        """Reset the state

        Reset a finished state does not impact the result of `is_active`.
        """
        self.started.clear()
        self.finished.clear()

    def is_active(self):
        """Tells if the state has started, but not finished

        Returns:
            bool: True if the state has started but not finished.
        """
        return self.has_started() and not self.has_finished()

    def has_started(self):
        """Tells if the state has started.

        Returns:
            bool: True if the state has stated.
        """
        return self.started.is_set()

    def has_finished(self):
        """Tells if the state has finished.

        Returns:
            bool: True if the state has finished.
        """
        return self.finished.is_set()

    def wait_start(self, *args, **kwargs):
        """Wait for the start event to be set
        """
        self.started.wait(*args, **kwargs)

    def wait_finish(self, *args, **kwargs):
        """Wait for the finish event to be set
        """
        self.finished.wait(*args, **kwargs)
