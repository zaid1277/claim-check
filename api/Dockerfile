FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/home/app/.cache/huggingface
WORKDIR /app/api
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.lock requirements-models.txt ./
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir -r requirements-models.txt
COPY app ./app
COPY migrations ./migrations
RUN useradd --create-home app && mkdir -p /home/app/.cache/huggingface && chown -R app:app /app /home/app/.cache
USER app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
