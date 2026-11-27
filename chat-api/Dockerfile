FROM python:3.11-slim-bookworm

WORKDIR /app

# torch CPU d'abord : l'image reste bien plus légère
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY chat-api/requirements.txt /app/chat-api/requirements.txt
RUN pip install --no-cache-dir -r chat-api/requirements.txt

COPY chat-api /app/chat-api

CMD ["python", "chat-api/chatbot_test.py"]