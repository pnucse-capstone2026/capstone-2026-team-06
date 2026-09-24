import { LuEllipsisVertical } from "react-icons/lu";

import "./ChatHistoryItem.css";

function ChatHistoryItem({
    chat,

    activeChatId,
    handleSelectChat,

    menuChatId,
    setMenuChatId,

    menuRef,
    setMenuPosition,

    editingChatId,
    editingTitle,
    setEditingTitle,
    setEditingChatId,

    chatHistory,
    setChatHistory,

    handleRenameChat,
}) {
    return (
        <div
            className={`chat-history-item
                ${activeChatId === chat.id ? "active" : ""}
                ${menuChatId === chat.id ? "menu-open" : ""}
            `}
        >

            <button
                className="chat-main"
                onClick={() => handleSelectChat(chat.id)}
            >

                {editingChatId === chat.id ? (

                    <input
                        className="chat-title-input"
                        autoFocus
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={async (e) => {

                            if (e.key !== "Enter") return;

                            const title = editingTitle.trim();

                            if (title === "") {
                                setEditingTitle(chat.title);
                                setEditingChatId(null);
                                return;
                            }

                            if (title === chat.title) {
                                setEditingChatId(null);
                                return;
                            }
                            
                            await handleRenameChat(
                                chat.id,
                                title,
                            );

                            setEditingChatId(null);
                        }}
                        onBlur={() => {
                            if (editingChatId !== chat.id) return;

                            setEditingTitle(chat.title);
                            setEditingChatId(null);
                        }}
                    />

                ) : (

                    <span
                        className={`chat-history-title
                            ${activeChatId === chat.id
                                ? "active-title"
                                : ""
                            }
                        `}
                    >
                        {chat.title}
                    </span>

                )}

            </button>

            <div
                className="chat-more-wrapper"
                ref={
                    menuChatId === chat.id
                        ? menuRef
                        : null
                }
            >

                <button
                    className="chat-more"
                    onClick={(e) => {

                        e.stopPropagation();

                        if (menuChatId === chat.id) {
                            setMenuChatId(null);
                            return;
                        }

                        const rect =
                            e.currentTarget.getBoundingClientRect();

                        setMenuPosition({
                            top: rect.bottom + 6,
                            left: rect.right - 25,
                        });

                        setMenuChatId(chat.id);
                    }}
                >
                    <LuEllipsisVertical />
                </button>

            </div>

        </div>
    );
}

export default ChatHistoryItem;