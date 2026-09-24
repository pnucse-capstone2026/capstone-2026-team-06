from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ---------- Message ----------

class MessageCreate(BaseModel):
    role: str
    content: str


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str

    question_ko: str | None = None
    answer_ko: str | None = None
    graph: dict[str, Any] | None = None
    guidelines: str | None = None

    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Chat ----------

class ChatCreate(BaseModel):
    title: str


class ChatUpdate(BaseModel):
    title: str


class ChatResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatDetail(ChatResponse):
    messages: list[MessageResponse]


class ChatQAResponse(BaseModel):
    chat_id: int
    answer: str
    sources: list | None = None