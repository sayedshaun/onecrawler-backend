"""MLflow tracing for deepharness runs.

mlflow.langchain.autolog() worked by patching LangChain. deepharness has no SDK
dependencies — it POSTs to each vendor's REST API with httpx — so there is nothing
for an autolog integration to hook, and the spans have to be opened by hand at the
two seams that matter: every model call, and every tool call.

Tracing is off when MLFLOW_TRACKING_URI is empty, which is how the test suite avoids
exporting spans to a tracking server that isn't there.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Any

import mlflow
from deepharness import Ctx
from deepharness.providers.base import LLM, CompletionResponse, StreamEvent
from mlflow.entities import SpanType

from src.core.config import settings

from .tools import EventToolbox

ENABLED = bool(settings.MLFLOW_TRACKING_URI)

if ENABLED:
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)


def _record(span: Any, response: CompletionResponse) -> None:
    span.set_outputs(
        {
            "content": response.content,
            "tool_calls": [
                {"name": call.name, "arguments": call.arguments}
                for call in response.tool_calls
            ],
        }
    )
    if response.usage is not None:
        # The key MLflow's UI reads token counts from.
        span.set_attribute(
            "mlflow.chat.tokenUsage",
            {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )


class TracedLLM(LLM):
    """A provider that records each completion as a CHAT_MODEL span.

    Wraps rather than subclasses a provider so it works for every vendor, and
    overrides astream_events/stream_events rather than leaving them to the base
    class: streaming is the path /chat/stream takes, and its span has to stay open
    until the turn is assembled.
    """

    __slots__ = ("_inner", "_name")

    def __init__(self, inner: LLM, name: str) -> None:
        self._inner = inner
        self._name = name

    def _inputs(self, messages: list[dict], tools: list[dict] | None) -> dict:
        return {
            "messages": messages,
            "tools": [tool["name"] for tool in tools or []],
        }

    async def agenerate(
        self, messages: list[dict[str, Any]], *, tools: list[dict] | None = None
    ) -> CompletionResponse:
        with mlflow.start_span(self._name, span_type=SpanType.CHAT_MODEL) as span:
            span.set_inputs(self._inputs(messages, tools))
            response = await self._inner.agenerate(messages, tools=tools)
            _record(span, response)
            return response

    def generate(
        self, messages: list[dict[str, Any]], *, tools: list[dict] | None = None
    ) -> CompletionResponse:
        with mlflow.start_span(self._name, span_type=SpanType.CHAT_MODEL) as span:
            span.set_inputs(self._inputs(messages, tools))
            response = self._inner.generate(messages, tools=tools)
            _record(span, response)
            return response

    async def astream_events(
        self, messages: list[dict[str, Any]], *, tools: list[dict] | None = None
    ) -> AsyncIterator[StreamEvent]:
        with mlflow.start_span(self._name, span_type=SpanType.CHAT_MODEL) as span:
            span.set_inputs(self._inputs(messages, tools))
            async for event in self._inner.astream_events(messages, tools=tools):
                if hasattr(event, "response"):
                    _record(span, event.response)
                yield event

    def stream_events(
        self, messages: list[dict[str, Any]], *, tools: list[dict] | None = None
    ) -> Iterator[StreamEvent]:
        with mlflow.start_span(self._name, span_type=SpanType.CHAT_MODEL) as span:
            span.set_inputs(self._inputs(messages, tools))
            for event in self._inner.stream_events(messages, tools=tools):
                if hasattr(event, "response"):
                    _record(span, event.response)
                yield event


class TracedToolbox(EventToolbox):
    """EventToolbox that also records each call as a TOOL span."""

    __slots__ = ()

    async def call(self, name: str, *, ctx: Ctx | None = None, **kwargs: Any) -> Any:
        with mlflow.start_span(name, span_type=SpanType.TOOL) as span:
            span.set_inputs(kwargs)
            result = await super().call(name, ctx=ctx, **kwargs)
            span.set_outputs(result)
            return result


@contextmanager
def agent_run(conversation_id: str, message: str):
    """The root span one chat turn's model and tool spans hang off.

    A no-op when tracing is disabled, so the endpoints can wrap a run
    unconditionally. Asyncio tasks started inside it inherit the span's context,
    which is what keeps /chat/stream's driver task attached to this trace.
    """
    if not ENABLED:
        yield None
        return

    with mlflow.start_span("agent_run", span_type=SpanType.AGENT) as span:
        span.set_inputs({"conversation_id": conversation_id, "message": message})
        yield span
