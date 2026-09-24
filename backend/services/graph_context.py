"""
neo4j_search.py의 결과를 받아 자연어(Graph Context)로 변환하는 모듈

파이프라인:
  paths -> 전부(1단계) -> 넘으면 하드필터(2단계) -> 넘으면 우선순위 예산캡(3단계)

GraphContext 클래스 (진입점):
  Neo4jSearch 인스턴스를 받아 조립. 렌더링 기본값(max_chars 등)은 생성자에서 1회 설정.
      searcher = Neo4jSearch(driver)                       # 앱 시작 시 1회
      gc_builder = GraphContext(searcher)                  # 앱 시작 시 1회
      ctx = gc_builder.build(question, concept_set)        # 요청마다
  ctx["context_text"] -> LLM 프롬프트용 / ctx["graph"] -> 프론트엔드용

graph(프론트엔드용):
  build_graph_context()의 반환값 중 하나. {"nodes": [...], "edges": [...]} 구조
    - node는 {id, concept_id, ontology, name, is_root} # id는 "ontology:concept_id" 구조 -> id만 하려고 하니, 중복이 존재했음.
    - edge는 {source, target, relation, direction}
                          
build() 호출 인자:
  (max_chars/min_chars_per_concept/max_siblings_per_relation)만
  이번 호출에 한해 덮어씀. 기본값(20000/none/none)은 유지.
  # ollama 기본 context - 서버 환경변수 또는 llm.py에서 num_ctx 명시해야 늘릴 수 있음.

파일 구조:
  1. 설정         - 상수 전부 여기 모여 있음 (동작을 바꾸려면 여기만)
  2. 판정         - is_relevant_relation / relation_rank
  3. 트리 구성     - build_tree_from_paths
  4. edge 선택    - _subtree_relevant_min_rank / select_edges_by_budget
  5. 문장 렌더링   - _render_relation_sentence / format_sentence / render_tree_pruned / _rendered_length
  6. path 필터    - filter_relation_bounce / hard_filter_paths
  7. 3단계 조립    - _reserve_per_root / render_all_trees_pruned / render_graph_context
  8. 그래프 payload - build_graph_payload
  9. 파이프라인    - build_graph_context
  10. 클래스      - GraphContext
"""

import heapq
from typing import Any, Dict, List, Optional, Set, Tuple

import backend.db.neo4j_search as ns # import neo4j_search as ns -> import backend.db.neo4j_search as ns


# ============================================================================
# 1. 설정  (수정 가능)
# ============================================================================

# 1-1. 문장 템플릿  (relation, direction) -> 문장 형태
FRAGMENT_TEMPLATES: Dict[Tuple[str, str], str] = {
    # SNOMED_CT
    ("IS_A", "out"): "{A} is a type of {B}",
    ("IS_A", "in"):  "{B} is a more specific subtype of {A}",
    ("FINDING_SITE", "out"): "{A} occurs at {B}",
    ("FINDING_SITE", "in"):  "{B} occurs at {A}",
    ("ASSOCIATED_MORPHOLOGY", "out"): "{A} is associated with the morphological change {B}",
    ("ASSOCIATED_MORPHOLOGY", "in"):  "{B} is associated with the morphological change {A}",
    ("CAUSATIVE_AGENT", "out"): "{A} may be caused by {B}",
    ("CAUSATIVE_AGENT", "in"):  "{B} may be caused by {A}",
    ("OCCURRENCE", "out"): "{A} occurs during {B}",
    ("OCCURRENCE", "in"):  "{B} occurs during {A}",
    ("DUE_TO", "out"): "{A} can occur as a result of {B}",
    ("DUE_TO", "in"):  "{B} can occur as a result of {A}",
    ("INTERPRETS", "out"): "{A} is assessed by evaluating {B}",
    ("INTERPRETS", "in"):  "{B} is assessed by evaluating {A}",

    # 여러 온톨로지 공유
    ("HAS_DRUG", "out"): "{B} may be used to treat {A}",
    ("HAS_DRUG", "in"):  "{A} may be used to treat {B}",
    ("HAS_TEST", "out"): "{A} is monitored by the test {B}",
    ("HAS_TEST", "in"):  "{B} is monitored by the test {A}",

    # RxNorm
    ("HAS_INGREDIENT", "out"): "{A} is an ingredient in {B}",
    ("HAS_INGREDIENT", "in"):  "{B} is an ingredient in {A}",
    ("HAS_TRADENAME", "out"): "{A} is a brand name for {B}",
    ("HAS_TRADENAME", "in"):  "{B} is a brand name for {A}",
    ("CONSISTS_OF", "out"): "{A} is a component of {B}",
    ("CONSISTS_OF", "in"):  "{B} is a component of {A}",
    ("HAS_FORM", "out"): "{A} is a specific form of {B}",
    ("HAS_FORM", "in"):  "{B} is a specific form of {A}",
    ("HAS_DOSE_FORM", "out"): "{A} is the dose form of {B}",
    ("HAS_DOSE_FORM", "in"):  "{B} is available in the dose form {A}",
    ("HAS_PART", "out"): "{A} is a part of the combination {B}",
    ("HAS_PART", "in"):  "{B} is a part of the combination {A}",

    # LOINC
    ("COMPONENT", "out"): "{A} measures {B}",
    ("COMPONENT", "in"):  "{B} measures {A}",
    ("HAS_MEMBER", "out"): "{A} includes the test {B}",
    ("HAS_MEMBER", "in"):  "{B} includes the test {A}",
    ("SCALE", "out"):    "{A} is reported on the {B} scale",
    ("SCALE", "in"):     "{B} is the scale used by {A}",
    ("TIME", "out"):     "{A} is measured over the time aspect {B}",
    ("TIME", "in"):      "{B} is the time aspect of {A}",
    ("PROPERTY", "out"): "{A} measures the property {B}",
    ("PROPERTY", "in"):  "{B} is the property measured by {A}",
    ("SYSTEM", "out"):   "{A} is measured in the specimen {B}",
    ("SYSTEM", "in"):    "{B} is the specimen for {A}",
    ("METHOD", "out"):   "{A} uses the method {B}",
    ("METHOD", "in"):    "{B} is the method used by {A}",
}

