# Backend Dockerfile
FROM python:3.10-slim

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements.txt
COPY ../requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código del proyecto
COPY .. .

# Exponer puerto 8000 para FastAPI
EXPOSE 8000

# Comando para ejecutar  la API
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
