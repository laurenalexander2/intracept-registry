//! TD-H1 cross-impl diff harness.
//!
//! Runs every row in the diff-matchers corpus through all three matcher
//! implementations and compares the output against a checked-in snapshot.
//! Surfaces tokenizer + shell-splitter + lookup-key drift across:
//!   - intracept-registry SDK (`Registry::lookup`)
//!   - intracept patterns crate (`Matcher::translate`)
//!   - intracept translator crate (`parser::parse`)
//!
//! For each impl we emit a deterministic per-row record (see `Row`) and join
//! them with a newline. The harness is byte-strict on the output: any change in
//! tokens, splits, or matched key for any impl fails CI. Reviewers see in the
//! diff which impl moved.
//!
//! Day-1 known divergence (heredoc, --command='…' inner extraction, env-var
//! prefixes, shell keywords) is captured in the snapshot — TD-H1 is the
//! observation-then-fix track. The snapshot lets us watch existing drift
//! without breaking CI on day one, while still failing PRs that change behavior.
//!
//! Refresh the snapshot when an implementation change is intentional:
//!   cargo run --manifest-path tests/diff-matchers/harness/Cargo.toml -- \
//!     --corpus tests/diff-matchers/corpus.jsonl \
//!     --snapshot tests/diff-matchers/cross-snapshot.jsonl --update

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Debug, Deserialize)]
struct CorpusRow {
    id: String,
    command: String,
}

#[derive(Debug, Serialize)]
struct ImplOutput {
    tokens: Vec<String>,
    splits: Vec<String>,
    /// Matched command path (e.g. "git push"). None when no registry match or
    /// when the impl does not perform lookup (translator parser).
    match_path: Option<String>,
}

#[derive(Debug, Serialize)]
struct Row {
    id: String,
    sdk: ImplOutput,
    patterns: ImplOutput,
    translator: ImplOutput,
    /// True when sdk.tokens == patterns.tokens (translator uses shell-words and
    /// is allowed to differ — recorded but excluded from the strict bool).
    tokens_agree_sdk_patterns: bool,
    /// True when sdk.splits == patterns.splits == translator.splits.
    splits_agree: bool,
    /// True when sdk.match_path == patterns.match_path.
    match_agree_sdk_patterns: bool,
}

fn run_sdk(registry: &intracept_registry::Registry, command: &str) -> ImplOutput {
    let tokens: Vec<String> = intracept_registry::tokenize(command)
        .into_iter()
        .map(String::from)
        .collect();
    let splits = intracept_registry::split_shell_commands(command);
    let match_path = registry.lookup(command).map(|v| v.command_path);
    ImplOutput {
        tokens,
        splits,
        match_path,
    }
}

fn run_patterns(matcher: &intracept_patterns::Matcher, command: &str) -> ImplOutput {
    let tokens: Vec<String> = intracept_patterns::matcher::tokenize(command)
        .into_iter()
        .map(String::from)
        .collect();
    let splits = intracept_patterns::matcher::split_shell_commands(command);
    let translation = matcher.translate(command);
    ImplOutput {
        tokens,
        splits,
        match_path: translation.matched_key,
    }
}

fn run_translator(command: &str) -> ImplOutput {
    let segments = intracept_translator::parser::parse(command);
    // Tokens: concatenation of every segment's tokens. parser::parse strips
    // shell operators, so this is the closest analogue to the other two impls'
    // single-pass tokenization.
    let mut tokens: Vec<String> = Vec::new();
    for seg in &segments {
        for tok in &seg.tokens {
            tokens.push(tok.clone());
        }
    }
    let splits: Vec<String> = segments.iter().map(|s| s.command.clone()).collect();
    ImplOutput {
        tokens,
        splits,
        match_path: None, // translator parser does not perform lookup
    }
}

fn build_row(
    registry: &intracept_registry::Registry,
    matcher: &intracept_patterns::Matcher,
    corpus: &CorpusRow,
) -> Row {
    let sdk = run_sdk(registry, &corpus.command);
    let patterns = run_patterns(matcher, &corpus.command);
    let translator = run_translator(&corpus.command);

    let tokens_agree_sdk_patterns = sdk.tokens == patterns.tokens;
    let splits_agree = sdk.splits == patterns.splits && sdk.splits == translator.splits;
    let match_agree_sdk_patterns = sdk.match_path == patterns.match_path;

    Row {
        id: corpus.id.clone(),
        sdk,
        patterns,
        translator,
        tokens_agree_sdk_patterns,
        splits_agree,
        match_agree_sdk_patterns,
    }
}

