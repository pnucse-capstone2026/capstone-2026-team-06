"""
Neo4j 그래프 탐색 모듈:
질문 + Concept Set을 받아 intent를 분류하고, 규칙에 따라 BFS로 탐색해 path 리스트를 반환

Neo4jSearch 클래스 (진입점)
    - driver/hub_keys/max_hop을 인스턴스가 들고 있음
    - .search(question, concept_set)  탐색 실행

사용법:
  (driver, hub_keys)은 시작 시 1회만 만들고, 요청마다 재사용.
  요청마다 Neo4jSearch를 새로 만들면 hub_keys 조회(degree 집계)가 매번 발생함.

    # 앱 시작 시 1회
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    searcher = Neo4jSearch(driver)          # 여기서 hub_keys 자동 로드 (조회 1회)

    # 요청마다
    result = searcher.search(question, concept_set)
    # -> {"intents": [...], "paths": [...], "per_start": [...]}

  hub_keys를 이미 갖고 있으면 넘겨서 재조회를 건너뜀:
    searcher = Neo4jSearch(driver, hub_keys=hub_keys)
 
실험:
  방향/hop은 ONTOLOGY_CONFIG만 바꾸면 다른 코드 수정 없이 변경 가능

파일 구조:
  1. 설정        - 상수 전부 여기 모여 있음 (동작을 바꾸려면 여기만)
  2. 정규화      - normalize_ontology
  3. 의도 분류    - classify_intent / signal_from_ontology / classify_intent_with_ontology
  4. hop_map     - resolve_hop_map
  5. 허브 노드    - load_hub_keys
  6. BFS         - bfs_paths
  7. path 구성    - get_name_lookup / _build_step_lists / build_path_list
  8. 조립        - search_graph
  9. 클래스      - Neo4jSearch
  주석           - LLM 기반 의도 분류 (대안)

"""

from typing import Any, Dict, List, Set, Tuple, Optional
from contextlib import nullcontext


# ============================================================================
# 1. 설정  (수정 가능)
# ============================================================================

# 1-1. 온톨로지별 탐색 설정 (관계 / hop 상한 / 방향)
ONTOLOGY_CONFIG: Dict[str, Dict[str, Any]] = {
    "SNOMED_CT": {
        "hop_map": {
            "IS_A":                  {"hop": 2, "dir": "both"},
            "FINDING_SITE":          {"hop": 2, "dir": "out"},
            "ASSOCIATED_MORPHOLOGY": {"hop": 3, "dir": "out"},
            "CAUSATIVE_AGENT":       {"hop": 3, "dir": "out"},
            "OCCURRENCE":            {"hop": 3, "dir": "out"},
            "DUE_TO":                {"hop": 3, "dir": "both"},
            "INTERPRETS":            {"hop": 3, "dir": "out"},
            "HAS_DRUG":              {"hop": 3, "dir": "out"},
        },
    },
    "RxNorm": {
        "hop_map": {
            "IS_A":            {"hop": 2, "dir": "both"},
            "HAS_INGREDIENT":  {"hop": 2, "dir": "both"}, # 중요도가 높지 않은 정보가 다량, has_part, consists_of로도 포괄할 수 있다고 생각해서 제외할수도
            "HAS_TRADENAME":   {"hop": 2, "dir": "both"},
            "CONSISTS_OF":     {"hop": 2, "dir": "both"},
            "HAS_FORM":        {"hop": 2, "dir": "both"},
            "HAS_DOSE_FORM":   {"hop": 3, "dir": "in"},
            "HAS_PART":        {"hop": 2, "dir": "both"},
            "HAS_DRUG":        {"hop": 3, "dir": "both"},
            "HAS_TEST":        {"hop": 3, "dir": "both"},
        },
    },
    "LOINC": {
        "hop_map": {
            "IS_A":       {"hop": 2, "dir": "both"},
            "COMPONENT":  {"hop": 3, "dir": "out"},
            "HAS_MEMBER": {"hop": 2, "dir": "both"},
            "SCALE":      {"hop": 1, "dir": "out"}, # 1로 설정해둔건 loinc에서 존재하길 원래 1홉만 되어있는 애들
            "TIME":       {"hop": 1, "dir": "out"},
            "PROPERTY":   {"hop": 1, "dir": "out"},
            "SYSTEM":     {"hop": 1, "dir": "out"},
            "METHOD":     {"hop": 1, "dir": "out"},
            "HAS_TEST":   {"hop": 3, "dir": "both"},
        },
    },
}

