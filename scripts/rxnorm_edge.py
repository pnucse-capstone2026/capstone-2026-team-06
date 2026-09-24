"""
RxNorm 내부 관계(엣지) 생성 전처리 스크립트: Neo4j 적재용 CSV 생성
- RXNREL.RRF에서 STYPE1=STYPE2=CUI인 개념 대 개념 관계만 사용 (AUI 레벨 관계 제외)
- RB/RN, RO 관계는 항상 역방향 쌍(예: isa ↔ inverse_isa)으로 존재하므로,
  정방향 RELA 14종만 남겨 중복 생성을 방지 (역방향 절반은 버림, 정보 손실 없음)
- 가독성을 위해 일부 관계명 보정 (isa -> IS_A, has_doseformgroup -> HAS_DOSE_FORM_GROUP)
  * IS_A는 SNOMED의 IS_A와 라벨과 겹침
- rxnorm_concepts.csv에 이미 존재하는 노드(RXCUI)만 관계로 남김 (source/target 둘 다 매칭 확인)
- 관계 없는 고립 노드 4,340개는 제외하지 않고 그대로 유지
  (추후 SNOMED/UMLS 연결 시 재검토 가능성 있음)
- (source, target, relationship) 조합 중복 여부 검증 (SNOMED와 달리 relationshipGroup 같은
  구분 속성이 없어, 중복이 있으면 Neo4j MERGE 시 관계가 하나로 합쳐질 수 있음)

출력:
- neo4j/import/rxnorm/rxnorm_relationships.csv (source, target, relationship)

실행: (scripts/ 폴더에서) python rxnorm_edge.py
필요 파일: ../data/RXNORM/RXNREL.RRF, ../neo4j/import/rxnorm/rxnorm_concepts.csv
"""

import re
import pandas as pd

RXNORM_DIR = "../data/RXNORM"
RXNREL_PATH = f"{RXNORM_DIR}/RXNREL.RRF"
RXNORM_NODES_PATH = "../neo4j/import/rxnorm/rxnorm_concepts.csv"
OUTPUT_PATH = "../neo4j/import/rxnorm/rxnorm_relationships.csv"

RXNREL_COLUMNS = [
    "RXCUI1", "RXAUI1", "STYPE1", "REL", "RXCUI2", "RXAUI2", "STYPE2",
    "RELA", "RUI", "SRUI", "SAB", "SL", "RG", "DIR", "SUPPRESS", "CVF"
]

# RxNorm 내부 관계 중 "정방향"만 남기기 위한 RELA 목록
# (RB/RN, RO는 항상 역방향 쌍으로 존재하므로 한쪽만 선택 -> 중복 방지)
FORWARD_RELAS = [
    "isa", "has_ingredient", "has_tradename", "consists_of",
    "has_dose_form", "has_doseformgroup", "has_form",
    "has_precise_ingredient", "has_boss", "has_part",
    "has_ingredients", "contains", "has_quantified_form", "reformulated_to"
]

# 가독성 보정 (RxNorm 자체 표기 일관성 목적, SNOMED와 무관)
MANUAL_RENAME = {
    "isa": "IS_A",
    "has_doseformgroup": "HAS_DOSE_FORM_GROUP",
}


def load_cui_relationships(rxnrel_path: str):
    rxnrel = pd.read_csv(rxnrel_path, sep="|", header=None, names=RXNREL_COLUMNS,
                          dtype=str, index_col=False)
    print(f"[load_cui_relationships] 전체 행 수: {len(rxnrel):,}")

    cui_rel = rxnrel[(rxnrel["STYPE1"] == "CUI") & (rxnrel["STYPE2"] == "CUI")].copy()
    print(f"[load_cui_relationships] CUI-CUI 관계 행 수: {len(cui_rel):,}")
    print(f"[load_cui_relationships] SAB 분포:\n{cui_rel['SAB'].value_counts()}")

    return cui_rel

