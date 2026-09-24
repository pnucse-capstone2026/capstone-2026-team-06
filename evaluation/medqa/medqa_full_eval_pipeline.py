def run_baseline_full(llm, question: str) -> dict:
    system_prompt = """You are a clinical decision support assistant."""
    user_prompt = f"""## Question
{question}

## Answer
"""
    answer = llm.generate(system_prompt, user_prompt)
    return {"answer": answer}


def run_graphrag_full(p, question: str) -> dict:
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
    answer = p.llm.generate(system_prompt, user_prompt)
    return {"answer": answer}
