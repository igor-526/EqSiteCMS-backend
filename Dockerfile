# Base python image
FROM python:3.13

# Dependencies install
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/0.8.15/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin/:$PATH"

WORKDIR /eqsitecms
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked

COPY src/ ./src
CMD ["uv", "run", "src/main.py"]
