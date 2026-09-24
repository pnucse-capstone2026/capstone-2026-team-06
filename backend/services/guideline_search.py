from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from typing import List, Dict
from qdrant_client.models import ScoredPoint


class GuidelineSearch:

    def __init__(
        self,
        model: SentenceTransformer,
        client: QdrantClient,
        collection_name: str = "guidelines",
        score_threshold: float | None = None,
    ):
        self.model = model
        self.client = client
        self.collection_name = collection_name
        self.score_threshold = score_threshold

    def encode_query(self, query: str) -> List[float]:
        vector = self.model.encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return vector.tolist()

    def search(self, query: str, top_k: int = 3) -> List[Dict]:

        vector = self.encode_query(query)

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=top_k,
            score_threshold=self.score_threshold,
            with_payload=True,
        )

        output = []

        for point in results.points:
            output.append(
                {
                    "score": point.score,
                    **point.payload,
                }
            )

        return output
