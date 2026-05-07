# Coverage Report

Generated: 2026-05-07T04:39:48.778337+00:00

- Total unique commands analyzed: **10286**
- Total command invocations: **13779**
- Hit rate (full match): **21.8%** (2246 / 10286)
- Partial rate: **62.7%** (6450 / 10286)
- Miss rate: **15.5%** (1590 / 10286)
- JSONL lines scanned: **140578**
- Malformed JSONL lines skipped: **0**

## Top 50 missed commands by frequency

| # | Freq | Command | Parsed path | Flags |
|---|------|---------|-------------|-------|
| 1 | 36 | `claude-swarm --db .claude-swarm/bus.db orchestrate dashboard` | `(none)` | `--db` |
| 2 | 34 | `claude-swarm --db .claude-swarm/bus.db sync --session R1 2>&1` | `(none)` | `--db --session` |
| 3 | 31 | `claude-swarm --db .claude-swarm/bus.db sync --session B` | `(none)` | `--db --session` |
| 4 | 25 | `/Users/laurenalexander/intracept/scripts/pilot_infra.sh up 2>&1` | `(none)` | `—` |
| 5 | 24 | `claude-swarm --db .claude-swarm/bus.db sync --session C` | `(none)` | `--db --session` |
| 6 | 20 | `claude-swarm --db .claude-swarm/bus.db sync --session E 2>&1` | `(none)` | `--db --session` |
| 7 | 19 | `claude-swarm --db .claude-swarm/bus.db context show 2>&1` | `(none)` | `--db` |
| 8 | 19 | `claude-swarm --db .claude-swarm/bus.db sync --session A` | `(none)` | `--db --session` |
| 9 | 18 | `claude-swarm --db .claude-swarm/bus.db sync --session D 2>&1` | `(none)` | `--db --session` |
| 10 | 17 | `claude-swarm --db .claude-swarm/bus.db context show` | `(none)` | `--db` |
| 11 | 17 | `claude-swarm --db .claude-swarm/bus.db sync --session C 2>&1` | `(none)` | `--db --session` |
| 12 | 14 | `claude-swarm --db .claude-swarm/bus.db sync --session A 2>&1` | `(none)` | `--db --session` |
| 13 | 13 | `claude-swarm --db .claude-swarm/bus.db orchestrate dashboard 2>&1` | `(none)` | `--db` |
| 14 | 13 | `claude-swarm --db .claude-swarm/bus.db sync --session S8` | `(none)` | `--db --session` |
| 15 | 12 | `claude-swarm --db .claude-swarm/bus.db sync --session D` | `(none)` | `--db --session` |
| 16 | 11 | `claude-swarm --db .claude-swarm/bus.db sync --session F 2>&1` | `(none)` | `--db --session` |
| 17 | 10 | `claude-swarm --db .claude-swarm/bus.db orchestrate run --interval 10 --auto-approve` | `(none)` | `--auto-approve --db --interval` |
| 18 | 10 | `claude-swarm --db .claude-swarm/bus.db pull --session A` | `(none)` | `--db --session` |
| 19 | 10 | `claude-swarm --db .claude-swarm/bus.db pull --session C` | `(none)` | `--db --session` |
| 20 | 9 | `claude-swarm --db .claude-swarm/bus.db sync --session G` | `(none)` | `--db --session` |
| 21 | 9 | `claude-swarm --db .claude-swarm/bus.db sync --session G 2>&1` | `(none)` | `--db --session` |
| 22 | 8 | `claude-swarm --db .claude-swarm/bus.db status` | `(none)` | `--db` |
| 23 | 8 | `claude-swarm --db .claude-swarm/bus.db sync --session B 2>&1` | `(none)` | `--db --session` |
| 24 | 8 | `claude-swarm --db .claude-swarm/bus.db sync --session C && claude-swarm --db .claude-swarm/bus.db inbox --session C` | `(none)` | `--db --db --session --session` |
| 25 | 8 | `claude-swarm --db .claude-swarm/bus.db sync --session E` | `(none)` | `--db --session` |
| 26 | 7 | `claude-swarm --db .claude-swarm/bus.db pull --session B` | `(none)` | `--db --session` |
| 27 | 7 | `claude-swarm --db .claude-swarm/bus.db sync --session orchestrator` | `(none)` | `--db --session` |
| 28 | 6 | `./target/debug/intracept stop 2>&1; sleep 1; ./target/release/intracept start &>/tmp/intracept-daemon.log & sleep 1; ./target/debug/intra...` | `(none)` | `—` |
| 29 | 5 | `claude-swarm --db .claude-swarm/bus.db claim src/lib/api.ts --session E 2>&1` | `(none)` | `--db --session` |
| 30 | 5 | `claude-swarm --db .claude-swarm/bus.db orchestrate run --interval 10` | `(none)` | `--db --interval` |
| 31 | 5 | `claude-swarm --db .claude-swarm/bus.db push --session B` | `(none)` | `--db --session` |
| 32 | 4 | `./target/release/intracept stop 2>&1 && ./target/release/intracept start 2>&1 &` | `(none)` | `—` |
| 33 | 4 | `claude-swarm --db .claude-swarm/bus.db pull --session D` | `(none)` | `--db --session` |
| 34 | 4 | `claude-swarm --db .claude-swarm/bus.db pull --session D 2>&1` | `(none)` | `--db --session` |
| 35 | 4 | `claude-swarm --db .claude-swarm/bus.db push --session A` | `(none)` | `--db --session` |
| 36 | 4 | `claude-swarm --db .claude-swarm/bus.db review request --from B --to orchestrator --diff "$(git diff main~1)"` | `(none)` | `--db --diff --from --to` |
| 37 | 4 | `claude-swarm --db .claude-swarm/bus.db review request --from C --to orchestrator --diff "$(git diff main~1)"` | `(none)` | `--db --diff --from --to` |
| 38 | 4 | `claude-swarm --db .claude-swarm/bus.db sync --session S4` | `(none)` | `--db --session` |
| 39 | 4 | `claude-swarm --db .claude-swarm/bus.db sync --session orchestrator 2>&1` | `(none)` | `--db --session` |
| 40 | 3 | `# Check per-region GPU quotas for regions that have A100-80GB for region in us-central1 us-east4 us-east5 europe-west4 asia-southeast1; d...` | `(none)` | `--format --project -c` |
| 41 | 3 | `# Try A100 zones for judge — sequential, first success wins for zone in us-central1-a us-central1-c us-east4-c us-east5-b us-east5-a euro...` | `(none)` | `--accelerator --boot-disk-size --boot-disk-type --image-family --image-project --instance-termination-action --machine-type --maintenance-policy --metadata --no-restart-on-failure --project --provisioning-model --scopes --tags --zone` |
| 42 | 3 | `./engine/run.sh report 2>&1` | `(none)` | `—` |
| 43 | 3 | `SOURCE_IP=$(gcloud compute instances describe intracept-pilot-source --project=intracept --zone=us-central1-b --format="value(networkInte...` | `(none)` | `--format --project --zone -sf` |
| 44 | 3 | `STAGING_DIR=/var/folders/80/r5sjnfh14mqct2dj6vtqlmdm0000gn/T/tmp.YtnyaacjGp && gcloud builds submit "$STAGING_DIR" --project=intracept --...` | `(none)` | `--config --project --substitutions --timeout` |
| 45 | 3 | `claude-swarm --db .claude-swarm/bus.db claim infra/cloud-run/README.md --session D` | `(none)` | `--db --session` |
| 46 | 3 | `claude-swarm --db .claude-swarm/bus.db claim src/hooks/useWebSocket.ts --session E 2>&1` | `(none)` | `--db --session` |
| 47 | 3 | `claude-swarm --db .claude-swarm/bus.db merge-ok B 2>&1` | `(none)` | `--db` |
| 48 | 3 | `claude-swarm --db .claude-swarm/bus.db message --help 2>&1` | `(none)` | `--db --help` |
| 49 | 3 | `claude-swarm --db .claude-swarm/bus.db orchestrate dashboard 2>&1 \| head -10` | `(none)` | `--db -10` |
| 50 | 3 | `claude-swarm --db .claude-swarm/bus.db orchestrate dashboard 2>&1 \| head -40` | `(none)` | `--db -40` |

