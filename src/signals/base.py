"""Base class for all signal processors — handles stream consumption and signal publishing."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

import orjson
import structlog

from src.cache.streams import RedisStreamConsumer
from src.signals.models import Signal
from src.signals.streams import SignalPublisher


class BaseSignalProcessor(ABC):
    """
    Base class for all signal processors.
    Handles stream consumption, signal publishing, health reporting.
    """

    PROCESSOR_NAME: str = "base"
    INPUT_STREAMS: list[str] = []
    OUTPUT_STREAM: str = ""
    CONSUMER_GROUP: str = "signal_processors"

    def __init__(
        self,
        redis_consumer: RedisStreamConsumer,
        signal_publisher: SignalPublisher,
        config: dict,
    ) -> None:
        self.consumer = redis_consumer
        self.publisher = signal_publisher
        self.config = config
        self.logger = structlog.get_logger().bind(processor=self.PROCESSOR_NAME)
        self._message_count = 0
        self._signal_count = 0
        self._last_stats_time = time.time()

    @abstractmethod
    async def process_message(self, stream: str, message: dict) -> list[Signal]:
        """
        Process a single message from an input stream.
        Returns zero or more signals.
        """
        ...

    async def run(self) -> None:
        """Main processing loop. Consumes from all INPUT_STREAMS."""
        self.logger.info("starting", input_streams=self.INPUT_STREAMS)

        tasks = []
        for stream in self.INPUT_STREAMS:
            consumer_name = f"{self.PROCESSOR_NAME}_{stream.replace(':', '_')}"
            tasks.append(
                asyncio.create_task(
                    self.consumer.consume(
                        stream=stream,
                        group=self.CONSUMER_GROUP,
                        consumer=consumer_name,
                        handler=lambda msgs, s=stream: self._handle_batch(s, msgs),
                        batch_size=100,
                    )
                )
            )

        # Stats logging task
        tasks.append(asyncio.create_task(self._stats_loop()))

        await asyncio.gather(*tasks)

    async def _handle_batch(self, stream: str, messages: list[dict[str, Any]]) -> None:
        """Process a batch of messages from a stream."""
        for msg in messages:
            try:
                data = msg.get("data", "{}")
                if isinstance(data, str):
                    parsed = orjson.loads(data)
                else:
                    parsed = data

                signals = await self.process_message(stream, parsed)
                self._message_count += 1

                for signal in signals:
                    await self.emit_signal(signal)

            except Exception:
                self.logger.exception(
                    "message_processing_error",
                    stream=stream,
                    msg_id=msg.get("id"),
                )

    async def emit_signal(self, signal: Signal) -> None:
        """Publish a signal to this processor's output stream AND kalshi:signals:all."""
        await self.publisher.publish(self.OUTPUT_STREAM, signal)
        await self.publisher.publish("kalshi:signals:all", signal)
        self._signal_count += 1
        self.logger.debug(
            "signal_emitted",
            signal_type=signal.signal_type,
            market=signal.market_ticker,
            direction=signal.direction.value,
            strength=signal.strength,
        )

    async def _stats_loop(self) -> None:
        """Log stats every 60 seconds."""
        while True:
            await asyncio.sleep(60)
            elapsed = time.time() - self._last_stats_time
            self.logger.info(
                "processor_stats",
                messages_processed=self._message_count,
                signals_emitted=self._signal_count,
                msg_per_sec=round(self._message_count / elapsed, 2) if elapsed > 0 else 0,
            )
            self._message_count = 0
            self._signal_count = 0
            self._last_stats_time = time.time()

    async def get_health(self) -> dict:
        """Return health metrics for monitoring."""
        return {
            "processor": self.PROCESSOR_NAME,
            "messages_processed": self._message_count,
            "signals_emitted": self._signal_count,
            "status": "running",
        }
