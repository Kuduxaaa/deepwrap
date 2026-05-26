from __future__ import annotations

import hashlib
import threading
import uuid

from dataclasses import dataclass, field
from typing import Dict, Generator, Literal, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from deepwrap import Client
from deepwrap.utils.config_store import ConfigStore


ModelName = Literal["expert", "default", "vision"]
StreamFormat = Literal["text", "sse"]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    model: ModelName = "expert"
    token: Optional[str] = None
    thinking: bool = True
    search: bool = True
    god_mode: bool = False
    stream: bool = False
    stream_format: StreamFormat = "text"
    session_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message cannot be empty.")

        return value


class ChatResponse(BaseModel):
    model: str
    response: str
    session_id: Optional[str] = None


class CreateSessionRequest(BaseModel):
    model: ModelName = "expert"
    token: Optional[str] = None
    god_mode: bool = False


class CreateSessionResponse(BaseModel):
    session_id: str
    model: str
    god_mode: bool


class DeleteSessionResponse(BaseModel):
    ok: bool
    session_id: str


class HealthResponse(BaseModel):
    ok: bool
    app: str
    version: str
    token_configured: bool
    cached_clients: int
    active_sessions: int


@dataclass
class SessionRecord:
    chat: object
    model: str
    token_fingerprint: str
    god_mode: bool
    lock: threading.Lock = field(default_factory=threading.Lock)


class APIState:
    def __init__(self) -> None:
        self.store = ConfigStore()

        self._clients: Dict[str, Client] = {}
        self._sessions: Dict[str, SessionRecord] = {}

        self._clients_lock = threading.Lock()
        self._sessions_lock = threading.Lock()

    @staticmethod
    def fingerprint_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def resolve_token(self, explicit_token: Optional[str] = None) -> str:
        if explicit_token:
            return explicit_token.strip()

        config = self.store.load()

        if config.token:
            return config.token.strip()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "No token configured. Run `deepwrap auth --browser` first "
                "or pass `token` in the request body."
            ),
        )

    def get_client(self, token: str) -> Client:
        fingerprint = self.fingerprint_token(token)

        with self._clients_lock:
            client = self._clients.get(fingerprint)

            if client is not None:
                return client

            try:
                client = Client(api_key=token)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to initialize DeepWrap client: {exc}",
                ) from exc

            self._clients[fingerprint] = client

            return client

    def create_session(
        self,
        token: Optional[str],
        model: str,
        god_mode: bool,
    ) -> CreateSessionResponse:
        resolved_token = self.resolve_token(token)
        fingerprint = self.fingerprint_token(resolved_token)
        client = self.get_client(resolved_token)

        try:
            chat = client.chats.create_session(
                model=model,
                god_mode=god_mode,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to create chat session: {exc}",
            ) from exc

        session_id = f"chat_{uuid.uuid4().hex}"

        record = SessionRecord(
            chat=chat,
            model=model,
            token_fingerprint=fingerprint,
            god_mode=god_mode,
        )

        with self._sessions_lock:
            self._sessions[session_id] = record

        return CreateSessionResponse(
            session_id=session_id,
            model=model,
            god_mode=god_mode,
        )

    def delete_session(self, session_id: str) -> DeleteSessionResponse:
        with self._sessions_lock:
            if session_id not in self._sessions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Unknown session_id: {session_id}",
                )

            self._sessions.pop(session_id)

        return DeleteSessionResponse(
            ok=True,
            session_id=session_id,
        )

    def get_session(self, session_id: str) -> SessionRecord:
        with self._sessions_lock:
            record = self._sessions.get(session_id)

        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown session_id: {session_id}",
            )

        return record

    def create_ephemeral_chat(
        self,
        token: Optional[str],
        model: str,
        god_mode: bool,
    ):
        resolved_token = self.resolve_token(token)
        client = self.get_client(resolved_token)

        try:
            return client.chats.create_session(
                model=model,
                god_mode=god_mode,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to create chat session: {exc}",
            ) from exc

    @property
    def cached_clients_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    @property
    def active_sessions_count(self) -> int:
        with self._sessions_lock:
            return len(self._sessions)


def format_sse_chunk(chunk: str) -> str:
    chunk = chunk.replace("\r", "")

    lines = chunk.split("\n")

    return "".join(f"data: {line}\n" for line in lines) + "\n"


def create_app() -> FastAPI:
    app = FastAPI(
        title="DeepWrap API",
        version="0.1.0",
        description="Local HTTP API for DeepWrap.",
    )

    state = APIState()

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        config = state.store.load()

        return HealthResponse(
            ok=True,
            app="deepwrap",
            version="0.1.0",
            token_configured=bool(config.token),
            cached_clients=state.cached_clients_count,
            active_sessions=state.active_sessions_count,
        )

    @app.post("/sessions", response_model=CreateSessionResponse)
    def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
        return state.create_session(
            token=request.token,
            model=request.model,
            god_mode=request.god_mode,
        )

    @app.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
    def delete_session(session_id: str) -> DeleteSessionResponse:
        return state.delete_session(session_id)

    @app.post("/chat")
    def chat(request: ChatRequest):
        if request.session_id:
            record = state.get_session(request.session_id)

            if record.model != request.model:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Session model mismatch. Session uses '{record.model}', "
                        f"but request asked for '{request.model}'."
                    ),
                )

            chat_session = record.chat
            session_lock = record.lock
            response_session_id = request.session_id

        else:
            chat_session = state.create_ephemeral_chat(
                token=request.token,
                model=request.model,
                god_mode=request.god_mode,
            )

            session_lock = threading.Lock()
            response_session_id = None

        if request.stream:
            def stream_text() -> Generator[str, None, None]:
                with session_lock:
                    try:
                        for chunk in chat_session.respond(
                            request.message,
                            thinking=request.thinking,
                            search=request.search,
                            stream=True,
                        ):
                            yield chunk

                    except Exception as exc:
                        yield f"\n[DeepWrap API error] {exc}\n"

            def stream_sse() -> Generator[str, None, None]:
                with session_lock:
                    try:
                        for chunk in chat_session.respond(
                            request.message,
                            thinking=request.thinking,
                            search=request.search,
                            stream=True,
                        ):
                            yield format_sse_chunk(chunk)

                        yield "event: done\ndata: [DONE]\n\n"

                    except Exception as exc:
                        yield f"event: error\ndata: {str(exc)}\n\n"

            if request.stream_format == "sse":
                return StreamingResponse(
                    stream_sse(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )

            return StreamingResponse(
                stream_text(),
                media_type="text/plain; charset=utf-8",
            )

        with session_lock:
            try:
                response = chat_session.respond(
                    request.message,
                    thinking=request.thinking,
                    search=request.search,
                    stream=False,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Chat request failed: {exc}",
                ) from exc

        return ChatResponse(
            model=request.model,
            response=response,
            session_id=response_session_id,
        )

    return app


app = create_app()