# Coverage Report

Generated: 2026-05-07T04:39:51.772023+00:00

- Total unique commands analyzed: **8259**
- Total command invocations: **10693**
- Hit rate (full match): **25.6%** (2116 / 8259)
- Partial rate: **69.9%** (5772 / 8259)
- Miss rate: **4.5%** (371 / 8259)
- JSONL lines scanned: **140578**
- Malformed JSONL lines skipped: **0**
- Excluded as custom internal tooling: **2027** unique / **3086** invocations

## Top 50 missed commands by frequency

| # | Freq | Command | Parsed path | Flags |
|---|------|---------|-------------|-------|
| 1 | 3 | `# Check per-region GPU quotas for regions that have A100-80GB for region in us-central1 us-east4 us-east5 europe-west4 asia-southeast1; d...` | `(none)` | `--format --project -c` |
| 2 | 3 | `# Try A100 zones for judge — sequential, first success wins for zone in us-central1-a us-central1-c us-east4-c us-east5-b us-east5-a euro...` | `(none)` | `--accelerator --boot-disk-size --boot-disk-type --image-family --image-project --instance-termination-action --machine-type --maintenance-policy --metadata --no-restart-on-failure --project --provisioning-model --scopes --tags --zone` |
| 3 | 3 | `SOURCE_IP=$(gcloud compute instances describe intracept-pilot-source --project=intracept --zone=us-central1-b --format="value(networkInte...` | `(none)` | `--format --project --zone -sf` |
| 4 | 3 | `STAGING_DIR=/var/folders/80/r5sjnfh14mqct2dj6vtqlmdm0000gn/T/tmp.YtnyaacjGp && gcloud builds submit "$STAGING_DIR" --project=intracept --...` | `(none)` | `--config --project --substitutions --timeout` |
| 5 | 3 | `for zone in us-central1-c us-east4-c us-east1-b us-east5-b europe-west4-a; do echo "=== $zone ==="; gcloud compute instances create test-...` | `(none)` | `--accelerator --dry-run --instance-termination-action --machine-type --maintenance-policy --project --provisioning-model --zone -5;` |
| 6 | 2 | `# Check if process is still alive and what it's doing ps aux \| grep intracept_engine \| grep -v grep \| awk '{print $2, $10, $11}' && ec...` | `(none)` | `-1 -I{} -c -i -p -v -v` |
| 7 | 2 | `# Check judge install status via IAP gcloud compute ssh intracept-pilot-judge --zone=us-central1-a --project=intracept --tunnel-through-i...` | `(none)` | `--command --project --tunnel-through-iap --zone` |
| 8 | 2 | `# Check stderr too - maybe errors are going there wc -l /private/tmp/claude-501/-Users-laurenalexander-intracept/c53850f3-79e7-45b3-97a5-...` | `(none)` | `-l` |
| 9 | 2 | `# Fix source: restart vllm with writable log path gcloud compute ssh intracept-pilot-source --zone=us-east4-a --project=intracept --comma...` | `(none)` | `--command --project --zone` |
| 10 | 2 | `# Install pip + vllm + start server on judge gcloud compute ssh intracept-pilot-judge --zone=us-central1-a --project=intracept --command=...` | `(none)` | `--command --project --zone` |
| 11 | 2 | `# Install pip + vllm + start server on source gcloud compute ssh intracept-pilot-source --zone=us-east4-a --project=intracept --command='...` | `(none)` | `--command --project --zone` |
| 12 | 2 | `# Judge gcloud compute ssh intracept-pilot-judge --zone=us-central1-a --project=intracept --tunnel-through-iap --command=' set -ex # Inst...` | `(none)` | `--command --project --tunnel-through-iap --zone` |
| 13 | 2 | `# Just install everything directly via SSH on the already-running instances # Source first gcloud compute ssh intracept-pilot-source --zo...` | `(none)` | `--command --project --tunnel-through-iap --zone` |
| 14 | 2 | `# Quick test: can we reach the source vLLM? curl -sf "http://34.122.184.137:8000/health" && echo "vLLM OK" \|\| echo "vLLM DOWN" # Quick ...` | `(none)` | `-c -sf` |
| 15 | 2 | `# Restart vLLM on source via IAP gcloud compute ssh intracept-pilot-source --zone=us-east4-a --project=intracept --tunnel-through-iap --c...` | `(none)` | `--command --project --tunnel-through-iap --zone` |
| 16 | 2 | `# Stop the OOM loop on judge and delete it gcloud compute ssh intracept-pilot-judge --zone=us-central1-a --project=intracept --tunnel-thr...` | `(none)` | `--command --project --project --quiet --tunnel-through-iap --zone --zone` |
| 17 | 2 | `# Tear down both gcloud compute instances delete intracept-pilot-source --project=intracept --zone=us-east1-b --quiet 2>&1 & gcloud compu...` | `(none)` | `--project --project --quiet --quiet --zone --zone` |
| 18 | 2 | `# Try with IAP tunnel gcloud compute ssh intracept-pilot-source --zone=us-east4-a --project=intracept --tunnel-through-iap --command='ech...` | `(none)` | `--command --project --tunnel-through-iap --zone` |
| 19 | 2 | `# Use serial port output to check source — no SSH needed gcloud compute instances get-serial-port-output intracept-pilot-source --zone=us...` | `(none)` | `--project --zone -20 -i` |
| 20 | 2 | `# Wait for vLLM health for i in $(seq 1 40); do     sleep 15     if curl -sf "http://35.245.243.13:8000/health" > /dev/null 2>&1; then   ...` | `(none)` | `-sf` |
| 21 | 2 | `INTRACEPT_ML_MODEL_DIR=/Users/laurenalexander/intracept/spikes/spike_a/onnx/cross_encoder cargo test --package intracept-ml-server 2>&1` | `(none)` | `--package` |
| 22 | 2 | `SOURCE_IP=$(gcloud compute instances describe intracept-pilot-source --project=intracept --zone=us-east4-a --format="value(networkInterfa...` | `(none)` | `--format --format --project --project --zone --zone -sf -sf` |
| 23 | 2 | `STAGING_DIR=/var/folders/80/r5sjnfh14mqct2dj6vtqlmdm0000gn/T/tmp.YtnyaacjGp && cp /Users/laurenalexander/intracept/infra/cloud-run/Docker...` | `(none)` | `—` |
| 24 | 2 | `TOKEN=$(gcloud auth print-identity-token 2>/dev/null) && \ curl -s -X POST \   -H "Authorization: Bearer $TOKEN" \   -H "Content-Type: ap...` | `(none)` | `-H -H -X -d -s` |
| 25 | 2 | `TOKEN=$(gcloud auth print-identity-token) && curl -s -H "Authorization: Bearer $TOKEN" https://intracept-ml-server-gpu-236988891070.us-ea...` | `(none)` | `-H -s` |
| 26 | 2 | `TOKEN=$(gcloud auth print-identity-token) && curl -s -X POST \   -H "Content-Type: application/json" \   -H "Authorization: Bearer $TOKEN...` | `(none)` | `-H -H -X -d -s` |
| 27 | 2 | `TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 /Users/laurenalexander/intracept/spikes/spike_a/.venv/bin/python -m pytest test_model.py -v --tb=...` | `(none)` | `--tb -m -v` |
| 28 | 2 | `TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 /Users/laurenalexander/intracept/spikes/spike_a/.venv/bin/python benchmark.py --n-runs 30 2>&1` | `(none)` | `--n-runs` |
| 29 | 2 | `\   export GOOGLE_CLOUD_PROJECT=intracept && \   export PYTHONUNBUFFERED=1 && \   export VLLM_API_BASE_QWEN_25_7B="http://34.63.232.14:80...` | `(none)` | `--budget-usd --elites --project --secret --seeds --source --targets -m` |
| 30 | 2 | `for cmd in crontab at launchctl systemctl journalctl login logout shutdown reboot halt last w who finger id; do which $cmd 2>/dev/null &&...` | `(none)` | `—` |
| 31 | 2 | `for f in exemplars/*.toml; do echo ""; echo "════════════════════════════════════════════════════════════════"; echo "  $(basename $f)"; ...` | `(none)` | `-l` |
| 32 | 2 | `pid=$(pgrep -f "intracept_engine pilot" \| head -1) && echo "PID: $pid" && ps -p $pid -o stat,etime,pcpu 2>&1 && echo "---THREADS---" && ...` | `(none)` | `---CONNECTIONS--- ---THREADS--- -1) -10 -20 -M -a -f -i -o -p -p -p` |
| 33 | 2 | `some-totally-fake-command --flag` | `(none)` | `--flag` |
| 34 | 1 | ` # Calculate flag combinations for highest-flag commands # Formula: 2^N - 1 (all non-empty subsets)  calculate_combos() {   local flags=$...` | `(none)` | `-c` |
| 35 | 1 | ` # Count flags per command in docker.toml echo "=== DOCKER ==="  awk ' /^\[\[command\]\]/ { in_cmd=1; next } /^\[\[flag\]\]/ { in_flag=1;...` | `(none)` | `-15 -15 -15 -rn -rn -rn` |
| 36 | 1 | ` # Count flags per command in git.toml awk ' /^\[\[command\]\]/ { in_cmd=1; next } /^\[\[flag\]\]/ { in_flag=1; in_cmd=0; next } in_cmd &...` | `(none)` | `-20 -rn` |
| 37 | 1 | ` # Extract all flags for high-flag commands to identify patterns echo "=== MUTUALLY EXCLUSIVE FLAG PATTERNS ===" echo "" echo "GIT PUSH (...` | `(none)` | `-A1 -A1 -A1 -A1 -A1` |
| 38 | 1 | `# Add and commit all new toml files in one batch per file python3 << 'PYEOF' import json, os, tomllib, subprocess  partition = json.load(...` | `(none)` | `—` |
| 39 | 1 | `# Also need icon.ico — create a minimal one cp src-tauri/icons/32x32.png src-tauri/icons/icon.ico  # Tauri will handle conversion # Check...` | `(none)` | `-A` |
| 40 | 1 | `# Check a bigger batch for installation and minimal docs for t in apachectl apropos ar arch arp at atos base64 basename bash batch bc bg ...` | `(none)` | `-n` |
| 41 | 1 | `# Check current state of these entries grep -n "XS" tools/package-stash-conflicts.toml tools/package-stash-conflicts5.34.toml echo "---" ...` | `(none)` | `--- -n -n` |
| 42 | 1 | `# Check for any "the terminal" in translation fields that shouldn't be there grep -n "the terminal" tools/funzip.toml tools/sort.toml too...` | `(none)` | `-n` |
| 43 | 1 | `# Check i-j tools for tool in iconv id ifconfig indent install installer iostat iotop ipconfig ipcrm ipcs irb jobs join jot jpegtran json...` | `(none)` | `—` |
| 44 | 1 | `# Check remaining jargon in rationales grep -rn "symlink\b" tools/*.toml \| grep rationale echo "---" grep -rn "SIGKILL\\|SIGTERM" tools/...` | `(none)` | `--- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- -rn -rn -rn -rn -rn -rn -rn -rn -rn -rn -rn -rn -rn -rn -rn -rn -rn -rn` |
| 45 | 1 | `# Check remaining jargon items we may have missed grep -n "symlinks\\|symlink" tools/c_rehash.toml echo "---" grep -n "TSIG" tools/tsig-k...` | `(none)` | `--- --- --- --- -n -n -n -n -n` |
| 46 | 1 | `# Check remaining tools from the list that need install verification for tool in filebyproc.d filecoordinationd fileproviderctl filtercal...` | `(none)` | `—` |
| 47 | 1 | `# Check remaining tools: g++ through gzexe for tool in "g++" gacutil gcc gcore gcov gunzip gzcat gzexe groups halt hash hexdump hdiutil h...` | `(none)` | `—` |
| 48 | 1 | `# Check the preprocessed image sizes to see if there's a dimension mismatch python3 -c " import cv2 import os  base_dir = 'data/357a3238-...` | `(none)` | `-c` |
| 49 | 1 | `# Clean up the L4 instance — we'll use Together API for Llama-70B instead kill 63581 2>/dev/null  # kill SSH tunnel gcloud compute instan...` | `(none)` | `--project --quiet --zone` |
| 50 | 1 | `# Create .icns from the 512px PNG using macOS sips + iconutil mkdir -p /tmp/intracept.iconset for size in 16 32 128 256 512; do   sips -z...` | `(none)` | `--out --out -c -la -le -o -p -z -z` |