DEFAULT_MAX_HOP = 3

# 몰리는 노드 판정 기준값 (현재 768)
# 바꾸면 load_hub_keys를 다시 호출해 hub_keys를 재생성
HUB_DEGREE_THRESHOLD = 768

# 1-2. ontology 표기 정규화 (EL/Qdrant 표기 -> Neo4j 노드 표기)
_ONTOLOGY_ALIAS = {
    "SNOMED": "SNOMED_CT", "SNOMED_CT": "SNOMED_CT",
    "RXNORM": "RxNorm", "RxNorm": "RxNorm",
    "LOINC": "LOINC",
}

# 1-3. 의도 분류 키워드
INTENT_KEYWORDS: Dict[str, List[str]] = {
    "DRUG": [
        "drug", "drugs", "medication", "medicine", "prescribe", "prescription",
        "treatment", "treat", "therapy", "dose", "dosage", "administer",
        "약", "약물", "복용", "처방", "치료제", "투약",
    ],
    "TEST": [
        "test", "tests", "lab", "laboratory", "monitor", "monitoring",
        "measure", "screening", "check",
        "blood level", "glucose level", "sugar level", "levels of",
        "검사", "수치", "모니터링", "측정", "검진",
    ],
    "PATHO": [
        "cause", "causes", "caused", "due to", "complication", "complications",
        "risk", "symptom", "symptoms", "site", "location", "where",
        "warning sign", "warning signs",
        "원인", "합병증", "증상", "부위", "위험",
    ],
}

# 특정 구문은 무조건 PATHO로 강제
PATHO_OVERRIDE = ["treatment-resistant", "risk level"]

# SNOMED는 광범위해 안 씀
ONTOLOGY_TO_INTENT = {"RXNORM": "DRUG", "LOINC": "TEST"}

# intent 정렬순서: set 연산 결과를 그대로 list로 쓰면 PYTHONHASHSEED에 따라 순서가 달라져서 고정함.
INTENT_ORDER: List[str] = ["DRUG", "TEST", "PATHO", "COMPREHENSIVE"]

# 1-4. intent -> SNOMED 관계 매핑
INTENT_TO_SNOMED_RELATIONS: Dict[str, List[str]] = {
    "DRUG":  ["HAS_DRUG", "IS_A"],
    #"TEST":  ["HAS_DRUG", "INTERPRETS", "IS_A"], # HAS_TEST -> HAS_DRUG로 수정(snomed에 달린 관계)
    "TEST":  ["INTERPRETS", "IS_A"], 
    "PATHO": ["DUE_TO", "FINDING_SITE", "CAUSATIVE_AGENT",
              "ASSOCIATED_MORPHOLOGY", "OCCURRENCE", "IS_A"],
    "COMPREHENSIVE": list(ONTOLOGY_CONFIG["SNOMED_CT"]["hop_map"].keys()),
}

INTENT_APPLIES_TO = {"SNOMED_CT"}   # RxNorm, LOINC는 intent 무관 (전체 허용)


# ============================================================================
# 2. ontology 표기 정규화
# ============================================================================

def normalize_ontology(onto: Optional[str]) -> Optional[str]:
    if not isinstance(onto, str):   # None 및 문자열이 아닌 값(int 등) 모두 방어
        return None
    return _ONTOLOGY_ALIAS.get(onto, _ONTOLOGY_ALIAS.get(onto.upper()))


# ============================================================================
# 3. 의도 분류  (키워드 + ontology 보완)
# ============================================================================

#def classify_intent(question: str) -> List[str]:
#    q = question.lower()
#    override_hit = any(p in q for p in PATHO_OVERRIDE)
#    matched = [it for it, kws in INTENT_KEYWORDS.items() if any(kw in q for kw in kws)]
#    if override_hit:
#        matched = [m for m in matched if m == "PATHO"] or ["PATHO"]
#    return matched if matched else ["COMPREHENSIVE"] # 매치 안되면 "comprehensive"

