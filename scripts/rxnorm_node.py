"""
RxNorm 노드 생성 전처리 스크립트: Neo4j 적재용 CSV 생성
- RXNCONSO에서 SAB=RXNORM 우선 사용, 없는 RXCUI만 MTHSPL -> MTHCMSFRF 순으로 보충
- TTY 중 순수 동의어(SY, TMSY, PSN)만 제외, 나머지(DF/DFG/PT 포함)는 유지
- TTY 기준으로 semantic_type 부여 (DF/DFG -> DoseForm, PT -> MedicalSupply, 그 외 -> Drug)

출력:
- neo4j/import/rxnorm/rxnorm_concepts.csv (concept_id, name, ontology, semantic_type, tty)

실행: python scripts/rxnorm_node.py
"""

import pandas as pd
import os

RXNORM_DIR = "../data/RXNORM"
OUTPUT_PATH = "../neo4j/import/rxnorm/rxnorm_concepts.csv"

RXNCONSO_COLUMNS = [
    "RXCUI", "LAT", "TS", "LUI", "STT", "SUI", "ISPREF",
    "RXAUI", "SAUI", "SCUI", "SDUI", "SAB", "TTY", "CODE",
    "STR", "SRL", "SUPPRESS", "CVF"
]

# TTY 필터링 기준: 순수 동의어성 타입만 제외
EXCLUDE_TTY = ["SY", "TMSY", "PSN"]


def load_rxnconso(rxnorm_dir: str):
    path = os.path.join(rxnorm_dir, "RXNCONSO.RRF")
    df = pd.read_csv(path, sep="|", header=None, names=RXNCONSO_COLUMNS,
                      dtype=str, index_col=False)
    print(f"[load_rxnconso] 전체 행 수: {len(df)}, 고유 RXCUI 수: {df['RXCUI'].nunique()}")
    return df


def build_combined(rxnconso: pd.DataFrame):
    # 1) RXNORM 우선 확보
    rxnorm_only = rxnconso[rxnconso["SAB"] == "RXNORM"]
    rxnorm_cuis = set(rxnorm_only["RXCUI"])

    # 2) RXNORM에 없는 것만 MTHSPL로 보충
    mthspl_only = rxnconso[rxnconso["SAB"] == "MTHSPL"]
    only_in_mthspl = set(mthspl_only["RXCUI"]) - rxnorm_cuis
    supplement_mthspl = (
        mthspl_only[mthspl_only["RXCUI"].isin(only_in_mthspl)]
        .drop_duplicates(subset="RXCUI", keep="first")
    )

    # 3) 그래도 없는 것만 MTHCMSFRF로 보충
    covered_so_far = rxnorm_cuis | set(supplement_mthspl["RXCUI"])
    mthcmsfrf_only = rxnconso[rxnconso["SAB"] == "MTHCMSFRF"]
    only_in_mthcmsfrf = set(mthcmsfrf_only["RXCUI"]) - covered_so_far
    supplement_mthcmsfrf = (
        mthcmsfrf_only[mthcmsfrf_only["RXCUI"].isin(only_in_mthcmsfrf)]
        .drop_duplicates(subset="RXCUI", keep="first")
    )

    combined = pd.concat(
        [rxnorm_only, supplement_mthspl, supplement_mthcmsfrf],
        ignore_index=True
    )

    print(f"[build_combined] RXNORM: {len(rxnorm_cuis)}, "
          f"MTHSPL 보충: {len(supplement_mthspl)}, "
          f"MTHCMSFRF 보충: {len(supplement_mthcmsfrf)}")
    print(f"[build_combined] combined 고유 RXCUI 수: {combined['RXCUI'].nunique()}")

    return combined


def filter_tty(combined: pd.DataFrame):
    # 동의어성 TTY(SY, TMSY, PSN)만 
    filtered = combined[~combined["TTY"].isin(EXCLUDE_TTY)].copy()

    print(f"[filter_tty] 필터링 전 행 수: {len(combined)}, "
          f"필터링 후 행 수: {len(filtered)}, "
          f"필터링 후 고유 RXCUI 수: {filtered['RXCUI'].nunique()}")

    # 검증: RXCUI당 정확히 1행만 남았는지 확인
    if len(filtered) != filtered["RXCUI"].nunique():
        raise ValueError(
            "[filter_tty] 경고: RXCUI당 1행이 아닙니다. "
            "TTY 필터링 기준을 다시 확인해야 합니다."
        )

    return filtered


def classify_semantic_type(tty: str):
    # TTY 값에 따라 semantic_type을 3분류
    if tty in ["DF", "DFG"]:
        return "DoseForm"
    elif tty == "PT":
        return "MedicalSupply"
    else:
        return "Drug"


def build_concepts_df(filtered: pd.DataFrame):
    concepts = pd.DataFrame({
        "concept_id": filtered["RXCUI"],
        "name": filtered["STR"],
        "ontology": "RxNorm",
        "semantic_type": filtered["TTY"].apply(classify_semantic_type),
        "tty": filtered["TTY"]
    })

    print(f"[build_concepts_df] 최종 행 수: {len(concepts)}")
    print(concepts["semantic_type"].value_counts())

    return concepts


def save_and_verify(concepts: pd.DataFrame, output_path: str):
    concepts.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[save_and_verify] 저장 완료: {output_path}")

    check_df = pd.read_csv(output_path)
    if len(check_df) != len(concepts):
        raise ValueError(
            f"[save_and_verify] 경고: 저장 전({len(concepts)})과 "
            f"저장 후({len(check_df)}) 행 수가 다릅니다."
        )
    print(f"[save_and_verify] 검증 완료: 행 수 {len(check_df)} 일치")


def main():
    rxnconso = load_rxnconso(RXNORM_DIR)
    combined = build_combined(rxnconso)
    filtered = filter_tty(combined)
    concepts = build_concepts_df(filtered)
    save_and_verify(concepts, OUTPUT_PATH)


if __name__ == "__main__":
    main()