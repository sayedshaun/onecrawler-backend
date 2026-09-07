import asyncio
import json
import logging

from deepharness import Finished, TextDelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.executor import get_agent
from src.agent.llm import DEFAULT_LOCAL_MODEL
from src.agent.tracing import agent_run
from src.api.security.dependencies import (
    CurrentUser,
    get_bearer_token,
    get_current_user,
)
from src.db.models import AgentSettings, ChatMessage, Conversation
from src.db.pg import get_db

from .helper import agent_deps, history_messages, serialize_event
from .schema import (
    AgentSettingsIn,
    AgentSettingsOut,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ConversationDetailOut,
    ConversationOut,
    LLMConfigOut,
    SearchConfigOut,
)

router = APIRouter(tags=["Agent"])

logger = logging.getLogger(__name__)

_TITLE_MAX_LEN = 60


async def _resolve_agent_settings(
    payload: ChatRequest, current_user: CurrentUser, db: AsyncSession
) -> tuple[str, str, str | None, str | None, str | None]:
    """Resolve (llm_provider, llm_model, llm_api_key, llm_base_url, search_api_key) for
    this call.

    llm is required — saved per-user settings (PUT /api/v1/settings/agent) are the only
    source, there's no shared fallback brain. A per-request provider/model override only
    reuses the saved api_key and base_url when it doesn't change the provider (a saved
    OpenAI key can't drive an Anthropic model); switching provider requires saved
    settings for that provider already. openai_compatible is the one provider needing
    no api_key — a self-hosted llama.cpp/vLLM server is reached by base_url instead.
    search_api_key is optional — it's None until the user saves one, and web_search
    just isn't available until then.
    """
    result = await db.execute(
        select(AgentSettings).where(AgentSettings.user_id == current_user.id)
    )
    stored = result.scalar_one_or_none()

    provider = payload.provider or (stored.llm_provider if stored else None)
    model = payload.model or (stored.llm_model if stored else None)
    same_provider = bool(stored) and stored.llm_provider == provider
    api_key = stored.llm_api_key if same_provider else None
    base_url = stored.llm_base_url if same_provider else None

    if provider == "openai_compatible":
        configured = bool(base_url)
        model = model or DEFAULT_LOCAL_MODEL
    else:
        configured = bool(provider and model and api_key)

    if not configured:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No LLM settings configured for your account. Call "
            'PUT /api/v1/settings/agent with {"llm": {...}} before using '
            "/chat, or pass provider/model matching your saved settings if "
            "you've already configured a different one.",
        )

    search_api_key = stored.search_api_key if stored else None
    return provider, model, api_key, base_url, search_api_key


async def _record_turn(
    db: AsyncSession, user_id: str, conversation_id: str, message: str, reply: str
) -> None:
    """Upsert the conversation (title set once, from the first message) and append this
    turn's two messages — also the agent's only memory of the conversation, since
    deepharness has no server-side checkpointer (see helper.history_messages)."""
    stmt = (
        pg_insert(Conversation)
        .values(
            conversation_id=conversation_id,
            user_id=user_id,
            title=message[:_TITLE_MAX_LEN],
        )
        .on_conflict_do_update(
            index_elements=[Conversation.conversation_id],
            set_={"updated_at": func.now()},
        )
    )
    await db.execute(stmt)
    db.add_all(
        [
            ChatMessage(conversation_id=conversation_id, role="human", content=message),
            ChatMessage(conversation_id=conversation_id, role="ai", content=reply),
        ]
    )
    await db.commit()


async def _conversation_history(
    db: AsyncSession, conversation_id: str
) -> list[ChatMessage]:
    """This conversation's stored turns, oldest first — the agent's memory."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
    )
    return list(result.scalars().all())


@router.get("/chats", response_model=list[ConversationOut])
async def list_chats(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ConversationOut]:
    """List this user's conversations, most recently active first — for a chat-history
    sidebar."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return [
        ConversationOut(
            conversation_id=row.conversation_id,
            title=row.title,
            updated_at=row.updated_at.isoformat(),
        )
        for row in result.scalars().all()
    ]


