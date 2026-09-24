<p align="center">
  <img src="./docs/images/medicalqa.png" width="100%">
</p>

<p align="center">
</p>

## MedicalQA: 의료 지식 그래프와 임상 진료지침을 활용한 GraphRAG 기반 의료 질의응답 시스템

### 1. 프로젝트 배경

#### 1.1. 문제점

대규모 언어 모델(LLM)은 의료 질의응답에 활용될 수 있지만, 단독으로 사용할 경우 부정확한 답변이 생성되거나 답변의 근거를 충분히 제시하기 어렵다는 한계가 있다. 또한 기존 RAG 방식은 주로 텍스트 유사도를 기반으로 정보를 검색하기 때문에 의료 개념 간의 구조적인 관계를 충분히 활용하기 어렵다.

#### 1.2. 필요성

의료 질의에 대한 답변의 신뢰성을 높이기 위해서는 질문에 포함된 의료 개념을 정확하게 식별하고, 의료 개념 간 관계 정보와 임상 진료지침을 함께 활용하는 검색 방식이 필요하다.

이에 본 프로젝트에서는 의료 지식 그래프 기반 GraphRAG와 임상 진료지침 검색을 결합한 MedicalQA를 개발하였다.

#### 1.3. 기대효과

의료 지식 그래프의 구조적 관계 정보와 임상 진료지침의 근거 정보를 함께 활용하여, LLM의 생성 능력에만 의존하지 않는 근거 기반 의료 질의응답을 지원한다.

### 2. 개발 목표

#### 2.1. 목표 및 세부 내용

본 프로젝트는 의료 지식 그래프와 임상 진료지침을 결합한 GraphRAG 기반 의료 질의응답 시스템 MedicalQA를 구축하는 것을 목표로 한다.

사용자의 의료 질문에서 주요 의료 개념을 식별하고, 의료 지식 그래프와 임상 진료지침에서 관련 정보를 검색하여 답변 생성에 활용한다.

주요 개발 내용은 다음과 같다.

* **의료 지식 그래프 구축**
  SNOMED CT, RxNorm, LOINC 등의 의료 표준 용어를 활용하여 의료 개념 및 관계 정보를 Neo4j 기반 지식 그래프로 구축

* **의료 개념 검색 및 연결**
  질문에 포함된 의료 개념을 탐지하고 BM25와 임베딩 기반 Hybrid Search를 통해 관련 개념을 검색

* **GraphRAG 기반 관계 탐색**
  질문의 의도에 따라 지식 그래프의 관련 관계를 탐색하여 의료 개념 간 구조적 정보를 검색

* **임상 진료지침 검색**
  NICE 및 WHO의 임상 진료지침을 전처리하고 벡터 검색을 통해 질문과 관련된 근거 정보를 검색

* **근거 기반 답변 생성**
  지식 그래프에서 검색한 관계 정보와 임상 진료지침을 결합하여 LLM 기반 의료 답변 생성

* **웹 기반 의료 질의응답 서비스 구현**
  React와 FastAPI를 활용하여 사용자가 의료 질문을 입력하고 검색 결과를 바탕으로 생성된 답변을 확인할 수 있는 웹서비스 구현

#### 2.2. 차별성

MedicalQA는 단순히 LLM의 생성 능력이나 텍스트 유사도 기반 검색에 의존하지 않고, 의료 지식 그래프의 구조적 관계 정보와 임상 진료지침을 함께 활용한다는 점에서 차별성을 가진다.

| 구분              | LLM 단독 | 일반 RAG | MedicalQA |
| --------------- | ------ | ------ | --------- |
| 외부 근거 검색        | ❌      | ○      | ○         |
| 의료 개념 간 관계 활용   | ❌      | 제한적    | **○**     |
| 의료 지식 그래프 활용    | ❌      | ❌      | **○**     |
| 임상 진료지침 활용      | ❌      | △      | **○**     |
| 구조적·문서 기반 근거 결합 | ❌      | △      | **○**     |
> 일반 RAG는 외부 문서를 검색할 수 있지만, 의료 지식 그래프의 구조적 관계나 전문 임상 진료지침을 별도의 지식원으로 활용하는 데에는 한계가 있다.