## Top 50 partial-match commands by frequency

| # | Freq | Command | Matched path | Missing flags |
|---|------|---------|--------------|---------------|
| 1 | 43 | `git log --oneline -5` | `git log` | `-5` |
| 2 | 28 | `touch crates/hook/src/main.rs && cargo build --release --package intracept-hook 2>&1 \| tail -3` | `touch` | `--package --release -3` |
| 3 | 25 | `ls -la /Users/laurenalexander/Developer/Gate/docs/web/` | `ls` | `-la` |
| 4 | 24 | `npx tsc --noEmit 2>&1` | `npx` | `--noEmit` |
| 5 | 21 | `git log --oneline -10` | `git log` | `-10` |
| 6 | 21 | `ls -la /Users/laurenalexander/Developer/Gate/rust/` | `ls` | `-la` |
| 7 | 21 | `python3 -m pytest tests/ -q 2>&1 \| tail -5` | `python3` | `-5` |
| 8 | 19 | `ls -la /Users/laurenalexander/Developer/Gate/docs/` | `ls` | `-la` |
| 9 | 18 | `git log --oneline -20` | `git log` | `-20` |
| 10 | 18 | `ls -la /Users/laurenalexander/intracept/` | `ls` | `-la` |
| 11 | 17 | `git status --short` | `git status` | `--short` |
| 12 | 16 | `git log --oneline -3` | `git log` | `-3` |
| 13 | 15 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-core/src/` | `ls` | `-la` |
| 14 | 15 | `python3 -m pytest tests/ -q 2>&1 \| tail -10` | `python3` | `-10` |
| 15 | 14 | `ls -la /Users/laurenalexander/Developer/Gate/` | `ls` | `-la` |
| 16 | 13 | `ls -la /Users/laurenalexander/intracept/crates/` | `ls` | `-la` |
| 17 | 12 | `cargo test 2>&1 \| tail -20` | `cargo test` | `-20` |
| 18 | 12 | `echo -n "<redacted-secret>" \| gcloud secrets create ANTHROPIC_API_KEY --data-file=- --project=intracept 2>&1` | `echo` | `--data-file --project` |
| 19 | 12 | `ls -la /Users/laurenalexander/Developer/Gate` | `ls` | `-la` |
| 20 | 12 | `ls -la /Users/laurenalexander/Developer/Gate/sdk/` | `ls` | `-la` |
| 21 | 12 | `ls -la /Users/laurenalexander/intracept/docs/` | `ls` | `-la` |
| 22 | 12 | `node docs/web/tests/index.test.js 2>&1 \| tail -5` | `node` | `-5` |
| 23 | 12 | `npx tsc -p ./ 2>&1` | `npx` | `-p` |
| 24 | 11 | `cargo build --release -p intracept -p intracept-hook 2>&1 \| tail -3` | `cargo build` | `-3 -p -p` |
| 25 | 11 | `cargo check -p intracept 2>&1` | `cargo check` | `-p` |
| 26 | 11 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-core/src/db/repositories/` | `ls` | `-la` |
| 27 | 11 | `python3 -m pytest tests/ -q 2>&1 \| tail -20` | `python3` | `-20` |
| 28 | 10 | `cargo test 2>&1 \| tail -30` | `cargo test` | `-30` |
| 29 | 10 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-core/src/rules/` | `ls` | `-la` |
| 30 | 10 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-core/src/types/` | `ls` | `-la` |
| 31 | 10 | `ls -la /Users/laurenalexander/Developer/Gate/sdk/python/` | `ls` | `-la` |
| 32 | 10 | `npx next build 2>&1 \| tail -20` | `npx` | `-20` |
| 33 | 10 | `python3 -m pytest tests/ -q 2>&1 \| tail -3` | `python3` | `-3` |
| 34 | 9 | `cd /Users/laurenalexander/intracept/engine && python -m pytest tests/ -q 2>&1 \| tail -20` | `cd` | `-20 -m -q` |
| 35 | 9 | `gcloud compute ssh intracept --project=intracept --zone=northamerica-northeast1-c --command="cd ~/intracept && git pull && sudo docker co...` | `gcloud compute` | `--command --project --zone` |
| 36 | 9 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-proxy/src/handlers/` | `ls` | `-la` |
| 37 | 9 | `npm run build 2>&1 \| tail -5` | `npm run` | `-5` |
| 38 | 9 | `npx next build 2>&1 \| tail -15` | `npx` | `-15` |
| 39 | 9 | `python3 -m pytest tests/ -q 2>&1 \| tail -15` | `python3` | `-15` |
| 40 | 8 | `cargo build --release -p intracept-hook 2>&1` | `cargo build` | `-p` |
| 41 | 8 | `cargo check 2>&1 \| tail -5` | `cargo check` | `-5` |
| 42 | 8 | `git log --oneline -15` | `git log` | `-15` |
| 43 | 8 | `ls -la` | `ls` | `-la` |
| 44 | 8 | `ls -la /Users/laurenalexander/Developer/Gate/GateApp/` | `ls` | `-la` |
| 45 | 8 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-api/src/` | `ls` | `-la` |
| 46 | 8 | `ls -la /Users/laurenalexander/Developer/Gate/rust/gate-api/src/handlers/` | `ls` | `-la` |
| 47 | 8 | `ls -la /Users/laurenalexander/intracept/ \| head -30` | `ls` | `-30 -la` |
| 48 | 8 | `ls -la /Users/laurenalexander/intracept/crates/patterns/` | `ls` | `-la` |
| 49 | 8 | `sleep 180 && tail -30 /private/tmp/claude-501/-Users-laurenalexander-intracept/9a315425-7dfa-4ab4-a068-44b3f99cdb60/tasks/b3wmv2c71.outpu...` | `sleep` | `---LINES--- -30 -l` |
| 50 | 8 | `which python3 && python3 --version` | `which` | `--version` |

