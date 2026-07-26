# StockFlow

StockFlow is a full-stack inventory and order-fulfilment system built to demonstrate
the backend problems that appear in real commerce systems: concurrent stock updates,
temporary reservations, idempotent order creation, payment outcomes, and an auditable
inventory ledger.

## Why this project is more than CRUD

- PostgreSQL row locks prevent two customers from reserving the same final unit.
- Every order request requires an idempotency key, preventing duplicate orders on retry.
- Stock moves through `available` and `reserved` quantities instead of being blindly deducted.
- Failed, cancelled, and expired orders release their reservations.
- Only paid orders can be fulfilled.
- Every stock change creates an immutable ledger record.
- JWT authentication and role checks separate customer and administrator operations.

## Stack

- FastAPI and Pydantic
- PostgreSQL 17
- SQLAlchemy 2 and Alembic
- JWT authentication with Argon2 password hashing
- Docker Compose
- HTML, CSS, and vanilla JavaScript dashboard
- Pytest, Ruff, and GitHub Actions

## Order lifecycle

```text
Customer reserves stock
        |
        v
    RESERVED ---- payment fails/cancel/expiry ----> stock released
        |
   payment succeeds
        v
      PAID ---- administrator fulfils ----> FULFILLED
```

## Run locally

Requirements: Docker Desktop with its Linux engine running.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Then open:

- Storefront and dashboard: http://localhost:8000
- Interactive API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The development administrator is configured through `.env`. Never commit `.env` or
reuse its password in a deployed environment.

Stop the project with:

```powershell
docker compose down
```

Use `docker compose down -v` only when you intentionally want to delete the local
database volume and all StockFlow data.

## Demonstration flow

1. Sign in as the bootstrap administrator.
2. Create a product and warehouse, then add inventory.
3. Register or sign in as a customer.
4. Add the product to the cart and reserve the order.
5. Simulate a successful payment.
6. Sign back in as administrator and fulfil the paid order.
7. Inspect inventory and the ledger to see each transition.

Repeat with a failed payment to verify that reserved stock returns to available stock.

## API overview

| Area | Capabilities |
| --- | --- |
| Authentication | Register, login, current user |
| Catalog | Products and warehouse availability |
| Customer orders | Reserve, list, inspect, pay, cancel |
| Administration | Products, warehouses, stock adjustment, inventory, ledger |
| Fulfilment | List all orders and fulfil paid orders |

The complete request and response schemas are always available through Swagger at
`/docs`.

## Important invariants

For every inventory record:

```text
available_quantity >= 0
reserved_quantity >= 0
```

Reservation and release operations lock inventory rows inside database transactions.
Locks are acquired in deterministic order for multi-line orders, reducing deadlock risk.

## Development checks

Create a Python 3.12 virtual environment, then run:

```powershell
pip install -e ".[dev]"
ruff check .
pytest
```

GitHub Actions runs linting and unit tests for each push and pull request.

## Production considerations

This repository is deliberately deployable-shaped but uses a simulated payment endpoint.
Before real production use, add a payment provider with signed webhooks, a background job
for expiring reservations, rate limiting, managed secrets, HTTPS, monitoring, and database
backups.
