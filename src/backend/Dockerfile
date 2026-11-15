FROM python:3.12-slim

WORKDIR /app

# curl para el healthcheck declarado en infra/taller/docker-compose.yml
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# El contexto de build es src/ (no src/backend), para que la imagen pueda
# traer agentlib ademas de backend. Asi la capa de proveedores tiene UNA sola
# implementacion: el backend y el codigo de los pasos usan el mismo archivo.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/
COPY agentlib/ /agentlib/
# agentlib se importa como paquete desde /, que es donde chat.py lo busca.
ENV PYTHONPATH=/

EXPOSE 8000

# En desarrollo, infra/taller/docker-compose.override.yml reemplaza esto por
# uvicorn --reload con el codigo montado en vivo.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
