FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd -r app && useradd -r -g app app
COPY pyproject.toml requirements.lock ./
COPY config ./config
COPY shop ./shop
COPY manage.py ./manage.py
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && pip install --no-cache-dir --no-deps --no-build-isolation . \
    && pip check \
    && python -m compileall -q config shop \
    && DJANGO_DEBUG=true python manage.py collectstatic --noinput \
    && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--access-logformat", "%(m)s %(s)s %(b)s %(L)s"]
