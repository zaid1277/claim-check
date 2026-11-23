# PostgreSQL without Docker

PostgreSQL 17 can run locally without changing the application's database layer.
For macOS, install the command-line tools with `brew install postgresql@17`.
The following disposable test cluster uses a private Unix socket and no TCP listener.
Run from the repository root after installing the API dependencies:

```sh
CC_PG_BIN="$(brew --prefix postgresql@17)/bin"
CC_PG_DIR="$(mktemp -d /tmp/claim-check-pg.XXXXXX)"
"$CC_PG_BIN/initdb" -D "$CC_PG_DIR/data" -U claim_check --auth-local=trust --auth-host=scram-sha-256 --encoding=UTF8 --locale=C
"$CC_PG_BIN/pg_ctl" -D "$CC_PG_DIR/data" -l "$CC_PG_DIR/server.log" -o "-h '' -k $CC_PG_DIR -p 55439" -w start
"$CC_PG_BIN/createdb" -h "$CC_PG_DIR" -p 55439 -U claim_check claim_check_test
export TEST_DATABASE_URL="postgresql://claim_check@localhost/claim_check_test?host=$CC_PG_DIR&port=55439"
api/.venv/bin/python -m pytest api/tests -q
"$CC_PG_BIN/pg_ctl" -D "$CC_PG_DIR/data" -m fast -w stop
unset TEST_DATABASE_URL
```

The URL's host query directs libpq to the Unix socket; the localhost authority keeps
it valid for Pydantic's PostgreSQL URL validation. The temporary directory is private
to the operating-system user. Trust authentication here is restricted to that socket,
not a public deployment recommendation. No login service is enabled.

The integration test creates a random schema, applies migrations twice, exercises
report storage/sharing, and removes its schema. Use a disposable database regardless.
The final verification also restarted PostgreSQL and retrieved a fixture report
from a new API process. Container builds and deployed database configuration remain
separate checks. Use deployment.md for the full Compose stack.
