import { useEffect, useState } from "react";
import {
    getChats,
    getChat,
    deleteChat,
    renameChat,
} from "./api/chatApi";

import "./App.css";

import Sidebar from "./components/Sidebar/Sidebar";
import ChatPage from "./components/Chat/ChatPage/ChatPage";

function App() {
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    const [activeChatId, setActiveChatId] = useState(null);
    const [chatHistory, setChatHistory] = useState([]);

    const [page, setPage] = useState("home");

    const [question, setQuestion] = useState("");
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        async function fetchChats() {
        try {
            const chats = await getChats();
            setChatHistory(chats);
        } catch (error) {
            console.error(error);
        }
        }

        fetchChats();
    }, []);

    const handleSelectChat = async (chatId) => {
        try {
            const chat = await getChat(chatId);
            setActiveChatId(chatId);
            setMessages(
                [...chat.messages]
                    .sort((a, b) => a.id - b.id)
                    .map((message) => ({
                        id: message.id,
                        sender: message.role,
                        text: message.content,
                        questionKo: message.question_ko,
                        answerKo: message.answer_ko,
                        graph: message.graph,
                        guidelines: message.guidelines,
                        createdAt: message.created_at,
                    }))
            );

            setQuestion("");
            setPage("chat");
        } catch (error) {
            console.error(error);
        }
    };

    const handleDeleteChat = async (chatId) => {
        try {
            await deleteChat(chatId);

            const chats = await getChats();
            setChatHistory(chats);

            if (activeChatId === chatId) {
                setActiveChatId(null);
                setMessages([]);
                setQuestion("");
                setPage("chat");
            }
        } catch (error) {
            console.error(error);
        }
    };

    const handleRenameChat = async (
        chatId,
        title,
    ) => {
        try {
            await renameChat(chatId, title);

            setChatHistory(prev =>
                prev.map(chat =>
                    chat.id === chatId
                        ? { ...chat, title }
                        : chat
                )
            );
        } catch (error) {
            console.error(error);
        }
    };

    return (
        <div className="app">
        <Sidebar
            isOpen={isSidebarOpen}
            toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}

            activeChatId={activeChatId}
            setActiveChatId={setActiveChatId}

            chatHistory={chatHistory}
            setChatHistory={setChatHistory}

            page={page}
            setPage={setPage}

            setQuestion={setQuestion}
            setMessages={setMessages}

            handleSelectChat={handleSelectChat}
            handleDeleteChat={handleDeleteChat}
            handleRenameChat={handleRenameChat}
        />
        <ChatPage
            activeChatId={activeChatId}
            setActiveChatId={setActiveChatId}

            chatHistory={chatHistory}
            setChatHistory={setChatHistory}

            page={page}
            setPage={setPage}

            question={question}
            setQuestion={setQuestion}

            messages={messages}
            setMessages={setMessages}

            isLoading={isLoading}
            setIsLoading={setIsLoading}
        />
        </div>
    );
}

export default App;