def classify_intent(question: str) -> List[str]:
    q = question.lower()

    matched = {
        intent
        for intent, keywords in INTENT_KEYWORDS.items()
        if any(keyword in q for keyword in keywords)
    }

    # 특정 구문이 있으면 PATHO를 추가하되,
    # 기존에 탐지된 DRUG / TEST 의도는 유지
    if any(pattern in q for pattern in PATHO_OVERRIDE):
        matched.add("PATHO")

    if not matched:
        return ["COMPREHENSIVE"]

    # 항상 고정된 순서로 반환
    return [
        intent
        for intent in INTENT_ORDER
        if intent in matched
    ]
    
def signal_from_ontology(concept_set):
    sig = set()
    for c in concept_set:
        onto = c.get("ontology")
        if onto and onto.upper() in ONTOLOGY_TO_INTENT:
            sig.add(ONTOLOGY_TO_INTENT[onto.upper()])
    return [it for it in INTENT_ORDER if it in sig]      # ← 순서 고정

def classify_intent_with_ontology(question: str,
                                  concept_set: List[Dict[str, Any]]) -> List[str]:
    kw = classify_intent(question)
    onto = signal_from_ontology(concept_set)
    if not onto:
        return kw
    if kw == ["COMPREHENSIVE"]:
        return onto
    # 키워드로 잡은 의도를 앞에, ontology로 유추한 의도를 뒤에
    rest = [it for it in INTENT_ORDER if it in set(onto) - set(kw)]
    return [it for it in INTENT_ORDER if it in kw] + rest

# ============================================================================
# 4. intent -> hop_map 결정
# ============================================================================

def resolve_hop_map(ontology: str, intents: List[str]) -> Dict[str, Dict[str, Any]]:
    # 반환: {관계: {"hop": N, "dir": "out"|"in"|"both"}}
    base = ONTOLOGY_CONFIG.get(ontology)
    if base is None:
        return {}
    base_hop = base["hop_map"]

    if ontology not in INTENT_APPLIES_TO:
        return dict(base_hop)

    if "COMPREHENSIVE" in intents:
        wanted = set(INTENT_TO_SNOMED_RELATIONS["COMPREHENSIVE"])
    else:
        wanted = set()
        for it in intents:
            wanted |= set(INTENT_TO_SNOMED_RELATIONS.get(
                it, INTENT_TO_SNOMED_RELATIONS["COMPREHENSIVE"]))

    return {rel: cap for rel, cap in base_hop.items() if rel in wanted}


# ============================================================================
# 5. 허브 노드 로드
# ============================================================================

def load_hub_keys(driver,
                  threshold: int = HUB_DEGREE_THRESHOLD,
                  ontology_config: Optional[Dict[str, Any]] = None
                  ) -> Set[Tuple[str, str]]:
    if ontology_config is None:
        ontology_config = ONTOLOGY_CONFIG

    # degree = 탐색에서 이 노드를 경유할 수 있는 방향으로 계산.
    #   관계마다 dir(out/in/both)이 다르므로, 방향별로 나눠 세서 노드별 합산.
    hub_keys: Set[Tuple[str, str]] = set()
    for onto, cfg in ontology_config.items():
        # 관계를 방향별로 그룹핑
        by_dir: Dict[str, list] = {"out": [], "in": [], "both": []}
        for rel, spec in cfg["hop_map"].items():
            by_dir[spec["dir"]].append(rel)

        # 방향별 COUNT{}를 합산해 노드별 degree 계산
        count_terms = []
        if by_dir["out"]:
            count_terms.append(f"COUNT {{ (c)-[r:{'|'.join(by_dir['out'])}]->() }}")
        if by_dir["in"]:
            count_terms.append(f"COUNT {{ (c)<-[r:{'|'.join(by_dir['in'])}]-() }}")
        if by_dir["both"]:
            count_terms.append(f"COUNT {{ (c)-[r:{'|'.join(by_dir['both'])}]-() }}")
        if not count_terms:
            continue
        degree_expr = " + ".join(count_terms)

        query = f"""
        MATCH (c:Concept {{ontology: $onto}})
        WITH c, {degree_expr} AS degree
        WHERE degree > $th
        RETURN c.concept_id AS concept_id
        """
        with driver.session() as session:
            rows = session.run(query, onto=onto, th=threshold)
            hub_keys |= {(r["concept_id"], onto) for r in rows}
    return hub_keys


