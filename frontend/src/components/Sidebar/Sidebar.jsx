import { useEffect, useRef, useState } from "react";
import { FiMenu } from "react-icons/fi";
import {
  LuDroplets,
  LuHeartPulse,
  LuStethoscope,
  LuHeart,
  LuWind,
  LuPlus,
  LuEllipsisVertical,
  LuTrash2,
  LuPencil,
} from "react-icons/lu";
import { FiChevronDown } from "react-icons/fi";
import { PiCheeseFill } from "react-icons/pi";

import ChatHistoryItem from "../ChatHistoryItem/ChatHistoryItem";
import DeleteModal from "../DeleteModal/DeleteModal";
import MenuPortal from "../MenuPortal/MenuPortal";

import "./Sidebar.css";

function Sidebar({
    isOpen,
    toggleSidebar,
    activeChatId,
    setActiveChatId,

    chatHistory,
    setChatHistory,

    setPage,
    setQuestion,
    setMessages,

    handleSelectChat,
    handleDeleteChat,
    handleRenameChat,
}) {
  const [showChats, setShowChats] = useState(true);
  const [showDiseases, setShowDiseases] = useState(false);
  const [menuChatId, setMenuChatId] = useState(null);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [deleteChatId, setDeleteChatId] = useState(null);
  const [menuPosition, setMenuPosition] = useState({
      top: 0,
      left: 0,
  });
  const [editingChatId, setEditingChatId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const menuRef = useRef(null);
  const portalRef = useRef(null);

  useEffect(() => {
      function handleClickOutside(event) {
          if (
              menuRef.current &&
              !menuRef.current.contains(event.target) &&
              portalRef.current &&
              !portalRef.current.contains(event.target)
          ) {
              setMenuChatId(null);
          }
      }

      document.addEventListener(
          "click",
          handleClickOutside
      );

      return () => {
          document.removeEventListener(
              "click",
              handleClickOutside
          );
      };
  }, []);
  
  return (
    <aside className={`sidebar ${isOpen ? "open" : "closed"}`}>
      <div className="sidebar-top">
        {isOpen ? (
          <>
            <div className="team-logo">
              <PiCheeseFill />
            </div>

            <button
              className="menu-button"
              onClick={toggleSidebar}
            >
              <FiMenu />
            </button>
          </>
        ) : (
          <button
            className="logo-button"
            onClick={toggleSidebar}
          >
            <PiCheeseFill className="logo-icon" />
            <FiMenu className="menu-icon-hover" />
          </button>
        )}
      </div>

      {isOpen && (
        <>
            {/* ================= 위쪽 ================= */}
            <div className="sidebar-content">

              {/* 새 채팅 */}
              <button
                className="new-chat-btn"
                onClick={() => {
                    setActiveChatId(null);
                    setPage("chat");
                    setQuestion("");
                    setMessages([]);
                }}
              >
                <LuPlus className="new-chat-icon" />
                <span>새 채팅</span>
              </button>

              {/* 채팅 목록 */}
              <div className="sidebar-section chat-section">

                <button
                  className="section-header"
                  onClick={() => setShowChats(!showChats)}
                >
                  <span>채팅</span>

                  <FiChevronDown
                    className={`section-arrow ${
                      showChats ? "open" : ""
                    }`}
                  />
                </button>

                {showChats && (
                  <div className="chat-history-list">

                    <div className="section-content">

                    {chatHistory.map((chat) => (

                        <ChatHistoryItem
                            key={chat.id}

                            chat={chat}

                            activeChatId={activeChatId}
                            handleSelectChat={handleSelectChat}

                            menuChatId={menuChatId}
                            setMenuChatId={setMenuChatId}

                            menuRef={menuRef}
                            setMenuPosition={setMenuPosition}

                            editingChatId={editingChatId}
                            editingTitle={editingTitle}
                            setEditingTitle={setEditingTitle}
                            setEditingChatId={setEditingChatId}

                            chatHistory={chatHistory}
                            setChatHistory={setChatHistory}

                            handleRenameChat={handleRenameChat}
                        />

                    ))}

                    </div>

                  </div>
                )}

              </div>

            </div>

            {/* ================= 아래쪽 ================= */}
            <div className="sidebar-bottom">

              <div className="sidebar-section">

                <button
                  className="section-header"
                  onClick={() =>
                    setShowDiseases(!showDiseases)
                  }
                >
                  <span>지원 질환</span>

                  <FiChevronDown
                    className={`section-arrow ${
                      showDiseases ? "open" : ""
                    }`}
                  />
                </button>

                {showDiseases && (
                  <ul className="disease-list">

                    <li className="disease-item">
                      <div className="disease-icon">
                        <LuDroplets />
                      </div>
                      <span>제2형 당뇨병</span>
                    </li>

                    <li className="disease-item">
                      <div className="disease-icon">
                        <LuHeartPulse />
                      </div>
                      <span>고혈압</span>
                    </li>

                    <li className="disease-item">
                      <div className="disease-icon">
                        <LuStethoscope />
                      </div>
                      <span>만성 신장질환 (CKD)</span>
                    </li>

                    <li className="disease-item">
                      <div className="disease-icon">
                        <LuHeart />
                      </div>
                      <span>심부전</span>
                    </li>

                    <li className="disease-item">
                      <div className="disease-icon">
                        <LuWind />
                      </div>
                      <span>만성 폐쇄성 폐질환 (COPD)</span>
                    </li>

                  </ul>
                )}

            </div>

          </div>

          {/* ================= Footer ================= */}
          <div className="sidebar-footer">

            <div className="sidebar-notice">

              <div className="notice-text">
                &#8251; 본 시스템은 의료 정보 제공을 위한 서비스이며,
                전문적인 의료 상담 및 진료를 대체하지 않습니다.
              </div>

            </div>

          </div>
        </>
      )}

      <MenuPortal
          isOpen={menuChatId !== null}
          top={menuPosition.top}
          left={menuPosition.left}
      >
          <div
              ref={portalRef}
              className="chat-menu"
          >

              <button
                  className="chat-menu-item rename"
                  onClick={() => {
                      const chat = chatHistory.find(
                          (c) => c.id === menuChatId
                      );

                      setEditingChatId(menuChatId);
                      setEditingTitle(chat.title);

                      setMenuChatId(null);
                  }}
              >
                  <LuPencil className="chat-menu-icon edit" />
                  <span>이름 바꾸기</span>
              </button>

              <button
                  className="chat-menu-item delete"
                  onClick={() => {
                      setDeleteChatId(menuChatId);
                      setIsDeleteOpen(true);
                      setMenuChatId(null);
                  }}
              >
                  <LuTrash2 className="chat-menu-icon delete" />
                  <span>삭제</span>
              </button>

          </div>
      </MenuPortal>

      <DeleteModal
          isOpen={isDeleteOpen}
          onClose={() => setIsDeleteOpen(false)}
          onDelete={async () => {
              await handleDeleteChat(deleteChatId);

              setIsDeleteOpen(false);
              setDeleteChatId(null);
          }}
      />
    </aside>
  );
}

export default Sidebar;