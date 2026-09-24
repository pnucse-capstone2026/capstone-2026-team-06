"""
LOINC 노드 생성 전처리 스크립트: Neo4j 적재용 CSV 생성
  1) 검사 노드 (LOINC test) - Loinc.csv(공식 Full 릴리즈) 기반
    * STATUS = DEPRECATED 인 검사는 제외
    * name 은 LONG_COMMON_NAME 사용
    * semantic_type 은 공식 CLASSTYPE(1~4)로 4분류
      1 -> LabTest, 2 -> ClinicalObservation, 3 -> ClaimsDocument, 4 -> Survey
  2) 6축 Part 노드          - LoincPartLink_Primary.csv 기반
    * LoincPartLink_Primary.csv 에서 검사 노드에 연결되는 Part 만 추출
    * PartTypeName 이 6축(COMPONENT/PROPERTY/TIME/SYSTEM/SCALE/METHOD)인 것만
    * semantic_type 은 'Part' 로 통일 (세부 축 구분은 관계 타입으로 표현하므로 노드에는 안 넣음)

- 검사/Part 모두 ontology = 'LOINC' 로 통일 (concept_id 체계가 달라 충돌 없음:
  검사는 '4548-4' 형식, Part는 'LP...' 형식)

출력:
- neo4j/import/loinc/loinc_all_concepts.csv (concept_id, name, ontology, semantic_type)

실행: python loinc_concepts.py

"""

import pandas as pd
from pathlib import Path

LOINC_DIR = Path("../data/LOINC")
OUT_DIR = Path("../neo4j/import/loinc")
OUTPUT_PATH = OUT_DIR / "loinc_all_concepts.csv"

CLASSTYPE_TO_SEMANTIC_TYPE = {
    "1": "LabTest",
    "2": "ClinicalObservation",
    "3": "ClaimsDocument",
    "4": "Survey",
}
EXCLUDE_STATUS = ["DEPRECATED"]

AXIS_TYPES = ["COMPONENT", "PROPERTY", "TIME", "SYSTEM", "SCALE", "METHOD"]


def build_test_nodes():
    """Loinc.csv 기반 검사 노드. DEPRECATED 제외, CLASSTYPE -> semantic_type."""
    loinc_full = pd.read_csv(LOINC_DIR / "Loinc.csv", dtype=str, low_memory=False)
    filtered = loinc_full[~loinc_full["STATUS"].isin(EXCLUDE_STATUS)].copy()

    nodes = pd.DataFrame({
        "concept_id": filtered["LOINC_NUM"],
        "name": filtered["LONG_COMMON_NAME"],
        "ontology": "LOINC",
        "semantic_type": filtered["CLASSTYPE"].map(CLASSTYPE_TO_SEMANTIC_TYPE),
    })

    print(f"[build_test_nodes] 전체 {len(loinc_full):,} -> DEPRECATED 제외 {len(nodes):,}")
    print(f"[build_test_nodes] semantic_type 분포:\n{nodes['semantic_type'].value_counts(dropna=False)}")

    assert nodes["semantic_type"].isna().sum() == 0, "semantic_type 매핑 안 된 행 존재 (CLASSTYPE 확인 필요)"
    assert nodes["name"].isna().sum() == 0, "name(LONG_COMMON_NAME) 결측 존재"
    assert nodes["concept_id"].duplicated().sum() == 0, "검사 concept_id 중복"
    return nodes


def build_part_nodes(test_ids: set):
    """LoincPartLink_Primary.csv 기반 6축 Part 노드. semantic_type='Part'로 통일."""
    partlink = pd.read_csv(LOINC_DIR / "LoincPartLink_Primary.csv", dtype=str,
                            engine="python", on_bad_lines="warn")

    valid = partlink[
        partlink["LoincNumber"].isin(test_ids) & partlink["PartTypeName"].isin(AXIS_TYPES)
    ]
    part_nodes = valid.drop_duplicates(subset="PartNumber")[["PartNumber", "PartName"]]

    part_df = pd.DataFrame({
        "concept_id": part_nodes["PartNumber"],
        "name": part_nodes["PartName"],
        "ontology": "LOINC",
        "semantic_type": "Part",
    })

    print(f"[build_part_nodes] 6축 Part 노드 수: {len(part_df):,}")

    assert part_df["concept_id"].duplicated().sum() == 0, "Part concept_id 중복"
    assert part_df["name"].isna().sum() == 0, "Part name 결측"
    return part_df


def save_and_verify(all_nodes: pd.DataFrame, output_path: Path):
    dup = all_nodes["concept_id"].duplicated().sum()
    print(f"\n[save_and_verify] 전체 노드: {len(all_nodes):,}, concept_id 중복: {dup}건")
    if dup > 0:
        raise ValueError("검사/Part 합친 후 concept_id 충돌 존재 (코드 체계 확인 필요)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    all_nodes.to_csv(output_path, index=False, encoding="utf-8")

    check = pd.read_csv(output_path, dtype=str)
    if len(check) != len(all_nodes):
        raise ValueError(f"저장 전({len(all_nodes)})/후({len(check)}) 행 수 불일치")
    print(f"[save_and_verify] 저장 및 검증 완료: {output_path} ({len(check):,}행)")


def main():
    test_nodes = build_test_nodes()
    test_ids = set(test_nodes["concept_id"])
    part_nodes = build_part_nodes(test_ids)

    all_nodes = pd.concat([test_nodes, part_nodes], ignore_index=True)
    all_nodes = all_nodes[["concept_id", "name", "ontology", "semantic_type"]]

    save_and_verify(all_nodes, OUTPUT_PATH)


if __name__ == "__main__":
    main()