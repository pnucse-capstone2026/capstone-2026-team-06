import {
  LuDroplets,
  LuHeartPulse,
  LuStethoscope,
  LuWind,
} from "react-icons/lu";

import "./ExampleQuestions.css";

function ExampleQuestions({ onSelect }) {
  const questions = [
    {
      icon: <LuDroplets />,
      color: "diabetes",
      text: "Why is a urine albumin test performed in patients with diabetes?",
    },
    {
      icon: <LuHeartPulse />,
      color: "hypertension",
      text: "How do calcium channel blockers (CCBs) lower blood pressure?",
    },
    {
      icon: <LuStethoscope />,
      color: "ckd",
      text: "What is the significance of BNP testing in heart failure?",
    },
    {
      icon: <LuWind />,
      color: "copd",
      text: "When COPD symptoms suddenly worsen, what signs suggest an acute exacerbation?",
    },
  ];

  return (
    <div className="example-questions">
      <h3 className="example-title">이런 질문을 할 수 있어요</h3>

      <ul className="question-list">
        {questions.map((question, index) => (
          <li
            key={index}
            className="question-card"
            onClick={() => onSelect(question.text)}
          >
            <div className={`question-icon ${question.color}`}>
              {question.icon}
            </div>

            <span className="question-text">
              {question.text}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ExampleQuestions;