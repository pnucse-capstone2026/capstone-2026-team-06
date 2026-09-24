"""
평가 전용 Dependency Injection

backend/dependencies.py와 달리 컨테이너명이 아닌 실제 접속 주소 사용.
LLM은 baseline과 동일 설정(seed 고정)으로 통일.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from neo4j import GraphDatabase

from backend.services.mention_detection import MentionDetection
from backend.services.qdrant_search import QdrantSearch
from backend.services.bm25_search import BM25Search
from backend.services.hybrid_search import HybridSearch
from backend.services.entity_linking import EntityLinking
from backend.db.neo4j_search import Neo4jSearch
from backend.services.graph_context import GraphContext
from backend.services.guideline_search import GuidelineSearch
from backend.services.guideline_context import GuidelineContext
from backend.services.prompt_builder import PromptBuilder
from backend.services.llm import LLM

from backend.pipeline import Pipeline


# ========== Config ==========
ROOT = "/workspace/MedicalQA"
load_dotenv(f"{ROOT}/.env")

EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
EMBEDDING_DEVICE = os.getenv(
    "MEDQA_EMBEDDING_DEVICE",
    "cpu",
)

QDRANT_HOST = "172.17.0.1"
QDRANT_PORT = 2040

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "gemma4:12b"

# 평가용 생성 파라미터 (baseline / graphrag 공통)
GEN_TEMPERATURE = 0.1
GEN_NUM_PREDICT = 1024
GEN_SEED = 42

GUIDELINE_SCORE_THRESHOLD = 0.70

BM25_PATH = f"{ROOT}/data/bm25/bm25.pkl"
DESCRIPTION_PATH = f"{ROOT}/data/bm25/description_df.pkl"


# ========== Shared ==========
@lru_cache()
def get_embedding_model():
    return SentenceTransformer(EMBEDDING_MODEL, device=EMBEDDING_DEVICE)

@lru_cache()
def get_qdrant_client():
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=60)

@lru_cache()
def get_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

@lru_cache()
def get_llm():
    return LLM(
        host=OLLAMA_HOST,
        model=OLLAMA_MODEL,
        temperature=GEN_TEMPERATURE,
        num_predict=GEN_NUM_PREDICT,
        seed=GEN_SEED,
        think=False,
    )


# ========== Services ==========
@lru_cache()
def get_hybrid_search():
    return HybridSearch(
        qdrant_search=QdrantSearch(
            model=get_embedding_model(),
            client=get_qdrant_client(),
            collection_name="concept_descriptions",
        ),
        bm25_search=BM25Search(bm25_path=BM25_PATH, description_path=DESCRIPTION_PATH),
        qdrant_weight=0.8,
        bm25_weight=0.2,
    )

@lru_cache()
def get_guideline_search():
    return GuidelineSearch(
        model=get_embedding_model(),
        client=get_qdrant_client(),
        collection_name="guidelines",
        score_threshold=GUIDELINE_SCORE_THRESHOLD,
    )


# ========== Pipeline ==========
@lru_cache()
def get_eval_pipeline():
    return Pipeline(
        mention_detector=MentionDetection(),
        hybrid_search=get_hybrid_search(),
        entity_linker=EntityLinking(),
        graph_context=GraphContext(searcher=Neo4jSearch(driver=get_neo4j_driver())),
        guideline_search=get_guideline_search(),
        guideline_context=GuidelineContext(),
        prompt_builder=PromptBuilder(),
        llm=get_llm(),
    )