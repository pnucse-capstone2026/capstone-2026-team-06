import pickle
import numpy as np
import pandas as pd

class BM25Search:

    def __init__(
        self,
        bm25_path: str,
        description_path: str,
    ):
        with open(bm25_path, "rb") as f:
            self.bm25 = pickle.load(f)

        self.description_df = pd.read_pickle(
            description_path
        )

        # batch BM25 계산에서 반복 변환하지 않도록 미리 생성
        self.doc_len = np.asarray(
            self.bm25.doc_len,
            dtype=np.float64,
        )

    def tokenize(
        self,
        text: str,
    ):
        return (
            text
            .lower()
            .replace("-", " ")
            .split()
        )

    def _build_results(
        self,
        scores,
        top_k: int,
    ):
        """
        BM25 score 배열을 기존 반환 형식으로 변환.
        기존 search()와 batch search()가 공통 사용.
        """

        internal_limit = top_k * 2

        # 일단 기존 결과와 완전히 동일한지 확인하기 위해
        # argsort는 아직 변경하지 않음
        top_idx = np.argsort(scores)[::-1][
            :internal_limit
        ]

        results = []
        seen = set()

        for idx in top_idx:

            if scores[idx] <= 0:
                continue

            row = self.description_df.iloc[idx]

            concept_id = row["conceptId"]
            ontology = row["ontology"]

            concept_key = (
                str(ontology),
                str(concept_id),
            )

            if concept_key in seen:
                continue

            seen.add(concept_key)

            results.append(
                {
                    "conceptId": concept_id,
                    "term": row["term"],
                    "descriptionType": row[
                        "descriptionType"
                    ],
                    "ontology": ontology,
                    "score": float(scores[idx]),
                }
            )

            if len(results) == top_k:
                break

        return results

    def search(
        self,
        query: str,
        top_k: int = 20,
    ):
        """
        기존 단일 Query 검색.
        기존 동작 유지.
        """

        query_tokens = self.tokenize(query)

        scores = self.bm25.get_scores(
            query_tokens
        )

        return self._build_results(
            scores,
            top_k,
        )

    def _build_query_postings(
        self,
        query_terms,
    ):
        """
        현재 batch에서 실제 필요한 query term에 대해서만
        corpus를 한 번 순회하여 posting 정보를 생성.

        반환:
        {
            term: (doc_indices, term_frequencies)
        }
        """

        if not query_terms:
            return {}

        query_terms = set(query_terms)

        postings = {
            term: [[], []]
            for term in query_terms
        }

        # corpus 전체를 단 한 번만 순회
        for doc_idx, doc_freq in enumerate(
            self.bm25.doc_freqs
        ):
            for term, freq in doc_freq.items():

                if term not in postings:
                    continue

                postings[term][0].append(
                    doc_idx
                )
                postings[term][1].append(
                    freq
                )

        # 이후 vector 연산을 위해 numpy array로 변환
        return {
            term: (
                np.asarray(
                    values[0],
                    dtype=np.int32,
                ),
                np.asarray(
                    values[1],
                    dtype=np.float64,
                ),
            )
            for term, values in postings.items()
        }

    def _get_scores_from_postings(
        self,
        query_tokens,
        postings,
    ):
        """
        rank_bm25.BM25Okapi.get_scores()와 동일한
        BM25 계산식을 사용하되,
        query term이 존재하는 문서만 계산.
        """

        scores = np.zeros(
            self.bm25.corpus_size,
            dtype=np.float64,
        )

        for q in query_tokens:

            idf = self.bm25.idf.get(q) or 0

            if idf == 0:
                continue

            posting = postings.get(q)

            if posting is None:
                continue

            doc_indices, q_freq = posting

            if len(doc_indices) == 0:
                continue

            doc_len = self.doc_len[
                doc_indices
            ]

            scores[doc_indices] += (
                idf
                * (
                    q_freq
                    * (self.bm25.k1 + 1)
                    /
                    (
                        q_freq
                        + self.bm25.k1
                        * (
                            1
                            - self.bm25.b
                            + self.bm25.b
                            * doc_len
                            / self.bm25.avgdl
                        )
                    )
                )
            )

        return scores

    def search_batch(
        self,
        queries,
        top_k: int = 20,
    ):
        """
        여러 mention을 batch로 BM25 검색.

        모든 query token을 먼저 모은 뒤
        159만 document corpus를 한 번만 순회한다.

        BM25 계산식과 결과 형식은 기존과 동일.
        """

        if not queries:
            return []

        tokenized_queries = [
            self.tokenize(query)
            for query in queries
        ]

        query_terms = {
            token
            for tokens in tokenized_queries
            for token in tokens
        }

        postings = self._build_query_postings(
            query_terms
        )

        batch_results = []

        for query_tokens in tokenized_queries:

            scores = (
                self._get_scores_from_postings(
                    query_tokens,
                    postings,
                )
            )

            results = self._build_results(
                scores,
                top_k,
            )

            batch_results.append(results)

        return batch_results