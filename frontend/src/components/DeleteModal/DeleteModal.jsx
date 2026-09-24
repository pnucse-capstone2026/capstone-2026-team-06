import { useEffect } from "react";
import { IoClose } from "react-icons/io5";

import "./DeleteModal.css";

function DeleteModal({
    isOpen,
    onClose,
    onDelete,
}) {

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
        <div
            className="delete-modal-overlay"
            onClick={onClose}
        >
            <div
                className="delete-modal"
                onClick={(e) => e.stopPropagation()}
            >
                <button
                    className="delete-close-button"
                    onClick={onClose}
                >
                    <IoClose />
                </button>

                <h2>
                    채팅을 삭제하시겠습니까?
                </h2>

                <p>
                    삭제한 채팅은 복구할 수 없습니다.
                </p>

                <div className="delete-actions">

                    <button
                        className="cancel-button"
                        onClick={onClose}
                    >
                        취소
                    </button>

                    <button
                        className="delete-button"
                        onClick={onDelete}
                    >
                        삭제
                    </button>

                </div>

            </div>
        </div>
    );
}

export default DeleteModal;