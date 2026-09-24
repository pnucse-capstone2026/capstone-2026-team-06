"""
LOINC 약물-검사(HAS_TEST) 관계 생성 스크립트: Neo4j 적재용 CSV 생성
- has_drug_relationships.csv의 약물(rxcui) 중 PartRelatedCodeMapping에서 RxNorm으로 매핑되는 것만 사용
- 매핑된 PartNumber를 LoincPartLink_Primary.csv와 연결해 해당 약물과 관련된 LOINC 검사를 찾음
- 같은 (rxcui, LoincNumber) 쌍인데 disease_group만 다른 행은 세미콜론으로 병합해 하나로 유지
- [수정] Neo4j 적재 시 target(4033-7, DEPRECATED)이 매칭 안 되는 문제 발견 (풀버전 참조해서)
  -> LOINC 공식 STATUS 기준 ACTIVE만 남김 (TRIAL/DISCOURAGED/DEPRECATED 제외)

참고사항:
- 대표질환 5개(SNOMED) 기준으로 PartRelatedCodeMapping의 SNOMED 축을 확인했으나,
  질병 코드와 LOINC Part 간 직접 연결이 존재하지 않았고, Neo4j 그래프 상에서도
  SNOMED 질병 노드 -> 약물 연결이 희박하게 나타남
- UMLS를 거치지 않고 LOINC을 매개로 SNOMED-RxNorm-LOINC를 한 번에 잇는 경로도
  확인했으나, shortestPath 기준 hop이 너무 멀어(4hop) 실용적이지 않다고 판단
- 따라서 약물(RxNorm) 경로로 확보 가능한 42개 약물에 대해서만 우선적으로 HAS_TEST 관계를 생성

***** 추후 추가적으로 has_test 관계 보강 필요 ******
- 현재는 약물(RxNorm)에 연결되는 Loinc만 HAS_TEST 관계로 존재
- umls, loinc으로 관계 연결 쉽지 않음 -> 수작업 필요? 혹은 다른 접근법?

출력:
- ../neo4j/import/mapping/has_test_relationships.csv (source, target, source_name,  source_type, test_name, disease_group, relationship)

실행: scripts/ 폴더에서 python map_hastest.py
"""

import pandas as pd

# 경로 설정 
PART_MAPPING_PATH = "../data/LOINC/PartRelatedCodeMapping.csv"
PARTLINK_PATH = "../data/LOINC/LoincPartLink_Primary.csv"
HAS_DRUG_PATH = "../neo4j/import/mapping/has_drug_relationships.csv"
LOINC_FULL_FILE = "../data/LOINC/Loinc.csv"  
OUTPUT_PATH = "../neo4j/import/mapping/has_test_relationships.csv"

RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"

def load_loinc_status_map():
    # 공식 Full LOINC 파일에서 LOINC_NUM -> STATUS 매핑 (ACTIVE/TRIAL/DISCOURAGED/DEPRECATED)
    loinc_full = pd.read_csv(LOINC_FULL_FILE, dtype=str)
    return dict(zip(loinc_full["LOINC_NUM"], loinc_full["STATUS"]))


def filter_active_tests(test_link_df: pd.DataFrame, status_map: dict, code_col: str = "LoincNumber"):
    # LOINC 검사 코드(target)가 공식 STATUS 기준 ACTIVE인 것만 남김
    # (TRIAL/DISCOURAGED/DEPRECATED 제외)
    before = len(test_link_df)
    status_series = test_link_df[code_col].map(status_map)
    filtered = test_link_df[status_series == "ACTIVE"].copy()
    after = len(filtered)
    print(f"STATUS 필터링: {before}행 -> {after}행 ({before - after}행 제외)")
    return filtered