# 정방향 관계만 필터링 + 이름 변환 
def to_rel_type(name: str):
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").upper()


def rela_to_rel_type(rela: str):
    if rela in MANUAL_RENAME:
        return MANUAL_RENAME[rela]
    return to_rel_type(rela)


def filter_forward_relations(cui_rel: pd.DataFrame):
    forward_rel = cui_rel[cui_rel["RELA"].isin(FORWARD_RELAS)].copy()
    print(f"[filter_forward_relations] 정방향 관계 행 수: {len(forward_rel):,} "
          f"(전체 CUI-CUI의 절반이어야 함: {len(cui_rel) // 2:,})")

    forward_rel["relationship"] = forward_rel["RELA"].apply(rela_to_rel_type)
    print(forward_rel["relationship"].value_counts())

    return forward_rel

# rxnorm_concepts.csv와 매칭 검증
def validate_against_nodes(forward_rel: pd.DataFrame, nodes_path: str):
    rxnorm_nodes = pd.read_csv(nodes_path, dtype=str)
    valid_ids = set(rxnorm_nodes["concept_id"])

    missing_source = set(forward_rel["RXCUI1"]) - valid_ids
    missing_target = set(forward_rel["RXCUI2"]) - valid_ids
    print(f"[validate_against_nodes] source 중 노드 없음: {len(missing_source)}개")
    print(f"[validate_against_nodes] target 중 노드 없음: {len(missing_target)}개")

    valid_edges = forward_rel[
        forward_rel["RXCUI1"].isin(valid_ids) & forward_rel["RXCUI2"].isin(valid_ids)
    ].copy()
    print(f"[validate_against_nodes] 최종 유효 관계: {len(valid_edges):,} / {len(forward_rel):,}")

    connected = set(valid_edges["RXCUI1"]) | set(valid_edges["RXCUI2"])
    isolated = valid_ids - connected
    print(f"[validate_against_nodes] 관계 없는 고립 노드: {len(isolated):,}개 (그대로 유지)")

    return valid_edges

# 중복 검증 
def check_duplicates(valid_edges: pd.DataFrame):
    dup_count = valid_edges.duplicated(subset=["RXCUI1", "RXCUI2", "RELA"]).sum()
    print(f"[check_duplicates] (RXCUI1, RXCUI2, RELA) 중복 행 수: {dup_count}")

    if dup_count > 0:
        raise ValueError(
            f"[check_duplicates] 경고: 중복 조합이 {dup_count}건 존재합니다. "
            "Neo4j MERGE 시 구분 속성 없이는 데이터 손실 가능성이 있으니 확인이 필요합니다."
        )


def build_final_edges(valid_edges: pd.DataFrame):
    final_edges = valid_edges[["RXCUI1", "RXCUI2", "relationship"]].rename(
        columns={"RXCUI1": "source", "RXCUI2": "target"}
    )
    print(f"[build_final_edges] 최종 행 수: {len(final_edges):,}")
    return final_edges

# csv 저장
def save_and_verify(final_edges: pd.DataFrame, output_path: str):
    final_edges.to_csv(output_path, index=False)
    print(f"[save_and_verify] 저장 완료: {output_path}")

    check_df = pd.read_csv(output_path, dtype=str)
    if len(check_df) != len(final_edges):
        raise ValueError(
            f"[save_and_verify] 경고: 저장 전({len(final_edges)})과 "
            f"저장 후({len(check_df)}) 행 수가 다릅니다."
        )
    print(f"[save_and_verify] 검증 완료: 행 수 {len(check_df)} 일치")

if __name__ == "__main__":
    cui_rel = load_cui_relationships(RXNREL_PATH)
    forward_rel = filter_forward_relations(cui_rel)
    valid_edges = validate_against_nodes(forward_rel, RXNORM_NODES_PATH)

    check_duplicates(valid_edges)
    final_edges = build_final_edges(valid_edges)
    save_and_verify(final_edges, OUTPUT_PATH)