## Top 50 partial-match commands by frequency

| # | Freq | Command | Matched path | Missing flags |
|---|------|---------|--------------|---------------|
| 1 | 120 | `export CLAUDE_SWARM_DB="/Users/laurenalexander/intracept/.claude-swarm/bus.db" && sleep 15 && claude-swarm --db "$CLAUDE_SWARM_DB" sync -...` | `export` | `--db --session -E` |
| 2 | 50 | `export CLAUDE_SWARM_DB="/Users/laurenalexander/intracept/.claude-swarm/bus.db" && sleep 15 && claude-swarm --db "$CLAUDE_SWARM_DB" sync -...` | `export` | `--db --session -E` |
| 3 | 43 | `git log --oneline -5` | `git log` | `-5` |
| 4 | 38 | `sleep 30 && export CLAUDE_SWARM_DB="/Users/laurenalexander/intracept/.claude-swarm/bus.db" && claude-swarm --db $CLAUDE_SWARM_DB sync --s...` | `sleep` | `--db --session` |
| 5 | 33 | `export CLAUDE_SWARM_DB="/Users/laurenalexander/intracept/.claude-swarm/bus.db" && sleep 30 && claude-swarm --db "$CLAUDE_SWARM_DB" sync -...` | `export` | `--db --session -E` |
| 6 | 32 | `export CLAUDE_SWARM_DB="/Users/laurenalexander/intracept/.claude-swarm/bus.db" && sleep 60 && claude-swarm --db "$CLAUDE_SWARM_DB" sync -...` | `export` | `--db --session -E` |
| 7 | 30 | `cargo build --release -p intracept-hook 2>&1 \| tail -2 && cp /Users/laurenalexander/intracept/target/release/intracept-hook /Users/laure...` | `cargo build` | `-2 -p` |
| 8 | 28 | `touch crates/hook/src/main.rs && cargo build --release --package intracept-hook 2>&1 \| tail -3` | `touch` | `--package --release -3` |
| 9 | 25 | `ls -la /Users/laurenalexander/Developer/Gate/docs/web/` | `ls` | `-la` |
| 10 | 24 | `npx tsc --noEmit 2>&1` | `npx` | `--noEmit` |
| 11 | 23 | `sleep 30 && export CLAUDE_SWARM_DB="/Users/laurenalexander/intracept/.claude-swarm/bus.db" && claude-swarm --db $CLAUDE_SWARM_DB sync --s...` | `sleep` | `--db --session` |
| 12 | 21 | `git log --oneline -10` | `git log` | `-10` |
| 13 | 21 | `ls -la /Users/laurenalexander/Developer/Gate/rust/` | `ls` | `-la` |
| 14 | 21 | `python3 -m pytest tests/ -q 2>&1 \| tail -5` | `python3` | `-5` |
| 15 | 19 | `ls -la /Users/laurenalexander/Developer/Gate/docs/` | `ls` | `-la` |
| 16 | 18 | `git log --oneline -20` | `git log` | `-20` |
| 17 | 18 | `ls -la /Users/laurenalexander/intracept/` | `ls` | `-la` |
| 18 | 17 | `git status --short` | `git status` | `--short` |
| 19 | 16 | `git log --oneline -3` | `git log` | `-3` |
| 20 | 15 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-core/src/` | `ls` | `-la` |
| 21 | 15 | `python3 -m pytest tests/ -q 2>&1 \| tail -10` | `python3` | `-10` |
| 22 | 14 | `ls -la /Users/laurenalexander/Developer/Gate/` | `ls` | `-la` |
| 23 | 13 | `ls -la /Users/laurenalexander/intracept/crates/` | `ls` | `-la` |
| 24 | 12 | `cargo test 2>&1 \| tail -20` | `cargo test` | `-20` |
| 25 | 12 | `echo -n "<redacted-secret>" \| gcloud secrets create ANTHROPIC_API_KEY --data-file=- --project=intracept 2>&1` | `echo` | `--data-file --project` |
| 26 | 12 | `git log --oneline -5 2>&1 && echo "---" && claude-swarm --db .claude-swarm/bus.db sync --session R1 2>&1` | `git log` | `--- --db --session -5` |
| 27 | 12 | `ls -la /Users/laurenalexander/Developer/Gate` | `ls` | `-la` |
| 28 | 12 | `ls -la /Users/laurenalexander/Developer/Gate/sdk/` | `ls` | `-la` |
| 29 | 12 | `ls -la /Users/laurenalexander/intracept/docs/` | `ls` | `-la` |
| 30 | 12 | `node docs/web/tests/index.test.js 2>&1 \| tail -5` | `node` | `-5` |
| 31 | 12 | `npx tsc -p ./ 2>&1` | `npx` | `-p` |
| 32 | 11 | `cargo build --release -p intracept -p intracept-hook 2>&1 \| tail -3` | `cargo build` | `-3 -p -p` |
| 33 | 11 | `cargo check -p intracept 2>&1` | `cargo check` | `-p` |
| 34 | 11 | `git stash 2>&1 && claude-swarm --db .claude-swarm/bus.db pull --session R1 2>&1` | `git stash` | `--db --session` |
| 35 | 11 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-core/src/db/repositories/` | `ls` | `-la` |
| 36 | 11 | `python3 -m pytest tests/ -q 2>&1 \| tail -20` | `python3` | `-20` |
| 37 | 10 | `cargo test 2>&1 \| tail -30` | `cargo test` | `-30` |
| 38 | 10 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-core/src/rules/` | `ls` | `-la` |
| 39 | 10 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-core/src/types/` | `ls` | `-la` |
| 40 | 10 | `ls -la /Users/laurenalexander/Developer/Gate/sdk/python/` | `ls` | `-la` |
| 41 | 10 | `npx next build 2>&1 \| tail -20` | `npx` | `-20` |
| 42 | 10 | `python3 -m pytest tests/ -q 2>&1 \| tail -3` | `python3` | `-3` |
| 43 | 9 | `cd /Users/laurenalexander/intracept/engine && python -m pytest tests/ -q 2>&1 \| tail -20` | `cd` | `-20 -m -q` |
| 44 | 9 | `export CLAUDE_SWARM_DB="/Users/laurenalexander/intracept/.claude-swarm/bus.db" && claude-swarm --db "$CLAUDE_SWARM_DB" sync --session Y2 ...` | `export` | `--db --session -E` |
| 45 | 9 | `gcloud compute ssh intracept --project=intracept --zone=northamerica-northeast1-c --command="cd ~/intracept && git pull && sudo docker co...` | `gcloud compute` | `--command --project --zone` |
| 46 | 9 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-proxy/src/handlers/` | `ls` | `-la` |
| 47 | 9 | `npm run build 2>&1 \| tail -5` | `npm run` | `-5` |
| 48 | 9 | `npx next build 2>&1 \| tail -15` | `npx` | `-15` |
| 49 | 9 | `python3 -m pytest tests/ -q 2>&1 \| tail -15` | `python3` | `-15` |
| 50 | 8 | `cargo build --release -p intracept-hook 2>&1` | `cargo build` | `-p` |

## Tools by frequency (top 50)

| Tool | Invocations |
|------|-------------|
| `claude-swarm` | 1665 |
| `ls` | 1615 |
| `git` | 1382 |
| `find` | 1251 |
| `python3` | 769 |
| `export` | 727 |
| `grep` | 670 |
| `cat` | 586 |
| `cargo` | 506 |
| `gcloud` | 455 |
| `cd` | 450 |
| `man` | 426 |
| `sleep` | 422 |
| `wc` | 183 |
| `curl` | 174 |
| `for` | 162 |
| `head` | 143 |
| `npm` | 133 |
| `rm` | 126 |
| `echo` | 111 |
| `sed` | 110 |
| `gh` | 105 |
| `node` | 105 |
| `#` | 102 |
| `open` | 102 |
| `which` | 88 |
| `tail` | 84 |
| `mkdir` | 82 |
| `npx` | 81 |
| `pkill` | 63 |
| `ps` | 61 |
| `cp` | 52 |
| `sqlite3` | 50 |
| `lsof` | 40 |
| `jq` | 36 |
| `kill` | 33 |
| `TOKEN=$(gcloud` | 32 |
| `touch` | 31 |
| `bash` | 30 |
| `/Users/laurenalexander/intracept/scripts/pilot_infra.sh` | 25 |
| `source` | 24 |
| `pwd` | 23 |
| `pip3` | 17 |
| `tree` | 17 |
| `chmod` | 16 |
| `du` | 15 |
| `python` | 14 |
| `brew` | 13 |
| `docker` | 13 |
| `pgrep` | 11 |
