"""Own pause state and publication identity for a single capture channel."""
import threading


class CaptureControl:
    def __init__(self):
        self.lock = threading.RLock()
        self.revision = 0
        self.paused = False

    def snapshot(self):
        with self.lock:
            return self.paused, self.revision

    def pause(self, value):
        with self.lock:
            if self.paused != value:
                self.paused = value
                self.revision += 1

    def offer(self, expected_revision):
        with self.lock:
            if self.paused or self.revision != expected_revision:
                return None
            self.revision += 1
            return self.revision

    def current(self, revision):
        with self.lock:
            return not self.paused and self.revision == revision

    def publish(self, revision, stop, output, source, target):
        with self.lock:
            if not stop.is_set() and self.current(revision):
                output(source, target)
