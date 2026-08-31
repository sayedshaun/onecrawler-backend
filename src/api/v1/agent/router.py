import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.executor import get_agent
from src.api.security.dependencies import (
    CurrentUser,
    get_bearer_token,
    get_current_user,
)
from src.db.models import AgentSettings, ChatMessage, Conversation
from src.db.pg import get_db

from .helper import agent_config, serialize_message
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
) -> tuple[str, str, str, str | None]:
    """Resolve (llm_provider, llm_model, llm_api_key, search_api_key) for this call.

    llm is required — saved per-user settings (PUT /api/v1/settings/agent) are the only
    source, there's no shared fallback brain. A per-request provider/model override only
    reuses the saved api_key when it doesn't change the provider (a saved OpenAI key
    can't drive an Anthropic model); switching provider requires saved settings for that
    provider already. search_api_key is optional — it's None until the user saves one,
    and web_search just isn't available until then.
    """
    result = await db.execute(
        select(AgentSettings).where(AgentSettings.user_id == current_user.id)
    )
    stored = result.scalar_one_or_none()

    provider = payload.provider or (stored.llm_provider if stored else None)
    model = payload.model or (stored.llm_model if stored else None)
    api_key = stored.llm_api_key if stored and stored.llm_provider == provider else None

    if not provider or not model or not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No LLM settings configured for your account. Call "
            'PUT /api/v1/settings/agent with {"llm": {...}} before using '
            "/chat, or pass provider/model matching your saved settings if "
            "you've already configured a different one.",
        )

    search_api_key = stored.search_api_key if stored else None
    return provider, model, api_key, search_api_key


async def _record_turn(
    db: AsyncSession, user_id: str, conversation_id: str, message: str, reply: str
) -> None:
    """Upsert the conversation (title set once, from the first message) and append this
    turn's two messages — purely for the chat-history UI, kept separate from LangGraph's
    own checkpoint state."""
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
    provider, model, api_key, search_api_key = await _resolve_agent_settings(
        payload, current_user, db
    )

    agent = get_agent(provider, model, api_key)
    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=payload.message)]},
            config=agent_config(payload, token, search_api_key),
        )
    except Exception as exc:
        # The provider SDKs each raise their own error types (bad api key, rate limit,
        # timeout), so there's no useful set to enumerate here. Report it as an upstream
        # failure instead of a 500, matching the "error" event /chat/stream emits.
        logger.exception(
            "Agent run failed for conversation %s", payload.conversation_id
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent run failed: {exc}",
        ) from exc
    reply = result["messages"][-1].content
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
    """Server-Sent Events stream of every step the deep agent takes: model turns (with
    tool calls it decides to make), tool results, and any nested subagent steps — so the
    frontend can show the agent's internal working.

    The "updates" stream_mode branch below carries tool-call and tool-result messages;
    plain assistant text is skipped there since it's already streamed via the "messages"
    mode's token deltas. Agent/tool errors surface as an "error" SSE event rather than
    raising.
    """
    provider, model, api_key, search_api_key = await _resolve_agent_settings(
        payload, current_user, db
    )
    agent = get_agent(provider, model, api_key)

    async def event_generator():
        reply_parts: list[str] = []
        try:
            async for namespace, mode, data in agent.astream(
                {"messages": [HumanMessage(content=payload.message)]},
                config=agent_config(payload, token, search_api_key),
                stream_mode=["updates", "messages"],
                subgraphs=True,
            ):
                if mode == "messages":
                    chunk, metadata = data
                    if (
                        isinstance(chunk, AIMessageChunk)
                        and chunk.content
                        and not chunk.tool_call_chunks
                    ):
                        text = (
                            chunk.content
                            if isinstance(chunk.content, str)
                            else json.dumps(chunk.content, default=str)
                        )
                        if not namespace:
                            reply_parts.append(text)
                        event = {
                            "node": metadata.get("langgraph_node"),
                            "path": list(namespace),
                            "message_id": chunk.id,
                            "delta": text,
                        }
                        yield f"event: token\ndata: {json.dumps(event)}\n\n"
                    continue

                for node_name, delta in (data or {}).items():
                    messages = (
                        (delta or {}).get("messages")
                        if isinstance(delta, dict)
                        else None
                    )
                    if not messages:
                        continue
                    for message in messages:
                        if isinstance(message, AIMessage) and not message.tool_calls:
                            continue
                        event = {
                            "node": node_name,
                            "path": list(namespace),
                            "message": serialize_message(message),
                        }
                        yield f"data: {json.dumps(event)}\n\n"
            if reply_parts:
                await _record_turn(
                    db,
                    current_user.id,
                    payload.conversation_id,
                    payload.message,
                    "".join(reply_parts),
                )
            yield "event: done\ndata: {}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

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
        row.llm_provider = row.llm_model = row.llm_api_key = None
    else:
        row.search_provider = row.search_api_key = None
    await db.commit()
