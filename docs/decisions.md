# Architecture decisions

## PostgreSQL and SQLAlchemy

PostgreSQL gives the project real foreign keys, typed statuses, JSON audit details, and a path to reporting queries. SQLAlchemy 2 mappings keep persistence code typed; Alembic owns the schema history.

## JWT roles

Short-lived signed access tokens support a stateless API. A longer-lived refresh token can obtain a new access token. Every protected operation reloads the user and checks the current database role. Public registration creates viewer accounts only; local demo accounts are seeded from Compose environment values.

## Human approval boundary

The placement service calculates a proposal but does not create servers. Approving the proposal locks the request and racks, verifies capacity again, then writes server rows and occupancy changes in one database transaction. Rejection records the decision and leaves inventory unchanged.

## Greedy best-fit placement

The algorithm selects a single rack with the least excess capacity when possible. If the request is larger than every rack, it consumes the largest remaining racks until the quantity is met. It sorts candidate racks once, then uses binary search for a single-rack fit or walks a descending list for a split. It uses O(r log r) time and O(r) space for r candidate racks. Ties choose the lower rack ID for repeatable proposals. When total available capacity is too small, it returns no placement.

## Trade-offs

The first version uses a simple greedy placement policy; it does not model power, network locality, hardware class, or failure domains. Local demo credentials and the Compose signing key are development-only and must be replaced for deployment. Refresh tokens are signed but not stored or revoked server-side in this portfolio version.
