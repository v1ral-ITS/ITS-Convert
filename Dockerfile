# Portable translation runtime. Install build engines separately on their target OS.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY itsconvert ./itsconvert
COPY examples/hello.py ./examples/hello.py
COPY examples/artifacts ./examples/artifacts
RUN python -m pip install .
ENTRYPOINT ["itsconvert"]
CMD ["--help"]
LABEL maintainer="ImPerial TeK. Solutions" \
      org.opencontainers.image.source="https://github.com/v1ral-ITS/ITS-Convert"