# 1-2. 의도 + 시작 온톨로지별 관련성 정의
RENDER_RELATIONS_BY_INTENT: Dict[str, Dict[str, Set[str]]] = {
    "DRUG": {
        "SNOMED_CT": {"HAS_DRUG", "HAS_TRADENAME", "IS_A"},
        "RxNorm":    {"HAS_DRUG", "HAS_TRADENAME", "IS_A"},
    },
    "TEST": {
        "SNOMED_CT": {"HAS_TEST", "INTERPRETS", "IS_A"},
        "RxNorm":    {"HAS_TEST", "INTERPRETS", "IS_A"},
        "LOINC":     {"COMPONENT", "SYSTEM", "HAS_MEMBER", "PROPERTY", "SCALE", "METHOD", "IS_A"},
    },
    "PATHO": {
        "SNOMED_CT": {"DUE_TO", "FINDING_SITE", "CAUSATIVE_AGENT",
                      "ASSOCIATED_MORPHOLOGY", "OCCURRENCE", "IS_A"},
    },
}

# 복합제 정보(성분A / 성분B 형태)는 의도 상관없이 유용하다고 판단되면 예외로 관련 있음 처리
COMBO_RELATIONS: Set[str] = {"HAS_INGREDIENT", "HAS_PART", "CONSISTS_OF"}

# 1-3. 관계 우선순위 (예산이 부족할 때 살아남는 순서)
RELATION_PRIORITY: Dict[str, List[str]] = {
    "DRUG":  ["HAS_DRUG", "HAS_TRADENAME", "IS_A", "HAS_PART", "HAS_INGREDIENT", "CONSISTS_OF"],
    "TEST":  ["HAS_TEST", "INTERPRETS", "COMPONENT", "SYSTEM",
              "HAS_MEMBER", "PROPERTY", "SCALE", "METHOD", "IS_A"],
    "PATHO": ["DUE_TO", "FINDING_SITE", "CAUSATIVE_AGENT", "ASSOCIATED_MORPHOLOGY", "OCCURRENCE", "IS_A"],
    "COMPREHENSIVE": [
        "HAS_DRUG", "DUE_TO", "HAS_TEST", "IS_A", "FINDING_SITE", "INTERPRETS",
        "CAUSATIVE_AGENT", "ASSOCIATED_MORPHOLOGY", "OCCURRENCE",
        "HAS_TRADENAME", "HAS_PART", "HAS_INGREDIENT", "CONSISTS_OF",
        "HAS_DOSE_FORM", "HAS_FORM", "COMPONENT", "HAS_MEMBER",
        "SCALE", "TIME", "PROPERTY", "SYSTEM", "METHOD",
    ],
}


# 1-4. 렌더링 기본값
DEFAULT_MAX_CHARS: Optional[int] = 20000                    # 글자수 상한 (None = 무제한)
DEFAULT_MIN_CHARS_PER_CONCEPT: Optional[int] = None         # concept당 최소 글자수 보장 (None = 꺼짐)
DEFAULT_MAX_SIBLINGS_PER_RELATION: Optional[int] = None     # (부모, 관계)당 형제 수 제한 (None = 무제한)

# 위 세 옵션은 None 자체가 유효한 값(무제한 / 꺼짐)이라 None으로는 "안 넘김"을 구분할 수 없음.
# 따라서 build()의 기본값은 None이 아니라 이 _UNSET을 쓴다.
#   build(q, cs)                  -> _UNSET  -> 인스턴스 기본값 사용
#   build(q, cs, max_chars=None)  -> None    -> 이번 호출만 무제한
#   build(q, cs, max_chars=5000)  -> 5000    -> 이번 호출만 5000
_UNSET = object()


