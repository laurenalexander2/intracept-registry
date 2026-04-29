//! Registry-based command matcher.
//!
//! Tokenizes a shell command, finds the longest matching command path in the
//! registry, looks up each flag, and composes a plain-English translation with
//! the highest applicable verdict level.

use crate::types::{CommandEntry, FlagEntry, VerdictLevel, Verdict};
use ahash::AHashMap;
use serde::Deserialize;
use std::path::Path;

/// Error type for registry operations.
#[derive(Debug)]
pub enum Error {
    /// Failed to parse registry JSON.
    ParseError(String),
    /// Failed to read registry file from disk.
    IoError(std::io::Error),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::ParseError(msg) => write!(f, "Registry parse error: {msg}"),
            Error::IoError(err) => write!(f, "Registry I/O error: {err}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<std::io::Error> for Error {
    fn from(err: std::io::Error) -> Self {
        Error::IoError(err)
    }
}

impl From<serde_json::Error> for Error {
    fn from(err: serde_json::Error) -> Self {
        Error::ParseError(err.to_string())
    }
}

/// Raw JSON structure of the registry file.
#[derive(Debug, Deserialize)]
struct RegistryFile {
    commands: std::collections::HashMap<String, CommandEntry>,
    flags: std::collections::HashMap<String, FlagEntry>,
}

/// The loaded registry, backed by fast hash maps.
///
/// Use [`Registry::embedded`], [`Registry::from_path`], or [`Registry::from_json`]
/// to create an instance, then call [`Registry::lookup`] to translate commands.
pub struct Registry {
    commands: AHashMap<String, CommandEntry>,
    flags: AHashMap<String, FlagEntry>,
}

impl Registry {
    /// Load the registry that was embedded at compile time.
    ///
    /// This uses the `registry.json` found relative to the crate root during
    /// `cargo build`. Returns an error if the embedded JSON cannot be parsed.
    pub fn embedded() -> Result<Self, Error> {
        const EMBEDDED: &str = include_str!(concat!(env!("OUT_DIR"), "/registry.json"));
        Self::from_json(EMBEDDED)
    }

    /// Load a registry from a file on disk.
    pub fn from_path(path: impl AsRef<Path>) -> Result<Self, Error> {
        let json = std::fs::read_to_string(path)?;
        Self::from_json(&json)
    }

    /// Load a registry from a JSON string.
    pub fn from_json(json: &str) -> Result<Self, Error> {
        let raw: RegistryFile = serde_json::from_str(json)?;
        Ok(Registry {
            commands: raw.commands.into_iter().collect(),
            flags: raw.flags.into_iter().collect(),
        })
    }

    /// Look up a shell command and return a [`Verdict`] with the translation,
    /// verdict level, matched flags, and rationale.
    ///
    /// If the input contains chained commands (via `&&`, `||`, `;`, or `|`),
    /// each command is assessed independently and the **highest-verdict** result
    /// is returned. This prevents low-verdict prefixes from masking dangerous
    /// chained commands.
    ///
    /// Returns `None` if no matching command is found in the registry.
    ///
    /// # Examples
    ///
    /// ```no_run
    /// let registry = intracept_registry::Registry::embedded().unwrap();
    /// if let Some(verdict) = registry.lookup("rm -rf /tmp/build") {
    ///     println!("{} [{}]", verdict.translation, verdict.verdict);
    /// }
    /// ```
    pub fn lookup(&self, command: &str) -> Option<Verdict> {
        let command = command.trim();
        if command.is_empty() {
            return None;
        }

        let parts = split_shell_commands(command);
        let mut best: Option<Verdict> = None;

        for part in &parts {
            if let Some(v) = self.lookup_single(part) {
                best = Some(match best {
                    Some(prev) if v.verdict > prev.verdict => v,
                    Some(prev) => prev,
                    None => v,
                });
            }
        }

        best
    }

