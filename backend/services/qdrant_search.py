# Qdrant에서 Vector Search 수행 (Query -> Embedding -> Qdrant Vector Search -> 검색 결과(Point) 반환)
# 출력 예쁘게 하는 것, Hybrid Score, Entity Linking 등은 Notebook or 다른 Service가 담당함
# (+) encode_query()의 반환 타입과 search()의 반환 타입을 명시 - IDE 자동완성 및 유지보수에 좋음
'''
만약
class QdrantSearch:
    def __init__(self):
        self.model = SentenceTransformer(...)
이렇게 만들면
-> Notebook에서도 모델 하나, FastAPI에서도 하나, Entity Linking에서도 하나 등 총 3~4번 모델을 로드하게 됨
(BGE는 꽤 큰 모델이라 좋지 않음)

그래서
model = SentenceTransformer(...) 를 한 번만 만들고
-> QdrantSearch -> HybridSearcher -> EntityLinker
모두 공유하는 것이 좋음.
즉, 모델을 밖에서 받음

마찬가지로 Qdrant 연결도 client = QdrantClient(...) 한 번만 만들고 모든 Service가 공유하는 것이 좋음

따라서 Notebook에서는 아래와 같이 사용됨
model = SentenceTransformer(...)
client = QdrantClient(...)
searcher = QdrantSearch(
    model=model,
    client=client,
)
results = searcher.search(
    "type 2 diabetes",
    top_k=20,
)
'''


from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from typing import List, Dict
from qdrant_client.models import ScoredPoint

class QdrantSearch:

    def __init__(
        self,
        model: SentenceTransformer,
        client: QdrantClient,
        collection_name: str = "concept_descriptions",
    ):
        """
        Parameters
        model: SentenceTransformer - 이미 로드된 임베딩 모델
        client : QdrantClient - 이미 연결된 Qdrant Client
        collection_name : str - 검색할 Collection 이름
        """
        self.model = model
        self.client = client
        self.collection_name = collection_name

    def encode_query(self, query: str) -> List[float]:
        """
        Query를 Embedding Vector로 변환
        """
        vector = self.model.encode(
            query,
            normalize_embeddings=True,
        )
        return vector.tolist()

    def encode_queries(self, queries: List[str]) -> List[List[float]]:
        """
        여러 Query를 한 번에 Embedding Vector로 변환
        """
        if not queries:
            return []
    
        vectors = self.model.encode(
            queries,
            normalize_embeddings=True,
        )
    
        return vectors.tolist()

    def _search_by_vector(
        self,
        vector: List[float],
        top_k: int = 20,
    ) -> List[Dict]:
    
        internal_limit = top_k * 2
    
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=internal_limit,
            with_payload=True,
        )
    
        output = []
        seen = set()
    
        for point in results.points:
            concept_id = point.payload["conceptId"]
            ontology = point.payload["ontology"]
    
            concept_key = (
                str(ontology),
                str(concept_id),
            )
    
            if concept_key in seen:
                continue
    
            seen.add(concept_key)
    
            output.append(
                {
                    "conceptId": concept_id,
                    "term": point.payload["term"],
                    "descriptionType": point.payload["descriptionType"],
                    "ontology": ontology,
                    "score": point.score,
                }
            )
    
            if len(output) == top_k:
                break
    
        return output

    def search(
        self,
        query: str,
        top_k: int = 20,
    ) -> List[Dict]:
        """
        단일 Query Vector Search
        """
        vector = self.encode_query(query)
    
        return self._search_by_vector(
            vector=vector,
            top_k=top_k,
        )

    def search_batch(
        self,
        queries: List[str],
        top_k: int = 20,
    ) -> List[List[Dict]]:
        """
        여러 Query의 embedding을 한 번에 생성한 뒤,
        각 vector에 대해 Qdrant 검색 수행.
    
        반환 순서는 queries와 동일.
        """
    
        if not queries:
            return []
    
        vectors = self.encode_queries(queries)
    
        return [
            self._search_by_vector(
                vector=vector,
                top_k=top_k,
            )
            for vector in vectors
        ]