FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd -r app && useradd -r -g app app
COPY pyproject.toml ./
COPY config ./config
COPY shop ./shop
COPY manage.py ./manage.py
RUN pip install --no-cache-dir . && python -m compileall -q config shop && mkdir -p /app/staticfiles && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
