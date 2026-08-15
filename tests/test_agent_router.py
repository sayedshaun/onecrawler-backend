from unittest.mock import AsyncMock

from httpx import AsyncClient
from langchain_core.messages import AIMessage

from src.api.security.dependencies import CurrentUser


def _fake_agent(reply: str = "hello there") -> AsyncMock:
    agent = AsyncMock()
    agent.ainvoke.return_value = {"messages": [AIMessage(content=reply)]}
    return agent


async def test_set_agent_settings_requires_llm_or_search(client: AsyncClient) -> None:
    response = await client.put("/api/v1/settings/agent", json={})
    assert response.status_code == 422


async def test_agent_settings_roundtrip_never_leaks_api_key(
    client: AsyncClient,
) -> None:
    put_response = await client.put(
        "/api/v1/settings/agent",
        json={"llm": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-secret"}},
    )
    assert put_response.status_code == 200
    body = put_response.json()
    assert body["llm"] == {"provider": "openai", "model": "gpt-4o", "has_key": True}
    assert "sk-secret" not in put_response.text

    get_response = await client.get("/api/v1/settings/agent")
    assert get_response.status_code == 200
    assert get_response.json()["llm"]["has_key"] is True
    assert "sk-secret" not in get_response.text


async def test_get_agent_settings_defaults_when_unset(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/agent")
    assert response.status_code == 200
    assert response.json() == {
        "llm": {"provider": None, "model": None, "has_key": False},
        "search": {"provider": None, "has_key": False},
        "updated_at": None,
    }


async def test_clear_agent_settings_scope_llm_keeps_search(
    client: AsyncClient,
) -> None:
    await client.put(
        "/api/v1/settings/agent",
        json={
            "llm": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-1"},
            "search": {"provider": "tavily", "api_key": "tv-1"},
        },
    )

    delete_response = await client.delete(
        "/api/v1/settings/agent", params={"scope": "llm"}
    )
    assert delete_response.status_code == 204

    get_response = await client.get("/api/v1/settings/agent")
    body = get_response.json()
    assert body["llm"] == {"provider": None, "model": None, "has_key": False}
    assert body["search"] == {"provider": "tavily", "has_key": True}


async def test_list_chats_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/chats")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_chat_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/chats/does-not-exist")
    assert response.status_code == 404


async def test_chat_without_saved_settings_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/chat",
        json={"message": "hi", "conversation_id": "conv-1"},
    )
    assert response.status_code == 422


async def test_chat_success_records_turn_and_conversation(
    client: AsyncClient, monkeypatch
) -> None:
    await client.put(
        "/api/v1/settings/agent",
        json={"llm": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-1"}},
    )

    fake_agent = _fake_agent("42 is the answer")
    monkeypatch.setattr("src.api.v1.agent.router.get_agent", lambda *a, **k: fake_agent)

    chat_response = await client.post(
        "/api/v1/chat",
        json={"message": "what is the answer?", "conversation_id": "conv-1"},
    )
    assert chat_response.status_code == 200
    assert chat_response.json() == {
        "conversation_id": "conv-1",
        "reply": "42 is the answer",
    }
    fake_agent.ainvoke.assert_awaited_once()

    list_response = await client.get("/api/v1/chats")
    assert [c["conversation_id"] for c in list_response.json()] == ["conv-1"]

    detail_response = await client.get("/api/v1/chats/conv-1")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["title"] == "what is the answer?"
    assert [m["role"] for m in detail["messages"]] == ["human", "ai"]
    assert detail["messages"][1]["content"] == "42 is the answer"


async def test_chat_reuses_provider_from_saved_settings(
    client: AsyncClient, monkeypatch
) -> None:
    await client.put(
        "/api/v1/settings/agent",
        json={"llm": {"provider": "anthropic", "model": "claude", "api_key": "sk-2"}},
    )

    seen: dict = {}

    def fake_get_agent(provider: str, model: str, api_key: str):
        seen.update(provider=provider, model=model, api_key=api_key)
        return _fake_agent("ok")

    monkeypatch.setattr("src.api.v1.agent.router.get_agent", fake_get_agent)

    response = await client.post(
        "/api/v1/chat",
        json={"message": "hi", "conversation_id": "conv-2"},
    )
    assert response.status_code == 200
    assert seen == {"provider": "anthropic", "model": "claude", "api_key": "sk-2"}


async def test_another_user_cannot_read_first_users_conversation(
    app, client: AsyncClient, monkeypatch
) -> None:
    from src.api.security.dependencies import get_current_user

    monkeypatch.setattr(
        "src.api.v1.agent.router.get_agent", lambda *a, **k: _fake_agent("hi")
    )
    await client.put(
        "/api/v1/settings/agent",
        json={"llm": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-1"}},
    )
    await client.post(
        "/api/v1/chat",
        json={"message": "hi", "conversation_id": "conv-shared"},
    )

    other_user = CurrentUser(
        id="00000000-0000-0000-0000-000000000000",
        email="other@example.com",
        user_type="user",
        name="Other",
        jti="jti-2",
        exp=9999999999,
    )
    app.dependency_overrides[get_current_user] = lambda: other_user

    response = await client.get("/api/v1/chats/conv-shared")
    assert response.status_code == 404

    list_response = await client.get("/api/v1/chats")
    assert list_response.json() == []
