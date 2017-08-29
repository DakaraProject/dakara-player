from threading import Event, Timer, Thread
import logging


logger = logging.getLogger("daemon")


def stop_on_error(fun):
    """ Decorates a method whose failure implies to stop the daemon.

        The object must have an attribute `stop` which is an Event object. In
        case of error from the decorated method, the event is set.
    """
    def call(self, *args, **kwargs):
        object_name = self.__class__.__name__ \
                if hasattr(self, '__class__') else 'Object'

        assert hasattr(self, 'stop'), \
                "{} class must have stop attribute".format(object_name)

        assert isinstance(self.stop, Event), \
                "Stop attribute must be of type Event"

        try:
            return fun(self, *args, **kwargs)

        except:
            self.stop.set()
            raise

    return call


class DaemonWorker:
    def __init__(self, stop, *args, **kwargs):
        # associate the stop event
        assert isinstance(stop, Event), "Stop attribute must be of type Event"
        self.stop = stop

        # perform custom actions
        self.init_worker(*args, **kwargs)

    def init_worker(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass


class DaemonMaster(DaemonWorker):
    def init_worker(self, *args, **kwargs):
        # create empty pool of threads
        self.threads = []

        # create thread for itself
        self.thread = Thread(target=self.run)

        # perform other custom actions
        self.init_master(*args, **kwargs)

    def init_master(self, *args, **kwargs):
        pass

    def run(self):
        pass

    def __exit__(self, type, value, traceback):
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