def main():
    # RxNorm Part 매핑만 필터링
    # PartRelatedCodeMapping.csv에는 LOINC Part가 외부 코드(RxNorm, SNOMED 등)와
    # 어떻게 연결되는지 들어있음. 여기서 RxNorm 연결만 뽑아냄.
    df_part_mapping = pd.read_csv(PART_MAPPING_PATH, dtype=str)
    rxnorm_part_mapping = df_part_mapping[
        df_part_mapping["ExtCodeSystem"] == RXNORM_SYSTEM
    ].copy()
    print(f"[Step1] 전체 part mapping 행 수: {len(df_part_mapping)}")
    print(f"[Step1] RxNorm 관련 행 수: {len(rxnorm_part_mapping)}")

    # 기존 has_drug_relationships.csv 로드
    # (우리가 이미 만든 질병-약물 관계. target 컬럼이 rxcui)
    has_drug_df = pd.read_csv(HAS_DRUG_PATH, dtype=str)
    print(f"[Step2] has_drug 관계 행 수: {len(has_drug_df)}")

    # 우리 약물(rxcui) 중 RxNorm Part 매핑에 존재하는 것만 추림
    our_rxcuis = set(has_drug_df["target"])
    mapped_rxcuis = set(rxnorm_part_mapping["ExtCodeId"])
    overlap_rxcui = our_rxcuis & mapped_rxcuis
    print(f"[Step3] 우리 약물 {len(our_rxcuis)}개 중 LOINC Part-RxNorm 매핑에 존재: {len(overlap_rxcui)}개")

    # LoincPartLink_Primary.csv 로드 (Part <-> LOINC 검사 연결 정보)
    df_partlink = pd.read_csv(
        PARTLINK_PATH, dtype=str, engine="python", on_bad_lines="warn"
    )
    print(f"[Step4] LoincPartLink 전체 행 수: {len(df_partlink)}")

    # overlap_rxcui에 해당하는 PartNumber들 -> 그 Part로 연결된 LOINC 검사 찾기
    all_42_parts = rxnorm_part_mapping[
        rxnorm_part_mapping["ExtCodeId"].isin(overlap_rxcui)
    ]
    all_42_test_link = df_partlink[
        df_partlink["PartNumber"].isin(all_42_parts["PartNumber"])
    ]
    print(f"[Step5] 매칭된 PartNumber 수: {all_42_parts['PartNumber'].nunique()}")
    print(f"[Step5] 연결된 LOINC 검사 행 수: {len(all_42_test_link)}")

    # [수정] LOINC 공식 STATUS 기준 ACTIVE만 남김 (TRIAL/DISCOURAGED/DEPRECATED 제외)
    status_map = load_loinc_status_map()
    all_42_test_link = filter_active_tests(all_42_test_link, status_map, code_col="LoincNumber")
    print(f"[Step5-1] STATUS 필터링 후 행 수: {len(all_42_test_link)}")

    # rxcui 매핑 + has_drug_df의 drug_name/disease_group 붙이기
    merged_new = all_42_test_link.merge(
        all_42_parts[["PartNumber", "ExtCodeId"]].drop_duplicates(),
        on="PartNumber", how="left",
    ).rename(columns={"ExtCodeId": "rxcui"})

    merged_new = merged_new.merge(
        has_drug_df[["target", "drug_name", "disease_group"]]
            .drop_duplicates()
            .rename(columns={"drug_name": "source_name"}),
        left_on="rxcui", right_on="target", how="left",
    )
    print(f"[Step6] merge 후 행 수: {len(merged_new)}")
    print(f"[Step6] disease_group 결측 수: {merged_new['disease_group'].isna().sum()}")

    # (rxcui, LoincNumber, disease_group) 기준 중복 제거
    dedup_new = merged_new.drop_duplicates(subset=["rxcui", "LoincNumber", "disease_group"])
    print(f"[Step7] dedup 후 행 수: {len(dedup_new)}")

    # (rxcui, LoincNumber, drug_name, LongCommonName) 기준으로 disease_group 합치기
    # 같은 약물-검사 쌍인데 disease_group만 다른 행들을 하나로 합침 (세미콜론 구분)
    grouped = dedup_new.groupby(
        ["rxcui", "LoincNumber", "source_name", "LongCommonName"]
    )["disease_group"].apply(lambda x: ";".join(sorted(set(x)))).reset_index()
    print(f"[Step8] 최종 그룹핑 후 행 수: {len(grouped)}")

    # 컬럼 정리 및 저장
    final_grouped = grouped.rename(columns={
        "rxcui": "source",
        "LoincNumber": "target",
        "LongCommonName": "test_name",
    })
    final_grouped["relationship"] = "HAS_TEST"
    final_grouped["source_type"] = "RxNorm"
    final_grouped = final_grouped[
        ["source", "target", "source_name", "source_type", "test_name", "disease_group", "relationship"]
    ]

    final_grouped.to_csv(OUTPUT_PATH, index=False)
    print(f"[Step9] 저장 완료: {OUTPUT_PATH}, 행 수: {len(final_grouped)}")


if __name__ == "__main__":
    main()