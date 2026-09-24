import { getAIResponse } from "../../../api/medicalQA";
import { getChats } from "../../../api/chatApi";

import EmptyState from "../EmptyState/EmptyState";
import ChatRoom from "../ChatRoom/ChatRoom";

import "./ChatPage.css";

function ChatPage({
  activeChatId,
  setActiveChatId,

  chatHistory,
  setChatHistory,

  page,
  setPage,

  question,
  setQuestion,

  messages,
  setMessages,

  isLoading,
  setIsLoading,
}) {
  const handleSendQuestion = async (question) => {
    if (question.trim() === "") return;

    const userMessage = {
      id: Date.now(),
      sender: "user",
      text: question,
      questionKo: null,
      isTranslated: false,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setPage("chat");
    setIsLoading(true);

    try {
      const result = await getAIResponse(activeChatId, question);

      setMessages((prev) =>
        prev.map((message) =>
          message.id === userMessage.id
            ? {
                ...message,
                questionKo: result.question_ko,
              }
            : message
        )
      );

      if (activeChatId === null) {
          setActiveChatId(result.chat_id);

          const chats = await getChats();
          setChatHistory(chats);
      }

      const aiMessage = {
          id: Date.now() + 1,
          sender: "assistant",
          text: result.answer,
          answerKo: result.answer_ko,
          isTranslated: false,
          graph: result.graph,
          //conceptSet: result.concept_set,
          guidelines: result.guidelines,
          createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error(error);

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: "assistant",
          text: "오류가 발생했습니다.",
          answerKo: "An error occurred.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoHome = () => {
      setPage("home");

      setMessages([]);
      setQuestion("");
      setActiveChatId(null);
  };

  return (
    <main className="chat-page">
      {page === "chat" ? (
    <ChatRoom
        messages={messages}
        question={question}
        setQuestion={setQuestion}
        onSend={handleSendQuestion}
        isLoading={isLoading}
        onGoHome={handleGoHome}
    />
      ) : (
        <EmptyState
            onSend={handleSendQuestion}
            question={question}
            setQuestion={setQuestion}
        />
      )}
    </main>
  );
}

export default ChatPage;