    /// Look up a single simple command (no shell operators).
    fn lookup_single(&self, command: &str) -> Option<Verdict> {
        let command = command.trim();
        if command.is_empty() {
            return None;
        }

        let tokens = tokenize(command);
        if tokens.is_empty() {
            return None;
        }

        // Separate positional tokens from flags
        let mut positional: Vec<&str> = Vec::new();
        let mut flags: Vec<&str> = Vec::new();
        for tok in &tokens {
            if tok.starts_with('-') {
                flags.push(tok);
            } else {
                positional.push(tok);
            }
        }

        // Find the longest matching command path
        let mut matched_path: Option<String> = None;
        let mut matched_cmd: Option<&CommandEntry> = None;
        for len in (1..=positional.len()).rev() {
            let candidate = positional[..len].join(" ");
            if let Some(cmd) = self.commands.get(&candidate) {
                matched_path = Some(candidate);
                matched_cmd = Some(cmd);
                break;
            }
        }

        let (path, cmd) = match (matched_path, matched_cmd) {
            (Some(p), Some(c)) => (p, c),
            _ => return None,
        };

        // Start with base translation and verdict
        let mut translation = cmd.translation.clone();
        let mut max_verdict = parse_verdict(&cmd.verdict);
        let mut matched_flags: Vec<String> = Vec::new();
        let mut modifiers: Vec<String> = Vec::new();

        // Look up each flag. For bundled short flags like -rf, try the bundle
        // first, then split into individual flags (-r, -f) if not found.
        for flag in &flags {
            let key = format!("{path} {flag}");
            if let Some(f) = self.flags.get(&key) {
                matched_flags.push(flag.to_string());
                if !f.translation_modifier.is_empty() {
                    modifiers.push(f.translation_modifier.clone());
                }
                let flag_verdict = parse_verdict(&f.verdict);
                if flag_verdict > max_verdict {
                    max_verdict = flag_verdict;
                }
            } else if flag.starts_with('-') && !flag.starts_with("--") && flag.len() > 2 {
                // Bundled short flags: -rf -> try -r then -f
                for ch in flag[1..].chars() {
                    let single = format!("-{ch}");
                    let single_key = format!("{path} {single}");
                    if let Some(f) = self.flags.get(&single_key) {
                        matched_flags.push(single.clone());
                        if !f.translation_modifier.is_empty() {
                            modifiers.push(f.translation_modifier.clone());
                        }
                        let flag_verdict = parse_verdict(&f.verdict);
                        if flag_verdict > max_verdict {
                            max_verdict = flag_verdict;
                        }
                    }
                }
            }
        }

        // Compose: base translation + flag modifiers
        if !modifiers.is_empty() {
            let base_text = translation.trim_end_matches('.');
            translation = format!("{}, {}.", base_text, modifiers.join(", "));
        }

        Some(Verdict {
            command_path: path,
            matched_flags,
            verdict: max_verdict,
            translation,
            rationale: cmd.rationale.clone(),
        })
    }

    /// Return the number of commands in the registry.
    pub fn command_count(&self) -> usize {
        self.commands.len()
    }

