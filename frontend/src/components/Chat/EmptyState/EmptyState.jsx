import "./EmptyState.css";

import ChatInput from "../ChatInput/ChatInput";
import ExampleQuestions from "../ExampleQuestions/ExampleQuestions";

function EmptyState({ onSend, question, setQuestion }) {
  return (
    <div className="empty-state">
      <h1 className="empty-title">MedicalQA</h1>

      <h2 className="empty-subtitle">
        AI 의료 질의응답 시스템
      </h2>

      <p className="empty-description">
        의료 지식 그래프와 임상 가이드라인을 기반으로 신뢰할 수 있는 답변을 제공합니다.
      </p>

      <ChatInput 
          variant="home"
          onSend={onSend}
          question={question}
          setQuestion={setQuestion} 
      />

      <ExampleQuestions onSelect={setQuestion} />
    </div>
  );
}

export default EmptyState;