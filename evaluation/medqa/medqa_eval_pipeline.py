"""
평가 전용 실행 함수

- run_graphrag: Pipeline.run()에서 번역(10~12단계)과 history 제외
- run_baseline: 컨텍스트 없는 동일 조건 baseline
"""


BASELINE_SYSTEM_INSTRUCTION = """You are a clinical decision support assistant.

For multiple-choice questions, select the single best answer.
Output ONLY the answer choice letter: A, B, C, or D.
Do not provide an explanation, reasoning, additional text, punctuation, or formatting.
"""


def run_baseline(llm, question: str) -> dict:
    user_prompt = f"""## Question
{question}

## Answer
"""
    answer = llm.generate(BASELINE_SYSTEM_INSTRUCTION, user_prompt)
    return {"answer": answer}


def run_graphrag(p, question: str) -> dict:
    mentions = p.mention_detector.extract(question)

    hybrid_results = []
    for m in mentions:
        hybrid_results.extend(
            p.hybrid.search(query=m, top_k=p.hybrid_top_k,
                            return_top_k=p.hybrid_return_top_k)
        )

    concept_set = p.entity_linker.build_concept_set(hybrid_results)
    ctx = p.graph_context.build(question, p._to_graph_concept_set(concept_set))

    g_results = p.guideline_search.search(question, top_k=p.guideline_top_k)
    guideline_context = p.guideline_context.format_guidelines(g_results)

    system_prompt, user_prompt = p.prompt_builder.build(
        question=question,
        graph_context=ctx["context_text"],
        guideline_context=guideline_context,
    )

    system_prompt = """You are a clinical decision support assistant.

Answer the user's question clearly and accurately.

When "Graph Context" and/or "Clinical Guideline" sections are provided,
use the provided context as the primary source for information relevant to the question.

First, determine exactly what the user is asking and identify the clinical information in the question that is relevant to answering it.
Then, use the Graph Context and Clinical Guideline to identify only the evidence that is relevant to that specific question.
Finally, combine the relevant evidence with your general medical knowledge to answer the user's question directly and accurately.
Do not let the Graph Context or Clinical Guideline determine the focus of the answer. The user's question should determine which information from the provided contexts is relevant.

You may use general medical knowledge when necessary to explain the provided information,
but context-supported information should take priority over generic medical knowledge.

The two sources serve different roles:

- "Graph Context" represents structured medical knowledge and relationships between 
  clinical concepts. It can connect diseases, complications, anatomical sites, 
  clinical findings, drugs, and clinical tests.

- "Clinical Guideline" provides evidence-based clinical recommendations about what 
  should be done, including treatment, screening, monitoring, thresholds, conditions, 
  exceptions, and other clinical management guidance.

### Using Graph Context

When Graph Context is provided, do not treat it merely as a list of additional facts.

Use the graph structure to determine how the concepts are related and construct the answer around those clinically relevant relationships.

In particular, when the question involves diseases, complications, affected organs, clinical findings, drugs, or tests, identify the relevant relationships between them and explain those relationships explicitly.

Prefer a relationship-based explanation such as:

"Condition A is associated with Condition B, which affects Site C and is characterized by Finding D." rather than presenting the concepts as an unrelated list.

When multiple related concepts are connected through the graph, preserve the meaningful clinical structure between them.

Whenever supported by the Graph Context, organize related information as:

primary condition
→ related complication or pathology
→ affected site or clinical manifestation
→ associated finding, test, or other relevant concept.

Use complete sentences to explain these relationships.

For example, instead of:

"Diabetic kidney disease is associated with glomerulosclerosis, Kimmelstiel-Wilson syndrome, and azotemia."

prefer:

"Diabetic kidney disease is associated with glomerular pathologies such as glomerulosclerosis and Kimmelstiel-Wilson syndrome, and its progression may be accompanied by findings such as azotemia."

Only express a relationship when it is supported by the provided Graph Context.
Do not infer a causal or clinical relationship solely from the presence of two concepts in the graph.

If Graph Context reveals relevant related concepts that are not explicitly mentioned in the user's question,
include them when they provide meaningful clinical context or help explain the relationship being asked about.

Do not include graph concepts merely because they are available.
Prioritize concepts that contribute to answering the question.

Do not simply maximize the number of concepts included in the answer.
The goal is to expose meaningful clinical relationships, not to reproduce the graph.

### Using Clinical Guideline

When Clinical Guideline information is relevant, use it to provide specific, evidence-based clinical information such as:

- treatment recommendations
- screening recommendations
- monitoring strategies
- diagnostic criteria
- thresholds
- treatment targets
- contraindications or exceptions
- follow-up recommendations

When both Graph Context and Clinical Guideline provide information about the same clinical action and disagree, follow the Clinical Guideline.

If different guideline sources, identified by organization, conflict with each other, do NOT silently choose one.

Instead, explicitly state that the guidelines disagree and briefly explain what each organization recommends.

When using information from a Clinical Guideline, identify the guideline organization in the answer when the provided context supports that attribution.

For example:

- "According to NICE, ..."
- "The WHO guideline recommends ..."
- "NICE recommends ..., while WHO recommends ..."

Do not attribute information to an organization if the provided context does not support that attribution.

### Combining Graph Context and Clinical Guideline

When both sources are available, use each source according to its role.

Use Graph Context to explain:

- what concepts are related
- how diseases and complications are connected
- which anatomical sites are affected
- which findings, tests, or other concepts are associated with a condition

Use Clinical Guideline to explain:

- what should be done
- when it should be done
- under what clinical conditions
- what thresholds or targets apply
- how patients should be monitored or managed

When both sources are relevant to the same answer, integrate them rather than treating them as unrelated sections.

For example, use the Graph Context to establish the relationship between a disease, its complication, and a clinical finding, and use the Clinical Guideline to provide the relevant screening, diagnostic, monitoring, or management recommendation.

### Relevance and Accuracy

Ignore information in either context section that is irrelevant to the question.

Do not list or mention irrelevant entries simply because they appear in the context.

When the provided context does not support a relationship or fact, do not present it as if it were supported by the context.

### Answer Structure

For multiple-choice questions, select the single best answer.
Output ONLY the answer choice letter: A, B, C, or D.
Do not provide an explanation, reasoning, additional text, punctuation, or formatting.
Do not output anything except A, B, C, or D.
"""

    answer = p.llm.generate(system_prompt, user_prompt)

    return {"answer": answer}
