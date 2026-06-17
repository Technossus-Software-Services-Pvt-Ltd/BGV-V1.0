FROM python:3.10.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app/uploads

USER appuser

# Pre-download PaddleOCR models to cache them inside the image
COPY --chown=appuser:appuser download_models.py /home/appuser/download_models.py
RUN python /home/appuser/download_models.py && rm /home/appuser/download_models.py

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]