# 1. Empezar con una imagen oficial de Python
FROM python:3.11-slim

# 2. Establecer un directorio de trabajo
WORKDIR /app

# 3. --- ¡LA SOLUCIÓN! ---
# Instalar la librería 'potrace' del sistema (Linux) antes que nada
RUN apt-get update && apt-get install -y potrace

# 4. Copiar el archivo de requerimientos
COPY requirements.txt .

# 5. Instalar las librerías de Python
# pypotrace ahora encontrará la librería potrace y se instalará correctamente
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el resto del código de la app
COPY main.py .

# 7. Exponer el puerto (Render usará $PORT, pero esto es buena práctica)
EXPOSE 8000

# 8. Comando de inicio (Render lo leerá desde tu panel de control)
# Dejamos el comando que ya tenías: uvicorn main:app --host 0.0.0.0 --port $PORT