# 1-5. 시각화(프론트) 전용 제외 규칙
# LLM context(context_text)에는 그대로 들어가고, graph payload에서만 빠짐.
# 아래 관계는 root에서 2-hop 이상 떨어진 경우에만 제외한다.
#   - 병 질문(root=SNOMED): 이 관계들이 전부 2-hop에 있어 노이즈로 잘림
#   - 약/성분 질문(root=RxNorm): 0~1-hop에 있어 근거로 살아남음
VIZ_EXCLUDE_RELATIONS: Set[str] = {"HAS_TRADENAME", "HAS_PART", "HAS_INGREDIENT"}
VIZ_EXCLUDE_MIN_DEPTH: int = 1  


# ============================================================================
# 2. 관련성 / 우선순위 판정
# ============================================================================

def is_relevant_relation(
    relation: str,
    target_name: str,
    intents: List[str],
    start_ontology: str,
    render_relations_by_intent: Optional[Dict[str, Dict[str, Set[str]]]] = None,
    combo_relations: Optional[Set[str]] = None,
) -> bool:
    render_relations_by_intent = (
        render_relations_by_intent if render_relations_by_intent is not None else RENDER_RELATIONS_BY_INTENT
    )
    combo_relations = combo_relations if combo_relations is not None else COMBO_RELATIONS

    if "COMPREHENSIVE" in intents:
        return True

    allowed: Set[str] = set()
    for it in intents:
        onto_map = render_relations_by_intent.get(it, {})
        allowed |= onto_map.get(start_ontology, onto_map.get("SNOMED_CT", set()))

    if relation in allowed:
        return True
    if relation in combo_relations and " / " in target_name:
        return True
    return False

def relation_rank(
    relation: str,
    intents: List[str],
    priority_map: Optional[Dict[str, List[str]]] = None,
) -> int:
    priority_map = priority_map if priority_map is not None else RELATION_PRIORITY
    order: List[str] = []
    for it in intents:
        order.extend(priority_map.get(it, []))
    return order.index(relation) if relation in order else len(order)


# ============================================================================
# 3. 트리 구성  (공유 prefix 자동 dedup)
# ============================================================================

def _safe_name(name: Optional[str], concept_id: str, ontology: str) -> str:
    """이름이 없는(=Neo4j에 name 속성이 비어 있는) 노드 대비.

    그대로 두면 문장에 "None may be used to treat Diabetes"처럼 None이 찍혀
    LLM 컨텍스트와 화면 그래프에 그대로 노출됨. 버리면 근거가 조용히 사라지므로
    식별자로 대체해 edge는 살리고 None 노출만 막음.
    """
    return name if name else f"{ontology}:{concept_id}"


