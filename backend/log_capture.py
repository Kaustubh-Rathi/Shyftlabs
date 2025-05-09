# log_capture.py

import logging
from collections import deque

class InMemoryLogHandler(logging.Handler):
    def __init__(self, capacity=1000):
        super().__init__(level=logging.INFO)
        # now buffer holds dicts, not plain strings
        self.buffer = deque(maxlen=capacity)

    def emit(self, record):
        # capture only the two fields you care about:
        entry = {
            "name": record.name,
            "message": record.getMessage()
        }
        self.buffer.append(entry)

    def read_all(self):
        # return a snapshot
        return list(self.buffer)

    def clear(self):
        self.buffer.clear()

    def pop_one(self):
        """If you want to drain them one‑by‑one as you send."""
        return self.buffer.popleft() if self.buffer else None
