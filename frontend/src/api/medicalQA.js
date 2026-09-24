const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function getAIResponse(chatId, question) {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            chat_id: chatId,
            question,
        }),
    });

    if (!response.ok) {
        throw new Error("API 요청 실패");
    }

    const data = await response.json();

    console.log("Original Question:", data.question);
    console.log("Rewritten Question:", data.rewritten_question);

    return data;
}