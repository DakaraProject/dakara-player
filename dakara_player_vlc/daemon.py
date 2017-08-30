""" Daemon module

This module provides some daemon tools to daemonize a class. Among them, the
`DamonMaster` class should be unique and stands for the main daemon thread. The
`DaemonWorker` class can be multiple and stands for the various task domains to
perform within the daemon thread.

Especially, this process allows one or several `DaemonWorker` instances to have
a looping sub-thread. These sub-threads are managed by the `DaemonMaster`
instance which can stop them.

A main concept of this module is that a Python Event object is shared among the
`DaemonWorker` and the `DaemonMaster` instances. This event is reffered as the
stop event, as triggering it from anywhere leads to stop the whole daemon:

>>> from threading import Event
>>> stop = Event()
>>> daemon = DaemonMaster(stop)
>>> daemon.stop.set()
"""


import sys
from threading import Event, Timer, Thread
from queue import Queue
import logging


logger = logging.getLogger("daemon")


def stop_on_error(fun):
    """ Decorates a method whose failure implies to stop the daemon.

        Should be used within a `DaemonWorker` or a `DaemonMaster` class.

        The object must have an attribute `stop` which is an Event object. In
        case of error from the decorated method, the event is set.

        This mechanism allows to completely stop the execution of the daemon
        because an exception has been raised in a sub-thread of it. The
        excetpion is inconditionnaly shown on screen, there is no way for now to
        prevent it.
    """
    def call(self, *args, **kwargs):
        object_name = self.__class__.__name__ \
                if hasattr(self, '__class__') else 'Object'

        assert hasattr(self, 'stop'), \
                "{} must have a stop attribute".format(object_name)

        assert isinstance(self.stop, Event), \
                "Stop attribute must be of type Event"

        assert hasattr(self, 'errors'), \
                "{} must have an errors attribute".format(object_name)

        assert isinstance(self.errors, Queue), \
                "Errors attribute must be of type Queue"

        try:
            return fun(self, *args, **kwargs)

        except:
            self.stop.set()
            self.errors.put_nowait(sys.exc_info())

    return call


class Daemon:
    """ Base daemon class

        The base daemon is bound to a stop event which when triggered will stop
        the daemon. It has also an errors queue to communicate errors to the
        main thread.

        It behaves like a context manager that returns itself on enter and
        triggers the stop event on exit.

        Initialisation must be performed through the `init_daemon` method.
    """
    def __init__(self, stop, errors, *args, **kwargs):
        """ Initialization

            Cannot be modified directly by subclasses.

            Assign the mandatory stop event and errors queue to the instance.
        """
        # associate the stop event
        assert isinstance(stop, Event), "Stop attribute must be of type Event"
        self.stop = stop

        # associate the errors queue
        assert isinstance(errors, Queue), "Errors attribute must be of type Queue"
        self.errors = errors

        # perform custom actions
        self.init_daemon(*args, **kwargs)

    def init_daemon(self, *args, **kwargs):
        """ Stub for daemon custom initialization
        """
        pass

    def __enter__(self):
        """ Simple context manager enter

            Just returns the instance.
        """
        return self

    def __exit__(self, type, value, traceback):
        """ Simple context manager exit

            Just triggers the stop event.
        """
        # close daemon
        self.stop.set()

class DaemonWorker(Daemon):
    """ Worker daemon

        The worker daemon is bound to a stop event which when triggered will
        stop the daemon. It has also an errors queue to communicate errors to
        the main thread.

        It contains a timer thread `thread` already connected to the method
        `start` which has to be redefined.

        It behaves like a context manager that gives itself on enter. On exit,
        it cancels and ends its timer thread and also triggers the stop event.

        Methods should be decorated with `stop_on_error` to trigger the stop
        event if they encounter an exception during their call.

        Initialisation must be performed through the `init_worker` method.
    """
    def init_daemon(self, *args, **kwargs):
        """ Daemon initialization

            Cannot be modified directly by subclasses.

            Assign the timer thread to the instance and make it target the
            `start` method. The `start` method may call another method with a
            timer after.
        """
        # create timer for itself
        self.thread = Timer(0, self.start)

        # perform other custom actions
        self.init_worker(*args, **kwargs)

    def init_worker(self, *args, **kwargs):
        """ Stub for worker custom initialization
        """
        pass

    def start(self):
        """ Stub for the worker timer thread target
        """
        pass

    def __exit__(self, type, value, traceback):
        """ Context manager exit

            Triggers the stop event, then cancels and close its timer thread.
        """
        # stop the daemon
        self.stop.set()

        # exit now if the timer is not running
        if not self.thread.is_alive():
            return

        logger.debug("Closing worker thread '{}'".format(self.thread.getName()))

        # cancel the timer, if the timer was waiting
        self.thread.cancel()

        # wait for termination, if the timer was running
        self.thread.join()


class DaemonMaster(Daemon):
    """ Master daemon

        The master daemon is bound to a stop event which when triggered will
        stop the daemon. It has also an errors queue to communicate errors to
        the main thread.

        It contains a thread `thread` already connected to the method `run`
        which has to be redefined.

        The instance is a context manager that gives itself on enter. On exit,
        it ends its own thread and also triggers the stop event.

        Methods should be decorated with `stop_on_error` to trigger the stop
        event if they encounter an exception during their call.

        Initialisation must be performed through the `init_master` method.
    """
    def init_daemon(self, *args, **kwargs):
        """ Worker custom initialization

            Cannot be modified directly by subclasses.

            Assign its own thread to the instance and make it target the `run`
            method.
        """
        # create thread for itself
        self.thread = Thread(target=self.run)

        # perform other custom actions
        self.init_master(*args, **kwargs)

    def init_master(self, *args, **kwargs):
        """ Stub for master custom initialization
        """
        pass

    def run(self):
        """ Stub for daemon thread target
        """
        pass

    def __exit__(self, type, value, traceback):
        """ Context manager exit

            Triggers the stop event, then close its own thread.
        """
        # stop the daemon
        self.stop.set()

        # exit now if the timer is not running
        if not self.thread.is_alive():
            return

        logger.debug("Closing daemon thread '{}'".format(self.thread.getName()))

        # wait for termination
        self.thread.join()
