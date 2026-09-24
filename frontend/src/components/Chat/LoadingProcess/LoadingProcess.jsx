import { useEffect, useState } from "react";

import {
    LuSearch,
    LuLink2,
    LuNetwork,
    LuFileText,
    LuStethoscope,
    LuCheck,
} from "react-icons/lu";

import "./LoadingProcess.css";

const steps = [
    {
        icon: LuSearch,
        text: "Analyzing Question",
    },
    {
        icon: LuLink2,
        text: "Entity Linking",
    },
    {
        icon: LuNetwork,
        text: "Knowledge Graph Retrieval",
    },
    {
        icon: LuFileText,
        text: "Clinical Guideline Retrieval",
    },
    {
        icon: LuStethoscope,
        text: "Generating Answer...",
    },
];

function LoadingProcess() {

    const [currentStep, setCurrentStep] = useState(0);

    useEffect(() => {

        const timers = [];

        timers.push(
            setTimeout(() => setCurrentStep(1), 1500)
        );

        timers.push(
            setTimeout(() => setCurrentStep(2), 3400)
        );

        timers.push(
            setTimeout(() => setCurrentStep(3), 5900)
        );

        timers.push(
            setTimeout(() => setCurrentStep(4), 9000)
        );

        return () => {
            timers.forEach(clearTimeout);
        };

    }, []);

    return (

        <div className="loading-process">

            {steps.map((step, index) => {

                const Icon = step.icon;

                const completed = index < currentStep;
                const active = index === currentStep;

                return (

                    <div
                        key={step.text}
                        className={`loading-step
                            ${completed ? "completed" : ""}
                            ${active ? "active" : ""}`}
                    >

                        <div className="loading-icon">

                            {completed ? (
                                <LuCheck />
                            ) : (
                                <Icon />
                            )}

                        </div>

                        <span>

                            {step.text}

                        </span>

                    </div>

                );

            })}

        </div>

    );

}

export default LoadingProcess;