""" Daemon module

This module provides some daemon tools to daemonize a class. Among them, the
`Daemon` class prodives control for threads and timer threads. Especially, it
guarantees that a failure in a thread will be notified in the entire program.
The `DaemonMaster` class enhances this control by binding one thread and notify
it to close if necessary. The `DaemonWorker` is similar, but for one timer
thread.

These classes can be used as context managers. If so, they set the stop event
on exit.

A main concept of this module is that a Python Event object is shared among the
`Daemon`, `DaemonWorker` and `DaemonMaster` instances. This event is reffered
as the stop event, as it can be used to stop the program.

>>> from threading import Event
>>> from queue import Queue
>>> stop = Event()
>>> errors = Queue()
>>> daemon = Daemon(stop, errors)
>>> daemon_worker = DaemonWorker(stop, errors)
>>> daemon_master = DaemonMaster(stop, errors)
>>> daemon.stop.set()
>>> daemon_master.stop.is_set()
"""


import sys
from threading import Event, Timer, Thread
from queue import Queue
import logging


logger = logging.getLogger("daemon")


class BaseControlledThread:
    """ Base class for thread executed within a Daemon

        The thread is connected to the stop event and the error queue. In case
        of failure from the threaded function, the stop event is set and the
        exception is put in the error queue. The thread closes immediatlely.

        This mechanism allows to completely stop the execution of the program
        if an exception has been raised in a sub-thread. The excetpion is not
        shown on screen but passed to the main thread.

        This class is abstract and must be inherited with either
        `theading.Thread` or `threading.Timer`.

        Attributes:
            stop (threading.Event): stop event that notify to stop the entire
                program when set.
            errors (queue.Queue): error queue to communicate the exception to
                the main thread.
    """
    def __init__(self, stop, errors, *args, **kwargs):
        # check arguments are valid
        assert isinstance(stop, Event), \
            "Stop argument must be of type Event"

        assert isinstance(errors, Queue), \
            "Errors argument must be of type Queue"

        # assign stop event and error queue
        self.stop = stop
        self.errors = errors

        # specific initialization
        super().__init__(*args, **kwargs)

    def run(self):
        """ Method to run as a thread.

            Any exception is caught and put in the error queue. This sets the
            stop event as well.
        """
        # try to run the target
        try:
            return super().run()

        # if an error occurs, put it in the error queue and notify the stop
        # event
        except:
            self.errors.put_nowait(sys.exc_info())
            self.stop.set()


class ControlledThread(BaseControlledThread, Thread):
    """ Thread executed within a Daemon

        The thread is connected to the stop event and the error queue. In case
        of failure from the threaded function, the stop event is set and the
        exception is put in the error queue. The thread closes immediatlely.

        This mechanism allows to completely stop the execution of the program
        if an exception has been raised in a sub-thread. The excetpion is not
        shown on screen but passed to the main thread.

        Attributes:
            stop (threading.Event): stop event that notify to stop the entire
                program when set.
            errors (queue.Queue): error queue to communicate the exception to
                the main thread.

        Consult the help of `threading.Thread` for more information.
    """
    pass


class ControlledTimer(BaseControlledThread, Timer):
    """ Timer thread executed within a Daemon

        The timer thread is connected to the stop event and the error queue. In
        case of failure from the threaded function, the stop event is set and
        the exception is put in the error queue. The timer thread closes
        immediatlely.

        This mechanism allows to completely stop the execution of the program
        if an exception has been raised in a timer sub-thread. The excetpion is
        not shown on screen but passed to the main thread.

        Attributes:
            stop (threading.Event): stop event that notify to stop the entire
                program when set.
            errors (queue.Queue): error queue to communicate the exception to
                the main thread.

        Consult the help of `threading.timer` for more information.
    """
    pass


class Daemon:
    """ Base daemon class

        The base daemon is bound to a stop event which when triggered will stop
        the program. It has also an errors queue to communicate errors to the
        main thread.

        It behaves like a context manager that returns itself on enter and
        triggers the stop event on exit.

        New thread should be created with the `create_thread` method and new
        thread timer with the `create_timer` method.

        Extra actions for context manager enter and exit should be put in the
        `enter_daemon` and `exit_daemon` methods.

        Initialisation must be performed through the `init_daemon` method.

        Attributes:
            stop (threading.Event): stop event that notify to stop the entire
                program when set.
            errors (queue.Queue): error queue to communicate the exception to
                the main thread.
    """
    def __init__(self, stop, errors, *args, **kwargs):
        """ Initialization

            Cannot be modified directly by subclasses.

            Assign the mandatory stop event and errors queue to the instance.

            Args:
                stop (threading.Event): stop event that notify to stop the
                    entire program when set.
                errors (queue.Queue): error queue to communicate the exception
                    to the main thread.
        """
        # associate the stop event
        assert isinstance(stop, Event), \
            "Stop attribute must be of type Event"
        self.stop = stop

        # associate the errors queue
        assert isinstance(errors, Queue), \
            "Errors attribute must be of type Queue"
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
        # custom enter action
        self.enter_daemon()

        return self

    def enter_daemon(self):
        """ Stub for enterig the daemon context manager.
        """
        pass

    def __exit__(self, type, value, traceback):
        """ Simple context manager exit.

            Just triggers the stop event.
        """
        # notify the stop event
        self.stop.set()

        # custom exit action
        self.exit_daemon(type, value, traceback)

    def exit_daemon(self, type, value, traceback):
        """ Stub for exiting the daemon context manager.
        """
        pass

    def create_thread(self, *args, **kwargs):
        """ Helper to easily create a ControlledThread object.

            Returns:
                ControlledThread: secured thread instance.
        """
        return ControlledThread(self.stop, self.errors, *args, **kwargs)

    def create_timer(self, *args, **kwargs):
        """ Helper to easily create a ControlledTimer object.

            Returns:
                ControlledTimer: secured timer thread instance.
        """
        return ControlledTimer(self.stop, self.errors, *args, **kwargs)


