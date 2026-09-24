"""
backend/pipeline.py

전체 파이프라인 조립 모듈:
question -> mention -> hybrid search -> concept_set -> graph context
-> guideline -> prompt -> LLM -> 최종 응답 dict

무거운 준비물(임베딩 모델, Qdrant client, Neo4j driver, LLM, hub_keys)은
앱 시작 시 1회 생성해서 주입받는다.

사용법:
    from pipeline import Pipeline

    pipeline = Pipeline(
        mention_detector=mention_detector,
        hybrid_search=hybrid,
        entity_linker=entity_linker,
        graph_context=gc_builder,
        guideline_search=guideline_search,
        guideline_context = guideline_context,
        prompt_builder=prompt_builder,
        llm=llm,
    )
    result = pipeline.run("What drugs treat type 2 diabetes?")

"""

from typing import List, Dict


class Pipeline:
    """
    question 하나를 받아 전체 파이프라인을 실행하고
    최종 응답 dict를 반환

    무거운 준비물(모델, driver, 검색기)은 모두 외부에서 생성하여 주입받음
    """
class Pipeline:
    # Graph 탐색 시작점으로 사용하기에는 지나치게 일반적인 표현
    GENERIC_GRAPH_MENTIONS = {
        "patient",
        "patients",
        "medication",
        "medications",
        "treatment",
        "treated",
        "monitor",
        "monitored",
        "monitoring",
    }
    
    def __init__(
        self,
        mention_detector,
        hybrid_search,
        entity_linker,
        graph_context,
        guideline_search,
        guideline_context,
        prompt_builder,
        llm,
        hybrid_top_k: int = 20,       # hybrid 내부 후보 수
        hybrid_return_top_k: int = 3, # mention당 최종 concept 후보 수
        guideline_top_k: int = 3,     # guideline 몇 개 뽑을 건지? - 일단 3개로 설정
    ):
        self.mention_detector = mention_detector
        self.hybrid = hybrid_search
        self.entity_linker = entity_linker
        self.graph_context = graph_context
        self.guideline_search = guideline_search
        self.guideline_context = guideline_context
        self.prompt_builder = prompt_builder
        self.llm = llm

        self.hybrid_top_k = hybrid_top_k
        self.hybrid_return_top_k = hybrid_return_top_k
        self.guideline_top_k = guideline_top_k

    @classmethod
    def _select_graph_concepts(cls, concept_set: List[Dict]) -> List[Dict]:
        """
        Concept Set 전체는 유지하되,
        Neo4j Graph 탐색 시작점으로 부적절한
        일반적 mention은 제외한다.
        """

        selected = []

        for item in concept_set:
            mention = str(
                item.get("mention", "")
            ).strip().lower()

            if mention in cls.GENERIC_GRAPH_MENTIONS:
                continue

            selected.append(item)

        return selected
    
    # 내부 유틸
    @staticmethod
    def _to_graph_concept_set(concept_set: List[Dict]) -> List[Dict]:
        """entity_linking(conceptId) -> neo4j_search(concept_id) 키 어댑터"""
        return [{**item, "concept_id": item["conceptId"]} for item in concept_set]

    # 대화 history를 질문 재구성 prompt에 넣을 문자열로 변환
    @staticmethod
    def _format_history(history: List[Dict[str, str]]) -> str:
        """
        history를 LLM prompt에 넣기 위한 문자열로 변환

        ex:
            [
                {"role": "user", "content": "What is hypertension?"},
                {"role": "assistant", "content": "Hypertension is ..."}
            ]

        ->
            User: What is hypertension?
            Assistant: Hypertension is ...
        """

        history_lines = []

        for message in history:
            role = message.get("role", "").lower()
            content = message.get("content", "").strip()

            if not content:
                continue

            if role == "user":
                history_lines.append(f"User: {content}")
            elif role == "assistant":
                history_lines.append(f"Assistant: {content}")
            else:
                # 예상하지 못한 role이 들어와도 내용 자체는 보존
                history_lines.append(f"{role.capitalize()}: {content}")

        return "\n\n".join(history_lines)

    @staticmethod
    def _split_translation_result(text: str) -> tuple[str, str]:

        question_ko = ""
        answer_ko = ""

        if "<QUESTION_KO>" in text and "<ANSWER_KO>" in text:
            _, rest = text.split("<QUESTION_KO>", 1)
            question_ko, answer_ko = rest.split("<ANSWER_KO>", 1)

            question_ko = question_ko.strip()
            answer_ko = answer_ko.strip()

        return question_ko, answer_ko
    

    # 메인
    def run(self, question: str, history: List[Dict[str, str]] | None = None) -> Dict:
        
        # 1) 최종 답변 및 검색에 사용할 질문:
        # 첫 질문이면 원래 질문 그대로 사용하고,
        # 후속 질문이면 아래에서 재구성된 질문으로 변경
        search_question = question

        if history:
            history_text = self._format_history(
                history
            )

            # 질문 재구성용 Prompt 생성
            rewrite_system, rewrite_user = (
                self.prompt_builder.build_rewrite_prompt(
                    conversation_history=history_text,
                    question=question,
                )
            )

            search_question = self.llm.generate(
                rewrite_system,
                rewrite_user,
            )

        # 2) Mention Detection
        mentions = self.mention_detector.extract(search_question)

        # 3) Mention별 Hybrid Search
        # Qdrant embedding은 mention 전체를 batch로 처리
        hybrid_results = self.hybrid.search_batch(
            queries=mentions,
            top_k=self.hybrid_top_k,
            return_top_k=self.hybrid_return_top_k,
        )

        # 4) Entity Linking (concept_set)
        concept_set = self.entity_linker.build_concept_set(hybrid_results)

        # Concept Set 전체는 유지하되,
        # Graph 탐색에는 일반적인 mention을 제외한 Concept만 사용
        selected_graph_concepts = self._select_graph_concepts(concept_set)
        
        graph_concept_set = self._to_graph_concept_set(
            selected_graph_concepts
        )

        # 5) Graph Context 생성
        # concept이 없어도 build()는 빈 graph/context를 반환하므로 그대로 진행
        ctx = self.graph_context.build(search_question, graph_concept_set)

        # 6) Guideline Search
        guideline_results = self.guideline_search.search(
            search_question, top_k=self.guideline_top_k
        )

        # 7) Guideline Context 생성
        guideline_context = self.guideline_context.format_guidelines(
            guideline_results
        )
        
        # 8) Prompt 생성
        system_prompt, user_prompt = self.prompt_builder.build(
            question=search_question,
            graph_context=ctx["context_text"],
            guideline_context=guideline_context,
        )

        # 9) LLM 호출
        answer = self.llm.generate(system_prompt, user_prompt)

        # 10) 번역 Prompt 생성
        trans_system, trans_user = self.prompt_builder.build_translation_prompt(
            question=search_question,
            answer=answer,
        )

        # 11) LLM 호출(번역)
        translation = self.llm.generate(
            trans_system,
            trans_user,
            options={
                "temperature": 0,
                "num_predict": 2048,
            },
            think=False,
        )

        # 12) 번역 결과 파싱
        question_ko, answer_ko = self._split_translation_result(translation)

        # 13) 응답 반환
        return {
            "question": question,
            "rewritten_question": search_question,
            "answer": answer,
            "graph": ctx["graph"],             # 프론트 시각화용
            "mentions": mentions,
            "concept_set": concept_set,
            "guidelines": guideline_context,
            "question_ko": question_ko,
            "answer_ko": answer_ko,
        }
