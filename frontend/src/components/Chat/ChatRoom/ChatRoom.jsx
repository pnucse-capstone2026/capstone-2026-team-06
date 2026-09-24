import "./ChatRoom.css";

import MessageList from "../MessageList/MessageList";
import ChatInput from "../ChatInput/ChatInput";
import ChatHeader from "../ChatHeader/ChatHeader";

function ChatRoom({ 
    chatId,
    messages, 
    question, 
    setQuestion, 
    onSend, 
    isLoading, 
    onGoHome,
}) {

  return (
    <div className="chat-room">

        <ChatHeader onGoHome={onGoHome} />


            <div className="chat-content">

                {messages.length === 0 && (
                    <div className="chat-empty">
                        <h2 className="chat-empty-title">
                            대화를 시작하세요
                        </h2>

                        <p className="chat-empty-description">
                            의료 지식 그래프와 임상 가이드라인을 기반으로 답변을 제공합니다.
                        </p>
                    </div>
                )}

                <MessageList
                    chatId={chatId}
                    messages={messages}
                    isLoading={isLoading}
                />

            </div>

            <div className="chat-input-area">
                <ChatInput
                    variant="room"
                    question={question}
                    setQuestion={setQuestion}
                    onSend={onSend}
                    isLoading={isLoading}
                />
            </div>

        </div>
  );
}

export default ChatRoom;