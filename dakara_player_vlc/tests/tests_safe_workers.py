from unittest import TestCase, skipIf
from threading import Event, Timer, Thread
from queue import Queue
from contextlib import contextmanager
from time import sleep
import signal
import os
import sys

from dakara_player_vlc.safe_workers import (
    SafeThread,
    SafeTimer,
    Worker,
    WorkerSafeThread,
    WorkerSafeTimer,
    Runner,
    UnredefinedThreadError,
    UnredefinedTimerError,
)


class TestError(Exception):
    """Dummy error class
    """
    pass


class BaseTestCase(TestCase):
    """Generic test case

    It includes some dummy functions a new assertion method.
    """
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
    def assertNotRaises(self, ExceptionClass):
        """Assert that the provided exception does not raise

        Args:
            ExceptionClass (class): class of the exception.
        """
        try:
            yield None

        except ExceptionClass:
            self.fail("{} raised".format(ExceptionClass.__name__))


class SafeThreadTestCase(BaseTestCase):
    """Test the SafeThread class
    """
    def create_controlled_thread(self, target):
        """Helper to create a safe thread for a target function
        """
        return SafeThread(
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


class SafeTimerTestCase(SafeThreadTestCase):
    """Test the SafeTimer class
    """
    def create_controlled_thread(self, target):
        """Helper to create a safe timer thread for a target function

        The delay is non null (0.5 s).
        """
        return SafeTimer(
            self.stop,
            self.errors,
            0.5,  # set a non-null delay
            target,
        )


class WorkerTestCase(BaseTestCase):
    """Test the Worker class
    """
    def test_run_safe(self):
        """Test a safe run

        Test that a worker used with no error does not produce any error,
        finishes with a triggered stop event and an empty error queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with Worker(self.stop, self.errors):
            self.function_safe()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())

    def test_run_error(self):
        """Test a run with error

        Test that a worker used with error does produce an error, finishes
        with a triggered stop event and an empty error queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with self.assertRaises(TestError):
            with Worker(self.stop, self.errors):
                self.function_error()

        # there is no point continuing this test from here

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())

    def test_run_thread_safe(self):
        """Test a run with a safe thread

        Test that a worker used with a non-error thread does not produce any
        error, finishes with a triggered stop event and an empty error queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with Worker(self.stop, self.errors) as worker:
            worker.thread = worker.create_thread(target=self.function_safe)
            worker.thread.start()
            worker.thread.join()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())

    def test_run_thread_error(self):
        """Test a run with a thread with error

        Test that a worker used with a thread with an error does not produce
        any error, finishes with a triggered stop event and a non-empty error
        queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with self.assertNotRaises(TestError):
            with Worker(self.stop, self.errors) as worker:
                worker.thread = worker.create_thread(
                    target=self.function_error
                )
                worker.thread.start()
                worker.thread.join()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, TestError)


class WorkerSafeTimerTestCase(BaseTestCase):
    """Test the WorkerSafeTimer class
    """
    class WorkerSafeTimerToTest(WorkerSafeTimer):
        """Dummy worker class
        """
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
        """Test to end a worker when its timer is dead

        Test that a worker worker stopped with a dead timer finishes with a
        triggered stop event, an empty error queue and a still dead timer.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with self.WorkerSafeTimerToTest(self.stop, self.errors) as worker:
            worker.timer = worker.create_timer(0, worker.function_already_dead)
            worker.timer.start()
            worker.timer.join()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(worker.timer.is_alive())

    def test_run_timer_cancelled(self):
        """Test to end a deamon when its timer is waiting

        Test that a worker worker stopped with a waiting timer finishes with a
        triggered stop event, an empty error queue and a dead timer.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with self.WorkerSafeTimerToTest(self.stop, self.errors) as worker:
            worker.timer = worker.create_timer(0, worker.function_to_cancel)
            worker.timer.start()
            sleep(0.5)

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(worker.timer.is_alive())
        self.assertTrue(worker.timer.finished.is_set())

    def test_run_timer_joined(self):
        """Test to end a deamon when its timer is running

        Test that a worker worker stopped with a running timer finishes with a
        triggered stop event, an empty error queue and a dead timer.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with self.WorkerSafeTimerToTest(self.stop, self.errors) as worker:
            worker.timer = worker.create_timer(0, worker.function_to_join)
            worker.timer.start()
            sleep(0.5)

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(worker.timer.is_alive())

    def test_unredifined_timer(self):
        """Test the timer must be redefined

        Test that a worker worker with its default timer does not generate an
        error, but finishes with a triggered stop event and an non-empty error
        queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with self.assertNotRaises(UnredefinedTimerError):
            with self.WorkerSafeTimerToTest(self.stop, self.errors) as worker:
                worker.timer.start()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, UnredefinedTimerError)


