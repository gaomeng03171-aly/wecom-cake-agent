FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./

# Cache third-party dependencies before copying frequently changing source.
RUN touch README.md \
    && mkdir -p src/app \
    && touch src/app/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf src

COPY src ./src
COPY README.md ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts

RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
