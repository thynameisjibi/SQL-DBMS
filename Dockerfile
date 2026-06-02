FROM python:3.9-slim

# Storage is backed by Python's built-in `dbm` module, so there are no native
# libraries to install — just Python and the pure-Python `lark` parser.

WORKDIR /app

# Install Python deps first so the layer caches across code edits.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source is mounted as a volume at runtime (see docker-compose.yml) so that
# edits made by Claude Code / Cursor on the host are reflected instantly,
# with no rebuild. The COPY here is only a fallback for `docker run` without a mount.
COPY . .

CMD ["python", "run.py"]