def build_tree_from_paths(paths: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    roots: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for p in paths:
        s = p["start"]
        root_key = (s["concept_id"], s["ontology"])
        if root_key not in roots:
            roots[root_key] = {"concept_id": s["concept_id"], "ontology": s["ontology"],
                                "name": _safe_name(s["name"], s["concept_id"], s["ontology"]),
                                "children": {}}
        node = roots[root_key]
        node_names = [s["name"]] + [st["node_name"] for st in p["steps"][1:]] + [p["target"]["name"]]
        node_ids = (
            [(s["concept_id"], s["ontology"])]
            + [(st["node_id"], st["ontology"]) for st in p["steps"][1:]]
            + [(p["target"]["concept_id"], p["target"]["ontology"])]
        )
        for i, step in enumerate(p["steps"]):
            edge_key = (step["relation"], step["direction"], node_ids[i + 1][0], node_ids[i + 1][1])
            if edge_key not in node["children"]:
                node["children"][edge_key] = {
                    "concept_id": node_ids[i + 1][0], "ontology": node_ids[i + 1][1],
                    "name": _safe_name(node_names[i + 1], node_ids[i + 1][0], node_ids[i + 1][1]),
                    "children": {},
                }
            node = node["children"][edge_key]
    return roots


# ============================================================================
# 4. 예산 안에서 edge 선택
# ============================================================================

def _subtree_relevant_min_rank(
    node: Dict[str, Any],
    intents: List[str],
    start_ontology: str,
    priority_map: Optional[Dict[str, List[str]]] = None,
    render_relations_by_intent: Optional[Dict[str, Dict[str, Set[str]]]] = None,
    combo_relations: Optional[Set[str]] = None,
) -> Optional[int]:
    best: Optional[int] = None
    for edge_key, child in node["children"].items():
        rel = edge_key[0]
        if is_relevant_relation(
            rel, child["name"], intents, start_ontology, render_relations_by_intent, combo_relations,
        ):
            r = relation_rank(rel, intents, priority_map)
            if best is None or r < best:
                best = r
        sub_best = _subtree_relevant_min_rank(
            child, intents, start_ontology, priority_map, render_relations_by_intent, combo_relations,
        )
        if sub_best is not None and (best is None or sub_best < best):
            best = sub_best
    return best

def select_edges_by_budget(
    roots: Dict[Tuple[str, str], Dict[str, Any]],
    intents: List[str],
    fragment_templates: Dict[Tuple[str, str], str],
    max_chars: Optional[int] = DEFAULT_MAX_CHARS,
    priority_map: Optional[Dict[str, List[str]]] = None,
    render_relations_by_intent: Optional[Dict[str, Dict[str, Set[str]]]] = None,
    combo_relations: Optional[Set[str]] = None,
    max_siblings_per_relation: Optional[int] = DEFAULT_MAX_SIBLINGS_PER_RELATION,
    force_tier0: Optional[Set[int]] = None,
) -> Set[int]:
    # max_siblings_per_relation: 같은 (부모, 관계) 조합에서 몇 개까지만 보여줄지 제한 (기본 None = 무제한)
    # 형제가 많은 관계가 예산 잡아먹는 문제를 막기 위한 옵션
    force_tier0 = force_tier0 or set()
    kept_edges: Set[int] = set()
    heap: List[Tuple[int, int, int, int, str, Dict[str, Any], Tuple[str, str, str, str], str, int]] = []
    counter = 0
    total = 0
    sibling_count: Dict[Tuple[int, str], int] = {}

    for root_key, root in roots.items():
        start_onto = root["ontology"]
        for edge_key, child in root["children"].items():
            rel = edge_key[0]
            if id(child) in force_tier0:
                tier, rank = -1, relation_rank(rel, intents, priority_map)
            elif is_relevant_relation(
                rel, child["name"], intents, start_onto, render_relations_by_intent, combo_relations,
            ):
                tier, rank = 0, relation_rank(rel, intents, priority_map)
            else:
                sub_rank = _subtree_relevant_min_rank(
                    child, intents, start_onto, priority_map, render_relations_by_intent, combo_relations,
                )
                if sub_rank is not None:
                    # 다리: 자기가 이어주는 가장 중요한 자손과 동급 우선순위를 물려받음
                    tier, rank = 0, sub_rank
                else:
                    tier, rank = 1, relation_rank(rel, intents, priority_map)
            counter += 1
            heapq.heappush(heap, (tier, rank, 1, counter, root["name"], child, edge_key, start_onto, id(root)))

    while heap:
        tier, rank, depth, _, parent_name, child, edge_key, start_onto, parent_id = heapq.heappop(heap)
        rel, direction, _, _ = edge_key

        sibling_key = (parent_id, rel)
        if max_siblings_per_relation is not None and sibling_count.get(sibling_key, 0) >= max_siblings_per_relation:
            continue  # 다른 관계/깊이로 넘어감

        sentence = _render_relation_sentence(rel, direction, parent_name, child["name"], fragment_templates)
        indent = "  " * (depth - 1)
        length = len(indent) + len(sentence) + 1
        if max_chars is not None and total + length > max_chars:
            continue  # 예산 초과로 스킵 (관련성 낮은 것부터 여기서 잘림)
        total += length
        kept_edges.add(id(child))
        sibling_count[sibling_key] = sibling_count.get(sibling_key, 0) + 1

        for c_edge_key, grandchild in child["children"].items():
            c_rel = c_edge_key[0]
            if id(grandchild) in force_tier0:
                c_tier, c_rank = -1, relation_rank(c_rel, intents, priority_map)
            elif is_relevant_relation(
                c_rel, grandchild["name"], intents, start_onto, render_relations_by_intent, combo_relations,
            ):
                c_tier, c_rank = 0, relation_rank(c_rel, intents, priority_map)
            else:
                c_sub_rank = _subtree_relevant_min_rank(
                    grandchild, intents, start_onto, priority_map, render_relations_by_intent, combo_relations,
                )
                if c_sub_rank is not None:
                    c_tier, c_rank = 0, c_sub_rank
                else:
                    c_tier, c_rank = 1, relation_rank(c_rel, intents, priority_map)
            counter += 1
            heapq.heappush(heap, (c_tier, c_rank, depth + 1, counter, child["name"], grandchild, c_edge_key, start_onto, id(child)))

    return kept_edges


# ============================================================================
# 5. 문장 렌더링  (채택된 edge만 들여쓰기 트리 문장으로)
# ============================================================================

def _render_relation_sentence(
    relation: str, direction: str, A: str, B: str,
    fragment_templates: Dict[Tuple[str, str], str],
) -> str:
    tmpl = fragment_templates.get((relation, direction))
    if tmpl:
        return tmpl.format(A=A, B=B)
    return f"{A} --{relation}--> {B}"

def format_sentence(s: str) -> str: # 첫글자 -> 대문자
    s = s.strip()
    if not s:
        return s
    return s[0].upper() + s[1:]

def render_tree_pruned(
    node: Dict[str, Any], parent_name: str,
    fragment_templates: Dict[Tuple[str, str], str],
    kept_edges: Set[int],
    lines: Optional[List[str]] = None, depth: int = 0,
) -> List[str]:
    if lines is None:
        lines = []
    for edge_key, child in node["children"].items():
        if id(child) not in kept_edges:
            continue
        rel, direction, _, _ = edge_key
        sentence = format_sentence(_render_relation_sentence(rel, direction, parent_name, child["name"], fragment_templates))
        lines.append("  " * depth + sentence)
        render_tree_pruned(child, child["name"], fragment_templates, kept_edges, lines, depth + 1)
    return lines

def _rendered_length(sentences: List[str], join_sep: str = "\n") -> int:
    if not sentences:
        return 0
    return sum(len(s) for s in sentences) + len(join_sep) * (len(sentences) - 1)


# ============================================================================
# 6. path 필터
# ============================================================================

def filter_relation_bounce(paths): #같은 관계가 연속으로 반대 방향(in<->out)이면 그 path 제외 하도록 함수 추가함.
    kept = []
    for p in paths:
        steps = p["steps"]
        bounced = any(
            steps[i]["relation"] == steps[i+1]["relation"] and steps[i]["direction"] != steps[i+1]["direction"]
            for i in range(len(steps)-1)
        )
        if not bounced:
            kept.append(p)
    return kept

def hard_filter_paths(
    paths: List[Dict[str, Any]],
    intents: List[str],
    render_relations_by_intent: Optional[Dict[str, Dict[str, Set[str]]]] = None,
    combo_relations: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    if "COMPREHENSIVE" in intents:
        return paths
    kept = []
    for p in paths:
        if not p["steps"]:
            continue        # 방어: steps가 비면 판정할 관계가 없음 (정상 탐색에선 발생 안 함)
        if is_relevant_relation(
            p["steps"][-1]["relation"], p["target"]["name"], intents, p["start"]["ontology"],
            render_relations_by_intent, combo_relations,
        ):
            kept.append(p)
    return kept


# ============================================================================
# 7. 3단계 렌더 조립  (전부 -> 하드필터 -> 예산캡)
# ============================================================================

def _reserve_per_root(
    roots: Dict[Tuple[str, str], Dict[str, Any]],
    intents: List[str],
    fragment_templates: Dict[Tuple[str, str], str],
    min_chars_per_concept: int,
    priority_map: Optional[Dict[str, List[str]]],
    render_relations_by_intent: Optional[Dict[str, Dict[str, Set[str]]]],
    combo_relations: Optional[Set[str]],
    max_siblings_per_relation: Optional[int] = DEFAULT_MAX_SIBLINGS_PER_RELATION,
) -> Tuple[Set[int], int]:

    reserved_kept: Set[int] = set()
    reserved_chars = 0
    for root_key, root in roots.items():
        single = {root_key: root}
        kept = select_edges_by_budget(
            single, intents, fragment_templates, min_chars_per_concept,
            priority_map, render_relations_by_intent, combo_relations, max_siblings_per_relation,
        )
        reserved_kept |= kept
        lines = render_tree_pruned(root, root["name"], fragment_templates, kept)
        reserved_chars += sum(len(line) for line in lines)
    return reserved_kept, reserved_chars

def render_all_trees_pruned(
    paths: List[Dict[str, Any]],
    intents: List[str],
    fragment_templates: Dict[Tuple[str, str], str] = FRAGMENT_TEMPLATES,
    max_chars: Optional[int] = DEFAULT_MAX_CHARS,
    priority_map: Optional[Dict[str, List[str]]] = None,
    render_relations_by_intent: Optional[Dict[str, Dict[str, Set[str]]]] = None,
    combo_relations: Optional[Set[str]] = None,
    min_chars_per_concept: Optional[int] = DEFAULT_MIN_CHARS_PER_CONCEPT,
    max_siblings_per_relation: Optional[int] = DEFAULT_MAX_SIBLINGS_PER_RELATION,
) -> Tuple[List[str], Dict[Tuple[str, str], Dict[str, Any]], Set[int]]:
    roots = build_tree_from_paths(paths)
    root_lines_total = sum(len(root["name"] or "") + 1 for root in roots.values())
    budget_for_edges = None if max_chars is None else max(0, max_chars - root_lines_total)

    # min_chars_per_concept가 켜져 있고, concept(root)가 여러 개면 -> 먼저 concept별 최소치
    # 꺼져 있으면(기본값) 기존 동작 그대로 (전체 concept가 예산을 두고 그냥 경쟁).
    if min_chars_per_concept is not None and budget_for_edges is not None and len(roots) > 1:
        reserved_kept, _ = _reserve_per_root(
            roots, intents, fragment_templates, min_chars_per_concept,
            priority_map, render_relations_by_intent, combo_relations, max_siblings_per_relation,
        )
        kept_edges = select_edges_by_budget(
            roots, intents, fragment_templates, budget_for_edges,
            priority_map, render_relations_by_intent, combo_relations, max_siblings_per_relation,
            force_tier0=reserved_kept,
        )
    else:
        kept_edges = select_edges_by_budget(
            roots, intents, fragment_templates, budget_for_edges,
            priority_map, render_relations_by_intent, combo_relations, max_siblings_per_relation,
        )

    all_lines: List[str] = []
    for root_key, root in roots.items():
        if any(id(c) in kept_edges for c in root["children"].values()):
            root_name = root["name"] or ""
            root_line = root_name[0].upper() + root_name[1:] if root_name else root_name
            all_lines.append(root_line)
            all_lines.extend(render_tree_pruned(root, root["name"], fragment_templates, kept_edges))
    return all_lines, roots, kept_edges

def render_graph_context(
    paths: List[Dict[str, Any]],
    intents: List[str],
    fragment_templates: Dict[Tuple[str, str], str] = FRAGMENT_TEMPLATES,
    max_chars: Optional[int] = DEFAULT_MAX_CHARS,
    priority_map: Optional[Dict[str, List[str]]] = None,
    render_relations_by_intent: Optional[Dict[str, Dict[str, Set[str]]]] = None,
    combo_relations: Optional[Set[str]] = None,
    min_chars_per_concept: Optional[int] = DEFAULT_MIN_CHARS_PER_CONCEPT,
    max_siblings_per_relation: Optional[int] = DEFAULT_MAX_SIBLINGS_PER_RELATION,
) -> Tuple[List[str], Dict[Tuple[str, str], Dict[str, Any]], Set[int]]:

    # 1. 같은 관계를 따라갔다가 즉시 되돌아오는 왕복 Path 제거
    paths = filter_relation_bounce(paths)

    # 2. 질문 의도 기반 relevance filtering
    # Context 길이와 관계없이 항상 먼저 적용
    if "COMPREHENSIVE" not in intents:
        paths = hard_filter_paths(
            paths,
            intents,
            render_relations_by_intent,
            combo_relations,
        )

    # 3. 질문 의도와 관련된 Path 전체를 렌더링
    full_sentences, full_roots, full_kept = render_all_trees_pruned(
        paths,
        intents,
        fragment_templates,
        None,
        priority_map,
        render_relations_by_intent,
        combo_relations,
        None,
        max_siblings_per_relation,
    )

    # 4. 길이 제한 이하면 그대로 반환
    if max_chars is None or _rendered_length(full_sentences) <= max_chars:
        return full_sentences, full_roots, full_kept

    # 5. 길이를 초과할 때만 관계 우선순위와 Budget을 적용하여 추가 정제
    return render_all_trees_pruned(
        paths,
        intents,
        fragment_templates,
        max_chars,
        priority_map,
        render_relations_by_intent,
        combo_relations,
        min_chars_per_concept,
        max_siblings_per_relation,
    )

# ============================================================================
# 8. 그래프 시각화용 payload  (nodes / edges)
# ============================================================================

def build_graph_payload(
    roots: Dict[Tuple[str, str], Dict[str, Any]],
    kept_edges: Set[int],
    viz_exclude_relations: Optional[Set[str]] = None,
    viz_exclude_min_depth: int = VIZ_EXCLUDE_MIN_DEPTH,
) -> Dict[str, List[Dict[str, Any]]]:
    """render_graph_context가 실제로 채택한 roots(트리)와 kept_edges(edge id 집합)를
    프론트엔드 그래프 시각화용 nodes/edges 구조로 변환.

    - context_text(줄글)와 정확히 같은 근거(채택된 edge)만 포함 -> 화면과 텍스트가 일치.
    - 화살표 방향은 Neo4j 저장 방향(direction) 그대로 재현:
        direction == "out" -> parent -> child
        direction == "in"  -> child -> parent
    - 각 노드에 is_root(질문에서 나온 시작 concept 여부) 표시.
    """
    root_keys = set(roots.keys())  # {(concept_id, ontology), ...}
    nodes: Dict[Tuple[str, str], Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    viz_exclude_relations = (
        VIZ_EXCLUDE_RELATIONS if viz_exclude_relations is None else viz_exclude_relations
    )
    seen_edges: Set[Tuple[str, str, str]] = set()   # 중복 엣지 제거

    def node_id(concept_id: str, ontology: str) -> str:
        return f"{ontology}:{concept_id}"

    def add_node(concept_id: str, ontology: str, name: str) -> str:
        key = (concept_id, ontology)
        if key not in nodes:
            nodes[key] = {
                "id": node_id(concept_id, ontology),
                "concept_id": concept_id,
                "ontology": ontology,
                "name": name,
                "is_root": key in root_keys,
            }
        return nodes[key]["id"]

    def walk(node: Dict[str, Any], node_key: Tuple[str, str], depth: int = 0) -> None:
        parent_id = add_node(node_key[0], node_key[1], node["name"])
        for edge_key, child in node["children"].items():
            if id(child) not in kept_edges:
                continue
            relation, direction, child_concept_id, child_ontology = edge_key

            if relation in viz_exclude_relations and depth >= viz_exclude_min_depth:
                continue    # 이 엣지 + 하위 서브트리 통째로 스킵

            child_key = (child_concept_id, child_ontology)
            child_id = add_node(child_concept_id, child_ontology, child["name"])

            if direction == "out":
                src, tgt = parent_id, child_id
            else:
                src, tgt = child_id, parent_id

            sig = (src, tgt, relation)
            if sig not in seen_edges:
                seen_edges.add(sig)
                edges.append({
                    "source": src, "target": tgt,
                    "relation": relation, "direction": direction,
                })
            walk(child, child_key, depth + 1)

    for root_key, root in roots.items():
        if any(
            id(c) in kept_edges and not (k[0] in viz_exclude_relations
                                         and 0 >= viz_exclude_min_depth)
            for k, c in root["children"].items()
        ):
            walk(root, root_key, 0)

    return {"nodes": list(nodes.values()), "edges": edges}


# ============================================================================
# 9. 전체 파이프라인
# ============================================================================

def build_graph_context(
    driver,
    question: str,
    concept_set: List[Dict[str, Any]],
    hub_keys: Optional[Set[Tuple[str, str]]] = None,
    max_hop: int = 3,
    max_chars: Optional[int] = DEFAULT_MAX_CHARS,
    fragment_templates: Dict[Tuple[str, str], str] = FRAGMENT_TEMPLATES,
    priority_map: Optional[Dict[str, List[str]]] = None,
    render_relations_by_intent: Optional[Dict[str, Dict[str, Set[str]]]] = None,
    combo_relations: Optional[Set[str]] = None,
    min_chars_per_concept: Optional[int] = DEFAULT_MIN_CHARS_PER_CONCEPT,
    max_siblings_per_relation: Optional[int] = DEFAULT_MAX_SIBLINGS_PER_RELATION,   # 추가
    viz_exclude_relations: Optional[Set[str]] = None,                # 추가 (None = 상수 사용)
    viz_exclude_min_depth: int = VIZ_EXCLUDE_MIN_DEPTH,              # 추가
) -> Dict[str, Any]:
    result = ns.search_graph(driver, question, concept_set, hub_keys=hub_keys, max_hop=max_hop)
    intents = result["intents"]

    sentences, roots, kept_edges = render_graph_context(
        result["paths"], intents, fragment_templates, max_chars,
        priority_map, render_relations_by_intent, combo_relations, min_chars_per_concept,
        max_siblings_per_relation,   # 추가
    )
    context_text = "\n".join(sentences)
    graph = build_graph_payload(roots, kept_edges,
                                viz_exclude_relations, viz_exclude_min_depth)   # 추가

    return {
        "context_text": context_text,
        "sentences": sentences,
        "intents": intents,
        "per_start": result["per_start"],
        "paths": result["paths"],
        "graph": graph,
    }


# ============================================================================
# 10. 클래스
# ============================================================================

class GraphContext:
    """
    Neo4jSearch 인스턴스를 받아 조립 (driver/hub_keys는 Neo4jSearch가 관리하는 걸 그대로 사용).
    렌더링 옵션(max_chars 등)은
    이 클래스가 인스턴스 기본값으로 들고 있다가, build() 호출 시 안 넘기면 그 값을 씀.

    *** graph 필드 ***
    graph(nodes/edges)는 탐색된 전체(neo4j_search.py 결과)가 아니라
    context_text에 실제로 렌더링된 것만 포함함.(render_graph_context의 kept_edges 기준)

    *** 옵션 주의사항 ***
    - max_chars=None 이면 글자수 제한 없음 (1단계에서 바로 반환, paths 전부 렌더링).
      운영에서 이 값을 크게 잡을수록 context_text/graph가 커지고 LLM 토큰 비용도 커짐.
    - min_chars_per_concept: concept(=root)이 여러 개일 때만 의미 있음. 예산이 빠듯해서
      특정 concept 정보가 아예 안 보이는 걸 막고 싶을 때만 켜기 (기본 None = 꺼짐).
    - max_siblings_per_relation: 같은 (부모, 관계)에서 형제가 너무 많아 예산을 독식하는
      문제를 막는 옵션 (기본 None = 무제한). select_edges_by_budget 주석 참고.

    사용법:
        searcher = Neo4jSearch(driver)                       # 앱 시작 시 1회
        gc_builder = GraphContext(searcher)                   # 앱 시작 시 1회 (기본값은 섹션 1-4 상수)

        ctx = gc_builder.build(question, concept_set)         # 요청마다 호출
        # ctx["context_text"] -> LLM 프롬프트에
        # ctx["graph"]        -> 프론트엔드 화면에

        # 이번 호출만 다른 예산으로 (인스턴스 기본값은 안 바뀜):
        ctx = gc_builder.build(question, concept_set, max_chars=5000)
        ctx = gc_builder.build(question, concept_set, max_chars=None)   # 이번만 무제한

        # 이번 호출만 프론트 그래프도 pruning 없이 전부:
        ctx = gc_builder.build(question, concept_set, viz_exclude_relations=set())
    """

    def __init__(
        self,
        searcher: "ns.Neo4jSearch",
        max_chars: Optional[int] = DEFAULT_MAX_CHARS,
        fragment_templates: Dict[Tuple[str, str], str] = FRAGMENT_TEMPLATES,
        priority_map: Optional[Dict[str, List[str]]] = None,
        render_relations_by_intent: Optional[Dict[str, Dict[str, Set[str]]]] = None,
        combo_relations: Optional[Set[str]] = None,
        min_chars_per_concept: Optional[int] = DEFAULT_MIN_CHARS_PER_CONCEPT,
        max_siblings_per_relation: Optional[int] = DEFAULT_MAX_SIBLINGS_PER_RELATION,
        viz_exclude_relations: Optional[Set[str]] = None,
        viz_exclude_min_depth: int = VIZ_EXCLUDE_MIN_DEPTH,
    ):
        self.searcher = searcher
        # 렌더링 기본값들: 여기서 한 번 설정해두면 build() 호출마다 안 넘겨도 됨
        self.max_chars = max_chars
        self.fragment_templates = fragment_templates
        self.priority_map = priority_map
        self.render_relations_by_intent = render_relations_by_intent
        self.combo_relations = combo_relations
        self.min_chars_per_concept = min_chars_per_concept
        self.max_siblings_per_relation = max_siblings_per_relation
        # 시각화 전용 (None = 섹션 1-5 상수 사용). context_text에는 영향 없음
        self.viz_exclude_relations = viz_exclude_relations
        self.viz_exclude_min_depth = viz_exclude_min_depth

    def build(
        self,
        question: str,
        concept_set: List[Dict[str, Any]],
        max_chars: Any = _UNSET,
        min_chars_per_concept: Any = _UNSET,
        max_siblings_per_relation: Any = _UNSET,
        viz_exclude_relations: Any = _UNSET,
        viz_exclude_min_depth: Any = _UNSET,
    ) -> Dict[str, Any]:
        """질문 + concept_set -> {"context_text", "sentences", "intents",
        "per_start", "paths", "graph"}

        (max_chars / min_chars_per_concept / max_siblings_per_relation)은
        이번 호출에만 덮어쓸 수 있음. 안 넘기면 인스턴스 기본값을 씀 (기본값은 안 바뀜).

        None도 유효한 값으로 정확히 전달됨 (_UNSET 표식 사용):
            build(q, cs)                  -> 인스턴스 기본값
            build(q, cs, max_chars=None)  -> 이번 호출만 무제한
            build(q, cs, max_chars=5000)  -> 이번 호출만 5000
        """
        eff_max_chars = self.max_chars if max_chars is _UNSET else max_chars
        eff_min_chars = (self.min_chars_per_concept if min_chars_per_concept is _UNSET
                         else min_chars_per_concept)
        eff_siblings = (self.max_siblings_per_relation if max_siblings_per_relation is _UNSET
                        else max_siblings_per_relation)
        eff_viz_excl = (self.viz_exclude_relations if viz_exclude_relations is _UNSET
                        else viz_exclude_relations)
        eff_viz_depth = (self.viz_exclude_min_depth if viz_exclude_min_depth is _UNSET
                         else viz_exclude_min_depth)

        result = self.searcher.search(question, concept_set)
        intents = result["intents"]

        sentences, roots, kept_edges = render_graph_context(
            result["paths"], intents, self.fragment_templates,
            eff_max_chars,
            self.priority_map, self.render_relations_by_intent, self.combo_relations,
            eff_min_chars,
            eff_siblings,
        )
        context_text = "\n".join(sentences)
        graph = build_graph_payload(roots, kept_edges, eff_viz_excl, eff_viz_depth)

        return {
            "context_text": context_text, # ** llm 프롬프트에 전달 **
            "sentences": sentences, # context_text의 줄 단위 원본
            "intents": intents, # 질문에서 분류된 의도
            "per_start": result["per_start"], # 시작 concept별 탐색 요약
            "paths": result["paths"], # 렌더링 전 탐색 결과 원본
            "graph": graph, # ** 프론트엔드에 전달 **
        }