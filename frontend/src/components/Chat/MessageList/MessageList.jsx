import { useEffect, useRef, Fragment, useState } from "react";

import UserMessage from "../UserMessage/UserMessage";
import AIMessage from "../AIMessage/AIMessage";
import LoadingProcess from "../LoadingProcess/LoadingProcess";
import DateHeader from "../../DateHeader/DateHeader";

import "./MessageList.css";

function MessageList({
    chatId,
    messages,
    isLoading,
}) {
    const messagesEndRef = useRef(null);

    // localStorage에서 번역 상태 불러오기
    const storageKey = `translatedMap_${chatId || "temp"}`;

    const [translatedMap, setTranslatedMap] = useState(() => {
        const saved = localStorage.getItem(storageKey);
        return saved ? JSON.parse(saved) : {};
    });

    // 번역 상태가 바뀔 때마다 저장
    useEffect(() => {
        localStorage.setItem(
            storageKey,
            JSON.stringify(translatedMap)
        );
    }, [translatedMap, storageKey]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({
            behavior: "smooth",
        });
    }, [messages]);

    function isDifferentDay(prev, current) {
        if (!prev) return true;

        const prevDate = new Date(prev.createdAt);
        const currentDate = new Date(current.createdAt);

        return (
            prevDate.getFullYear() !== currentDate.getFullYear() ||
            prevDate.getMonth() !== currentDate.getMonth() ||
            prevDate.getDate() !== currentDate.getDate()
        );
    }

    return (
        <div className="message-list">
            <div className="message-content">

                {messages.map((message, index) => {
                    const previousMessage = messages[index - 1];
                    const isTranslated = translatedMap[message.id] || false;

                    return (
                        <Fragment key={message.id}>

                            {message.createdAt &&
                                isDifferentDay(previousMessage, message) && (
                                    <DateHeader date={message.createdAt} />
                            )}

                            {message.sender === "user" ? (() => {
                                // 바로 다음 assistant 메시지 찾기
                                const nextAssistant = messages
                                    .slice(index + 1)
                                    .find((m) => m.sender === "assistant");

                                return (
                                    <UserMessage
                                        text={message.text}
                                        translatedText={
                                            message.questionKo || nextAssistant?.questionKo
                                        }
                                        isTranslated={
                                            nextAssistant
                                                ? translatedMap[nextAssistant.id]
                                                : false
                                        }
                                    />
                                );
                            })() : (
                                <AIMessage
                                    text={message.text}
                                    answerKo={message.answerKo}
                                    guidelines={message.guidelines}
                                    graph={message.graph}
                                    isTranslated={isTranslated}
                                    setIsTranslated={() =>
                                        setTranslatedMap(prev => ({
                                            ...prev,
                                            [message.id]: !prev[message.id],
                                        }))
                                    }
                                />
                            )}

                        </Fragment>
                    );
                })}

                {isLoading && <LoadingProcess />}

                <div ref={messagesEndRef} />

            </div>
        </div>
    );
}

export default MessageList;