FROM python:3.12-slim

WORKDIR /srv/backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Migrations and seed files live outside the backend image context and are
# mounted by docker compose at /srv/db.
ENV MIGRATIONS_DIR=/srv/db/migrations \
    SEED_DIR=/srv/db/seed \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
