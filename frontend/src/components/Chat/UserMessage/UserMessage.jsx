import "./UserMessage.css";

function UserMessage({
  text,
  translatedText,
  isTranslated,
}) {
  const displayText =
    isTranslated && translatedText
      ? translatedText
      : text;

  return (
    <div className="user-message-container">
      <div className="user-message">
        {displayText}
      </div>
    </div>
  );
}

export default UserMessage;