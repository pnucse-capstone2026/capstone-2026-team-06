"""
SNOMED CT 노드+관계 전처리 스크립트: Neo4j 적재용 CSV 생성
- Concept 파일에서 active concept만 추출
- Description(FSN 우선, 없으면 synonym)으로 name 생성
- name 끝 semantic tag((disorder) 등) 파싱 -> semantic_type 부여
  (태그 없는 concept은 IS_A 부모의 semantic_type을 상속)
- Relationship 파일의 typeId를 이름으로 매핑하여 relationship 컬럼 생성

출력:
- neo4j/import/snomed/snomed_concepts.csv (concept_id, name, ontology, semantic_type)
- neo4j/import/snomed/snomed_relationships.csv (source, target, relationship, typeId, relationshipGroup)

실행: python scripts/snomed_all.py
"""

import re
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

BASE_DIR = Path("../data/SNOMED_CT")
OUT_DIR = Path("../neo4j/import/snomed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "concept":      BASE_DIR / "sct2_Concept_Snapshot_INT_20260301.txt",
    "description":  BASE_DIR / "sct2_Description_Snapshot-en_INT_20260301.txt",
    "relationship": BASE_DIR / "sct2_Relationship_Snapshot_INT_20260301.txt",
}

FSN_TYPE_ID = "900000000000003001"
SYNONYM_TYPE_ID = "900000000000013009"
ISA_TYPE_ID = "116680003"
ROOT_ID = "138875005"

TAG_TO_SEMANTIC_TYPE = {
    "disorder": "Disorder",
    "finding": "Finding",
    "procedure": "Procedure",
    "body structure": "BodyStructure",
    "organism": "Organism",
}

def load_active_concept_ids():
    concept_df = pd.read_csv(
        FILES["concept"], sep="\t", dtype=str, keep_default_na=False
    )
    return set(concept_df.loc[concept_df["active"] == "1", "id"])


def load_name_df(active_concept_ids):
    description_df = pd.read_csv(
        FILES["description"], sep="\t", dtype=str, keep_default_na=False
    )
    description_df = description_df[description_df["active"] == "1"]

    fsn_df = description_df[
        (description_df["typeId"] == FSN_TYPE_ID)
        & (description_df["conceptId"].isin(active_concept_ids))
    ][["conceptId", "term"]].rename(columns={"term": "name"})

    fsn_missing = active_concept_ids - set(fsn_df["conceptId"])

    synonym_fallback_df = description_df[
        (description_df["typeId"] == SYNONYM_TYPE_ID)
        & (description_df["conceptId"].isin(fsn_missing))
    ][["conceptId", "term"]].rename(columns={"term": "name"})
    synonym_fallback_df = (
        synonym_fallback_df
        .sort_values(["conceptId", "name"])
        .drop_duplicates(subset="conceptId", keep="first")
    )

    name_df = pd.concat([fsn_df, synonym_fallback_df], ignore_index=True)

    still_missing = active_concept_ids - set(name_df["conceptId"])
    if still_missing:
        raise ValueError(f"name 못 찾은 concept 존재: {still_missing}")

    return name_df, set(synonym_fallback_df["conceptId"])

def extract_semantic_tag(name):
    match = re.search(r"\(([^()]+)\)\s*$", name)
    return match.group(1) if match else None


def strip_semantic_tag(name):
    return re.sub(r"\s*\([^()]+\)\s*$", "", name).strip()


def load_parent_map(active_concept_ids):
    relationship_df = pd.read_csv(
        FILES["relationship"], sep="\t", dtype=str, keep_default_na=False
    )
    relationship_df = relationship_df[relationship_df["active"] == "1"]

    isa_df = relationship_df[
        (relationship_df["typeId"] == ISA_TYPE_ID)
        & (relationship_df["sourceId"].isin(active_concept_ids))
        & (relationship_df["destinationId"].isin(active_concept_ids))
    ][["sourceId", "destinationId"]].rename(columns={"sourceId": "child", "destinationId": "parent"})

    parent_map = defaultdict(list)
    for child, parent in isa_df.itertuples(index=False):
        parent_map[child].append(parent)

    return parent_map, relationship_df