**주요 차별점**

* **의료 지식 그래프 기반 관계 검색**
  의료 개념 간의 관계를 그래프 형태로 탐색하여 단순 텍스트 유사도만으로 찾기 어려운 구조적 정보를 활용한다.

* **임상 진료지침과 지식 그래프의 결합**
  그래프에서 확보한 의료 개념 및 관계 정보와 NICE, WHO 등의 임상 진료지침 검색 결과를 함께 활용한다.

* **질문 의도 기반 검색**
  질문의 의도에 따라 약물, 검사, 병리 등 필요한 그래프 관계를 선택적으로 탐색하여 답변에 필요한 정보를 구성한다.

* **근거 기반 답변 생성**
  검색된 의료 지식과 임상 진료지침을 답변 생성 과정에 활용하여 단순 생성형 답변이 아닌 근거 기반의 의료 질의응답을 지원한다.

### 3. 시스템 설계

#### 3.1. 시스템 구성

![MedicalQA 시스템 구성도](./docs/images/system_architecture.png)

MedicalQA는 React 기반 웹 프론트엔드와 FastAPI 기반 백엔드를 중심으로 구성되며,
Neo4j 의료 지식 그래프, Qdrant 벡터 데이터베이스, PostgreSQL, Ollama 기반 Gemma 등의
서비스를 연계하여 의료 질의응답을 처리한다.

각 구성요소는 Docker 컨테이너로 분리하고 Docker Compose를 통해 통합 실행할 수 있도록 구성하였다.

#### 3.2. 기술 스택

| 구분              | 기술                            | 주요 역할                   |
| --------------- | ----------------------------- | ----------------------- |
| Frontend        | React, Vite                   | 웹 사용자 인터페이스 구현          |
| Backend         | FastAPI, Python               | REST API 및 질의응답 처리      |
| LLM             | Gemma4, Ollama                | 의료 질의응답 생성 및 번역         |
| Knowledge Graph | Neo4j 5 Community             | 의료 지식 그래프 저장 및 그래프 탐색   |
| Vector DB       | Qdrant                        | 의료 개념 및 임상 진료지침 벡터 검색   |
| Database        | PostgreSQL 17                 | 채팅 및 메시지 데이터 저장         |
| Embedding       | BAAI/bge-base-en-v1.5         | 의료 개념 및 문서 임베딩          |
| NLP             | SciSpacy, en_core_sci_scibert | 의료 개념 Mention Detection |
| Search          | BM25, Embedding Search        | 의료 개념 Hybrid Search     |
| Data            | SNOMED CT, RxNorm, LOINC      | 의료 표준 용어 및 지식 그래프 구축    |
| Guideline       | NICE, WHO                     | 임상 진료지침 데이터 구축          |
| Infrastructure  | Docker, Docker Compose        | 서비스 컨테이너화 및 통합 실행       |

### 4. 개발 결과

#### 4.1. 전체 시스템 흐름

![MedicalQA 전체 시스템 흐름도](./docs/images/system_flow.png)

MedicalQA는 사용자의 질문을 입력받아 **질문 입력 → (후속 질문인 경우 질문 재구성) → 의료 개념 탐지 및 Entity Linking → 지식 그래프 탐색과 임상 진료지침 검색 → Graph Context 및 Guideline Context 구성 → Gemma 기반 답변 생성**의 과정을 거쳐 최종 답변을 제공한다.

질문과 관련된 의료 지식은 Neo4j 기반 지식 그래프에서 탐색하고,
임상 진료지침은 Qdrant 기반 벡터 검색을 통해 검색한다.
검색된 두 종류의 근거 정보를 LLM에 함께 제공하여 답변을 생성하도록 구성하였다.

#### 4.2. 주요 기능

##### 4.2.1. 의료 질의응답

![MedicalQA 메인 화면](./docs/images/main_screen.png)
![MedicalQA 답변 화면](./docs/images/answer_screen.png)