# ============================================================================
# 6. BFS 탐색  (온톨로지별 방향 + intent + 방향예외)
# ============================================================================

def bfs_paths(
    driver,
    start_id: str,
    start_ontology: str,
    intents: List[str],
    max_hop: int = DEFAULT_MAX_HOP,
    hub_keys: Optional[Set[Tuple[str, str]]] = None,
    session=None,
):

    if hub_keys is None:
        hub_keys = set()

    start_key = (start_id, start_ontology)
    visited: Set[Tuple[str, str]] = {start_key}
    frontier: Set[Tuple[str, str]] = {start_key}
    parents: Dict[Tuple[str, str], list] = {start_key: []}
    hop_of: Dict[Tuple[str, str], int] = {start_key: 0}

    def _run_match(session, cids, onto, rel_filter, arrow):
        """arrow: 'out'=-[r]->, 'in'=<-[r]-, 'both'=-[r]-"""
        pat = {"out": f"-[r:{rel_filter}]->",
               "in": f"<-[r:{rel_filter}]-",
               "both": f"-[r:{rel_filter}]-"}[arrow]
        query = f"""
        UNWIND $cids AS cid
        MATCH (n:Concept {{concept_id: cid, ontology: $onto}}){pat}(m:Concept)
        RETURN n.concept_id AS source, $onto AS source_ontology,
               m.concept_id AS target, m.ontology AS target_ontology,
               type(r) AS rel_type,
               CASE WHEN startNode(r).concept_id = n.concept_id
                         AND startNode(r).ontology = n.ontology
                    THEN 'out' ELSE 'in' END AS direction
        """
        return session.run(query, cids=cids, onto=onto).data()

    session_context = (
        driver.session()
        if session is None
        else nullcontext(session)
    )
    
    with session_context as active_session:
        for hop in range(1, max_hop + 1):
            if not frontier:
                break

            by_onto: Dict[str, list] = {}
            for cid, onto in sorted(frontier):
                by_onto.setdefault(onto, []).append(cid)

            new_keys: Set[Tuple[str, str]] = set()

            for onto, cids in by_onto.items():
                cfg = ONTOLOGY_CONFIG.get(onto)
                if cfg is None:
                    continue

                hop_map = resolve_hop_map(onto, intents)
                # 이번 hop에서 활성인 관계를 방향(out/in/both)별로 그룹핑
                by_dir: Dict[str, list] = {"out": [], "in": [], "both": []}
                for rel, spec in hop_map.items():
                    if spec["hop"] >= hop:
                        by_dir[spec["dir"]].append(rel)
                if not any(by_dir.values()):
                    continue

                rows = []
                for arrow, rels in by_dir.items():
                    if rels:
                        rows += _run_match(active_session, cids, onto, "|".join(rels), arrow)

                for row in rows:
                    tgt_key = (row["target"], row["target_ontology"])
                    src_key = (row["source"], row["source_ontology"])
                    if tgt_key not in visited:
                        new_keys.add(tgt_key)
                        parents.setdefault(tgt_key, []).append({
                            "parent_key": src_key,
                            "relation": row["rel_type"],
                            "direction": row["direction"],
                            "hop": hop,
                        })

            visited |= new_keys
            for k in sorted(new_keys):
                hop_of[k] = hop
            # 허브는 도착만 허용, 경유(다음 hop 확장)에서 제외
            frontier = sorted(k for k in new_keys if k not in hub_keys)

        return parents, hop_of


# ============================================================================
# 7. 이름 조회 + path 구성
# ============================================================================

