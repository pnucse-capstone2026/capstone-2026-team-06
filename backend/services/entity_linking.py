from typing import List, Dict

class EntityLinking:
    """
    Hybrid Search 결과를 Concept Set으로 변환
    """

    def __init__(self):
        pass

    def build_concept_set(self, hybrid_results: List[Dict]) -> List[Dict]:

        concept_set = []
        seen = set()

        for item in hybrid_results:

            concept_id = item["conceptId"]

            # 동일 Concept 제거
            # mention1 : diabetes → 44054006 / mention2 : type 2 diabetes → 44054006 이면,
            # Neo4j에 같은 Concept를 두 번 보낼 필요가 없음
            # (따라서 conceptId 기준으로 중복 제거 수행)X -> 동일 ontology 내 동일 conceptId만 중복으로 판단

            ontology = item["ontology"]
            concept_key = (
                str(ontology),
                str(concept_id),
            )
            if concept_key in seen:
                continue

            seen.add(concept_key)

            concept_set.append(
                {
                    "mention": item["mention"],
                    "conceptId": concept_id,
                    "term": item["term"],
                    "ontology": item["ontology"],
                }
            )

        return concept_set
        