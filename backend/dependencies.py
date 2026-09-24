"""
FastAPI Dependency Injection

객체 생성: 모든 Service 객체를 한 번만 생성하여 재사용
즉, 무거운 객체(SentenceTransformer, Qdrant, Neo4j, BM25, LLM 등)는 앱 시작 후 계속 재사용
"""

import os
from functools import lru_cache

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


# ==========================================
# Config
# ==========================================

EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

# 환경변수로 GPU를 지정할 수 있고,
# 지정하지 않으면 기존 설정인 cuda:3 사용
EMBEDDING_DEVICE = os.getenv(
    "EMBEDDING_DEVICE",
    "cuda:3",
)

QDRANT_HOST = "qdrant"
QDRANT_PORT = 6333

NEO4J_URI = "bolt://neo4j:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD") # 환경변수로

OLLAMA_HOST = "http://ollama:11434"
OLLAMA_MODEL = "gemma4:12b"

GUIDELINE_SCORE_THRESHOLD = 0.65

BM25_PATH = "data/bm25/bm25.pkl"
DESCRIPTION_PATH = "data/bm25/description_df.pkl"

# ==========================================
# Shared Resources
# ==========================================

@lru_cache()
def get_embedding_model():
    return SentenceTransformer(
        EMBEDDING_MODEL,
        device=EMBEDDING_DEVICE,
    )

@lru_cache()
def get_qdrant_client():
    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        timeout=60, # 원래 기본값이었는데 추가함: mention 여러개일때 timeout
    )

@lru_cache()
def get_neo4j_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )

@lru_cache()
def get_llm():
    return LLM(
        host=OLLAMA_HOST,
        model=OLLAMA_MODEL,
        think=False # True로 바꾸면 추론모드
    )


# ==========================================
# Search Services
# ==========================================

@lru_cache()
def get_qdrant_search():
    return QdrantSearch(
        model=get_embedding_model(),
        client=get_qdrant_client(),
        collection_name="concept_descriptions",
    )

@lru_cache()
def get_guideline_search():
    return GuidelineSearch(
        model=get_embedding_model(),
        client=get_qdrant_client(),
        collection_name="guidelines",
        score_threshold=GUIDELINE_SCORE_THRESHOLD,
    )

@lru_cache()
def get_bm25_search():
    return BM25Search(
        bm25_path=BM25_PATH,
        description_path=DESCRIPTION_PATH,
    )

@lru_cache()
def get_hybrid_search():
    return HybridSearch(
        qdrant_search=get_qdrant_search(),
        bm25_search=get_bm25_search(),
        qdrant_weight=0.8,
        bm25_weight=0.2,
    )


# ==========================================
# Entity Linking
# ==========================================

@lru_cache()
def get_mention_detector():
    return MentionDetection()

@lru_cache()
def get_entity_linker():
    return EntityLinking()


# ==========================================
# Neo4j
# ==========================================

@lru_cache()
def get_neo4j_search():
    return Neo4jSearch(
        driver=get_neo4j_driver(),
    )

@lru_cache()
def get_graph_context():
    return GraphContext(
        searcher=get_neo4j_search(),
        viz_exclude_relations=set(),   # 시각화 가지치기 없앰: 이 줄 주석처리하면 다시 가지치기하는 것으로
        # graph_context가 너무 길다면 아래 옵션들로 조정 가능
        # 현재 default: (20000, None, None)
        # max_chars=8000,
        # max_siblings_per_relation=3,
        # min_chars_per_concept=500,
    )


# ==========================================
# Prompt
# ==========================================

@lru_cache()
def get_guideline_context():
    return GuidelineContext()

@lru_cache()
def get_prompt_builder():
    return PromptBuilder()


# ==========================================
# Pipeline
# ==========================================

@lru_cache()
def get_pipeline():

    return Pipeline(
        mention_detector=get_mention_detector(),
        hybrid_search=get_hybrid_search(),
        entity_linker=get_entity_linker(),
        graph_context=get_graph_context(),
        guideline_search=get_guideline_search(),
        guideline_context=get_guideline_context(),
        prompt_builder=get_prompt_builder(),
        llm=get_llm(),
    )