class DaemonWorker(Daemon):
    """ Worker daemon

        The worker daemon is bound to a stop event which when triggered will
        stop the program. It has also an errors queue to communicate errors to
        the main thread.

        It contains a timer thread `timer` already connected to the method
        `start` which has to be redefined.

        It behaves like a context manager that gives itself on enter. On exit,
        it cancels and ends its timer thread and also triggers the stop event.

        New thread timer should be created with the `create_timer` method.

        Extra actions for context manager enter and exit should be put in the
        `enter_worker` and `exit_worker` methods.

        Initialisation must be performed through the `init_worker` method.

        Attributes:
            stop (threading.Event): stop event that notify to stop the entire
                program when set.
            errors (queue.Queue): error queue to communicate the exception to
                the main thread.
            timer (threading.Timer): timer thread bound to the `start` method.
    """
    def init_daemon(self, *args, **kwargs):
        """ Daemon initialization

            Cannot be modified directly by subclasses.

            Assign the timer thread to the instance and make it target the
            `start` method. The `start` method may call another method with a
            timer after.
        """
        # create timer for itself
        self.timer = self.create_timer(0, self.start)

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

    def enter_daemon(self):
        """ Daemon context manager enter.

            Just call the worker context manager enter method.
        """
        self.enter_worker()

    def enter_worker(self):
        """ Stub for worker context manager enter.
        """
        pass

    def exit_daemon(self, type, value, traceback):
        """ Daemon context manager exit.

            Triggers the stop event, then cancels and close its timer thread.
            It calls the worker context manager method.
        """
        # notify the stop event
        self.stop.set()

        # exit now if the timer is not running
        if not self.timer.is_alive():
            return

        logger.debug("Closing worker timer thread '{}' ({})".format(
            self.timer.getName(),
            self.__class__.__name__
            ))

        # cancel the timer, if the timer was waiting
        self.timer.cancel()

        # wait for termination, if the timer was running
        self.timer.join()

        # custom exit
        self.exit_worker(type, value, traceback)

    def exit_worker(self, type, value, traceback):
        """ Stub for worker context manager exit.
        """
        pass


class DaemonMaster(Daemon):
    """ Master daemon

        The master daemon is bound to a stop event which when triggered will
        stop the program. It has also an errors queue to communicate errors to
        the main thread.

        It contains a thread `thread` already connected to the method `run`
        which has to be redefined.

        The instance is a context manager that gives itself on enter. On exit,
        it ends its own thread and also triggers the stop event.

        New thread should be created with the `create_thread` method.

        Extra actions for context manager enter and exit should be put in the
        `enter_master` and `exit_master` methods.

        Initialisation must be performed through the `init_master` method.

        Attributes:
            stop (threading.Event): stop event that notify to stop the entire
                program when set.
            errors (queue.Queue): error queue to communicate the exception to
                the main thread.
            thread (threading.Thread): thread bound to the `run` method.
    """
    def init_daemon(self, *args, **kwargs):
        """ Worker custom initialization

            Cannot be modified directly by subclasses.

            Assign its own thread to the instance and make it target the `run`
            method.
        """
        # create thread for itself
        self.thread = self.create_thread(target=self.run)

        # perform other custom actions
        self.init_master(*args, **kwargs)

    def init_master(self, *args, **kwargs):
        """ Stub for master custom initialization
        """
        pass

    def run(self):
        """ Stub for master thread target
        """
        pass

    def enter_daemon(self):
        """ Daemon context manager enter.

            Just call the master context manager enter method.
        """
        self.enter_master()

    def enter_master(self):
        """ Stub for master context manager enter.
        """
        pass

    def exit_daemon(self, type, value, traceback):
        """ Daemon context manager exit

            Triggers the stop event, then close its own thread. It calls the
            worker context manager method.

        """
        # notify the stop event
        self.stop.set()

        # exit now if the thread is not running
        if not self.thread.is_alive():
            return

        logger.debug("Closing daemon thread '{}' ({})".format(
            self.thread.getName(),
            self.__class__.__name__
            ))

        # wait for termination
        self.thread.join()

        # custom exit action
        self.exit_master(type, value, traceback)

    def exit_master(self, type, value, traceback):
        """ Stub for master context manager exit.
        """
        pass
