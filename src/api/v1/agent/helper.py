import asyncio
import json

from deepharness import Message

from src.agent.tools import AgentDeps
from src.db.models import ChatMessage


def agent_deps(
    token: str, search_api_key: str | None, events: asyncio.Queue | None = None
) -> AgentDeps:
    return AgentDeps(auth_token=token, search_api_key=search_api_key, events=events)


def history_messages(rows: list[ChatMessage], message: str) -> list[Message]:
    """The transcript to run: this conversation's stored turns, then the new message.

    deepharness has no server-side checkpointer, so prior context is replayed from the
    ChatMessage rows /chat writes. Only the human/ai text survives that round-trip —
    the tool calls and results of earlier turns are not stored, so the model sees what
    it said, not how it got there.
    """
    messages = [
        Message.ai(row.content) if row.role == "ai" else Message.human(row.content)
        for row in rows
    ]
    messages.append(Message.human(message))
    return messages


def serialize_event(event: dict) -> dict:
    """One EventToolbox event as the message shape /chat/stream has always emitted.

    Tool call ids aren't visible at the toolbox boundary, so they come out None where
    the LangGraph stream used to carry the provider's id.
    """
    if event["kind"] == "tool_call":
        return {
            "kind": "AIMessage",
            "content": "",
            "tool_calls": [{"name": event["name"], "args": event["args"], "id": None}],
        }

    content = (
        event["error"]
        if event["kind"] == "tool_error"
        else json.dumps(event["result"], default=str)
    )
    return {
        "kind": "ToolMessage",
        "content": content,
        "name": event["name"],
        "tool_call_id": None,
    }
