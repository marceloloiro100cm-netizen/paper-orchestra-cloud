FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# Copia todos os módulos da API. Listar arquivo por arquivo deixou de fora
# model_access.py e access_requests.py e derrubava a API ao iniciar.
# tests/test_container_modules.py impede que isso volte a acontecer.
COPY *.py /app/
# Normas de formatação (pasta formatos/ na raiz do repositório, copiada para cá pelo deploy).
COPY formatos/ /app/formatos/
ENV PORT=8080
CMD ["sh", "-c", "exec uvicorn main:application --host 0.0.0.0 --port ${PORT}"]
