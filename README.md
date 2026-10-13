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

## Add an endorsement

After applying migrations with `python manage.py migrate`, send JSON to
`POST /api/contracts/{mga_reference}/endorsements/` (including the trailing slash).
The URL identifies the contract; clients do not supply its database ID.
Successful requests return 201. Validation failures, including unknown contracts,
return 400 with errors keyed by field. The original slip is not modified.

```json
{
  "endorsement_number": 1,
  "type": "CHANGE_SUM_INSURED",
  "status": "AGREED",
  "effective_date": "2026-03-01",
  "recorded_date": "2026-03-05",
  "premium_change": "20000.00",
  "changes": {"sum_insured": "6000000.00"},
  "reason": "Sum insured increased for new warehouse"
}
```

### Endorsement decisions

- Numbers are positive integers, unique per contract across both statuses; gaps are allowed.
- Recorded dates are retained for audit and do not restrict effective dates.
- `changes` must contain exactly `sum_insured`, `insured_name`, or `expiry_date`
  for the corresponding change type. Premium adjustments and cancellations use `{}`.
- Send amounts as decimal strings. Endorsement amounts are rounded half up to two
  places before storage and premium checks; floating-point inputs are rejected.
- Cancellation premiums are always calculated by the service, overriding any
  supplied amount; `null` is accepted as input for cancellations.
- Drafts must have valid fields, dates and changes, but their premium changes do
  not affect the balance or fund agreed returns. Draft cancellation refunds are
  estimates at creation and do not cancel the contract.
- A cancellation conflicting with existing agreed endorsements on or after its
  effective date is rejected. A subsequent agreed backdated change that would
  alter a stored cancellation refund is also rejected, rather than silently
  rewriting that refund.
- GET `/api/contracts/` currently lists original slips. Returning current
  positions and exposing the position API are subsequent implementation steps.
