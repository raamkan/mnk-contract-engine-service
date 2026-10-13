# mnk-contract-engine-service
contract engine service built using python and Django

## Local PostgreSQL setup

1. Create and activate a Python virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and set a local database password. Existing environment variables take precedence over `.env`.
3. Start PostgreSQL with `docker compose up -d --wait db`.
4. Run `python manage.py migrate`.
5. Start Django with `python manage.py runserver`.

Visit `/health/` to check database connectivity. A successful check returns HTTP 200 with `"status": "ok"` and `"database": "postgresql"`; a database connection failure returns HTTP 503.

PostgreSQL listens on `127.0.0.1:5433` and stores data in the `postgres_data` Docker volume. Database credentials are initialized when that volume is first created; changing `.env` does not change credentials in an existing database. Existing SQLite data is not automatically imported.