    /// Return the number of flags in the registry.
    pub fn flag_count(&self) -> usize {
        self.flags.len()
    }
}

/// Parse a verdict string into a [`VerdictLevel`].
fn parse_verdict(s: &str) -> VerdictLevel {
    match s {
        "allow" => VerdictLevel::Allow,
        "require_approval" => VerdictLevel::RequireApproval,
        _ => VerdictLevel::Unknown,
    }
}

/// Tokenize a command string, respecting single and double quotes.
pub fn tokenize(command: &str) -> Vec<&str> {
    let mut tokens = Vec::new();
    let bytes = command.as_bytes();
    let len = bytes.len();
    let mut i = 0;

    while i < len {
        // Skip whitespace
        while i < len && bytes[i] == b' ' {
            i += 1;
        }
        if i >= len {
            break;
        }

        let start = i;
        if bytes[i] == b'"' || bytes[i] == b'\'' {
            let quote = bytes[i];
            i += 1;
            while i < len && bytes[i] != quote {
                i += 1;
            }
            if i < len {
                i += 1; // skip closing quote
            }
        } else {
            while i < len && bytes[i] != b' ' {
                i += 1;
            }
        }
        if start < i {
            tokens.push(&command[start..i]);
        }
    }
    tokens
}

/// Split a shell command line into individual simple commands, splitting on
/// `|`, `&&`, `||`, `;`, and `&`. Redirects (`>`, `<`, `2>`, `2>&1`) are
/// stripped from each command but do not start a new command.
///
/// Respects single and double quotes — operators inside quotes are literal.
pub fn split_shell_commands(command: &str) -> Vec<String> {
    let mut commands: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut chars = command.chars().peekable();
    let mut in_quotes = false;
    let mut quote_char = ' ';

    while let Some(&c) = chars.peek() {
        // Quote handling
        if !in_quotes && (c == '"' || c == '\'') {
            in_quotes = true;
            quote_char = c;
            current.push(c);
            chars.next();
            continue;
        }
        if in_quotes && c == quote_char {
            in_quotes = false;
            current.push(c);
            chars.next();
            continue;
        }
        if in_quotes {
            current.push(c);
            chars.next();
            continue;
        }

        // Shell operators that delimit commands
        if c == '|' {
            chars.next();
            if chars.peek() == Some(&'|') {
                chars.next(); // skip ||
            }
            let trimmed = current.trim().to_string();
            if !trimmed.is_empty() {
                commands.push(trimmed);
            }
            current.clear();
            continue;
        }
        if c == ';' {
            chars.next();
            let trimmed = current.trim().to_string();
            if !trimmed.is_empty() {
                commands.push(trimmed);
            }
            current.clear();
            continue;
        }
        if c == '&' {
            chars.next();
            if chars.peek() == Some(&'&') {
                chars.next(); // skip &&
            }
            let trimmed = current.trim().to_string();
            if !trimmed.is_empty() {
                commands.push(trimmed);
            }
            current.clear();
            continue;
        }

        // Redirects — strip but don't split (they modify I/O, not a new command)
        if c == '>' {
            chars.next();
            if chars.peek() == Some(&'>') { chars.next(); } // >>
            // Skip whitespace and the filename
            while chars.peek() == Some(&' ') { chars.next(); }
            while let Some(&nc) = chars.peek() {
                if nc == ' ' || nc == '|' || nc == ';' || nc == '&' || nc == '>' || nc == '<' {
                    break;
                }
                chars.next();
            }
            continue;
        }
        if c == '<' {
            chars.next();
            if chars.peek() == Some(&'<') { chars.next(); } // <<
            while chars.peek() == Some(&' ') { chars.next(); }
            while let Some(&nc) = chars.peek() {
                if nc == ' ' || nc == '|' || nc == ';' || nc == '&' || nc == '>' || nc == '<' {
                    break;
                }
                chars.next();
            }
            continue;
        }
        if c == '2' {
            let mut peek = chars.clone();
            peek.next();
            if let Some(&next) = peek.peek() {
                if next == '>' {
                    // 2> or 2>>  or 2>&1 — skip entire redirect
                    chars.next(); // skip '2'
                    chars.next(); // skip '>'
                    // Handle 2>> or 2>&1
                    while let Some(&nc) = chars.peek() {
                        if nc == '>' || nc == '&' || nc.is_ascii_digit() {
                            chars.next();
                        } else {
                            break;
                        }
                    }
                    // Skip whitespace and filename if present
                    while chars.peek() == Some(&' ') { chars.next(); }
                    while let Some(&nc) = chars.peek() {
                        if nc == ' ' || nc == '|' || nc == ';' || nc == '&' || nc == '>' || nc == '<' {
                            break;
                        }
                        chars.next();
                    }
                    continue;
                }
            }
        }

        current.push(c);
        chars.next();
    }

    let trimmed = current.trim().to_string();
    if !trimmed.is_empty() {
        commands.push(trimmed);
    }

    commands
}
