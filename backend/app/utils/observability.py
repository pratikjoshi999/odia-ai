from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import json
import logging
import sys
from time import perf_counter
from typing import Iterator
from uuid import uuid4

from app.config.settings import Settings

logger = logging.getLogger("odia_ai.observability")
_current_metrics: ContextVar[RequestMetrics | None] = ContextVar("odia_ai_metrics", default=None)


@dataclass
class RequestMetrics:
    request_id: str = field(default_factory=lambda: str(uuid4()))
    started_at: float = field(default_factory=perf_counter)
    timings_ms: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def elapsed_ms(self) -> float:
        return round((perf_counter() - self.started_at) * 1000, 2)

    def record_timing(self, name: str, duration_ms: float) -> None:
        self.timings_ms[name] = round(duration_ms, 2)

    def record_error(self, category: str) -> None:
        if category not in self.errors:
            self.errors.append(category)

    def snapshot(self, status_code: int | None = None) -> dict[str, object]:
        result: dict[str, object] = {
            "request_id": self.request_id,
            "latency_ms": self.elapsed_ms(),
            "timings_ms": self.timings_ms,
            "errors": self.errors,
            "metadata": self.metadata,
        }
        if status_code is not None:
            result["status_code"] = status_code
        return result


def current_metrics() -> RequestMetrics | None:
    return _current_metrics.get()


def log_event(event: str, **fields: object) -> None:
    """Write a safe structured event with the current request ID."""
    metrics = current_metrics()
    payload: dict[str, object] = {
        "event": event,
        "request_id": metrics.request_id if metrics else None,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


@contextmanager
def request_metrics(metrics: RequestMetrics) -> Iterator[None]:
    token = _current_metrics.set(metrics)
    try:
        yield
    finally:
        _current_metrics.reset(token)


@contextmanager
def measure(name: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        metrics = current_metrics()
        if metrics:
            metrics.record_timing(name, (perf_counter() - started) * 1000)


class LangfuseTracer:
    """Optional Langfuse v4 root observation; local metrics remain authoritative."""

    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.langfuse_enabled
        self.client = None
        if not self.enabled:
            return
        try:
            from langfuse import Langfuse

            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_base_url,
            )
        except Exception:
            logger.exception("langfuse_initialization_failed")

    @contextmanager
    def request(self, metrics: RequestMetrics) -> Iterator[None]:
        if not self.client:
            yield
            return
        try:
            observation_context = self.client.start_as_current_observation(
                as_type="span",
                name="odia-ai-request",
                input={"request_id": metrics.request_id},
            )
            observation = observation_context.__enter__()
        except Exception:
            logger.exception("langfuse_request_failed", extra={"request_id": metrics.request_id})
            yield
            return
        try:
            yield
        except BaseException:
            try:
                observation_context.__exit__(*sys.exc_info())
            except Exception:
                logger.exception("langfuse_close_failed", extra={"request_id": metrics.request_id})
            raise
        else:
            try:
                observation.update(output=metrics.snapshot())
                observation_context.__exit__(None, None, None)
                self.client.flush()
            except Exception:
                logger.exception("langfuse_request_failed", extra={"request_id": metrics.request_id})


def log_request(metrics: RequestMetrics, method: str, path: str, status_code: int) -> None:
    logger.info(
        json.dumps(
            {"event": "request_complete", "method": method, "path": path, **metrics.snapshot(status_code)},
            ensure_ascii=False,
        )
    )
