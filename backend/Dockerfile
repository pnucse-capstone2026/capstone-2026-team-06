FROM python:3.11-slim

WORKDIR /app

# requirements 복사
COPY requirements.txt .

# pip 업데이트
RUN pip install --upgrade pip

# CUDA 12.8용 PyTorch 설치
RUN pip install --no-cache-dir \
    torch==2.11.0 \
    --index-url https://download.pytorch.org/whl/cu128
    
# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# SciSpaCy 모델 설치
RUN pip install --no-cache-dir \
    https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_scibert-0.5.4.tar.gz \
    --no-deps

# 프로젝트 전체 복사
COPY . .

# FastAPI 포트
EXPOSE 8000

CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]