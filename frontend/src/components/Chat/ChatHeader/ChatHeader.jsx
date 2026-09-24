import "./ChatHeader.css";

function ChatHeader({ onGoHome }) {
  return (
    <header className="chat-header">
      <h2
          className="chat-title"
          onClick={onGoHome}
      >
        MedicalQA
      </h2>
    </header>
  );
}

export default ChatHeader;