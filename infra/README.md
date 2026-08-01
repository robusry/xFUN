# infra/

Database migrations, scheduling, and deployment.

```
migrations/       schema migrations, applied in filename order
```

## Database

The skeleton runs on **SQLite**, stored at `.data/xfun.db`. This is a deliberate
choice for the walking skeleton: a collaborator can clone the repository and run the
end-to-end demo with no daemon, no container, and no credentials.

It is expected to be replaced by Postgres when real ingestion lands. The SQL dialect
differences are real — triggers and column types will need rewriting — which is why
all database access goes through SQLAlchemy and the migrations are kept small and
readable. See `docs/STUBS.md`.

## Migrations

Plain `.sql` files, applied in filename order by `scripts/migrate.py`. No migration
framework yet; at this size one would be more machinery than the problem deserves.

The append-only constraint on the score store is enforced here, by trigger, rather
than in application code — a rule the database refuses to break is worth more than a
rule the application politely observes.
