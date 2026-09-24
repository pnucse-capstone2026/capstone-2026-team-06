"""
SNOMED-RxNorm 매핑 스크립트: HAS_DRUG 관계 CSV 생성
- 대표질환 5개 + SNOMED IS_A 하위개념 추출 -> UMLS CUI 매칭 -> RxNorm 코드 매핑
- CUI 매칭 시 ambiguous(CUI 2개 이상)는 FSN 정확 일치 우선, 없으면 SUPPRESS=N 최다 CUI로 해소
- MRREL에 관계(may_treat/may_be_treated_by)가 없는 대표질환(CHF, CKD)은
  SNOMED IS_A 상위개념으로 대체 탐색 후 관계 존재 여부 재확인
- RxNorm 대표 코드 선택: UMLS 후보 중 IN 우선 -> PIN 차순 -> 그 외 TTY 순으로 확인하되,
  우리 RxNorm 노드(rxnorm_concepts.csv, Prescribe 버전)에 실제로 존재하는 코드만 채택
  (하나도 없으면 해당 관계 제외)

출력:
- ../neo4j/import/mapping/has_drug_relationships.csv (source, target, drug_name, disease_group, relationship)

실행: python3 mapping_rxnorm.py

* 로그 파일X, ambiguous CUI 해소 내역/drop 내역은 실행 중 print로만 확인
"""

import os
import pandas as pd
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv("../.env")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_AUTH = (NEO4J_USER, NEO4J_PASSWORD)


# 설정

MRCONSO_PATH = "../data/UMLS/MRCONSO.RRF"
MRREL_PATH = "../data/UMLS/MRREL.RRF"
OUTPUT_PATH = "../neo4j/import/mapping/has_drug_relationships.csv"  
RXNORM_NODES_PATH = "../neo4j/import/rxnorm/rxnorm_concepts.csv"


CHUNKSIZE = 1_000_000

MRCONSO_COLS = [
    "CUI", "LAT", "TS", "LUI", "STT", "SUI", "ISPREF", "AUI", "SAUI",
    "SCUI", "SDUI", "SAB", "TTY", "CODE", "STR", "SRL", "SUPPRESS", "CVF", "_EMPTY",
]
MRREL_COLS = [
    "CUI1", "AUI1", "STYPE1", "REL", "CUI2", "AUI2", "STYPE2",
    "RELA", "RUI", "SRUI", "SAB", "SL", "RG", "DIR", "SUPPRESS", "CVF", "_EMPTY",
]

TARGET_DISEASES = {
    "44054006": "T2DM",
    "709044004": "CKD",
    "48447003": "CHF",
    "13645005": "COPD",
    "38341003": "Hypertension",
}
ROOT_IDS = set(TARGET_DISEASES.keys())
TARGET_RELAS = {"may_treat", "may_be_treated_by"}


