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


from threading import Event, Timer, Thread
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

        try:
            return fun(self, *args, **kwargs)

        except:
            self.stop.set()
            raise

    return call


class DaemonWorker:
    """ Worker daemon

        The worker is bound to a stop event which when triggered will stop the
        daemon.

        Methods should be decorated with `stop_on_error` to stop the daemon if
        the they encounter an exception during their call.

        The instance is a context manager that simply gives itself on enter and
        does nothing on exit.

        Initialisation must be performed through the `init_worker` method.
    """
    def __init__(self, stop, *args, **kwargs):
        """ Initialization

            Cannot be modified directly by subclasses.

            Assign the mandatory stop event to the instance.
        """
        # associate the stop event
        assert isinstance(stop, Event), "Stop attribute must be of type Event"
        self.stop = stop

        # perform custom actions
        self.init_worker(*args, **kwargs)

    def init_worker(self, *args, **kwargs):
        """ Stub for worker custom initialization
        """
        pass

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass


class DaemonMaster(DaemonWorker):
    """ Master daemon

        The master daemon is a special worker daemon. It is bound to a stop
        event which when triggered will stop the daemon.

        The master daemon contains a pool of threads and its own thread, that
        should start its `run` method.

        The `run` method is designed to be called within the context manager
        offered by the class.

        Methods should be decorated with `stop_on_error` to stop the daemon if
        they encounter an exception during their call.

        The instance is a context manager that gives itself on enter and closes
        all the thread pool members as well as its own thread on exit. Exiting
        the context manager also triggers the stop event.

        Initialisation must be performed through the `init_master` method.
    """
    def init_worker(self, *args, **kwargs):
        """ Worker custom initialization

            Cannot be modified directly by subclasses.

            It creates the pool of threads controlled by the master daemon and
            its own thread.
        """
        # create empty pool of threads
        self.threads = []

        # create thread for itself
        self.thread = Thread(target=self.run)

        # perform other custom actions
        self.init_master(*args, **kwargs)

    def init_master(self, *args, **kwargs):
        """ Stub for master custom initialization
        """
        pass

    def run(self):
        """ Stub for daemon run
        """
        pass

    def __exit__(self, type, value, traceback):
        """ Exit the context manager

            Make sure to terminate all threads in the pool, terminate its own
            thread and trigger the stop event.
        """
        # request all threads to close
        threads_amount = len(self.threads)
        for index, thread in enumerate(self.threads):
            logger.debug("Closing thread '{}' {} of {}".format(
                thread.getName(),
                index + 1,
                threads_amount
                ))

            # leave if the thread is not running
            if not thread.is_alive():
                continue

            # cancel if the thread is a timer
            if isinstance(thread, Timer):
                thread.cancel()

            # in all case, wait for termination
            thread.join()

        # stop the daemon
        self.stop.set()

        # requeste to stop its own thread
        self.thread.join()
