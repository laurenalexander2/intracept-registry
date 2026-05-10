## Claude Swarm

This project uses [claude-swarm](https://github.com/laurenalexander2/agent-orchestrator) to coordinate parallel Claude Code sessions.

### Database

All coordination state is stored in `.claude-swarm/bus.db`. Every command below uses `--db` to point at it.

```
export CLAUDE_SWARM_DB=".claude-swarm/bus.db"
```

### Commands

**Sync (do this between every task — checks inbox, reads new context, sends heartbeat):**
```
claude-swarm --db .claude-swarm/bus.db sync --session {YOUR_SESSION_ID}
```

**Add shared context (share decisions, interfaces, warnings with all sessions):**
```
claude-swarm --db .claude-swarm/bus.db context add "description" --session {YOUR_SESSION_ID} --category decision
```
Categories: decision, interface, warning, convention, discovery

**View all shared context:**
```
claude-swarm --db .claude-swarm/bus.db context show
```

**Report what you're working on:**
```
claude-swarm --db .claude-swarm/bus.db update {YOUR_SESSION_ID} --status running --note "what you're doing"
```

**Report blocked:**
```
claude-swarm --db .claude-swarm/bus.db update {YOUR_SESSION_ID} --status blocked --note "why you're blocked"
```

**Message another session:**
```
claude-swarm --db .claude-swarm/bus.db message {TARGET_SESSION} "your question" --from {YOUR_SESSION_ID}
```

**Message the orchestrator:**
```
claude-swarm --db .claude-swarm/bus.db message orchestrator "your question" --from {YOUR_SESSION_ID}
```

**Claim a file before editing it:**
```
claude-swarm --db .claude-swarm/bus.db claim path/to/file --session {YOUR_SESSION_ID}
```

**Release a file claim:**
```
claude-swarm --db .claude-swarm/bus.db unclaim path/to/file --session {YOUR_SESSION_ID}
```

**Request a review:**
```
claude-swarm --db .claude-swarm/bus.db review request --from {YOUR_SESSION_ID} --to orchestrator --diff "$(git diff main)"
```

**Check if you're clear to merge:**
```
claude-swarm --db .claude-swarm/bus.db merge-ok {YOUR_SESSION_ID}
```

**Commit (auto-prefixes with session ID):**
```
claude-swarm --db .claude-swarm/bus.db commit "description" --session {YOUR_SESSION_ID}
```

**Push (acquires lock, rebases, pushes, releases):**
```
claude-swarm --db .claude-swarm/bus.db push --session {YOUR_SESSION_ID}
```

**Pull before starting work:**
```
claude-swarm --db .claude-swarm/bus.db pull --session {YOUR_SESSION_ID}
```

**Check orchestrator dashboard:**
```
claude-swarm --db .claude-swarm/bus.db orchestrate dashboard
```

### Workflow

1. Pull before starting
2. Sync between every task (replaces manual inbox check)
3. Share decisions and interfaces to shared context
4. Claim files before editing
5. Update status when starting, blocking, or completing
6. Commit often
7. Request review when ready
8. Wait for merge-ok before pushing
9. Push only via the CLI (never raw git push)
10. Never force push
