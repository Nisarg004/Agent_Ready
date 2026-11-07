# One image for all three agents. AGENT_SCRIPT picks which one a service runs;
# The default, start_all.sh, runs all three in one container (one free Render service).
FROM python:3.11-slim

# The Fixer clones repos and builds stores locally, so it needs git and Node.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV AGENT_MAILBOX=true PYTHONUNBUFFERED=1 AGENT_SCRIPT=start_all.sh
CMD ["sh", "-c", "case \"$AGENT_SCRIPT\" in *.sh) exec sh \"$AGENT_SCRIPT\" ;; *) exec python \"$AGENT_SCRIPT\" ;; esac"]
