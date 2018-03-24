from unittest import TestCase
from threading import Event, Timer, Thread
from queue import Queue
from contextlib import contextmanager
from time import sleep
import signal
import os

from dakara_player_vlc import daemon


class TestError(Exception):
    pass


class BaseTestCase(TestCase):
    def setUp(self):
        # create stop event and errors queue
        self.stop = Event()
        self.errors = Queue()

    def function_safe(self):
        """Function that does not raise any error
        """
        return

    def function_error(self):
        """Function that raises a TestError
        """
        raise TestError('test error')

    @contextmanager
    def assertNotRaises(self, Exc):
        try:
            yield None

        except Exc:
            self.fail("{} raised".format(Exc.__name__))


class ControlledThreadTestCase(BaseTestCase):
    """Test the ControlledThread class
    """
    def create_controlled_thread(self, target):
        return daemon.ControlledThread(
                self.stop,
                self.errors,
                target=target
                )

    def test_function_safe(self):
        """Test a safe function

        Test that a non-error function does not trigger any error, does not set
        the stop event and does not put an error in the error queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create thread
        controlled_thread = self.create_controlled_thread(self.function_safe)

        # run thread
        controlled_thread.start()
        controlled_thread.join()

        # post assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

    def test_function_error(self):
        """Test an error function

        Test that an error function does not trigger any error, sets the stop
        event and puts a TestError in the error queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create thread
        controlled_thread = self.create_controlled_thread(self.function_error)

        # run thread
        with self.assertNotRaises(TestError):
            controlled_thread.start()
            controlled_thread.join()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, TestError)


class ControlledTimerTestCase(ControlledThreadTestCase):
    """Test the ControlledTimer class
    """
    def create_controlled_thread(self, target):
        return daemon.ControlledTimer(
                self.stop,
                self.errors,
                0.5,  # set a non-null delay
                target,
                )


class DaemonTestCase(BaseTestCase):
    """Test the Daemon class
    """
    def test_run_safe(self):
        """Test a safe run

        Test that a daemon used with no error does not produce any error,
        finishes with a triggered stop event and an empty error queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with daemon.Daemon(self.stop, self.errors):
            self.function_safe()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())

    def test_run_error(self):
        """Test a run with error

        Test that a daemon used with error does produce an error, finishes
        with a triggered stop event and an empty error queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with self.assertRaises(TestError):
            with daemon.Daemon(self.stop, self.errors):
                self.function_error()

        # there is no point continuing this test from here

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())

    def test_run_thread_safe(self):
        """Test a run with a safe thread

        Test that a daemon used with a non-error thread does not produce any
        error, finishes with a triggered stop event and an empty error queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with daemon.Daemon(self.stop, self.errors) as d:
            d.thread = d.create_thread(target=self.function_safe)
            d.thread.start()
            d.thread.join()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())

    def test_run_thread_error(self):
        """Test a run with a thread with error

        Test that a daemon used with a thread with an error does not produce
        any error, finishes with a triggered stop event and a non-empty error
        queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with self.assertNotRaises(TestError):
            with daemon.Daemon(self.stop, self.errors) as d:
                d.thread = d.create_thread(target=self.function_error)
                d.thread.start()
                d.thread.join()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, TestError)


class DaemonWorkerTestCase(BaseTestCase):
    """Test the DaemonWorker class
    """
    class DaemonWorkerToTest(daemon.DaemonWorker):
        def function_already_dead(self):
            """Function that ends immediately
            """
            return

        def function_to_cancel(self):
            """Function that calls itself in loop every second
            """
            self.timer = Timer(1, self.function_to_cancel)
            self.timer.start()

        def function_to_join(self):
            """Function that waits one second
            """
            sleep(1)

    def test_run_timer_dead(self):
        """Test to end a daemon when its timer is dead

        Test that a worker daemon stopped with a dead timer finishes with a
        triggered stop event, an empty error queue and a still dead timer.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with self.DaemonWorkerToTest(self.stop, self.errors) as d:
            d.timer = d.create_timer(0, d.function_already_dead)
            d.timer.start()
            d.timer.join()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(d.timer.is_alive())

    def test_run_timer_cancelled(self):
        """Test to end a deamon when its timer is waiting

        Test that a worker daemon stopped with a waiting timer finishes with a
        triggered stop event, an empty error queue and a dead timer.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with self.DaemonWorkerToTest(self.stop, self.errors) as d:
            d.timer = d.create_timer(0, d.function_to_cancel)
            d.timer.start()
            sleep(0.5)

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(d.timer.is_alive())
        self.assertTrue(d.timer.finished.is_set())

    def test_run_timer_joined(self):
        """Test to end a deamon when its timer is running

        Test that a worker daemon stopped with a running timer finishes with a
        triggered stop event, an empty error queue and a dead timer.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with self.DaemonWorkerToTest(self.stop, self.errors) as d:
            d.timer = d.create_timer(0, d.function_to_join)
            d.timer.start()
            sleep(0.5)

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(d.timer.is_alive())

    def test_unredifined_timer(self):
        """Test the timer must be redefined

        Test that a worker daemon with its default timer does not generate an
        error, but finishes with a triggered stop event and an non-empty error
        queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with self.assertNotRaises(daemon.UnredefinedTimerError):
            with self.DaemonWorkerToTest(self.stop, self.errors) as d:
                d.timer.start()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, daemon.UnredefinedTimerError)


