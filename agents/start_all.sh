#!/bin/sh
# Runs all three agents in one container, so they fit on a single (free) Render web service.
#   sh start_all.sh
# AgentReady listens on $PORT, the port Render routes to. The Tester and the Fixer only talk
# outbound through their Agentverse mailboxes, so they get fixed internal ports. Each agent is
# restarted on its own if it exits, so one crash doesn't take the other two down.

run() {
  while true; do
    python "$1"
    echo "$1 exited with code $?, restarting in 5s" >&2
    sleep 5
  done
}

export TESTER_PORT="${TESTER_PORT:-8002}" FIXER_PORT="${FIXER_PORT:-8003}"

run tester_agent/agent.py &
run fixer_agent/agent.py &
run agentready_agent/agent.py
