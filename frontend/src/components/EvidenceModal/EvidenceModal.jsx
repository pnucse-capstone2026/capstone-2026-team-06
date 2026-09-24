import { useEffect } from "react";
import { IoClose } from "react-icons/io5";
import ReactMarkdown from "react-markdown";
import KnowledgeGraph from "./KnowledgeGraph";

import "./EvidenceModal.css";

function EvidenceModal({
    isOpen,
    onClose,
    guidelines,
    graph,
}) {
    const guidelineCards = guidelines
        ? guidelines.split(/\n(?=\[)/)
        : [];

    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = "hidden";
        } else {
            document.body.style.overflow = "auto";
        }
        return () => {
            document.body.style.overflow = "auto";
        };
    }, [isOpen]);
    if (!isOpen) return null;
    return (
        <div className="evidence-modal-overlay">
            <div className="evidence-modal">
                <div className="evidence-header">
                    <h2>답변 생성 근거</h2>
                    <button
                        className="evidence-close-button"
                        onClick={onClose}
                    >
                        <IoClose />
                    </button>
                </div>
                <div className="evidence-content">

                    <section>
                        <h3>1. 임상 진료지침(Clinical Guidelines)</h3>
                        {guidelines ? (
                            <>
                                {guidelineCards.map((card, index) => {
                                    const lines = card.trim().split("\n");

                                    const rawTitle = lines[0]
                                        .replace(/^\[/, "")
                                        .replace(/\]$/, "");

                                    const [organization, ...rest] = rawTitle.split(" - ");
                                    const disease = rest.join(" - ");

                                    // Section 추출
                                    let body = lines.slice(1);
                                    let section = "";

                                    if (body.length > 0 && body[0].startsWith("Section:")) {
                                        section = body[0].replace("Section:", "").trim();
                                        body = body.slice(1);
                                    }

                                    const markdown = body.join("\n");

                                    return (
                                        <div
                                            key={index}
                                            className="guideline-card"
                                        >
                                            <div className="guideline-header">
                                                <span
                                                    className={`guideline-badge ${organization.toLowerCase()}`}
                                                >
                                                    {organization}
                                                </span>
                                                <span className="guideline-title">
                                                    {disease}
                                                </span>
                                            </div>

                                            {section && (
                                                <div className="guideline-section">
                                                    <span className="section-badge">
                                                        Section
                                                    </span>
                                                    <span className="section-text">
                                                        {section}
                                                    </span>
                                                </div>
                                            )}
                                            <div className="guideline-divider" />

                                            <div className="guideline-content">
                                                <ReactMarkdown>
                                                    {markdown}
                                                </ReactMarkdown>
                                            </div>
                                        </div>
                                    );
                                })}
                            </>
                        ) : (
                            <div className="empty-card">
                                생성에 사용된 임상 진료지침이 없습니다.
                            </div>
                        )}
                    </section>

                    <section>
                        <h3>2. 지식 그래프(Knowledge Graph)</h3>
                        {graph &&
                        graph.nodes &&
                        graph.nodes.length > 0 ? (
                            <KnowledgeGraph graph={graph} />
                        ) : (
                            <div className="empty-card">
                                생성에 사용된 지식 그래프가 없습니다.
                            </div>
                        )}
                    </section>
                </div>
            </div>
        </div>
    );
}

export default EvidenceModal;