const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function createChat() {
  const response = await fetch(`${BASE_URL}/api/chats`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("채팅 생성 실패");
  }

  return response.json();
}

export async function getChats() {
  const response = await fetch(`${BASE_URL}/api/chats`);

  if (!response.ok) {
    throw new Error("채팅 목록 조회 실패");
  }

  return response.json();
}

export async function getChat(chatId) {
  const response = await fetch(`${BASE_URL}/api/chats/${chatId}`);

  if (!response.ok) {
    throw new Error("채팅 조회 실패");
  }

  return response.json();
}

export async function deleteChat(chatId) {
    const response = await fetch(
        `${BASE_URL}/api/chats/${chatId}`,
        {
            method: "DELETE",
        }
    );

    if (!response.ok) {
        throw new Error("채팅 삭제 실패");
    }

    return response.json();
}

export async function renameChat(chatId, title) {
    const response = await fetch(
        `${BASE_URL}/api/chats/${chatId}`,
        {
            method: "PATCH",

            headers: {
                "Content-Type": "application/json",
            },

            body: JSON.stringify({
                title,
            }),
        }
    );

    if (!response.ok) {
        throw new Error("채팅 이름 변경 실패");
    }

    return response.json();
}