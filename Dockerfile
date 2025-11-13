FROM python:3.11-slim

WORKDIR /app

# Instalar potrace desde source con soporte PNG
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    libpng-dev \
    zlib1g-dev \
    && wget https://potrace.sourceforge.net/download/potrace-1.16.tar.gz \
    && tar -xzf potrace-1.16.tar.gz \
    && cd potrace-1.16 \
    && ./configure --with-libpng \
    && make \
    && make install \
    && cd .. \
    && rm -rf potrace-1.16 potrace-1.16.tar.gz \
    && apt-get remove -y wget build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port $PORT