def get_name_lookup(
    driver,
    keys: Set[Tuple[str, str]],
    session=None,
) -> Dict[Tuple[str, str], str]:
    
    if not keys:
        return {}
    query = """
    UNWIND $pairs AS p
    MATCH (c:Concept {concept_id: p.concept_id, ontology: p.ontology})
    RETURN c.concept_id AS concept_id, c.ontology AS ontology, c.name AS name
    """
    pairs = [{"concept_id": cid, "ontology": ont} for cid, ont in keys]
    session_context = (
        driver.session()
        if session is None
        else nullcontext(session)
    )
    
    with session_context as active_session:
        result = active_session.run(
            query,
            pairs=pairs,
        )
    
        return {
            (r["concept_id"], r["ontology"]): r["name"]
            for r in result
        }

def _build_step_lists(target_key, parents, name_lookup):
    if target_key not in parents or not parents[target_key]:
        return [[]]  # 시작 노드 자신
    all_step_lists = []
    for p in parents[target_key]:
        sub = _build_step_lists(p["parent_key"], parents, name_lookup)
        pk = p["parent_key"]
        step = {
            "node_id": pk[0], "ontology": pk[1],
            "node_name": name_lookup.get(pk),
            "relation": p["relation"], "direction": p["direction"],
        }
        for s in sub:
            all_step_lists.append(s + [step])
    return all_step_lists

def build_path_list(start_key, hop_of, parents, name_lookup) -> List[Dict[str, Any]]:
    flat = []
    start_info = {"concept_id": start_key[0], "ontology": start_key[1],
                  "name": name_lookup.get(start_key)}
    for target_key, hop in hop_of.items():
        if target_key == start_key:
            continue
        for steps in _build_step_lists(target_key, parents, name_lookup):
            flat.append({
                "start": start_info,
                "target": {"concept_id": target_key[0], "ontology": target_key[1],
                           "name": name_lookup.get(target_key)},
                "hop": hop, "steps": steps,
            })
    return flat


# ============================================================================
# 8. 조립:  질문 + concept_set -> 탐색 결과
# ============================================================================

def search_graph(
    driver,
    question: str,
    concept_set: List[Dict[str, Any]],
    hub_keys: Optional[Set[Tuple[str, str]]] = None,
    max_hop: int = DEFAULT_MAX_HOP,
) -> Dict[str, Any]:
    """
    질문 + Concept Set → 그래프 탐색 결과.

    처리 흐름:
      1) 의도 분류
      2) Concept Set의 각 시작 노드에서 독립 BFS
      3) 모든 BFS에서 방문한 node key를 모음
      4) node name을 한 번에 조회
      5) 각 시작 노드별 path 구성

    반환:
      {
        "intents":   [...],
        "paths":     [...],
        "per_start": [...],
      }
    """

    if hub_keys is None:
        hub_keys = set()

    intents = classify_intent_with_ontology(
        question,
        concept_set,
    )

    all_paths: List[Dict[str, Any]] = []
    per_start: List[Dict[str, Any]] = []

    # 각 Root의 BFS 결과를 임시 저장
    traversal_results = []

    # 전체 BFS에서 방문한 Concept key
    all_node_keys: Set[Tuple[str, str]] = set()

    # 질문 1회당 Neo4j Session 하나만 사용
    with driver.session() as session:

        # 1. 모든 Root에 대해 BFS 먼저 수행
        for item in concept_set:

            cid = item.get("concept_id")
            onto = normalize_ontology(
                item.get("ontology")
            )

            if cid is None or onto is None:
                continue

            start_key = (cid, onto)

            parents, hop_of = bfs_paths(
                driver,
                cid,
                onto,
                intents,
                max_hop=max_hop,
                hub_keys=hub_keys,
                session=session,
            )

            # 이번 BFS에서 발견된 모든 node key 수집
            all_node_keys.update(
                hop_of.keys()
            )

            # path는 아직 만들지 않고 BFS 결과만 저장
            traversal_results.append({
                "concept_id": cid,
                "ontology": onto,
                "start_key": start_key,
                "parents": parents,
                "hop_of": hop_of,
            })

        # 2. 모든 Root에서 탐색된 node 이름을 한 번에 조회
        name_lookup = get_name_lookup(
            driver,
            all_node_keys,
            session=session,
        )

        # 3. 공통 name_lookup을 사용하여 Root별 path 구성
        for traversal in traversal_results:

            start_key = traversal["start_key"]
            parents = traversal["parents"]
            hop_of = traversal["hop_of"]

            paths = build_path_list(
                start_key,
                hop_of,
                parents,
                name_lookup,
            )

            all_paths.extend(paths)

            per_start.append({
                "concept_id": traversal["concept_id"],
                "ontology": traversal["ontology"],
                "name": name_lookup.get(start_key),
                "path_count": len(paths),
            })

    return {
        "intents": intents,
        "paths": all_paths,
        "per_start": per_start,
    }