사용자는 웹 인터페이스에서 의료 관련 질문을 입력할 수 있으며, 입력된 질문은 질문 분석과 의료 지식·임상 진료지침 검색 과정을 거쳐 Gemma 기반 답변으로 생성된다.

![MedicalQA 답변 근거 화면](./docs/images/answer_screen2.png)

생성된 답변은 영어 원문으로 제공되며, 답변 하단에서 **한국어 번역보기**와 **원문보기** 기능을 통해 답변 언어를 전환할 수 있다. 또한 답변 생성에 활용된 **임상 진료지침과 의료 개념의 개수**를 표시하고 **근거보기** 버튼을 제공한다. 근거보기를 선택하면 답변 생성에 활용된 **임상 진료지침과 의료 지식 그래프 기반 근거 정보**를 상세하게 확인할 수 있다. 대화형 인터페이스에서는 이전 대화 내용을 기반으로 연속적인 질의응답을 지원한다.

##### 4.2.2. 임상 진료지침 근거

![MedicalQA 임상 진료지침 화면](./docs/images/evidence_guideline.png)

답변 하단의 **근거보기** 기능을 통해 AI 답변 생성에 활용된 임상 진료지침을 확인할 수 있다. 검색된 진료지침의 관련 내용을 제공하여 답변이 어떤 임상 근거를 바탕으로 생성되었는지 확인할 수 있도록 구성하였다.

##### 4.2.3. 의료 지식 그래프 시각화

![MedicalQA 지식 그래프 화면](./docs/images/evidence_knowledge_graph.png)

또한, 답변 생성에 활용된 의료 개념과 개념 간 관계를 **의료 지식 그래프 형태로 시각화**하여 제공한다. 사용자는 질문과 관련된 의료 개념 및 관계를 그래프를 통해 확인할 수 있으며, 답변에 활용된 지식 그래프 기반 근거를 직관적으로 확인할 수 있다.

##### 4.2.4. 사용자 인터페이스

최종적으로 구현한 주요 사용자 인터페이스와 기능은 다음과 같다.

| 구분 | 구현 내용 |
|---|---|
| **메인 화면** | 서비스 안내, 지원 질환 표시 및 의료 질문 입력 |
| **질문 입력** | 사용자의 의료 질문 입력 및 전송 |
| **채팅 화면** | 사용자 질문과 AI 답변을 대화 형태로 표시 |
| **답변 출력** | Markdown 기반 AI 답변 렌더링 |
| **번역 기능** | 질문 및 답변의 원문과 한국어 번역 전환 |
| **근거 보기** | AI 답변 생성에 활용된 임상 진료지침 및 지식 그래프 확인 |
| **새 채팅** | 새로운 대화 세션 시작 |
| **채팅 목록** | 저장된 기존 채팅 목록 조회 |
| **대화 복원** | 기존 채팅 선택 시 이전 질문 및 답변 불러오기 |
| **채팅 관리** | 채팅 제목 변경 및 삭제 |

#### 4.3. 성능평가

MedicalQA의 성능을 평가하기 위해 의료 객관식 질의응답 데이터셋 **MedQA**를 활용하고, 동일한 **Gemma4:12b**를 사용하는 Gemma4-only와 MedicalQA의 답변 정확도를 비교하였다.

| 구분            | 정답 문항 수 | 전체 평가 항목 |         정확도 |
| ------------- | ------: | -------: | ----------: |
| Gemma4-only   |     237 |      330 |       71.8% |
| **MedicalQA** | **276** |  **330** |   **83.6%** |
| 변화            |     +39 |        - | **+11.8%p** |

MedicalQA는 동일한 LLM을 사용하면서 의료 지식 그래프와 임상 진료지침 검색 결과를 추가적으로 활용하였으며, 평가 결과 Gemma4-only 대비 **11.8%p 높은 정확도**를 기록하였다.

#### 4.4. 디렉토리 구조