@router.get("/chats/{conversation_id}", response_model=ConversationDetailOut)
async def get_chat(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ConversationDetailOut:
    """Full message history for one conversation, to reopen it — 404s if it doesn't
    exist or belongs to a different user."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.conversation_id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )

    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
    )
    return ConversationDetailOut(
        conversation_id=conversation.conversation_id,
        title=conversation.title,
        updated_at=conversation.updated_at.isoformat(),
        messages=[
            ChatMessageOut(
                role=row.role,
                content=row.content,
                created_at=row.created_at.isoformat(),
            )
            for row in messages_result.scalars().all()
        ],
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    token: str = Depends(get_bearer_token),
) -> ChatResponse:
    provider, model, api_key, base_url, search_api_key = await _resolve_agent_settings(
        payload, current_user, db
    )
    messages = history_messages(
        await _conversation_history(db, payload.conversation_id), payload.message
    )

    agent = get_agent(provider, model, api_key, base_url)
    try:
        with agent_run(payload.conversation_id, payload.message) as span:
            state = await agent.arun(
                {"messages": messages}, deps=agent_deps(token, search_api_key)
            )
            if span is not None:
                span.set_outputs({"reply": state.output})
    except Exception as exc:
        # Providers surface a bad api key, a rate limit or a timeout as a ProviderError
        # or a transport error, and a tool budget as TokenBudgetExceeded — none of them
        # a bug in this service. Report an upstream failure instead of a 500, matching
        # the "error" event /chat/stream emits.
        logger.exception(
            "Agent run failed for conversation %s", payload.conversation_id
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent run failed: {exc}",
        ) from exc

    if not state.answered:
        # Only stop_reason == "answer" leaves a real reply in state.output; a run that
        # spent its step budget or paused for a human has nothing to record.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent stopped without answering ({state.stop_reason}).",
        )

    reply = state.output
    await _record_turn(
        db, current_user.id, payload.conversation_id, payload.message, reply
    )
    return ChatResponse(conversation_id=payload.conversation_id, reply=reply)


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    token: str = Depends(get_bearer_token),
) -> StreamingResponse:
    """Server-Sent Events stream of every step the agent takes: assistant text as it
    arrives, plus the tool calls it makes and their results — so the frontend can show
    the agent's internal working.

    deepharness streams text deltas only, so the two are merged through one queue: the
    run is driven in a task that pushes its deltas, while EventToolbox pushes tool
    activity from inside the dispatch that happens between them. Agent/tool errors
    surface as an "error" SSE event rather than raising.
    """
    provider, model, api_key, base_url, search_api_key = await _resolve_agent_settings(
        payload, current_user, db
    )
    messages = history_messages(
        await _conversation_history(db, payload.conversation_id), payload.message
    )
    agent = get_agent(provider, model, api_key, base_url)

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        async def drive() -> None:
            # The run's span is opened here rather than around the consume loop below,
            # so it covers exactly the agent run and every model/tool span nests under
            # it — a span left open across a generator's yields would not.
            try:
                with agent_run(payload.conversation_id, payload.message) as span:
                    async for event in agent.astream_events(
                        {"messages": messages},
                        deps=agent_deps(token, search_api_key, events=queue),
                    ):
                        if span is not None and isinstance(event, Finished):
                            span.set_outputs({"reply": event.state.output})
                        await queue.put(event)
            except Exception as exc:  # noqa: BLE001 - reported as an SSE error event
                await queue.put(exc)

        run = asyncio.create_task(drive())
        final = None
        try:
            while True:
                item = await queue.get()
                if isinstance(item, TextDelta):
                    event = {"node": agent.name, "path": [], "delta": item.text}
                    yield f"event: token\ndata: {json.dumps(event)}\n\n"
                    continue
                if isinstance(item, dict):
                    event = {
                        "node": item["name"],
                        "path": [],
                        "message": serialize_event(item),
                    }
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                    continue
                if isinstance(item, Exception):
                    raise item
                if isinstance(item, Finished):
                    final = item.state
                    break

            # Every turn streams, tool-calling ones included, so the recorded reply is
            # the run's answer rather than everything that came down the wire.
            if final.answered:
                await _record_turn(
                    db,
                    current_user.id,
                    payload.conversation_id,
                    payload.message,
                    final.output,
                )
            yield "event: done\ndata: {}\n\n"
        except Exception as exc:  # noqa: BLE001 - the client is told, not the caller
            logger.exception(
                "Agent stream failed for conversation %s", payload.conversation_id
            )
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            run.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _settings_to_out(row: AgentSettings | None) -> AgentSettingsOut:
    if row is None:
        return AgentSettingsOut(llm=LLMConfigOut(), search=SearchConfigOut())
    return AgentSettingsOut(
        llm=LLMConfigOut(
            provider=row.llm_provider,
            model=row.llm_model,
            has_key=row.llm_api_key is not None,
            base_url=row.llm_base_url,
        ),
        search=SearchConfigOut(
            provider=row.search_provider,
            has_key=row.search_api_key is not None,
        ),
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.put("/settings/agent", response_model=AgentSettingsOut)
async def set_agent_settings(
    payload: AgentSettingsIn,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AgentSettingsOut:
    """Save this user's agent config.

    llm and search are independent — send just one to update only that part, or both
    together. llm is required before /chat works; search is optional, only needed for
    web_search.
    """
    if payload.llm is None and payload.search is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one of llm or search.",
        )

    update: dict = {}
    if payload.llm is not None:
        update["llm_provider"] = payload.llm.provider
        update["llm_model"] = payload.llm.model
        update["llm_api_key"] = payload.llm.api_key
        update["llm_base_url"] = payload.llm.base_url
    if payload.search is not None:
        update["search_provider"] = payload.search.provider
        update["search_api_key"] = payload.search.api_key

    stmt = (
        pg_insert(AgentSettings)
        .values(user_id=current_user.id, **update)
        .on_conflict_do_update(index_elements=[AgentSettings.user_id], set_=update)
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(
        select(AgentSettings).where(AgentSettings.user_id == current_user.id)
    )
    return _settings_to_out(result.scalar_one_or_none())


@router.get("/settings/agent", response_model=AgentSettingsOut)
async def get_agent_settings(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AgentSettingsOut:
    """Status only — never returns raw api_keys."""
    result = await db.execute(
        select(AgentSettings).where(AgentSettings.user_id == current_user.id)
    )
    return _settings_to_out(result.scalar_one_or_none())


@router.delete("/settings/agent", status_code=status.HTTP_204_NO_CONTENT)
async def clear_agent_settings(
    scope: str | None = Query(
        None, description="'llm', 'search', or omit to clear both."
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    if scope not in (None, "llm", "search"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scope must be 'llm', 'search', or omitted.",
        )

    result = await db.execute(
        select(AgentSettings).where(AgentSettings.user_id == current_user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return

    if scope is None:
        await db.delete(row)
    elif scope == "llm":
        row.llm_provider = row.llm_model = None
        row.llm_api_key = row.llm_base_url = None
    else:
        row.search_provider = row.search_api_key = None
    await db.commit()