def log(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


# 1. Neo4j에서 대표질환 5개 + 하위개념 추출

def step1_get_concepts(driver):
    log("Step 1: 대표질환 + 하위개념 추출")

    query = """
    MATCH (child:Concept {ontology: 'SNOMED_CT'})-[:IS_A*1..]->(parent:Concept {ontology: 'SNOMED_CT', concept_id: $parent_id})
    RETURN DISTINCT child.concept_id AS concept_id, child.name AS name
    """

    results = {}
    with driver.session() as session:
        for cid, label in TARGET_DISEASES.items():
            records = session.run(query, parent_id=cid).data()
            results[label] = records
            print(f"  {label} ({cid}): 하위개념 {len(records)}개")

    all_rows = []
    for label, records in results.items():
        for r in records:
            all_rows.append({"concept_id": r["concept_id"], "name": r["name"], "disease_group": label, "is_root": False})
    for cid, label in TARGET_DISEASES.items():
        all_rows.append({"concept_id": cid, "name": label, "disease_group": label, "is_root": True})

    concept_df = pd.DataFrame(all_rows).drop_duplicates(subset=["concept_id", "disease_group"])

    print(f"  총 row 수: {len(concept_df)} (고유 concept_id: {concept_df['concept_id'].nunique()})")
    print(concept_df["disease_group"].value_counts())

    return concept_df


# 2. SNOMED CODE -> UMLS CUI 매칭 + ambiguous 해소

def step2_map_to_cui(concept_df, driver):
    log("Step 2: SNOMED CODE -> UMLS CUI 매칭")

    target_ids = set(concept_df["concept_id"].unique())
    matched_chunks = []
    for chunk in pd.read_csv(
        MRCONSO_PATH, sep="|", header=None, names=MRCONSO_COLS,
        dtype=str, quoting=3, chunksize=CHUNKSIZE, engine="c",
    ):
        chunk = chunk[chunk["SAB"] == "SNOMEDCT_US"]
        hit = chunk[chunk["CODE"].isin(target_ids)]
        if not hit.empty:
            matched_chunks.append(hit)
    matched_df = pd.concat(matched_chunks)

    missing = target_ids - set(matched_df["CODE"].unique())
    print(f"  매칭된 고유 concept_id 수: {matched_df['CODE'].nunique()} / {len(target_ids)}")
    print(f"  매칭 안 된 concept 수: {len(missing)}")
    if missing:
        print(f"  매칭 안 된 concept_id 일부: {list(missing)[:10]}")

    # ambiguous 해소 (CUI가 2개 이상인 concept)
    cui_map = matched_df.groupby("CODE")["CUI"].unique().reset_index()
    cui_map["n_cui"] = cui_map["CUI"].apply(len)
    ambiguous = cui_map[cui_map["n_cui"] > 1]
    print(f"  CUI가 2개 이상인 concept 수: {len(ambiguous)}")

    resolved_log = []  # 파일로 안 남기고 메모리에만 유지
    if len(ambiguous) > 0:
        ambiguous_codes = ambiguous["CODE"].tolist()
        query = """
        MATCH (c:Concept {ontology: 'SNOMED_CT'})
        WHERE c.concept_id IN $ids
        RETURN c.concept_id AS concept_id, c.name AS fsn
        """
        with driver.session() as session:
            fsn_records = session.run(query, ids=ambiguous_codes).data()
        fsn_map = {r["concept_id"]: r["fsn"] for r in fsn_records}

        detail_sub = matched_df[matched_df["CODE"].isin(ambiguous_codes)]
        for code in ambiguous_codes:
            fsn = fsn_map.get(code, "")
            fsn_disorder_form = f"{fsn} (disorder)"
            sub = detail_sub[detail_sub["CODE"] == code]

            exact = sub[sub["STR"].str.lower() == fsn_disorder_form.lower()]
            if not exact.empty:
                chosen_cui = exact.iloc[0]["CUI"]
                reason = "FSN 정확 일치"
            else:
                not_suppressed = sub[sub["SUPPRESS"] == "N"]
                counts = not_suppressed["CUI"].value_counts()
                chosen_cui = counts.idxmax() if not counts.empty else None
                reason = "SUPPRESS=N 중 row 최다"

            resolved_log.append({"concept_id": code, "fsn": fsn, "chosen_cui": chosen_cui, "reason": reason})

        print("  [ambiguous 해소 로그 - 메모리에만 존재]")
        for row in resolved_log:
            print(f"    {row}")

    resolved_df = pd.DataFrame(resolved_log)

    clean = cui_map[cui_map["n_cui"] == 1].copy()
    clean["CUI"] = clean["CUI"].apply(lambda x: x[0])
    clean = clean[["CODE", "CUI"]].rename(columns={"CODE": "concept_id"})

    if not resolved_df.empty:
        resolved_clean = resolved_df[["concept_id", "chosen_cui"]].rename(columns={"chosen_cui": "CUI"})
        final_cui_map = pd.concat([clean, resolved_clean], ignore_index=True)
    else:
        final_cui_map = clean

    print(f"  최종 concept_id 수: {len(final_cui_map)} (중복: {final_cui_map['concept_id'].duplicated().sum()})")

    return final_cui_map, matched_df


# 3. MRREL에서 관계 조회 -> 직접 관계 있는 anchor / 없는 anchor 구분

def step3_find_direct_relations(final_cui_map, concept_df):
    log("Step 3: 대표질환 anchor CUI의 may_treat류 관계 존재 여부 확인")

    target_cuis = set(final_cui_map["CUI"].unique())
    matched_rel_chunks = []
    for chunk in pd.read_csv(
        MRREL_PATH, sep="|", header=None, names=MRREL_COLS,
        dtype=str, quoting=3, chunksize=CHUNKSIZE, engine="c",
    ):
        chunk = chunk[chunk["RELA"].isin(TARGET_RELAS)]
        hit = chunk[chunk["CUI1"].isin(target_cuis) | chunk["CUI2"].isin(target_cuis)]
        if not hit.empty:
            matched_rel_chunks.append(hit)
    mrrel_matched = pd.concat(matched_rel_chunks) if matched_rel_chunks else pd.DataFrame(columns=MRREL_COLS)

    covered_cuis = (set(mrrel_matched["CUI1"]) | set(mrrel_matched["CUI2"])) & target_cuis
    print(f"  관계가 하나라도 있는 anchor CUI 수: {len(covered_cuis)} / {len(target_cuis)}")

    covered_df = final_cui_map[final_cui_map["CUI"].isin(covered_cuis)].copy()
    covered_df = covered_df.merge(
        concept_df[["concept_id", "name", "disease_group"]].drop_duplicates(subset="concept_id"),
        on="concept_id", how="left",
    )
    covered_df["is_root"] = covered_df["concept_id"].isin(ROOT_IDS)

    return mrrel_matched, covered_df, target_cuis


# 4. 관계 없는 대표질환(CHF, CKD)의 상위개념 대체

def step4_ancestor_substitute(driver, mrrel_matched):
    log("Step 4: CHF/CKD 등 상위개념 대체 탐색")

    # CHF, CKD만 관계가 없는 것으로 확인되었음
    roots_without_relation = {
        "48447003": "CHF",
        "709044004": "CKD",
    }

    query = """
    MATCH path = (root:Concept {ontology:'SNOMED_CT', concept_id:$root_id})-[:IS_A*1..2]->(ancestor:Concept {ontology:'SNOMED_CT'})
    RETURN ancestor.concept_id AS concept_id, ancestor.name AS name, length(path) AS hop
    ORDER BY hop
    """

    all_ancestors = []
    with driver.session() as session:
        for root_id, label in roots_without_relation.items():
            records = session.run(query, root_id=root_id).data()
            for r in records:
                r["root"] = label
                all_ancestors.append(r)
            print(f"  {label} ({root_id}): 1~2hop 조상 {len(records)}개")

    ancestor_ids = {r["concept_id"]: (r["root"], r["hop"]) for r in all_ancestors}

    # 조상 CODE -> CUI 매칭
    matched_chunks = []
    for chunk in pd.read_csv(
        MRCONSO_PATH, sep="|", header=None, names=MRCONSO_COLS,
        dtype=str, quoting=3, chunksize=CHUNKSIZE, engine="c",
    ):
        chunk = chunk[(chunk["SAB"] == "SNOMEDCT_US") & (chunk["CODE"].isin(ancestor_ids))]
        if not chunk.empty:
            matched_chunks.append(chunk)
    ancestor_matched = pd.concat(matched_chunks) if matched_chunks else pd.DataFrame(columns=MRCONSO_COLS)

    ancestor_cui_map = ancestor_matched.groupby("CODE")["CUI"].unique().reset_index()
    ancestor_cui_map["n_cui"] = ancestor_cui_map["CUI"].apply(len)
    ancestor_cui_map["root"] = ancestor_cui_map["CODE"].map(lambda x: ancestor_ids[x][0])
    ancestor_cui_map["hop"] = ancestor_cui_map["CODE"].map(lambda x: ancestor_ids[x][1])

    # ambiguous 조상 CUI 해소
    ambiguous_codes = ancestor_cui_map[ancestor_cui_map["n_cui"] > 1]["CODE"].tolist()
    resolved_ancestors = []
    if ambiguous_codes:
        query_fsn = """
        MATCH (c:Concept {ontology: 'SNOMED_CT'})
        WHERE c.concept_id IN $ids
        RETURN c.concept_id AS concept_id, c.name AS fsn
        """
        with driver.session() as session:
            fsn_records = session.run(query_fsn, ids=ambiguous_codes).data()
        fsn_map = {r["concept_id"]: r["fsn"] for r in fsn_records}

        for code in ambiguous_codes:
            fsn = fsn_map.get(code, "")
            fsn_disorder_form = f"{fsn} (disorder)"
            sub = ancestor_matched[ancestor_matched["CODE"] == code]

            exact = sub[sub["STR"].str.lower() == fsn_disorder_form.lower()]
            if not exact.empty:
                chosen_cui = exact.iloc[0]["CUI"]
            else:
                not_suppressed = sub[sub["SUPPRESS"] == "N"]
                counts = not_suppressed["CUI"].value_counts()
                chosen_cui = counts.idxmax() if not counts.empty else None
            resolved_ancestors.append({"concept_id": code, "chosen_cui": chosen_cui})

        print("  [조상 ambiguous 해소 로그 - 메모리에만 존재]")
        for row in resolved_ancestors:
            print(f"    {row}")

    clean_ancestors = ancestor_cui_map[ancestor_cui_map["n_cui"] == 1].copy()
    clean_ancestors["CUI"] = clean_ancestors["CUI"].apply(lambda x: x[0])
    clean_ancestors = clean_ancestors[["CODE", "CUI", "root", "hop"]]

    if resolved_ancestors:
        resolved_df2 = pd.DataFrame(resolved_ancestors).rename(columns={"concept_id": "CODE", "chosen_cui": "CUI"})
        resolved_df2 = resolved_df2.merge(ancestor_cui_map[["CODE", "root", "hop"]], on="CODE")
        final_ancestor_map = pd.concat([clean_ancestors, resolved_df2], ignore_index=True)
    else:
        final_ancestor_map = clean_ancestors

    # 조상 CUI들의 may_treat류 관계 여부 확인
    ancestor_cuis = set(final_ancestor_map["CUI"])
    found_chunks = []
    for chunk in pd.read_csv(
        MRREL_PATH, sep="|", header=None, names=MRREL_COLS,
        dtype=str, quoting=3, chunksize=CHUNKSIZE, engine="c",
    ):
        chunk = chunk[chunk["RELA"].isin(TARGET_RELAS)]
        hit = chunk[chunk["CUI1"].isin(ancestor_cuis) | chunk["CUI2"].isin(ancestor_cuis)]
        if not hit.empty:
            found_chunks.append(hit)
    ancestor_rel = pd.concat(found_chunks) if found_chunks else pd.DataFrame(columns=MRREL_COLS)

    def has_relation(cui):
        if ancestor_rel.empty:
            return False
        return (ancestor_rel["CUI1"] == cui).any() or (ancestor_rel["CUI2"] == cui).any()

    final_ancestor_map["has_treat_relation"] = final_ancestor_map["CUI"].apply(has_relation)

    print("  root, hop별 관계 유무:")
    print(final_ancestor_map.sort_values(["root", "hop"])[["root", "hop", "CODE", "CUI", "has_treat_relation"]].to_string(index=False))

    return final_ancestor_map, ancestor_rel


# 5. anchor 테이블 확정 (+ CUI 중복 검증)

def step5_build_anchor_table(covered_df, final_ancestor_map):
    log("Step 5: 최종 anchor 테이블 확정")

    part1 = covered_df.copy()
    part1["source_type"] = part1["is_root"].apply(lambda x: "root_self" if x else "descendant")
    part1 = part1[["concept_id", "CUI", "name", "disease_group", "source_type"]]

    part2 = final_ancestor_map[final_ancestor_map["has_treat_relation"]].copy()
    part2 = part2.rename(columns={"CODE": "concept_id", "root": "disease_group"})
    part2["name"] = None
    part2["source_type"] = "ancestor_substitute"
    part2 = part2[["concept_id", "CUI", "name", "disease_group", "source_type"]]

    final_anchor_table = pd.concat([part1, part2], ignore_index=True)
    print(f"  최종 anchor concept 수: {len(final_anchor_table)}")

    # 검증: 같은 CUI를 공유하는 concept_id가 있는지 확인
    dup_cui = final_anchor_table.groupby("CUI")["concept_id"].apply(lambda x: sorted(set(x)))
    dup_cui = dup_cui[dup_cui.apply(len) > 1]
    print(f"  [검증] 같은 CUI를 공유하는 concept_id 그룹 수: {len(dup_cui)}")
    if len(dup_cui) > 0:
        print("  >>> 아래 CUI들은 뒤에서 drop_duplicates(subset='CUI') 할 때 정보 손실 가능. 확인 필요:")
        print(dup_cui)

    return final_anchor_table


# 6. MRREL 관계 통합 -> disease_cui/drug_cui_candidate 분리

def step6_build_combined(mrrel_matched, ancestor_rel, final_anchor_table):
    log("Step 6: disease-drug 관계 통합")

    anchor_cuis = set(final_anchor_table["CUI"].unique())

    combined = pd.concat([mrrel_matched, ancestor_rel], ignore_index=True)
    combined = combined[combined["CUI1"].isin(anchor_cuis) | combined["CUI2"].isin(anchor_cuis)]

    combined["pair_key"] = combined.apply(lambda r: tuple(sorted([r["CUI1"], r["CUI2"]])), axis=1)
    combined = combined.drop_duplicates(subset="pair_key")

    def split_anchor_other(row):
        if row["CUI1"] in anchor_cuis and row["CUI2"] in anchor_cuis:
            return pd.Series(["BOTH_ANCHOR", None])
        elif row["CUI1"] in anchor_cuis:
            return pd.Series([row["CUI1"], row["CUI2"]])
        elif row["CUI2"] in anchor_cuis:
            return pd.Series([row["CUI2"], row["CUI1"]])
        else:
            return pd.Series([None, None])

    combined[["disease_cui", "drug_cui_candidate"]] = combined.apply(split_anchor_other, axis=1)

    print(f"  최종 고유 관계 행 수: {len(combined)}")
    print(f"  이상 케이스(BOTH_ANCHOR): {(combined['disease_cui'] == 'BOTH_ANCHOR').sum()}")

    return combined


# 7. drug CUI -> RxNorm 매핑, 대표 RXCUI 확정, 최종 HAS_DRUG 생성

def step7_map_to_rxnorm_and_save(combined, final_anchor_table, valid_rxnorm_ids):
    log("Step 7: RxNorm 매핑 + 최종 HAS_DRUG 생성")

    drug_cuis = set(combined["drug_cui_candidate"].dropna().unique())
    rxnorm_hits = []
    for chunk in pd.read_csv(
        MRCONSO_PATH, sep="|", header=None, names=MRCONSO_COLS,
        dtype=str, quoting=3, chunksize=CHUNKSIZE, engine="c",
    ):
        chunk = chunk[(chunk["SAB"] == "RXNORM") & (chunk["CUI"].isin(drug_cuis))]
        if not chunk.empty:
            rxnorm_hits.append(chunk)
    rxnorm_matched = pd.concat(rxnorm_hits) if rxnorm_hits else pd.DataFrame(columns=MRCONSO_COLS)

    matched_drug_cuis = set(rxnorm_matched["CUI"].unique()) if not rxnorm_matched.empty else set()
    print(f"  RxNorm 코드가 있는 drug CUI 수: {len(matched_drug_cuis)} / {len(drug_cuis)}")

    # 검증: CUI당 TTY=IN row가 여러 개라 iloc[0] 선택이 실제로 애매한지 확인
    in_counts = rxnorm_matched[rxnorm_matched["TTY"] == "IN"].groupby("CUI").size()
    multi_in = in_counts[in_counts > 1]
    print(f"  [검증] TTY=IN row가 2개 이상인 CUI 수: {len(multi_in)}")
    if len(multi_in) > 0:
        sample_cui = multi_in.index[0]
        print("  >>> 예시 (iloc[0] 선택이 실제로 여러 후보 중 하나를 고르는 상황):")
        print(rxnorm_matched[(rxnorm_matched["CUI"] == sample_cui) & (rxnorm_matched["TTY"] == "IN")][["CUI", "CODE", "STR"]])

    # 대표 RXCUI 확정 (IN 우선, 없으면 PIN, rxnorm 노드에 없으면 drop)
    def pick_rxcui(group, valid_ids):
        priority = {"IN": 0, "PIN": 1}
        group_sorted = group.copy()
        group_sorted["_priority"] = group_sorted["TTY"].map(priority).fillna(99)
        group_sorted = group_sorted.sort_values("_priority")
    
        for _, row in group_sorted.iterrows():
            if row["CODE"] in valid_ids:
                return row["CODE"], row["STR"], row["TTY"]
    
        return None, None, None
    
    rxcui_rows = []
    dropped_cuis = []
    for cui, group in rxnorm_matched.groupby("CUI"):
        rxcui, name, tty = pick_rxcui(group, valid_rxnorm_ids)
        if rxcui is None:
            dropped_cuis.append(cui)
        rxcui_rows.append({"drug_cui_candidate": cui, "rxcui": rxcui, "drug_name": name, "tty_used": tty})
    
    rxcui_final = pd.DataFrame(rxcui_rows)
    print(f"  대표 RXCUI 확정된 drug CUI 수: {rxcui_final['rxcui'].notna().sum()} / {len(rxcui_final)}")
    print(f"  우리 노드에 없어서 drop된 CUI 수: {len(dropped_cuis)}")
    print(rxcui_final['tty_used'].value_counts())

    # combined + rxcui_final + anchor_info 병합
    final_has_drug = combined.merge(rxcui_final, on="drug_cui_candidate", how="left")

    anchor_info = final_anchor_table[["concept_id", "CUI", "disease_group"]].drop_duplicates(subset="CUI")
    final_has_drug = final_has_drug.merge(anchor_info, left_on="disease_cui", right_on="CUI", how="left")

    final_has_drug = final_has_drug[["concept_id", "disease_group", "rxcui", "drug_name"]].dropna(subset=["rxcui"])
    print(f"  최종 HAS_DRUG row 수: {len(final_has_drug)}")

    # CSV 저장
    final_csv = final_has_drug.rename(columns={"concept_id": "source", "rxcui": "target"})
    final_csv["relationship"] = "HAS_DRUG"
    final_csv = final_csv[["source", "target", "drug_name", "disease_group", "relationship"]]

    before = len(final_csv)
    final_csv = final_csv.drop_duplicates(subset=["source", "target"])
    print(f"  중복 제거 전: {before}, 후: {len(final_csv)}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    final_csv.to_csv(OUTPUT_PATH, index=False)
    print(f"  저장 완료: {OUTPUT_PATH}")

    return final_csv



def main():
    valid_rxnorm_ids = set(pd.read_csv(RXNORM_NODES_PATH, dtype=str)["concept_id"])
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        concept_df = step1_get_concepts(driver)
        final_cui_map, matched_df = step2_map_to_cui(concept_df, driver)
        mrrel_matched, covered_df, target_cuis = step3_find_direct_relations(final_cui_map, concept_df)
        final_ancestor_map, ancestor_rel = step4_ancestor_substitute(driver, mrrel_matched)
        final_anchor_table = step5_build_anchor_table(covered_df, final_ancestor_map)
        combined = step6_build_combined(mrrel_matched, ancestor_rel, final_anchor_table)
        final_csv = step7_map_to_rxnorm_and_save(combined, final_anchor_table, valid_rxnorm_ids)
    finally:
        driver.close()

    log("완료")
    print(final_csv.head(10).to_string(index=False))


if __name__ == "__main__":
    main()