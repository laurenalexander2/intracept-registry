//! # intracept-registry
//!
//! Translate shell commands into plain English using the Intracept registry.
//!
//! This crate provides a fast, offline command translator that maps shell
//! commands and their flags to human-readable descriptions with verdict levels.
//! It ships with a compile-time embedded copy of the registry, or you can
//! load one from disk / a JSON string at runtime.
//!
//! ## Quick start
//!
//! ```no_run
//! use intracept_registry::{Registry, VerdictLevel};
//!
//! let registry = Registry::embedded().unwrap();
//!
//! if let Some(verdict) = registry.lookup("rm -rf /tmp/build") {
//!     println!("Translation: {}", verdict.translation);
//!     println!("Verdict:     {}", verdict.verdict);
//!     println!("Flags:       {:?}", verdict.matched_flags);
//! }
//! ```

pub mod matcher;
pub mod types;

pub use matcher::{tokenize, split_shell_commands, Error, Registry};
pub use types::{CommandEntry, FlagEntry, VerdictLevel, Verdict};
