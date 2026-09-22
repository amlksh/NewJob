# WMIT MSK 해석 워커 — 기준 실행 환경.
#
# 로컬 결과와 이 컨테이너 결과가 다르면 컨테이너가 정답이다 (CLAUDE.md §2).
#
# OpenSim 4.6 PyPI wheel 요구사항:
#   - Linux glibc 2.27+ / x86-64
#   - CPython 3.11 / 3.12 / 3.13
# Debian bookworm 은 glibc 2.36 이므로 조건을 만족한다.
# WMIT 서버가 더 오래된 배포판이어도 이 컨테이너를 쓰면 영향을 받지 않는다.

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# OpenSim 네이티브 라이브러리가 요구하는 런타임 의존성.
# 헤드리스 서버이므로 GUI 관련 패키지는 넣지 않는다.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libstdc++6 \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --upgrade pip \
    && pip install ".[opensim]"

COPY configs/ ./configs/
COPY scripts/ ./scripts/

# data/ 와 runs/ 는 볼륨으로 마운트한다. 이미지에 데이터를 굽지 않는다.
VOLUME ["/app/data", "/app/runs", "/app/models"]

# 설치 확인. 빌드 시점에 OpenSim 이 실제로 import 되는지 본다.
RUN python -c "import opensim; print('OpenSim', opensim.__version__)"

CMD ["python", "scripts/run_poc.py", "--help"]
