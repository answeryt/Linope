"""How many model calls may wait at once."""

from __future__ import annotations


class InflightLimit:
    """A moving cap on requests waiting for a reply."""

    def __init__(
        self,
        *,
        minimum: int = 1,
        maximum: int = 1,
        queue_size: int = 4,
        smoothing: float = 0.2,
        rtt_tolerance: float = 1.5,
    ) -> None:
        if minimum < 1:
            raise ValueError("minimum must be at least 1")
        if maximum < minimum:
            raise ValueError("maximum cannot be under minimum")
        self.minimum = int(minimum)
        self.maximum = int(maximum)
        self.queue_size = int(queue_size)
        self.smoothing = float(smoothing)
        self.rtt_tolerance = float(rtt_tolerance)
        self.limit = float(self.maximum)
        self._long_rtt = 0.0
        self._short_rtt = 0.0

    @property
    def current(self) -> int:
        value = int(self.limit)
        if value < self.minimum:
            return self.minimum
        if value > self.maximum:
            return self.maximum
        return value

    def set_maximum(self, maximum: int) -> None:
        maximum = max(self.minimum, int(maximum))
        if maximum > self.maximum:
            self.limit = float(maximum)
        else:
            self.limit = min(self.limit, float(maximum))
        self.maximum = maximum

    def sample(self, rtt_seconds: float, inflight: int) -> int:
        """Record one round trip and return the allowance to use next."""
        rtt = float(rtt_seconds)
        if rtt <= 0:
            return self.current
        if self._long_rtt == 0.0:
            self._long_rtt = rtt
            self._short_rtt = rtt
            return self.current
        self._short_rtt = self._short_rtt * 0.5 + rtt * 0.5
        if inflight < max(1, self.current / 2):
            return self.current
        self._long_rtt = self._long_rtt * 0.95 + rtt * 0.05
        short = self._short_rtt if self._short_rtt > 0 else rtt
        gradient = self.rtt_tolerance * self._long_rtt / short
        if gradient < 0.5:
            gradient = 0.5
        if gradient > 1.0:
            gradient = 1.0
        proposed = self.limit * gradient + self.queue_size
        self.limit = self.limit * (1.0 - self.smoothing) + proposed * self.smoothing
        if self.limit < self.minimum:
            self.limit = float(self.minimum)
        if self.limit > self.maximum:
            self.limit = float(self.maximum)
        return self.current
