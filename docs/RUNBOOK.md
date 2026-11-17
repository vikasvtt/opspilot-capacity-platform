# OpsPilot runbook

## Start and stop

From the repository root, run `docker compose up --build`. Visit the web app at <http://localhost:4200>, API docs at <http://localhost:8000/docs>, Prometheus at <http://localhost:9090>, and Grafana at <http://localhost:3000>. Stop the foreground stack with Control+C or run `docker compose down` in another terminal.

## Local demo accounts

- Approver: `approver@opspilot-demo.com` / `LocalDev123!`
- Engineer: `engineer@opspilot-demo.com` / `Engineer123!`
- New self-registered accounts have viewer access.
- Grafana: `admin` / `opspilot-local`

These credentials are for local development only.

## Common problems

- **Docker command not found:** start Docker Desktop, reopen Terminal, then retry.
- **Port is already in use:** stop the service already using 4200, 5432, 8000, 9090, or 3000, or change the corresponding Compose port mapping.
- **API exits during migration:** inspect `docker compose logs backend`; migration errors must be fixed before the API can start.
- **Database is not ready:** check `docker compose ps` and `docker compose logs db`; Compose waits for `pg_isready` before starting the API.
- **Login fails:** use the local demo credentials above. If Compose credentials changed after the database volume was initialized, the seeded row is not overwritten; remove the local database volume only if you are comfortable deleting its data.
- **Frontend shows API errors:** verify the backend health at <http://localhost:8000/health> and inspect `docker compose logs backend`.

## Security notes

Replace the local JWT secret, demo credentials, database password, and Grafana password before any shared deployment. Put secrets in a secret manager rather than committing them. Enable HTTPS and configure secure cookie or token storage for a deployed client.
