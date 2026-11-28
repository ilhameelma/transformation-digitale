FROM python:3.11-slim-bookworm

WORKDIR /app

# torch CPU d'abord : l'image reste bien plus légère
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY chat-api/requirements.txt /app/chat-api/requirements.txt
RUN pip install --no-cache-dir -r chat-api/requirements.txt

# paquets légers de l'API (couche séparée : ils changent plus souvent)
COPY chat-api/requirements-api.txt /app/chat-api/requirements-api.txt
RUN pip install --no-cache-dir --default-timeout=120 --retries 10 -r chat-api/requirements-api.txt

COPY chat-api /app/chat-api

EXPOSE 8000
CMD ["uvicorn", "app:app", "--app-dir", "chat-api", "--host", "0.0.0.0", "--port", "8000"]