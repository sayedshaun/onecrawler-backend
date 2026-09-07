from unittest.mock import AsyncMock

from deepharness import AgentState, Finished, TextDelta
from httpx import AsyncClient

from src.api.security.dependencies import CurrentUser


def _fake_agent(reply: str = "hello there") -> AsyncMock:
    agent = AsyncMock()
    agent.arun.return_value = AgentState(output=reply, stop_reason="answer")
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
    assert body["llm"] == {
        "provider": "openai",
        "model": "gpt-4o",
        "has_key": True,
        "base_url": None,
    }
    assert "sk-secret" not in put_response.text

    get_response = await client.get("/api/v1/settings/agent")
    assert get_response.status_code == 200
    assert get_response.json()["llm"]["has_key"] is True
    assert "sk-secret" not in get_response.text


async def test_get_agent_settings_defaults_when_unset(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/agent")
    assert response.status_code == 200
    assert response.json() == {
        "llm": {"provider": None, "model": None, "has_key": False, "base_url": None},
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
    assert body["llm"] == {
        "provider": None,
        "model": None,
        "has_key": False,
        "base_url": None,
    }
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
    fake_agent.arun.assert_awaited_once()

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

    def fake_get_agent(provider: str, model: str, api_key: str, base_url=None):
        seen.update(provider=provider, model=model, api_key=api_key, base_url=base_url)
        return _fake_agent("ok")

    monkeypatch.setattr("src.api.v1.agent.router.get_agent", fake_get_agent)

    response = await client.post(
        "/api/v1/chat",
        json={"message": "hi", "conversation_id": "conv-2"},
    )
    assert response.status_code == 200
    assert seen == {
        "provider": "anthropic",
        "model": "claude",
        "api_key": "sk-2",
        "base_url": None,
    }


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


async def test_chat_maps_provider_failure_to_502(
    client: AsyncClient, monkeypatch
) -> None:
    await client.put(
        "/api/v1/settings/agent",
        json={"llm": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-bad"}},
    )

    agent = AsyncMock()
    agent.arun.side_effect = RuntimeError("Error code: 401 - invalid api key")
    monkeypatch.setattr("src.api.v1.agent.router.get_agent", lambda *a, **k: agent)

    response = await client.post(
        "/api/v1/chat",
        json={"message": "hi", "conversation_id": "conv-fail"},
    )
    assert response.status_code == 502
    assert "invalid api key" in response.json()["detail"]

    # A failed run must not leave a half-written turn behind.
    list_response = await client.get("/api/v1/chats")
    assert list_response.json() == []


async def test_chat_replays_stored_history_as_context(
    client: AsyncClient, monkeypatch
) -> None:
    await client.put(
        "/api/v1/settings/agent",
        json={"llm": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-1"}},
    )
    agent = _fake_agent("second reply")
    monkeypatch.setattr("src.api.v1.agent.router.get_agent", lambda *a, **k: agent)

    await client.post(
        "/api/v1/chat", json={"message": "first", "conversation_id": "conv-mem"}
    )
    await client.post(
        "/api/v1/chat", json={"message": "second", "conversation_id": "conv-mem"}
    )

    # No checkpointer any more: the second run must carry the first turn itself.
    messages = agent.arun.await_args.args[0]["messages"]
    assert [(m.role, m.content) for m in messages] == [
        ("user", "first"),
        ("assistant", "second reply"),
        ("user", "second"),
    ]


async def test_chat_without_an_answer_is_502(client: AsyncClient, monkeypatch) -> None:
    await client.put(
        "/api/v1/settings/agent",
        json={"llm": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-1"}},
    )
    agent = AsyncMock()
    agent.arun.return_value = AgentState(output="", stop_reason="step_budget")
    monkeypatch.setattr("src.api.v1.agent.router.get_agent", lambda *a, **k: agent)

    response = await client.post(
        "/api/v1/chat", json={"message": "hi", "conversation_id": "conv-budget"}
    )
    assert response.status_code == 502
    assert "step_budget" in response.json()["detail"]


async def test_chat_stream_emits_tokens_tool_events_and_records_the_answer(
    client: AsyncClient, monkeypatch
) -> None:
    await client.put(
        "/api/v1/settings/agent",
        json={"llm": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-1"}},
    )

    class FakeAgent:
        name = "onecrawler"

        async def astream_events(self, state, *, deps):
            # What EventToolbox pushes while the model's tool calls run.
            await deps.events.put(
                {"kind": "tool_call", "name": "get_crawl", "args": {"job_id": "j1"}}
            )
            await deps.events.put(
                {"kind": "tool_result", "name": "get_crawl", "result": {"s": "done"}}
            )
            yield TextDelta("job ")
            yield TextDelta("j1 is done")
            yield Finished(AgentState(output="job j1 is done", stop_reason="answer"))

    monkeypatch.setattr(
        "src.api.v1.agent.router.get_agent", lambda *a, **k: FakeAgent()
    )

    response = await client.post(
        "/api/v1/chat/stream",
        json={"message": "how is j1?", "conversation_id": "conv-stream"},
    )
    assert response.status_code == 200
    body = response.text
    assert '"delta": "job "' in body
    assert '"name": "get_crawl"' in body
    assert '"kind": "ToolMessage"' in body
    assert body.endswith("event: done\ndata: {}\n\n")

    detail = await client.get("/api/v1/chats/conv-stream")
    assert detail.json()["messages"][1]["content"] == "job j1 is done"


async def test_openai_compatible_settings_need_no_key_or_model(
    client: AsyncClient,
) -> None:
    response = await client.put(
        "/api/v1/settings/agent",
        json={
            "llm": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:8080/v1",
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["llm"] == {
        "provider": "openai_compatible",
        "model": "",
        "has_key": False,
        "base_url": "http://localhost:8080/v1",
    }


async def test_openai_compatible_settings_require_base_url(
    client: AsyncClient,
) -> None:
    response = await client.put(
        "/api/v1/settings/agent",
        json={"llm": {"provider": "openai_compatible", "model": "qwen3"}},
    )
    assert response.status_code == 422


async def test_chat_with_openai_compatible_passes_base_url_and_default_model(
    client: AsyncClient, monkeypatch
) -> None:
    await client.put(
        "/api/v1/settings/agent",
        json={
            "llm": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:8080/v1",
            }
        },
    )

    seen: dict = {}

    def fake_get_agent(provider: str, model: str, api_key: str, base_url=None):
        seen.update(provider=provider, model=model, api_key=api_key, base_url=base_url)
        return _fake_agent("ok")

    monkeypatch.setattr("src.api.v1.agent.router.get_agent", fake_get_agent)

    response = await client.post(
        "/api/v1/chat",
        json={"message": "hi", "conversation_id": "conv-local"},
    )
    assert response.status_code == 200
    assert seen == {
        "provider": "openai_compatible",
        "model": "local-model",
        "api_key": None,
        "base_url": "http://localhost:8080/v1",
    }


def test_key_less_openai_compatible_sends_a_usable_auth_header() -> None:
    """httpx rejects the "Bearer " an empty key would produce, so a key-less
    self-hosted server must still get a non-empty placeholder token."""
    from src.agent.llm import build_chat_model

    model = build_chat_model(
        "openai_compatible", "", None, "https://llm.example.com/v1"
    )
    headers = model._http._async_client.headers
    assert headers["authorization"].strip() != "Bearer"
