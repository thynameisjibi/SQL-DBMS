# Thin wrappers so humans *and* AI agents (Claude Code / Cursor) can drive the
# containerized engine with one short command instead of long docker invocations.

.PHONY: build run shell test reset

# Build the image (only needed once, or after changing requirements.txt / Dockerfile).
build:
	docker compose build

# Start the interactive SQL REPL inside the container.
run:
	docker compose run --rm app python run.py

# Open a bash shell in the container (for poking around, running scripts, etc.).
shell:
	docker compose run --rm app bash

# Smoke-test: pipe a few statements through the engine to confirm it still runs.
# (Note: test/*.sql contain `--` / `/* */` comments the grammar doesn't accept,
# so they can't be piped in raw — feed clean statements ending in `exit;`.)
test:
	printf "create table t ( id int not null, name char(15), primary key(id) );\ninsert into t values(1, 'alice');\ninsert into t values(2, 'bob');\nselect * from t;\nexit;\n" | docker compose run --rm -T app python run.py

# Wipe the database volume to start from a clean slate.
reset:
	docker compose down -v
