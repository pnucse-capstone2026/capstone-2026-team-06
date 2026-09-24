'''
# Gemma(Ollama)와 통신만 담당하는 모듈
# 즉, prompt(str)을 받아 Gemma에게 보내고 답변(str)을 반환

# 사용할 라이브러리: Ollama
- 로컬에서 실행
- 내부적으로 http://localhost:11434에 API 서버를 열어줌
FastAPI -> localhost:11434 -> Gemma 처럼 사용 가능함
- 모델 교체가 쉬움
- 코드가 짧음

# def __init__의 parameters
- host: LLM 서버(Ollama)가 실행되고 있는 주소
Ollama를 실행하면 기본적으로 localhost:11434에 API 서버를 열어줌
- model: "gemma4:12b" 사용 예정
(ollama list 실행해서 실제 모델 이름 확인 후 model에 넣기)
- temperature: 답변의 랜덤성(창의성)을 조절하는 값
값이 0이면 항상 거의 같은 답변
값이 1이면 조금씩 표현이 달라져 다양한 표현이 나옴
값이 2이면 제법 창의적이어서 소설 등을 쓸 때 좋음
우리 플젝은 의료 QA이므로 정확성>창의성 -> 0.0~0.2 사용
- num_predict: 최대 몇개의 토큰을 생성할 것인가
- top_p: 랜덤성 조절
- top_k: 후보 개수 제한
- repeat_penalty: 같은 말을 계속 반복하지 못하게 하는 옵션
- seed: random seed, seed=42로 설정하면 매번 같은 질문에 거의 같은 답변 생성
실험을 반복하거나 모델이나 성능을 비교할때 유용
LLM 단독 vs Graph-RAG 비교하는 실험할 때, seed를 고정해 두는 것이 결과를 비교하기에 더 좋음

# def generate에서의 client.generate(...) vs client.chat(...)
- client.generate(model="gemma4", prompt="...")
Prompt Builder 안에 Question, Graph Context, Guideline 뿐만 아니라,
Instruction까지 넣어서 prompt를 만듦

- client.chat(model="gemma4", messages=[...])
messages=[
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt},
]
Prompt Builder 안에 Instruction을 만들지 않고,
Prompt Builder = System Prompt + User Prompt 형태로 만듦
즉, System Prompt에 instruction을 넣고
User Prompt에 Question, Graph Context, Guideline을 넣음

llm은 내부적으로 System -> User -> Assistant 순서로 읽음
System: AI의 행동 원칙을 정하는 곳
(절대 변하지 않는 규칙만 넣는 것이 좋음)
User: 이번 질문에서 처리해야 하는 데이터
(매 질문마다 바뀌는 내용만 넣는 것이 좋음)


system_prompt, user_prompt = prompt_builder.build(
    question,
    graph_context,
    guideline_context
)

answer = llm.generate(
    system_prompt,
    user_prompt
)
'''


from ollama import Client


class LLM:
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "gemma4:12b",
        temperature: float = 0.1,
        num_predict: int = 1024,
        seed: int | None = None,
        think: bool = False # 추론모드
    ):
        self.client = Client(host=host)
        self.model = model
        self.think = think

        self.options = {
            "temperature": temperature,
            "num_predict": num_predict,
        }

        if seed is not None:
            self.options["seed"] = seed

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        options: dict | None = None,  # 호출 시 일부 옵션만 변경 가능 (ex.번역 시 temperature=0)
        think: bool | None = None,  # 호출 시 think 모드 변경 가능 (ex.번역 시 think=False)
    ) -> str:

        try:
            # 기본 옵션 복사 후 필요한 값만 덮어쓰기
            chat_options = self.options.copy()
            if options is not None:
                chat_options.update(options)

            # think를 넘기지 않으면 기본값(self.think) 사용
            chat_think = self.think if think is None else think

            
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                options=chat_options,
                think=chat_think,
            )

            return response["message"]["content"].strip()

        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {e}")