```text
MedicalQA/
├── backend/                              # FastAPI 기반 백엔드
│   ├── api.py                            # API 엔드포인트
│   ├── pipeline.py                       # 질의응답 처리 파이프라인
│   ├── database/                         # PostgreSQL 데이터 관리
│   ├── db/                               # Neo4j 지식 그래프 검색
│   ├── services/                         # 의료 검색 및 LLM 서비스
│   ├── Dockerfile                        # 백엔드 Docker 설정
│   └── requirements.txt                  # Python 의존성
│
├── frontend/                             # React + Vite 기반 프론트엔드
│   └── src/
│       ├── api/                           # 백엔드 API 통신
│       ├── components/
│       │   ├── Chat/                      # 의료 질의응답 화면
│       │   ├── EvidenceModal/             # 답변 근거 및 지식 그래프
│       │   ├── Sidebar/                   # 채팅 목록 관리
│       │   └── ...                        # 기타 UI 컴포넌트
│       ├── App.jsx                        # 메인 애플리케이션
│       └── main.jsx                       # 애플리케이션 진입점
│
├── evaluation/                            # 모델 및 시스템 평가
├── scripts/                               # 데이터 및 지식 그래프 구축 스크립트
└── docker-compose.yml                     # 전체 서비스 구성

### 5. 설치 및 실행 

#### 5.1. 설치 및 실행 방법

### 6. 소개 자료

[MedicalQA 발표자료.pdf](./docs/03.발표자료/발표자료.pdf)

[![MedicalQA 영상](https://img.youtube.com/vi/gM6ocnumYhs/0.jpg)](https://youtu.be/gM6ocnumYhs)

### 7. 팀 구성
| 성명  | 구성원별 역할                                                                                                                                                         |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 김채은 | - 의료 온톨로지 데이터 전처리 및 검색 인덱스 구축<br>- Hybrid Search 및 Entity Linking 구현<br>- 임상 진료지침 전처리 및 Guideline Retrieval 구현<br>- LLM 연동 및 프롬프트 설계<br>- 전체 파이프라인 조립 및 모듈 통합   |
| 신우솜 | - MedicalQA 웹 인터페이스 개발<br>- 임상 진료지침 및 지식 그래프 기반 근거정보 시각화<br>- FastAPI 백엔드 API 및 데이터 연동<br>- PostgreSQL 기반 채팅 데이터 관리 기능 구현<br>- Gemma4-only와 MedicalQA의 정성 비교 평가 |
| 이정현 | - 의료 온톨로지 데이터 전처리 및 매핑<br>- 의료 지식 그래프 구축 및 Neo4j 적용<br>- 질문 의도 기반 Graph Query 설계<br>- Graph Context 생성 모듈 구현<br>- GraphRAG 파이프라인 통합 모듈 구성                       |

### 8. 참고 문헌 및 출처

#### 8.1 논문 및 기술 문헌

1. Robertson, S. & Zaragoza, H. (2009). *The Probabilistic Relevance Framework: BM25 and Beyond.*
2. Han, H. et al. (2025). *Retrieval-Augmented Generation with Graphs (GraphRAG).*
3. Xiao, S. et al. (2024). *C-Pack: Packed Resources for General Chinese Embeddings.*
4. Reimers, N. & Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings Using Siamese BERT-Networks.*
5. Neumann, M. et al. (2019). *ScispaCy: Fast and Robust Models for Biomedical Natural Language Processing.*

#### 8.2 의료 데이터 및 임상 진료지침

* **SNOMED CT** — 의료 임상 개념 및 관계 데이터
* **RxNorm** — 의약품 및 약물 개념 데이터
* **LOINC** — 임상검사 및 관찰 항목 데이터
* **NICE (National Institute for Health and Care Excellence)** — Type 2 Diabetes, Hypertension, COPD, CKD, Chronic Heart Failure 임상 진료지침
* **WHO (World Health Organization)** — Type 2 Diabetes, Hypertension 임상 진료지침

#### 8.3 모델 및 오픈소스

* **SciSpaCy** — Biomedical Natural Language Processing
* **d4data/biomedical-ner-all** — Biomedical Named Entity Recognition
* **Gemma** — Google DeepMind의 오픈 LLM
* **BAAI/bge-base-en-v1.5** — Sentence Embedding Model
