# ITS-Convert Dockerfile
# Multi-stage build for creating portable executables
#
# This Dockerfile creates a build environment with all necessary tools
# for translating, reviewing, and building scripts to various formats.

# Stage 1: Builder image with all build tools
FROM python:3.12-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[dev]" && \
    pip install --no-cache-dir pyinstaller nuitka && \
    pip cache purge

# Download and install linuxdeploy for AppImage creation
RUN wget -q https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage -O /usr/local/bin/linuxdeploy && \
    chmod +x /usr/local/bin/linuxdeploy && \
    wget -q https://github.com/linuxdeploy/linuxdeploy-plugin-python/releases/download/continuous/linuxdeploy-plugin-python-x86_64.AppImage -O /usr/local/bin/linuxdeploy-plugin-python && \
    chmod +x /usr/local/bin/linuxdeploy-plugin-python

# Download appimagetool as fallback
RUN wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O /usr/local/bin/appimagetool && \
    chmod +x /usr/local/bin/appimagetool

# Install shc for shell script compilation
RUN apt-get install -y shc

# Stage 2: Runtime image (smaller, production-ready)
FROM python:3.12-alpine as runtime

# Install runtime dependencies
RUN apk add --no-cache \
    bash \
    curl \
    ca-certificates \
    && update-ca-certificates

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/itsconvert /usr/local/bin/itsconvert
COPY --from=builder /usr/local/bin/linuxdeploy /usr/local/bin/linuxdeploy
COPY --from=builder /usr/local/bin/linuxdeploy-plugin-python /usr/local/bin/linuxdeploy-plugin-python
COPY --from=builder /usr/local/bin/appimagetool /usr/local/bin/appimagetool

# Copy application code
WORKDIR /app
COPY . .

# Set entrypoint
ENTRYPOINT ["itsconvert"]
CMD ["--help"]

# Label
LABEL maintainer="Bear Carrington <ITSolutions_MGNT@proton.me>" \
      description="ITS-Convert: Cross-language script translator and builder" \
      version="0.1.0" \
      org.opencontainers.image.source="https://github.com/v1ral-ITS/ITS-Convert"
