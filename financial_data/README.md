# Financial Data Market Dashboard

<img width="1461" height="1196" alt="Screenshot1" src="https://github.com/user-attachments/assets/423a6203-7f36-4740-814d-b748b5a58a25" />


A local **FastAPI + PostgreSQL/TimescaleDB** project for working with time-series market data.

The project is designed as a practical database/API troubleshooting lab covering:

* FastAPI
* PostgreSQL
* TimescaleDB
* Connection pooling
* SQL queries
* Time-series data
* API health checks
* Database connectivity
* Query performance troubleshooting

---

## Architecture

```text
Frontend
   |
   | HTTP
   v
FastAPI
localhost:8000
   |
   | psycopg connection pool
   v
PostgreSQL / TimescaleDB
localhost:5433
   |
   v
financial_data
```

---

## Tech Stack

| Component             | Technology        |
| --------------------- | ----------------- |
| Backend               | FastAPI           |
| API Server            | Uvicorn           |
| Database              | PostgreSQL        |
| Time-series extension | TimescaleDB       |
| PostgreSQL driver     | psycopg           |
| Configuration         | python-dotenv     |
| API documentation     | Swagger / OpenAPI |

---

## Project Structure

```text
financial_data/
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── settings.py
│   │
│   ├── routes/
│   │   ├── health.py
│   │   └── market.py
│   │
│   └── services/
│
├── database/
│   └── setup.sql
│
├── .env.example
├── .gitignore
└── README.md
```

---

# 1. Prerequisites

Install the following:

* Python 3.11+
* PostgreSQL
* TimescaleDB
* Git

For this project, PostgreSQL is exposed locally on:

```text
localhost:5433
```

The API runs on:

```text
localhost:8000
```

---

# 2. Database Configuration

The application expects the following environment variables:

```env
DB_HOST=localhost
DB_PORT=5433
DB_NAME=financial_data
DB_USER=postgres
DB_PASSWORD=your_password_here

DB_POOL_MIN_CONN=1
DB_POOL_MAX_CONN=10

DB_CONNECT_TIMEOUT=5
DB_STATEMENT_TIMEOUT_MS=15000

API_HOST=0.0.0.0
API_PORT=8000

CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500,http://localhost:5173

LOG_LEVEL=INFO
```

Copy `.env.example` to `.env` and update the database password.

**Do not commit `.env` to GitHub.**

---

# 3. Create the Database

If the database does not already exist, connect to PostgreSQL and run:

```sql
CREATE DATABASE financial_data;
```

Then connect to the database:

```bash
psql -h localhost -p 5433 -U postgres -d financial_data
```

Run the setup script:

```bash
psql -h localhost -p 5433 -U postgres -d financial_data -f database/setup.sql
```

Or open:

```text
database/setup.sql
```

in DBeaver and execute it while connected to `financial_data`.

---

# 4. Verify TimescaleDB

Run:

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'timescaledb';
```

You should see the TimescaleDB extension.

Verify the hypertable:

```sql
SELECT *
FROM timescaledb_information.hypertables;
```

You should see:

```text
crypto_ticks
```

---

# 5. Verify the Data

Run:

```sql
SELECT *
FROM crypto_ticks
ORDER BY time DESC, volume DESC NULLS LAST;
```

The query sorts:

1. Newest `time` first
2. Highest `volume` first for identical timestamps
3. NULL volumes last

---

# 6. Python Environment

Go to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install fastapi uvicorn psycopg[binary] python-dotenv
```

---

# 7. Start the API

From the `backend` directory:

```bash
python -m uvicorn main:app --reload
```

Expected output:

```text
Uvicorn running on http://127.0.0.1:8000
```

---

# 8. Test the API

Open:

```text
http://127.0.0.1:8000
```

Health endpoint:

```text
http://127.0.0.1:8000/health
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

---

# 9. Database Connection Test

The project includes a database connectivity endpoint.

Open:

```text
http://127.0.0.1:8000/db-test
```

A successful response should confirm that the API can connect to PostgreSQL.

---

# 10. Troubleshooting

## API does not start

Check that you are running Uvicorn from the directory containing `main.py`:

```bash
cd backend
python -m uvicorn main:app --reload
```

---

## Connection refused on port 5433

Check whether PostgreSQL/TimescaleDB is running.

If using Docker:

```bash
docker ps
```

You should see the TimescaleDB container with a port mapping similar to:

```text
0.0.0.0:5433->5432/tcp
```

---

## Database does not exist

Create it:

```sql
CREATE DATABASE financial_data;
```

---

## Password authentication failed

Check the values in `.env`:

```env
DB_HOST=localhost
DB_PORT=5433
DB_NAME=financial_data
DB_USER=postgres
DB_PASSWORD=your_password
```

---

## TimescaleDB extension does not exist

Check:

```sql
SELECT *
FROM pg_available_extensions
WHERE name = 'timescaledb';
```

If it is not available, the PostgreSQL instance is not using a TimescaleDB-enabled installation.

---

# 11. Useful PostgreSQL Troubleshooting Queries

Check active connections:

```sql
SELECT
    pid,
    usename,
    datname,
    state,
    wait_event_type,
    wait_event,
    query
FROM pg_stat_activity;
```

Check locks:

```sql
SELECT *
FROM pg_locks;
```

Check table size:

```sql
SELECT
    relname,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

Check indexes:

```sql
SELECT
    schemaname,
    relname,
    indexrelname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```

---

# 12. Query Performance

Use `EXPLAIN ANALYZE` when investigating query performance:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT *
FROM crypto_ticks
WHERE symbol = 'BTC/USD'
ORDER BY time DESC;
```

This allows investigation of:

* Sequential scans
* Index scans
* Sort operations
* Execution time
* Buffer hits
* Buffer reads
* Query plans

---

# 13. Project Purpose

This project is also used as a PostgreSQL/TimescaleDB troubleshooting lab.

Areas that can be investigated include:

```text
API
 |
 +-- Connection failures
 +-- Connection pool exhaustion
 +-- Timeouts
 +-- Slow requests
 |
Database
 |
 +-- Locks
 +-- Long-running queries
 +-- Indexes
 +-- Query plans
 +-- Buffer usage
 +-- Autovacuum
 +-- WAL
 +-- TimescaleDB chunks
 +-- Hypertables
```

The goal is to understand the complete path:

```text
Application
    ↓
Connection Pool
    ↓
PostgreSQL
    ↓
TimescaleDB
    ↓
Storage
```

rather than treating database problems as isolated SQL errors.
