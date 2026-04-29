//! CLI tool that translates a shell command using the embedded registry.
//!
//! Usage:
//!     cargo run --example translate -- "rm -rf /tmp/build"

use intracept_registry::Registry;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        eprintln!("Usage: translate <command>");
        eprintln!("Example: translate \"rm -rf /tmp/build\"");
        std::process::exit(1);
    }

    let command = args.join(" ");
    let registry = Registry::embedded().expect("failed to load embedded registry");

    match registry.lookup(&command) {
        Some(verdict) => {
            println!("Command:     {}", command);
            println!("Matched:     {}", verdict.command_path);
            println!("Translation: {}", verdict.translation);
            println!("Verdict:     {}", verdict.verdict);
            println!("Rationale:   {}", verdict.rationale);
            if !verdict.matched_flags.is_empty() {
                println!("Flags:       {}", verdict.matched_flags.join(", "));
            }
        }
        None => {
            println!("Command:     {}", command);
            println!("Result:      Not found in registry.");
        }
    }
}