# ============================================================================
# 9. 클래스
# ============================================================================

class Neo4jSearch:
    """Neo4j 그래프 탐색기.

    driver / hub_keys / max_hop 을 인스턴스가 들고 있어서 검색할 때마다 넘길 필요가 없음.

    hub_keys는 degree 집계라 조회 비용이 큼 -> 생성자에서 1회 로드하고 인스턴스 당 재사용.
    이미 갖고 있으면 hub_keys 인자로 넘겨서 재조회를 건너뛸 수 있음.

    사용:
        searcher = Neo4jSearch(driver)                   # hub_keys 자동 로드 (DB 조회 1회)
        result = searcher.search(question, concept_set)  # {"intents", "paths", "per_start"}

        searcher = Neo4jSearch(driver, hub_keys=hub_keys)   # 이미 있으면 재조회 생략
    """

    def __init__(
        self,
        driver,
        hub_keys: Optional[Set[Tuple[str, str]]] = None,
        max_hop: int = DEFAULT_MAX_HOP,
        ontology_config: Optional[Dict[str, Any]] = None,
        hub_threshold: int = HUB_DEGREE_THRESHOLD,
    ):
        self.driver = driver
        self.max_hop = max_hop
        self.ontology_config = ontology_config if ontology_config is not None else ONTOLOGY_CONFIG
        self.hub_threshold = hub_threshold

        if hub_keys is None:
            hub_keys = load_hub_keys(
                driver, threshold=self.hub_threshold, ontology_config=self.ontology_config,
            )
        self.hub_keys = hub_keys

    def search(
        self,
        question: str,
        concept_set: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        return search_graph(
            self.driver,
            question,
            concept_set,
            hub_keys=self.hub_keys,
            max_hop=self.max_hop,
        )


# ============================================================================
# 대안. LLM 기반 의도 분류 (미사용)
# ============================================================================
#
# 고유명사(약 이름 등) 인식은 키워드보다 나음
# 교체 가능하도록 함수 형태만 남겨둠. 사용 시 위 classify_intent_with_ontology 대신
# 이 함수를 호출하고, 반환 형식(List[str], INTENT_KEYWORDS의 키와 동일)만 맞추면 됨.
#
#
# import requests
#
# OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma")
#
# INTENT_LLM_SYSTEM_PROMPT = """You classify a medical question into one or more intents.
# Allowed intents: DRUG, TEST, PATHO, COMPREHENSIVE.
# - DRUG: about medications/treatment.
# - TEST: about lab tests, monitoring, measured values.
# - PATHO: about causes, complications, symptoms, affected sites.
# - COMPREHENSIVE: general/overview or none of the above.
# Return ONLY a JSON list of intent strings, e.g. ["DRUG"]. No prose."""
#
# def classify_intent_llm(question: str) -> List[str]:
#     try:
#         resp = requests.post(
#             f"{OLLAMA_HOST}/api/chat",
#             json={
#                 "model": OLLAMA_MODEL,
#                 "messages": [
#                     {"role": "system", "content": INTENT_LLM_SYSTEM_PROMPT},
#                     {"role": "user", "content": question},
#                 ],
#                 "stream": False,
#                 "format": "json",
#             },
#             timeout=30,
#         )
#         resp.raise_for_status()
#         import json as _json
#         content = resp.json()["message"]["content"]
#         intents = _json.loads(content)
#         valid = {"DRUG", "TEST", "PATHO", "COMPREHENSIVE"}
#         intents = [i for i in intents if i in valid]
#         return intents if intents else ["COMPREHENSIVE"]
#     except Exception:
#         return classify_intent(question)