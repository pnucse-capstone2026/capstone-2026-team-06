# 지금은 qdrant_weight, bm25_weight, top_k, return_top_k를 기본값만 정해두고,
# 나중에 값들 변경 가능
# hybrid_search.py -> 후보 Concept 검색

'''
실제 사용할 때 아래와 같이 사용
from sentence_transformers import SentenceTransformer

from backend.services.qdrant_search import QdrantSearch
from backend.services.bm25_search import BM25Search
from backend.services.hybrid_search import HybridSearch

model = SentenceTransformer(...)

qdrant = QdrantSearch(
    model=model,
    client=client,
)

bm25 = BM25Search(
    bm25_path=...,
    description_path=...,
)

hybrid = HybridSearch(
    qdrant_search=qdrant,
    bm25_search=bm25,
)
'''

import pandas as pd

class HybridSearch:

    def __init__(
        self,
        qdrant_search,
        bm25_search,
        qdrant_weight: float = 0.8,
        bm25_weight: float = 0.2,
    ):
        self.qdrant = qdrant_search
        self.bm25 = bm25_search

        self.qdrant_weight = qdrant_weight
        self.bm25_weight = bm25_weight

    def _min_max_normalize(self, series: pd.Series) -> pd.Series:
        if series.max() == series.min():
            return series * 0

        return ((series - series.min()) / (series.max() - series.min()))

    def _merge_results(
        self,
        query: str,
        q_results,
        b_results,
        return_top_k: int = 3,
    ):
        """
        Qdrant / BM25 결과를 결합하여
        Hybrid Score 기준 Top-k 반환
        """

        # 검색 결과가 모두 없는 경우
        if len(q_results) == 0 and len(b_results) == 0:
            return []

        # DataFrame 생성
        q_df = pd.DataFrame(q_results)
        b_df = pd.DataFrame(b_results)

        # score 컬럼명 변경
        if not q_df.empty:
            q_df = q_df.rename(columns={"score": "qdrant_score"})
        
        if not b_df.empty:
            b_df = b_df.rename(columns={"score": "bm25_score"})

        # 빈 dataframe 대응
        if q_df.empty:
            q_df = pd.DataFrame(
                columns=[
                    "conceptId",
                    "term",
                    "ontology",
                    "descriptionType",
                    "qdrant_score",
                ]
            )

        if b_df.empty:
            b_df = pd.DataFrame(
                columns=[
                    "conceptId",
                    "term",
                    "ontology",
                    "descriptionType",
                    "bm25_score",
                ]
            )

        # merge key 타입 통일
        q_df["conceptId"] = q_df["conceptId"].astype(str)
        b_df["conceptId"] = b_df["conceptId"].astype(str)

        q_df["ontology"] = q_df["ontology"].astype(str)
        b_df["ontology"] = b_df["ontology"].astype(str)

        # ontology + conceptId 기준 Merge
        hybrid_df = pd.merge(
            q_df,
            b_df,
            on=["conceptId", "ontology"],
            how="outer",
            suffixes=("_q", "_b"),
        )

        # Qdrant 값 우선, 없으면 BM25 값
        hybrid_df["term"] = (
            hybrid_df["term_q"].combine_first(
                hybrid_df["term_b"]
            )
        )

        hybrid_df["descriptionType"] = (
            hybrid_df["descriptionType_q"].combine_first(
                hybrid_df["descriptionType_b"]
            )
        )

        hybrid_df["qdrant_score"] = (
            hybrid_df["qdrant_score"].fillna(0)
        )

        hybrid_df["bm25_score"] = (
            hybrid_df["bm25_score"].fillna(0)
        )

        hybrid_df = hybrid_df[
            [
                "conceptId",
                "term",
                "ontology",
                "descriptionType",
                "qdrant_score",
                "bm25_score",
            ]
        ]

        # Normalize
        hybrid_df["qdrant_score_norm"] = (self._min_max_normalize(hybrid_df["qdrant_score"]))
        hybrid_df["bm25_score_norm"] = (self._min_max_normalize(hybrid_df["bm25_score"]))

        # Hybrid Score
        hybrid_df["hybrid_score"] = (
            self.qdrant_weight * hybrid_df["qdrant_score_norm"]
            + self.bm25_weight * hybrid_df["bm25_score_norm"]
        )

        # Sort
        hybrid_df = (hybrid_df.sort_values(by="hybrid_score", ascending=False).reset_index(drop=True))

        # Top-k
        hybrid_df = hybrid_df.head(return_top_k)

        # mention 추가
        hybrid_df["mention"] = query
        
        # dict 리스트 반환
        return hybrid_df.to_dict("records")

    def search(
        self,
        query: str,
        top_k: int = 20,
        return_top_k: int = 3,
    ):
        """
        단일 mention Hybrid Search
        """
        
        q_results = self.qdrant.search(
            query=query,
            top_k=top_k,
        )

        b_results = self.bm25.search(
            query=query,
            top_k=top_k,
        )

        return self._merge_results(
            query=query,
            q_results=q_results,
            b_results=b_results,
            return_top_k=return_top_k,
        )

    def search_batch(
        self,
        queries,
        top_k: int = 20,
        return_top_k: int = 3,
    ):
        """
        여러 mention을 한 번에 처리.

        Qdrant embedding은 batch로 1회 생성하고,
        BM25 검색은 기존 방식대로 mention별 수행.

        반환 형식은 기존 Pipeline에서 사용하기 쉽도록
        모든 mention 결과를 하나의 flat list로 반환.
        """

        if not queries:
            return []

        # Qdrant batch
        q_batch_results = self.qdrant.search_batch(
            queries=queries,
            top_k=top_k,
        )

        # BM25 batch
        b_batch_results = self.bm25.search_batch(
            queries=queries,
            top_k=top_k,
        )

        hybrid_results = []
        
        for query, q_results, b_results in zip(
            queries,
            q_batch_results,
            b_batch_results,
        ):
            merged = self._merge_results(
                query=query,
                q_results=q_results,
                b_results=b_results,
                return_top_k=return_top_k,
            )
        
            hybrid_results.extend(merged)
        
        return hybrid_results

