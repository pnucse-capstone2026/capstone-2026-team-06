import { useState } from "react";
import { LuSearchCode, LuSearch, LuSparkle } from "react-icons/lu";
import ReactMarkdown from "react-markdown";

import EvidenceModal from "../../EvidenceModal/EvidenceModal";

import "./AIMessage.css";

function AIMessage({
    text,
    answerKo,
    guidelines,
    graph,
    isTranslated,
    setIsTranslated,
}) {
    const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);
    
    const guidelineCount = guidelines
        ? guidelines
            .split(/\n(?=\[)/)
            .filter((card) => card.trim()).length
        : 0;
    const conceptCount = graph?.nodes?.length ?? 0;
    const hasEvidence = guidelineCount > 0 || conceptCount > 0;
    return (
        <div className="ai-message-container">
            <div className="ai-message">

                <div className="ai-message-text">
                    <ReactMarkdown>
                        {isTranslated && answerKo ? answerKo : text}
                    </ReactMarkdown>
                </div>

                <div className="evidence-button-wrapper">

                    <button
                        className="evidence-button"
                        onClick={setIsTranslated}
                    >
                        <LuSparkle />

                        <span className="evidence-tooltip">
                            {isTranslated ? "원문 보기" : "한국어 번역"}
                        </span>
                    </button>

                </div>
                
                {hasEvidence && (
                    <div className="evidence-card">

                        <div className="evidence-card-icon">
                            <LuSearch />
                        </div>

                        <div className="evidence-card-content">
                            <div className="evidence-card-title">
                                근거 기반 답변
                            </div>

                            <div className="evidence-card-description">
                                임상 가이드라인{" "}
                                <strong>{guidelineCount}건</strong>
                                {" · "}
                                의료개념{" "}
                                <strong>{conceptCount}개</strong>를
                                바탕으로 작성되었습니다
                            </div>
                        </div>

                        <button
                            type="button"
                            className="evidence-card-action"
                            onClick={() => setIsEvidenceOpen(true)}
                        >
                            근거 보기
                        </button>

                    </div>
                )}

                <EvidenceModal
                    isOpen={isEvidenceOpen}
                    onClose={() => setIsEvidenceOpen(false)}
                    guidelines={guidelines}
                    graph={graph}
                />

            </div>
        </div>
    );
}

export default AIMessage;