fn parse_args() -> (PathBuf, PathBuf, bool, bool) {
    let mut corpus = PathBuf::from("tests/diff-matchers/corpus.jsonl");
    let mut snapshot = PathBuf::from("tests/diff-matchers/cross-snapshot.jsonl");
    let mut update = false;
    let mut strict = false;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--corpus" => corpus = PathBuf::from(args.next().expect("--corpus needs value")),
            "--snapshot" => snapshot = PathBuf::from(args.next().expect("--snapshot needs value")),
            "--update" => update = true,
            "--strict" => strict = true,
            "--help" | "-h" => {
                eprintln!(
                    "usage: diff-matchers [--corpus FILE] [--snapshot FILE] [--update] [--strict]"
                );
                std::process::exit(0);
            }
            other => panic!("unknown arg: {other}"),
        }
    }
    (corpus, snapshot, update, strict)
}

fn main() -> ExitCode {
    let (corpus_path, snapshot_path, update, strict) = parse_args();

    let corpus_text = std::fs::read_to_string(&corpus_path)
        .unwrap_or_else(|e| panic!("read corpus {}: {e}", corpus_path.display()));

    let registry = intracept_registry::Registry::embedded().expect("registry embedded");
    let matcher = intracept_patterns::default_matcher().expect("patterns matcher");

    let mut produced = String::new();
    let mut disagreements: Vec<String> = Vec::new();
    for line in corpus_text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let corpus_row: CorpusRow =
            serde_json::from_str(line).unwrap_or_else(|e| panic!("corpus row JSON: {e}: {line}"));
        let row = build_row(&registry, &matcher, &corpus_row);
        if !(row.tokens_agree_sdk_patterns && row.splits_agree && row.match_agree_sdk_patterns) {
            disagreements.push(row.id.clone());
        }
        produced.push_str(&serde_json::to_string(&row).unwrap());
        produced.push('\n');
    }

    if update {
        std::fs::write(&snapshot_path, &produced)
            .unwrap_or_else(|e| panic!("write snapshot {}: {e}", snapshot_path.display()));
        eprintln!(
            "wrote snapshot {} ({} disagreement(s) in this run, recorded)",
            snapshot_path.display(),
            disagreements.len()
        );
        return ExitCode::SUCCESS;
    }

    let expected = std::fs::read_to_string(&snapshot_path).unwrap_or_else(|e| {
        panic!(
            "read snapshot {}: {e}\nbootstrap: rerun with --update.",
            snapshot_path.display()
        )
    });

    if expected != produced {
        let want_lines: Vec<&str> = expected.lines().collect();
        let got_lines: Vec<&str> = produced.lines().collect();
        let len = want_lines.len().max(got_lines.len());
        for i in 0..len {
            let w = want_lines.get(i).copied().unwrap_or("<missing>");
            let g = got_lines.get(i).copied().unwrap_or("<missing>");
            if w != g {
                eprintln!(
                    "cross-impl matcher drift at snapshot line {}:\n  expected: {w}\n  got:      {g}\n\nIf intentional, refresh: rerun with --update.",
                    i + 1
                );
                return ExitCode::FAILURE;
            }
        }
        eprintln!(
            "snapshot length mismatch: expected {} lines, got {} lines",
            want_lines.len(),
            got_lines.len()
        );
        return ExitCode::FAILURE;
    }

    if strict && !disagreements.is_empty() {
        eprintln!(
            "--strict: {} corpus row(s) have cross-impl disagreement: {}",
            disagreements.len(),
            disagreements.join(", ")
        );
        return ExitCode::FAILURE;
    }

    eprintln!(
        "diff-matchers OK ({} rows, {} day-1 disagreement(s) frozen in snapshot)",
        produced.lines().count(),
        disagreements.len()
    );
    ExitCode::SUCCESS
}
