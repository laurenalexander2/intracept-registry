//! TD-H1 diff-matchers SDK guardrail.
//!
//! Runs the SDK matcher across `tests/diff-matchers/corpus.jsonl` and asserts
//! every input still produces the snapshot's tokenization, shell-split, and
//! lookup-key. Pair: `[intracept]` runs all three impls (SDK + patterns +
//! translator) against the same corpus; this side only watches the SDK so a
//! drift in this repo can't slip through without the snapshot diff failing.
//!
//! Refresh: `UPDATE_SNAPSHOTS=1 cargo test -p intracept-registry diff_matchers`.

use intracept_registry::{split_shell_commands, tokenize, Registry};
use serde_json::{json, Value};
use std::path::PathBuf;

fn registry_root() -> PathBuf {
    // sdk/rust/ -> sdk/ -> repo root
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf()
}

fn run_sdk(registry: &Registry, command: &str) -> Value {
    let tokens: Vec<String> = tokenize(command).into_iter().map(String::from).collect();
    let splits = split_shell_commands(command);
    let match_path = registry.lookup(command).map(|v| v.command_path);
    json!({
        "tokens": tokens,
        "splits": splits,
        "match_path": match_path,
    })
}

#[test]
fn sdk_matcher_matches_snapshot() {
    let root = registry_root();
    let corpus_path = root.join("tests/diff-matchers/corpus.jsonl");
    let snapshot_path = root.join("tests/diff-matchers/sdk-snapshot.jsonl");
    let registry = Registry::embedded().expect("embedded registry");

    let corpus_text = std::fs::read_to_string(&corpus_path)
        .unwrap_or_else(|e| panic!("read {}: {e}", corpus_path.display()));

    let mut produced = String::new();
    for line in corpus_text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let row: Value = serde_json::from_str(line).expect("corpus row JSON");
        let id = row.get("id").and_then(Value::as_str).expect("id");
        let command = row.get("command").and_then(Value::as_str).expect("command");

        let result = json!({
            "id": id,
            "sdk": run_sdk(&registry, command),
        });
        produced.push_str(&serde_json::to_string(&result).unwrap());
        produced.push('\n');
    }

    if std::env::var("UPDATE_SNAPSHOTS").is_ok() {
        std::fs::write(&snapshot_path, &produced)
            .unwrap_or_else(|e| panic!("write snapshot {}: {e}", snapshot_path.display()));
        eprintln!("wrote snapshot {}", snapshot_path.display());
        return;
    }

    let expected = std::fs::read_to_string(&snapshot_path).unwrap_or_else(|e| {
        panic!(
            "read snapshot {}: {e}\nrun `UPDATE_SNAPSHOTS=1 cargo test -p intracept-registry diff_matchers` to bootstrap.",
            snapshot_path.display()
        )
    });

    if expected != produced {
        // Find the first divergence for a precise error.
        let want_lines: Vec<&str> = expected.lines().collect();
        let got_lines: Vec<&str> = produced.lines().collect();
        let len = want_lines.len().max(got_lines.len());
        for i in 0..len {
            let w = want_lines.get(i).copied().unwrap_or("<missing>");
            let g = got_lines.get(i).copied().unwrap_or("<missing>");
            if w != g {
                panic!(
                    "SDK matcher drift at corpus line {}:\n  expected: {w}\n  got:      {g}\n\nIf intentional, refresh: `UPDATE_SNAPSHOTS=1 cargo test -p intracept-registry diff_matchers`.",
                    i + 1
                );
            }
        }
        panic!("snapshot length mismatch: expected {} lines, got {} lines", want_lines.len(), got_lines.len());
    }
}
