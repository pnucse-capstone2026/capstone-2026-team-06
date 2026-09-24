"""
LOINC 관계 생성 전처리 스크립트: Neo4j 적재용 CSV 생성
  (A) SNOMED 확장판 관계 - sct2_Relationship_Snapshot(LOINC 확장판) 기반
        LOINC 검사 -> (LOINC 검사 또는 core SNOMED 개념). typeId 16종.
      * source 는 loinc_code 있는 concept 만
      * 도우미 개념(loinc_code 도 없고 core SNOMED active 도 아닌 확장판 전용 개념, 323개)이
        target 이면 제외 (검증 결과 이들을 살려도 실익이 거의 없어 제외하기로 결정)
      * target 이 LOINC 이면 loinc_code 로, core SNOMED 면 SCTID 그대로
      * relationshipGroup 은 note 컬럼으로 보존
          (SNOMED 개념모델에서 같은 그룹끼리 묶어 해석해야 하는 검사가 존재 -
           이 값이 없으면 일부 검사의 다중 속성그룹이 뭉개짐)
  (B) 6축 관계          - LoincPartLink_Primary.csv 기반
        LOINC 검사 -> LOINC Part. COMPONENT/PROPERTY/TIME/SYSTEM/SCALE/METHOD.
      * 검사 노드에 연결되는 6축 Part 관계만
      * relationship = PartTypeName 그대로 (COMPONENT 등)     
  (C) Panel 관계        - PanelsAndForms.csv 기반
        패널(LOINC) -> 멤버 검사(LOINC). HAS_MEMBER.
      * 루트 행(ParentId==ID)과 셀프 루프(ParentLoinc==Loinc) 제외
      * 같은 (패널, 멤버) 쌍이 여러 SEQUENCE 로 중복될 수 있어 병합
      (ObservationRequiredInPanel 은 하나라도 'R'이면 'R'로, note 컬럼에 보존)
      
- 관계 이름 겹침 주의:
  COMPONENT/PROPERTY 등 -> 출처 구분은 (relationship, target_ontology) 조합으로 가능함

출력:
- neo4j/import/loinc/loinc_all_relationships.csv (source, target, relationship, target_ontology, note)
  * source 는 항상 LOINC. target_ontology 는 'LOINC' 또는 'SNOMED_CT'.
  
실행: python loinc_relationships.py  (loinc_concepts.py 실행 후)

"""

import pandas as pd
from pathlib import Path

LOINC_DIR = Path("../data/LOINC")
SNOMED_DIR = Path("../data/SNOMED_CT")
OUT_DIR = Path("../neo4j/import/loinc")
NODES_PATH = OUT_DIR / "loinc_all_concepts.csv"          # loinc_concepts.py 산출물
OUTPUT_PATH = OUT_DIR / "loinc_all_relationships.csv"

AXIS_TYPES = ["COMPONENT", "PROPERTY", "TIME", "SYSTEM", "SCALE", "METHOD"]

# SNOMED 확장판 typeId -> 관계 이름 (노트북에서 확정한 16종)
TYPE_ID_TO_RELATION = {
    "116680003": "IS_A",
    "246093002": "COMPONENT",
    "370130000": "PROPERTY",
    "370132008": "SCALE_TYPE",
    "370134009": "TIME_ASPECT",
    "246501002": "TECHNIQUE",
    "704327008": "DIRECT_SITE",
    "370133003": "SPECIMEN_SUBSTANCE",
    "704319004": "INHERES_IN",
    "704320005": "TOWARDS",
    "704321009": "CHARACTERIZES",
    "704324001": "PROCESS_OUTPUT",
    "704325000": "RELATIVE_TO",
    "704326004": "PRECONDITION",
    "424226004": "USING_DEVICE",
    "704322002": "PROCESS_AGENT",
}


# (A) SNOMED 확장판 관계

