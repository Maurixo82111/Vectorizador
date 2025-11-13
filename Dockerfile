# 1. Empezar con una imagen oficial de Python
FROM python:3.11-slim

# 2. Establecer un directorio de trabajo
WORKDIR /app

# 3. --- ¡LA SOLUCIÓN ACTUALIZADA! ---
# Instalar potrace Y las herramientas de compilación (build-essential)
RUN apt-get update && apt-get install -y potrace build-essential && rm -rf /var/lib/apt/lists/*

# 4. Copiar el archivo de requerimientos
COPY requirements.txt .

# 5. Instalar las librerías de Python
# pypotrace ahora encontrará potrace Y el compilador, y se instalará correctamente
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el resto del código de la app
COPY main.py .

# 7. Exponer el puerto (Render usará $PORT, pero esto es buena práctica)
EXPOSE 8000

# 8. --- ¡COMANDO DE INICIO AÑADIDO! ---
# Render usará el $PORT que nos asigna automáticamente.
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
