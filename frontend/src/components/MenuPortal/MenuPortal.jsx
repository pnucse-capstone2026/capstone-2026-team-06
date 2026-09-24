import { createPortal } from "react-dom";

function MenuPortal({
    isOpen,
    top,
    left,
    children,
}) {
    if (!isOpen) return null;

    return createPortal(
        <div
            style={{
                position: "fixed",
                top,
                left,
                zIndex: 3000,
            }}
        >
            {children}
        </div>,
        document.body
    );
}

export default MenuPortal;