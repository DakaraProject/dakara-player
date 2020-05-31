from threading import Event


class State:
    def __init__(self):
        self.started = Event()
        self.finished = Event()

    def start(self):
        self.reset()
        self.started.set()

    def finish(self):
        self.finished.set()

    def reset(self):
        self.started.clear()
        self.finished.clear()

    def is_active(self):
        return self.has_started() and not self.has_finished()

    def has_started(self):
        return self.started.is_set()

    def has_finished(self):
        return self.finished.is_set()

    def wait_start(self):
        self.started.wait()

    def wait_finish(self):
        self.finished.wait()