def build_snomed_ext_edges():
    rel_df = pd.read_csv(LOINC_DIR / "sct2_Relationship_Snapshot_LO1010000_20260321.txt",
                         sep="\t", dtype=str)
    rel_active = rel_df[rel_df["active"] == "1"].copy()

    # SCTID -> loinc_code 매핑
    identifier_df = pd.read_csv(LOINC_DIR / "sct2_Identifier_Snapshot_LO1010000_20260321.txt",
                                sep="\t", dtype=str)
    identifier_active = identifier_df[identifier_df["active"] == "1"]
    sctid_to_loinc = dict(zip(identifier_active["referencedComponentId"],
                              identifier_active["alternateIdentifier"]))
    loinc_sctid_set = set(sctid_to_loinc.keys())

    # core SNOMED active concept id
    snomed_concept_df = pd.read_csv(SNOMED_DIR / "sct2_Concept_Snapshot_INT_20260301.txt",
                                    sep="\t", dtype=str)
    snomed_active_ids = set(snomed_concept_df.loc[snomed_concept_df["active"] == "1", "id"])

    # LOINC 확장판 concept 전체 (도우미 개념 계산용)
    loinc_concept_df = pd.read_csv(LOINC_DIR / "sct2_Concept_Snapshot_LO1010000_20260321.txt",
                                   sep="\t", dtype=str)
    loinc_concept_ids = set(loinc_concept_df.loc[loinc_concept_df["active"] == "1", "id"])

    # 도우미 개념(loinc_code 도 없고 core SNOMED 도 아닌 것) - 323개
    helper_only_ids = loinc_concept_ids - loinc_sctid_set - snomed_active_ids
    print(f"[snomed_ext] active 관계 {len(rel_active):,}, 도우미 개념 {len(helper_only_ids)}개 (323 기대)")

    # 1) source 필터: loinc_code 있는 것만
    step1 = rel_active[rel_active["sourceId"].isin(loinc_sctid_set)]
    # 2) target 도우미 개념 제외
    step2 = step1[~step1["destinationId"].isin(helper_only_ids)]
    # 3) target 신원 불명 제외 (loinc_code 도 core SNOMED 도 아님)
    step3 = step2[
        step2["destinationId"].isin(loinc_sctid_set) | step2["destinationId"].isin(snomed_active_ids)
    ].copy()
    print(f"[snomed_ext] source→도우미제외→신원확인 후: {len(step3):,}")

    # concept_id 변환 + target_ontology + note(relationshipGroup)
    def convert(row):
        tgt = row["destinationId"]
        if tgt in loinc_sctid_set:
            target_id, target_ontology = sctid_to_loinc[tgt], "LOINC"
        else:
            target_id, target_ontology = tgt, "SNOMED_CT"
        return pd.Series({
            "source": sctid_to_loinc[row["sourceId"]],
            "target": target_id,
            "relationship": TYPE_ID_TO_RELATION[row["typeId"]],
            "target_ontology": target_ontology,
            "note": row.get("relationshipGroup", None),
        })

    edge_df = step3.apply(convert, axis=1)
    print(f"[snomed_ext] 최종 {len(edge_df):,}건")
    print(edge_df["target_ontology"].value_counts())
    return edge_df[["source", "target", "relationship", "target_ontology", "note"]]


# (B) 6축 관계

def build_6axis_edges(test_ids: set):
    partlink = pd.read_csv(LOINC_DIR / "LoincPartLink_Primary.csv", dtype=str,
                           engine="python", on_bad_lines="warn")
    valid = partlink[
        partlink["LoincNumber"].isin(test_ids) & partlink["PartTypeName"].isin(AXIS_TYPES)
    ].copy()

    edge_df = pd.DataFrame({
        "source": valid["LoincNumber"],
        "target": valid["PartNumber"],
        "relationship": valid["PartTypeName"],
        "target_ontology": "LOINC",
        "note": None,
    }).drop_duplicates(subset=["source", "target", "relationship"])

    print(f"[6axis] {len(edge_df):,}건, 커버 검사 {edge_df['source'].nunique():,} / {len(test_ids):,}")
    return edge_df[["source", "target", "relationship", "target_ontology", "note"]]


