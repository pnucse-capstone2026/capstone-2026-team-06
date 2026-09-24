"""
FastAPI

역할
- HTTP Request 수신
- Pipeline 실행
- 결과 반환

실제 의료 QA 로직은 pipeline.py에서 수행
"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.dependencies import get_pipeline, get_neo4j_driver
from backend.pipeline import Pipeline

from backend.database.database import get_db
from backend.database import crud, schemas, models


# lifespan 추가
# verify_connectivity()로 여기서 미리 접속을 확인해 설정이 잘못됐으면 앱 기동 단계에서 바로 실패시킴.
@asynccontextmanager 
async def lifespan(app: FastAPI):
    driver = get_neo4j_driver()
    driver.verify_connectivity()
    yield
    driver.close()

FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN",
    "http://localhost:2042",
)

app = FastAPI(
    title="Medical QA API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    chat_id: int | None = None
    question: str

# 엔드포인트 정의
@app.get("/")
def root():
    return {
        "message": "Medical QA API is running."
    }

@app.post("/api/chat")
def medical_qa(
    request: ChatRequest,
    pipeline: Pipeline = Depends(get_pipeline),
    db: Session = Depends(get_db),
):
    # 1. 채팅 찾기 또는 생성
    if request.chat_id:
        chat = crud.get_chat(db, request.chat_id)

        if chat is None:
            raise HTTPException(
                status_code=404,
                detail="Chat not found",
            )
    else:
        # 첫 질문 일부만 채팅 제목으로 사용
        title = request.question.strip()

        if len(title) > 80:
            title = title[:80].rstrip() + "..."

        chat = crud.create_chat(
            db=db,
            title=title,
        )

    # 2. 대화 히스토리 조회 (질문 재구성용)
    # 신규 채팅이면 이전 대화가 없으므로 조회 생략
    if request.chat_id:
        history = crud.get_recent_messages(
            db=db,
            chat_id=chat.id,
            limit=6,   # 최근 3턴 (질문 + 답변 3쌍)
        )
    else:
        history = []

    # 3. 사용자 질문 저장
    user_message = crud.create_message(
        db=db,
        chat_id=chat.id,
        role="user",
        content=request.question,
    )

    # 4. QA 실행
    result = pipeline.run(
        request.question,
        history=history,
    )

    # 5. 사용자 질문의 한국어 번역 업데이트
    crud.update_message_translation(
        db=db,
        message_id=user_message.id,
        question_ko=result.get("question_ko"),
    )

    # 6. AI 답변 저장
    crud.create_message(
        db=db,
        chat_id=chat.id,
        role="assistant",
        content=result["answer"],
        answer_ko=result.get("answer_ko"),
        graph=result.get("graph"),
        guidelines=result.get("guidelines"),
    )

    # 6. chat_id 추가
    result["chat_id"] = chat.id

    return result

@app.post("/api/chats", response_model=schemas.ChatResponse)
def create_chat(
    db: Session = Depends(get_db),
):
    """
    새 채팅 생성
    """

    return crud.create_chat(
        db=db,
        title="새 채팅",
    )

@app.get("/api/chats", response_model=list[schemas.ChatResponse])
def get_chats(
    db: Session = Depends(get_db),
):
    """
    채팅 목록 조회
    """

    return crud.get_chats(db)

@app.get("/api/chats/{chat_id}", response_model=schemas.ChatDetail)
def get_chat(
    chat_id: int,
    db: Session = Depends(get_db),
):
    """
    채팅 하나 조회
    """

    chat = crud.get_chat(db, chat_id)

    if chat is None:
        raise HTTPException(
            status_code=404,
            detail="Chat not found",
        )

    return chat

@app.delete("/api/chats/{chat_id}")
def delete_chat(
    chat_id: int,
    db: Session = Depends(get_db),
):
    """
    채팅 삭제
    """

    chat = crud.delete_chat(
        db,
        chat_id,
    )

    if chat is None:
        raise HTTPException(
            status_code=404,
            detail="Chat not found",
        )

    return {
        "message": "Deleted successfully"
    }

@app.patch(
    "/api/chats/{chat_id}",
    response_model=schemas.ChatResponse,
)
def rename_chat(
    chat_id: int,
    request: schemas.ChatUpdate,
    db: Session = Depends(get_db),
):
    """
    채팅 제목 변경
    """

    chat = crud.rename_chat(
        db=db,
        chat_id=chat_id,
        title=request.title,
    )

    if chat is None:
        raise HTTPException(
            status_code=404,
            detail="Chat not found",
        )

    return chat