class WorkerSafeThreadTestCase(BaseTestCase):
    """Test the WorkerSafeThread class
    """
    class WorkerSafeThreadToTest(WorkerSafeThread):
        """Dummy worker class
        """
        def function_already_dead(self):
            """Function that ends immediately
            """
            return

        def function_to_join(self):
            """Function that waits one second
            """
            sleep(1)

    def test_run_thread_dead(self):
        """Test to end a worker when its thread is dead

        Test that a worker worker stopped with a dead thread finishes with a
        triggered stop event, an empty error queue and a still dead thread.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with self.WorkerSafeThreadToTest(self.stop, self.errors) as worker:
            worker.thread = worker.create_thread(
                target=worker.function_already_dead
            )
            worker.thread.start()
            worker.thread.join()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(worker.thread.is_alive())

    def test_run_thread_joined(self):
        """Test to end a deamon when its thread is running

        Test that a worker worker stopped with a running thread finishes with a
        triggered stop event, an empty error queue and a dead thread.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with self.WorkerSafeThreadToTest(self.stop, self.errors) as worker:
            worker.thread = worker.create_thread(
                target=worker.function_to_join
            )
            worker.thread.start()
            sleep(0.5)

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertTrue(self.errors.empty())
        self.assertFalse(worker.thread.is_alive())

    def test_unredifined_thread(self):
        """Test the thread must be redefined

        Test that a worker worker with its default thread does not generate an
        error, but finishes with a triggered stop event and an non-empty error
        queue.
        """
        # pre assertions
        self.assertFalse(self.stop.is_set())
        self.assertTrue(self.errors.empty())

        # create and run worker
        with self.assertNotRaises(UnredefinedThreadError):
            with self.WorkerSafeThreadToTest(self.stop, self.errors) as worker:
                worker.thread.start()

        # post assertions
        self.assertTrue(self.stop.is_set())
        self.assertFalse(self.errors.empty())
        _, error, _ = self.errors.get()
        self.assertIsInstance(error, UnredefinedThreadError)


class RunnerTestCase(BaseTestCase):
    """Test the Runner class

    The class to test should leave because of a Ctrl+C, or because of an
    internal eror.
    """
    class WorkerError(Worker):
        """Dummy worker class
        """
        def init_worker(self):
            """Initialize the worker
            """
            self.thread = self.create_thread(target=self.test)

        def test(self):
            """Raise an error
            """
            raise TestError('test error')

    @staticmethod
    def get_worker_ready():
        """Get a worker connected to an event

        This will be used for tests that produce side effects.
        """
        ready = Event()

        class WorkerReady(Worker):
            """Dummy worker class
            """
            def init_worker(self):
                """Initialize the worker
                """
                self.thread = self.create_thread(target=self.test)

            def test(self):
                """Signal to stop
                """
                ready.set()
                return

        return ready, WorkerReady

    def setUp(self):
        # create class to test
        self.runner = Runner()

    @skipIf(sys.platform.startswith('win'), "Disabled for Windows")
    def test_run_interrupt(self):
        """Test a run with an interruption by Ctrl+C

        The run should end with a set stop event and an empty errors queue.
        """
        # pre assertions
        self.assertFalse(self.runner.stop.is_set())
        self.assertTrue(self.runner.errors.empty())

        # get the class
        ready, WorkerReady = self.get_worker_ready()

        # prepare the sending of SIGINT to simulate a Ctrl+C
        def send_ctrl_c():
            """Simulate the Ctrl+C

            The signal is SIGINT on *NIX and  CTRL_C_EVENT on Windows.
            """
            pid = os.getpid()
            ready.wait()
            if sys.platform.startswith('win'):
                os.kill(pid, signal.CTRL_C_EVENT)

            else:
                os.kill(pid, signal.SIGINT)

        kill_thread = Thread(target=send_ctrl_c)
        kill_thread.start()

        # call the method
        with self.assertNotRaises(KeyboardInterrupt):
            self.runner.run_safe(WorkerReady)

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
            self.runner.run_safe(self.WorkerError)

        # post assertions
        self.assertTrue(self.runner.stop.is_set())
        self.assertTrue(self.runner.errors.empty())