## Tools by frequency (top 50)

| Tool | Invocations |
|------|-------------|
| `ls` | 1558 |
| `git` | 1279 |
| `find` | 1247 |
| `python3` | 757 |
| `grep` | 668 |
| `cat` | 581 |
| `cargo` | 462 |
| `gcloud` | 455 |
| `man` | 426 |
| `cd` | 422 |
| `sleep` | 251 |
| `wc` | 183 |
| `curl` | 172 |
| `for` | 147 |
| `head` | 143 |
| `npm` | 121 |
| `rm` | 120 |
| `sed` | 110 |
| `gh` | 105 |
| `node` | 105 |
| `#` | 90 |
| `which` | 85 |
| `open` | 84 |
| `tail` | 84 |
| `echo` | 83 |
| `npx` | 80 |
| `mkdir` | 76 |
| `ps` | 61 |
| `lsof` | 40 |
| `pkill` | 39 |
| `jq` | 36 |
| `TOKEN=$(gcloud` | 32 |
| `cp` | 32 |
| `touch` | 31 |
| `export` | 29 |
| `bash` | 26 |
| `kill` | 25 |
| `source` | 24 |
| `pwd` | 22 |
| `tree` | 17 |
| `du` | 14 |
| `python` | 14 |
| `brew` | 13 |
| `docker` | 13 |
| `pip3` | 12 |
| `ffmpeg` | 10 |
| `pgrep` | 10 |
| `STAGING_DIR=/var/folders/80/r5sjnfh14mqct2dj6vtqlmdm0000gn/T/tmp.YtnyaacjGp` | 8 |
| `TRANSFORMERS_OFFLINE=1` | 8 |
| `/Users/laurenalexander/intracept/spikes/spike_a/.venv/bin/python` | 7 |
