FROM python:3.12-slim

# System dependencies for OpenCV, libGL, and Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra tesseract-ocr-deu \
    tesseract-ocr-spa tesseract-ocr-rus tesseract-ocr-ara tesseract-ocr-chi-sim \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY config.example.yaml ./
COPY profiles/ profiles/

# Install the package (no extras — bare install)
RUN uv sync --frozen

# Tesseract data path
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/

ENTRYPOINT ["uv", "run", "ocr-pipeline"]
CMD ["--help"]
