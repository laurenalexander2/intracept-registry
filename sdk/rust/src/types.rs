//! Public types for the intracept-registry SDK.

use serde::{Deserialize, Serialize};
use std::fmt;

/// Verdict level for a command or flag.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VerdictLevel {
    /// Unknown or unclassified command.
    Unknown,
    /// Allowed — read-only or benign.
    Allow,
    /// Requires approval — destructive or security-affecting.
    RequireApproval,
}

impl fmt::Display for VerdictLevel {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            VerdictLevel::Unknown => write!(f, "unknown"),
            VerdictLevel::Allow => write!(f, "allow"),
            VerdictLevel::RequireApproval => write!(f, "require_approval"),
        }
    }
}

/// The result of looking up a command in the registry.
#[derive(Debug, Clone)]
pub struct Verdict {
    /// The matched command path (e.g. `"git push"`).
    pub command_path: String,
    /// Flags that were matched from the registry.
    pub matched_flags: Vec<String>,
    /// The highest verdict level across the command and its matched flags.
    pub verdict: VerdictLevel,
    /// The composed plain-English translation of the command.
    pub translation: String,
    /// The rationale for the verdict.
    pub rationale: String,
}

/// A command entry from the registry.
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CommandEntry {
    /// The tool binary name.
    pub tool: String,
    /// Verdict level as a string (e.g. "allow", "require_approval").
    pub verdict: String,
    /// Plain-English translation of the command.
    pub translation: String,
    /// Rationale for the verdict level.
    pub rationale: String,
}

/// A flag entry from the registry.
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct FlagEntry {
    /// The command this flag applies to.
    pub applies_to: String,
    /// The tool binary name.
    pub tool: String,
    /// Verdict level as a string.
    pub verdict: String,
    /// How to modify the base translation when this flag is present.
    pub translation_modifier: String,
    /// Rationale for the verdict level.
    pub rationale: String,
}
