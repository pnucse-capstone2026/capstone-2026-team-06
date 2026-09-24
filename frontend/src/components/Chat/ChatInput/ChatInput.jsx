import { useEffect, useRef } from "react";
import { IoSend } from "react-icons/io5";

import "./ChatInput.css";

function ChatInput({
  onSend,
  question,
  setQuestion,
  isLoading,
  variant = "room",
}) {
  const textareaRef = useRef(null);
  const MAX_HEIGHT = 200;
  const handleSend = () => {
    if (question.trim() === "" || isLoading) return;
    onSend(question);
  };
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  const handleChange = (e) => {
    setQuestion(e.target.value);
  };
  useEffect(() => {
    const textarea = textareaRef.current;

    if (!textarea) return;

    // 질문이 비어 있으면 무조건 원래 크기로 초기화
    if (question === "") {
      textarea.style.height = "auto";
      textarea.style.overflowY = "hidden";
      return;
    }

    // 먼저 높이를 초기화한 뒤 실제 내용 높이를 측정
    textarea.style.height = "auto";

    if (textarea.scrollHeight > MAX_HEIGHT) {
      textarea.style.height = `${MAX_HEIGHT}px`;
      textarea.style.overflowY = "auto";
    } else {
      textarea.style.height = `${textarea.scrollHeight}px`;
      textarea.style.overflowY = "hidden";
    }
  }, [question]);

  return (
    <div className={`chat-input-container ${variant}`}>
      <textarea
        ref={textareaRef}
        className="chat-input"
        placeholder="의료 관련 질문을 입력하세요..."
        value={question}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        rows={1}
      />

      <button
        className="send-button"
        onClick={handleSend}
        disabled={question.trim() === "" || isLoading}
      >
        <IoSend />
      </button>
    </div>
  );
}

export default ChatInput;