from sqlalchemy.orm import Session
from backend.database.models import Chat, Message


def create_chat(db: Session, title: str) -> Chat:
    """
    새로운 채팅 생성
    """

    # DB VARCHAR(255) 보호
    safe_title = title.strip()[:200]

    chat = Chat(title=title)

    db.add(chat)
    db.commit()
    db.refresh(chat)

    return chat


def get_chats(db: Session):
    """
    전체 채팅 목록 조회
    최신 수정순
    """
    return (
        db.query(Chat)
        .order_by(Chat.updated_at.desc())
        .all()
    )


def get_chat(db: Session, chat_id: int):
    """
    채팅 하나 조회
    """
    return (
        db.query(Chat)
        .filter(Chat.id == chat_id)
        .first()
    )


def create_message(
    db: Session,
    chat_id: int,
    role: str,
    content: str,
    question_ko=None,
    answer_ko=None,
    graph=None,
    guidelines=None,
) -> Message:
    """
    메시지 저장
    """

    message = Message(
        chat_id=chat_id,
        role=role,
        content=content,
        question_ko=question_ko,
        answer_ko=answer_ko,
        graph=graph,
        guidelines=guidelines,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


def get_messages(
    db: Session,
    chat_id: int,
):
    """
    채팅의 모든 메시지 조회
    """

    return (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.id.asc())
        .all()
    )


def delete_chat(
    db: Session,
    chat_id: int,
):
    """
    채팅 삭제
    """

    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id)
        .first()
    )

    if chat is None:
        return None

    db.delete(chat)
    db.commit()

    return chat


def rename_chat(
    db: Session,
    chat_id: int,
    title: str,
):
    """
    채팅 제목 변경
    """

    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id)
        .first()
    )

    if chat is None:
        return None

    chat.title = title.strip()[:200]

    db.commit()
    db.refresh(chat)

    return chat

    
def get_recent_messages(
    db: Session,
    chat_id: int,
    limit: int = 6,          # 3턴(질문+답변 3쌍) = 메시지 6개
    exclude_last: int = 0,   # 최근 N개 제외 (방금 저장한 현재 질문을 걸러낼 때)
) -> list[dict]:
    """
    최근 메시지를 재작성 프롬프트용 형태로 반환

    Returns:
        [{"role": "user", "content": "..."},
         {"role": "assistant", "content": "..."}, ...]
        (오래된 것 -> 최신 순)
    """

    # 1) 최신순으로 필요한 만큼만 조회
    messages = (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.id.desc())
        .limit(limit + exclude_last)
        .all()
    )

    # 2) 방금 저장한 메시지 제외 (최신순 상태에서 앞쪽을 자름)
    if exclude_last > 0:
        messages = messages[exclude_last:]

    # 3) 시간순(오래된 것부터)으로 뒤집기
    messages = list(reversed(messages))

    # 4) dict 형태로 변환
    return [
        {"role": m.role, "content": m.content}
        for m in messages
    ]


def update_message_translation(
    db: Session,
    message_id: int,
    question_ko: str | None = None,
):
    """
    사용자 메시지의 한국어 번역 업데이트
    """

    message = (
        db.query(Message)
        .filter(Message.id == message_id)
        .first()
    )

    if message is None:
        return None

    message.question_ko = question_ko

    db.commit()
    db.refresh(message)

    return message