"""
Neo4j 적재 스크립트: SNOMED Concept + Relationship
- 제약조건/인덱스 생성
- Concept 노드 적재 (MERGE, 청크 10,000건)
- Relationship 적재 (MERGE, relationshipGroup을 매칭 키에 포함, 타입별 자동 청크)

실행: python scripts/import_snomed.py
"""

import time
import pandas as pd
from neo4j import GraphDatabase
from tqdm import tqdm
import os
from dotenv import load_dotenv

load_dotenv("../.env")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_AUTH = (NEO4J_USER, NEO4J_PASSWORD)

CONCEPT_CSV_PATH = "../neo4j/import/snomed/snomed_concepts.csv"
RELATIONSHIP_CSV_PATH = "../neo4j/import/snomed/snomed_relationships.csv"

CHUNK_SIZE = 10000


def chunk_dataframe(df, size):
    for i in range(0, len(df), size):
        yield df.iloc[i:i + size]


def create_constraints_and_indexes(driver):
    def _create(tx):
        tx.run("""
            CREATE CONSTRAINT concept_unique IF NOT EXISTS
            FOR (c:Concept) REQUIRE (c.ontology, c.concept_id) IS UNIQUE
        """)
        tx.run("CREATE INDEX concept_semantic_idx IF NOT EXISTS FOR (c:Concept) ON (c.semantic_type)")

    with driver.session() as session:
        session.execute_write(_create)

    print("제약조건/인덱스 생성 완료")


def load_concepts(driver):
    concept_df = pd.read_csv(CONCEPT_CSV_PATH, dtype=str)

    query = """
    UNWIND $rows AS row
    MERGE (c:Concept {ontology: row.ontology, concept_id: row.concept_id})
    SET c.name = row.name, c.semantic_type = row.semantic_type
    """

    def _load(tx, rows):
        tx.run(query, rows=rows)

    chunks = list(chunk_dataframe(concept_df, CHUNK_SIZE))

    for chunk in tqdm(chunks, desc="Concept 적재"):
        rows = chunk.to_dict("records")
        with driver.session() as session:
            session.execute_write(_load, rows)

    print(f"Concept 적재 완료 (총 {len(concept_df):,}건)")


def build_relationship_query(rel_type):
    return f"""
    UNWIND $rows AS row
    MATCH (a:Concept {{ontology: 'SNOMED_CT', concept_id: row.source}})
    MATCH (b:Concept {{ontology: 'SNOMED_CT', concept_id: row.target}})
    MERGE (a)-[r:{rel_type} {{relationshipGroup: row.relationshipGroup}}]->(b)
    SET r.typeId = row.typeId
    """


def load_relationships(driver):
    relationship_df = pd.read_csv(RELATIONSHIP_CSV_PATH, dtype=str)
    rel_groups = dict(list(relationship_df.groupby("relationship")))

    def _load(tx, query, rows):
        tx.run(query, rows=rows)

    logs = []

    for rel_type in tqdm(rel_groups.keys(), desc="Relationship 적재"):
        df = rel_groups[rel_type]
        query = build_relationship_query(rel_type)
        start = time.time()

        if len(df) > CHUNK_SIZE:
            sub_chunks = list(chunk_dataframe(df, CHUNK_SIZE))
            for sub_chunk in tqdm(sub_chunks, desc=f"  {rel_type}", leave=False):
                rows = sub_chunk.to_dict("records")
                with driver.session() as session:
                    session.execute_write(_load, query, rows)
        else:
            rows = df.to_dict("records")
            with driver.session() as session:
                session.execute_write(_load, query, rows)

        elapsed = time.time() - start
        logs.append({"relationship": rel_type, "count": len(df), "elapsed_sec": round(elapsed, 2)})

    print(f"Relationship 적재 완료 (총 {len(relationship_df):,}건)")
    return logs


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    create_constraints_and_indexes(driver)
    load_concepts(driver)
    load_relationships(driver)

    driver.close()
    print("전체 적재 프로세스 완료")


if __name__ == "__main__":
    main()