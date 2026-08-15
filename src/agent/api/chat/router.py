import json

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ...agents.executor import get_agent
from ...core.client import OneCrawlerClient
from ...db.models import AgentSettings, ChatMessage, Conversation
from ...db.pg import get_db
from ..deps import bearer_token, reraise_as_http_error, verified_user
from .helper import agent_config, serialize_message
from .schema import (
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ConversationDetailOut,
    ConversationOut,
)

router = APIRouter(tags=["Chat"])

_TITLE_MAX_LEN = 60


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


async def resolve_agent_settings(
    payload: ChatRequest, token: str, db: AsyncSession
) -> tuple[str, str, str, str | None, str]:
    """Resolve (llm_provider, llm_model, llm_api_key, search_api_key, user_id)
    for this call in one lookup. llm is required — saved per-user settings
    (PUT /api/settings/agent) are the only source, this service has no shared
    fallback brain. A per-request provider/model override only reuses the
    saved api_key when it doesn't change the provider (a saved OpenAI key
    can't drive an Anthropic model); switching provider requires saved
    settings for that provider already. search_api_key is optional — it's
    None until the user saves one, and web_search just isn't available until
    then.
    """
    user = await verified_user(token)
    result = await db.execute(
        select(AgentSettings).where(AgentSettings.user_id == user["id"])
    )
    stored = result.scalar_one_or_none()

    provider = payload.provider or (stored.llm_provider if stored else None)
    model = payload.model or (stored.llm_model if stored else None)
    api_key = stored.llm_api_key if stored and stored.llm_provider == provider else None

    if not provider or not model or not api_key:
        raise HTTPException(
            status_code=422,
            detail="No LLM settings configured for your account. Call "
            'PUT /api/settings/agent with {"llm": {...}} before using /chat, '
            "or pass provider/model matching your saved settings if you've "
            "already configured a different one.",
        )

    search_api_key = stored.search_api_key if stored else None
    return provider, model, api_key, search_api_key, user["id"]


async def _record_turn(
    db: AsyncSession, user_id: str, conversation_id: str, message: str, reply: str
) -> None:
    """Upsert the conversation (title set once, from the first message) and
    append this turn's two messages — purely for the chat-history UI, kept
    separate from LangGraph's own checkpoint state."""
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
    authorization: str = Header(...), db: AsyncSession = Depends(get_db)
) -> list[ConversationOut]:
    """List this user's conversations, most recently active first — for a
    chat-history sidebar."""
    user = await verified_user(bearer_token(authorization))

    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user["id"])
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
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailOut:
    """Full message history for one conversation, to reopen it — 404s if it
    doesn't exist or belongs to a different user."""
    user = await verified_user(bearer_token(authorization))

    result = await db.execute(
        select(Conversation).where(
            Conversation.conversation_id == conversation_id,
            Conversation.user_id == user["id"],
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

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


@router.get("/crawls/{job_id}")
async def crawl_status(job_id: str, authorization: str = Header(...)) -> dict:
    """Direct status lookup — bypasses the agent/LLM entirely so the UI can
    cheaply poll a job it started without spending tokens on every check."""
    token = bearer_token(authorization)
    try:
        return await OneCrawlerClient(token=token).get_crawl(job_id)
    except Exception as exc:
        reraise_as_http_error(exc)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    token = bearer_token(authorization)
    provider, model, api_key, search_api_key, user_id = await resolve_agent_settings(
        payload, token, db
    )

    agent = get_agent(provider, model, api_key)
    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=payload.message)]},
            config=agent_config(payload, token, search_api_key),
        )
    except Exception as exc:
        reraise_as_http_error(exc)
    reply = result["messages"][-1].content
    await _record_turn(db, user_id, payload.conversation_id, payload.message, reply)
    return ChatResponse(conversation_id=payload.conversation_id, reply=reply)


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Server-Sent Events stream of every step the deep agent takes: model
    turns (with tool calls it decides to make), tool results, and any nested
    subagent steps — so the frontend can show the agent's internal working.

    The "updates" stream_mode branch below carries tool-call and tool-result
    messages; plain assistant text is skipped there since it's already
    streamed via the "messages" mode's token deltas. Agent/tool errors
    surface as an "error" SSE event rather than raising."""
    token = bearer_token(authorization)
    provider, model, api_key, search_api_key, user_id = await resolve_agent_settings(
        payload, token, db
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
                    user_id,
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