class DaemonMasterTestCase(BaseTestCase):
    """Test the DaemonMaster class
    """
    class DaemonMasterToTest(daemon.DaemonMaster):
        def function_already_dead(self):
            """Function that ends immediately
            """
            return

        def function_to_join(self):
            """Function that waits one second
            """
            sleep(1)

    def test_run_thread_dead(self):
        """Test to end a daemon when its thread is dead

        Test that a worker daemon stopped with a dead thread finishes with a
        triggered stop event, an empty error queue and a still dead thread.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with self.DaemonMasterToTest(self.stop, self.errors) as d:
            d.thread = d.create_thread(target=d.function_already_dead)
            d.thread.start()
            d.thread.join()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(d.thread.is_alive())

    def test_run_thread_joined(self):
        """Test to end a deamon when its thread is running

        Test that a worker daemon stopped with a running thread finishes with a
        triggered stop event, an empty error queue and a dead thread.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with self.DaemonMasterToTest(self.stop, self.errors) as d:
            d.thread = d.create_thread(target=d.function_to_join)
            d.thread.start()
            sleep(0.5)

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(d.thread.is_alive())

    def test_unredifined_thread(self):
        """Test the thread must be redefined

        Test that a worker daemon with its default thread does not generate an
        error, but finishes with a triggered stop event and an non-empty error
        queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run daemon
        with self.assertNotRaises(daemon.UnredefinedThreadError):
            with self.DaemonMasterToTest(self.stop, self.errors) as d:
                d.thread.start()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, daemon.UnredefinedThreadError)


class RunnerTestCase(BaseTestCase):
    """Test the Runner class

    The class to test should leave because of a Ctrl+C, or because of an
    internal eror.
    """
    class DaemonError(daemon.Daemon):
        def init_daemon(self):
            self.thread = self.create_thread(target=self.test)

        def test(self):
            raise TestError('test error')

    def get_daemon_ready(self):
        """Get a daemon connected to an event

        This will be used for tests that produce side effects.
        """
        ready = Event()

        class DaemonReady(daemon.Daemon):
            def init_daemon(self):
                self.thread = self.create_thread(target=self.test)

            def test(self):
                ready.set()
                return

        return ready, DaemonReady

    def setUp(self):
        # create class to test
        self.runner = daemon.Runner()

    def test_run_interrupt(self):
        """Test a run with an interruption by Ctrl+C

        The run should end with a set stop event and an empty errors queue.
        """
        # pre assertions
        self.assertFalse(self.runner.stop.is_set())
        self.assertTrue(self.runner.errors.empty())

        # get the class
        ready, DaemonReady = self.get_daemon_ready()

        # prepare the sending of SIGINT to simulate a Ctrl+C
        def send_sigint():
            pid = os.getpid()
            ready.wait()
            os.kill(pid, signal.SIGINT)

        kill_thread = Thread(target=send_sigint)
        kill_thread.start()

        # call the method
        with self.assertNotRaises(KeyboardInterrupt):
            self.runner.run_safe(DaemonReady)

        # post assertions
        self.assertTrue(self.runner.stop.is_set())
        self.assertTrue(self.runner.errors.empty())
        self.assertFalse(kill_thread.is_alive())

    def test_run_error(self):
        """Test a run with an error

        The run should raise a TestError, end with a set stop event and an
        empty error queue.
        """
        # pre assertions
        self.assertFalse(self.runner.stop.is_set())
        self.assertTrue(self.runner.errors.empty())

        # call the method
        with self.assertRaises(TestError):
            self.runner.run_safe(self.DaemonError)

        # post assertions
        self.assertTrue(self.runner.stop.is_set())
        self.assertTrue(self.runner.errors.empty())
