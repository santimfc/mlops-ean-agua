# Imagen base liviana de Python
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias primero (aprovecha la caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la API
COPY main.py .

# Container Apps enviará el tráfico a este puerto
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
