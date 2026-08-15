import json

from langchain_core.messages import AIMessage, ToolMessage

from .schema import ChatRequest


def agent_config(payload: ChatRequest, token: str, search_api_key: str | None) -> dict:
    return {
        "configurable": {
            "thread_id": payload.conversation_id,
            "auth_token": token,
            "search_api_key": search_api_key,
        }
    }


def serialize_message(message) -> dict:
    content = message.content
    if not isinstance(content, str):
        content = json.dumps(content, default=str)

    data = {"kind": message.__class__.__name__, "content": content}

    if isinstance(message, AIMessage) and message.tool_calls:
        data["tool_calls"] = [
            {"name": tc["name"], "args": tc["args"], "id": tc["id"]}
            for tc in message.tool_calls
        ]

    if isinstance(message, ToolMessage):
        data["tool_call_id"] = message.tool_call_id
        data["name"] = getattr(message, "name", None)

    return data