# (C) Panel 관계

def build_panel_edges(test_ids: set):
    panels = pd.read_csv(LOINC_DIR / "PanelsAndForms.csv", dtype=str, low_memory=False)
    real = panels[panels["ParentId"] != panels["ID"]]            # 루트 행 제외
    real = real[real["ParentLoinc"] != real["Loinc"]]            # 셀프 루프 제외
    valid = real[real["ParentLoinc"].isin(test_ids) & real["Loinc"].isin(test_ids)].copy()

    def merge_required(series):
        non_null = series.dropna()
        return "R" if "R" in set(non_null) else (non_null.iloc[0] if len(non_null) > 0 else None)

    grouped = valid.groupby(["ParentLoinc", "Loinc"], as_index=False).agg(
        note=("ObservationRequiredInPanel", merge_required)
    )
    edge_df = grouped.rename(columns={"ParentLoinc": "source", "Loinc": "target"})
    edge_df["relationship"] = "HAS_MEMBER"
    edge_df["target_ontology"] = "LOINC"

    print(f"[panel] {len(edge_df):,}건")
    assert (edge_df["source"] == edge_df["target"]).sum() == 0, "패널 셀프 루프 존재"
    assert edge_df.duplicated(subset=["source", "target"]).sum() == 0, "패널 (source,target) 중복"
    return edge_df[["source", "target", "relationship", "target_ontology", "note"]]


# 합치기 + 검증 + 저장

def save_and_verify(all_edges: pd.DataFrame, all_node_ids: set, output_path: Path):
    print(f"\n[merge] 전체 관계: {len(all_edges):,}")
    print(f"[merge] target_ontology 분포:\n{all_edges['target_ontology'].value_counts()}")

    # 중복 검증 (note까지 포함 - 이걸로 SNOMED 다중그룹 15개 검사의 구분이 유지됨)
    dup = all_edges.duplicated(subset=["source", "target", "relationship", "note"]).sum()
    print(f"[merge] (source,target,relationship,note) 중복: {dup}건 (0 기대)")

    # 노드 매칭 (target 이 LOINC 인 것만; SNOMED_CT 는 별도 그래프이므로 검증 제외)
    missing_source = set(all_edges["source"]) - all_node_ids
    loinc_target = all_edges[all_edges["target_ontology"] == "LOINC"]
    missing_target = set(loinc_target["target"]) - all_node_ids
    print(f"[merge] source 매칭 안 됨: {len(missing_source)}개")
    print(f"[merge] target(LOINC) 매칭 안 됨: {len(missing_target)}개")
    assert len(missing_source) == 0 and len(missing_target) == 0, "노드 매칭 실패 (loinc_concepts.py 먼저 실행했는지 확인)"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    all_edges.to_csv(output_path, index=False, encoding="utf-8")
    check = pd.read_csv(output_path, dtype=str)
    if len(check) != len(all_edges):
        raise ValueError(f"저장 전({len(all_edges)})/후({len(check)}) 행 수 불일치")
    print(f"[merge] 저장 및 검증 완료: {output_path} ({len(check):,}행)")


def main():
    # 노드 CSV(loinc_concepts.py 산출물) 로드 - source/target 검증용
    nodes = pd.read_csv(NODES_PATH, dtype=str)
    all_node_ids = set(nodes["concept_id"])
    test_ids = set(nodes.loc[nodes["semantic_type"] != "Part", "concept_id"])
    print(f"[main] 노드 CSV 로드: 전체 {len(all_node_ids):,}, 검사 {len(test_ids):,}")

    snomed_ext = build_snomed_ext_edges()
    axis = build_6axis_edges(test_ids)
    panel = build_panel_edges(test_ids)

    all_edges = pd.concat([snomed_ext, axis, panel], ignore_index=True)
    save_and_verify(all_edges, all_node_ids, OUTPUT_PATH)


if __name__ == "__main__":
    main()