def assign_semantic_type(name_df, no_tag_ids, parent_map):
    name_df = name_df.copy()
    name_df["semantic_tag"] = name_df["name"].apply(extract_semantic_tag)
    name_df["semantic_type"] = name_df["semantic_tag"].map(TAG_TO_SEMANTIC_TYPE).fillna("Other")

    # 태그 없는 concept: 부모 태그를 상속 (검증 결과 전부 'finding' -> Finding)
    tag_lookup = name_df.set_index("conceptId")["semantic_type"]
    for cid in no_tag_ids:
        parents = parent_map.get(cid, [])
        parent_types = {tag_lookup.get(p) for p in parents if p in tag_lookup.index}
        if len(parent_types) != 1:
            raise ValueError(f"{cid}: 부모 semantic_type이 하나로 안 정해짐 -> {parent_types}")
        name_df.loc[name_df["conceptId"] == cid, "semantic_type"] = parent_types.pop()

    name_df["name_clean"] = name_df["name"].apply(strip_semantic_tag)
    return name_df


def to_rel_type(name):
    if pd.isna(name) or name == "":
        return None
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").upper()


def build_relationship_type_mapping(relationship_df, name_df):
    active_type_ids = relationship_df["typeId"].unique()
    type_name_lookup = name_df.set_index("conceptId")["name_clean"]

    mapping = {}
    missing = []
    for type_id in active_type_ids:
        if type_id in type_name_lookup.index:
            mapping[type_id] = to_rel_type(type_name_lookup[type_id])
        else:
            missing.append(type_id)

    if missing:
        raise ValueError(f"이름 못 찾은 relationship typeId: {missing}")

    return mapping


def build_edge_df(relationship_df, active_concept_ids, relationship_type_mapping):
    df = relationship_df.copy()
    df["relationship"] = df["typeId"].map(relationship_type_mapping)

    edge_df = df[
        df["sourceId"].isin(active_concept_ids)
        & df["destinationId"].isin(active_concept_ids)
    ][["sourceId", "destinationId", "relationship", "typeId", "relationshipGroup"]].rename(
        columns={"sourceId": "source", "destinationId": "target"}
    )

    if edge_df["relationship"].isna().any():
        raise ValueError("relationship 이름 매핑 안 된 edge 존재")

    return edge_df

def build_neo4j_concept_df(name_df):
    concept_df = name_df[["conceptId", "name_clean", "semantic_type"]].rename(
        columns={"conceptId": "concept_id", "name_clean": "name"}
    )
    concept_df["ontology"] = "SNOMED_CT"
    return concept_df[["concept_id", "name", "ontology", "semantic_type"]]


if __name__ == "__main__":
    active_concept_ids = load_active_concept_ids()
    print(f"active concept 수: {len(active_concept_ids):,}")

    name_df, no_tag_ids = load_name_df(active_concept_ids)
    parent_map, relationship_df = load_parent_map(active_concept_ids)
    name_df = assign_semantic_type(name_df, no_tag_ids, parent_map)

    relationship_type_mapping = build_relationship_type_mapping(relationship_df, name_df)
    edge_df = build_edge_df(relationship_df, active_concept_ids, relationship_type_mapping)

    neo4j_concept_df = build_neo4j_concept_df(name_df)

    concept_out_path = OUT_DIR / "snomed_concepts.csv"
    edge_out_path = OUT_DIR / "snomed_relationships.csv"

    neo4j_concept_df.to_csv(concept_out_path, index=False)
    edge_df.to_csv(edge_out_path, index=False)

    print(f"concept CSV 저장: {concept_out_path}  ({len(neo4j_concept_df):,}행)")
    print(f"relationship CSV 저장: {edge_out_path}  ({len(edge_df):,}행)")