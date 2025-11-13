# Usar una imagen base más robusta
FROM python:3.11-bookworm

WORKDIR /app

# Instalar dependencias del sistema de forma más exhaustiva
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libpotrace-dev \
    potrace \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Instalar con flags específicos para compilación
RUN pip install --no-cache-dir --verbose -r requirements.txt

COPY main.py .

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port $PORT
