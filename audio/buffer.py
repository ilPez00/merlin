import numpy as np

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16


class RingBuffer:
    """Circular buffer holding the last N seconds of 16kHz mono PCM."""

    def __init__(self, seconds: int = 600):
        self.capacity = seconds * SAMPLE_RATE
        self.buffer = np.zeros(self.capacity, dtype=DTYPE)
        self.pos = 0
        self.full = False

    def write(self, samples: np.ndarray):
        n = len(samples)
        if n >= self.capacity:
            self.buffer[:] = samples[-self.capacity:]
            self.pos = 0
            self.full = True
            return
        end = self.pos + n
        if end <= self.capacity:
            self.buffer[self.pos:end] = samples
        else:
            first = self.capacity - self.pos
            self.buffer[self.pos:] = samples[:first]
            self.buffer[:end - self.capacity] = samples[first:]
        self.pos = end % self.capacity
        if self.pos != 0 or n > 0:
            self.full = self.full or (self.pos == 0 and n > 0)

    def read(self, seconds: float) -> np.ndarray:
        n = int(seconds * SAMPLE_RATE)
        if n > self.capacity:
            n = self.capacity
        if not self.full and self.pos < n:
            return self.buffer[:self.pos].copy()
        start = (self.pos - n) % self.capacity
        if start < self.pos:
            return self.buffer[start:self.pos].copy()
        else:
            return np.concatenate([
                self.buffer[start:],
                self.buffer[:self.pos],
            ])

    def read_all(self) -> np.ndarray:
        if not self.full:
            return self.buffer[:self.pos].copy()
        return np.concatenate([
            self.buffer[self.pos:],
            self.buffer[:self.pos],
        ])

    @property
    def filled_seconds(self) -> float:
        if self.full:
            return self.capacity / SAMPLE_RATE
        return self.pos / SAMPLE_RATE

    @property
    def fill_ratio(self) -> float:
        return self.filled_seconds / (self.capacity / SAMPLE_RATE)
