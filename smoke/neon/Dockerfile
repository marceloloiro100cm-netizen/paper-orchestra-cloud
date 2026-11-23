FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir 'google-genai>=2.34.0,<3'
COPY smoke.py /app/smoke.py
CMD ["python", "/app/smoke.py"]
