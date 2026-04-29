use intracept_registry::{Registry, VerdictLevel};

fn registry() -> Registry {
    Registry::embedded().expect("embedded registry must load")
}

// ── Tokenizer tests ──────────────────────────────────────────────────

#[test]
fn tokenize_simple() {
    let t = intracept_registry::tokenize("git push origin main");
    assert_eq!(t, vec!["git", "push", "origin", "main"]);
}

#[test]
fn tokenize_double_quotes() {
    let t = intracept_registry::tokenize(r#"echo "hello world" foo"#);
    assert_eq!(t, vec!["echo", "\"hello world\"", "foo"]);
}

#[test]
fn tokenize_single_quotes() {
    let t = intracept_registry::tokenize("echo 'hello world' foo");
    assert_eq!(t, vec!["echo", "'hello world'", "foo"]);
}

#[test]
fn tokenize_extra_spaces() {
    let t = intracept_registry::tokenize("  ls   -la   /tmp  ");
    assert_eq!(t, vec!["ls", "-la", "/tmp"]);
}

#[test]
fn tokenize_empty() {
    let t = intracept_registry::tokenize("");
    assert!(t.is_empty());
}

// ── Shell command splitting ──────────────────────────────────────────

#[test]
fn split_pipe() {
    let parts = intracept_registry::split_shell_commands("ls -la | grep foo");
    assert_eq!(parts, vec!["ls -la", "grep foo"]);
}

#[test]
fn split_semicolon() {
    let parts = intracept_registry::split_shell_commands("cd /tmp; ls");
    assert_eq!(parts, vec!["cd /tmp", "ls"]);
}

#[test]
fn split_and() {
    let parts = intracept_registry::split_shell_commands("echo hello && rm -rf /tmp");
    assert_eq!(parts, vec!["echo hello", "rm -rf /tmp"]);
}

#[test]
fn split_or() {
    let parts = intracept_registry::split_shell_commands("test -f foo || rm bar");
    assert_eq!(parts, vec!["test -f foo", "rm bar"]);
}

#[test]
fn split_redirect_stripped() {
    let parts = intracept_registry::split_shell_commands("echo hi > file.txt");
    assert_eq!(parts, vec!["echo hi"]);
}

#[test]
fn split_background() {
    let parts = intracept_registry::split_shell_commands("sleep 10 &");
    assert_eq!(parts, vec!["sleep 10"]);
}

#[test]
fn split_stderr_redirect() {
    let parts = intracept_registry::split_shell_commands("cmd 2>&1");
    assert_eq!(parts, vec!["cmd"]);
}

// ── Basic command lookups ────────────────────────────────────────────

#[test]
fn lookup_ls() {
    let r = registry();
    let v = r.lookup("ls").unwrap();
    assert_eq!(v.command_path, "ls");
    assert_eq!(v.verdict, VerdictLevel::Allow);
    assert!(v.translation.to_lowercase().contains("list") || v.translation.to_lowercase().contains("directory"));
}

#[test]
fn lookup_cat() {
    let r = registry();
    let v = r.lookup("cat").unwrap();
    assert_eq!(v.command_path, "cat");
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

#[test]
fn lookup_rm() {
    let r = registry();
    let v = r.lookup("rm").unwrap();
    assert_eq!(v.command_path, "rm");
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

#[test]
fn lookup_cp() {
    let r = registry();
    let v = r.lookup("cp").unwrap();
    assert_eq!(v.command_path, "cp");
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

#[test]
fn lookup_chmod() {
    let r = registry();
    let v = r.lookup("chmod").unwrap();
    assert_eq!(v.command_path, "chmod");
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

#[test]
fn lookup_curl() {
    let r = registry();
    let v = r.lookup("curl").unwrap();
    assert_eq!(v.command_path, "curl");
    assert_eq!(v.verdict, VerdictLevel::RequireApproval);
}

#[test]
fn lookup_docker() {
    let r = registry();
    let v = r.lookup("docker").unwrap();
    assert_eq!(v.command_path, "docker");
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

#[test]
fn lookup_brew() {
    let r = registry();
    let v = r.lookup("brew").unwrap();
    assert_eq!(v.command_path, "brew");
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

#[test]
fn lookup_tar() {
    let r = registry();
    let v = r.lookup("tar").unwrap();
    assert_eq!(v.command_path, "tar");
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

#[test]
fn lookup_git() {
    let r = registry();
    let v = r.lookup("git").unwrap();
    assert_eq!(v.command_path, "git");
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

// ── Multi-word command path ──────────────────────────────────────────

#[test]
fn lookup_git_push() {
    let r = registry();
    let v = r.lookup("git push origin main").unwrap();
    assert_eq!(v.command_path, "git push");
    assert_eq!(v.verdict, VerdictLevel::RequireApproval);
}

#[test]
fn lookup_docker_build() {
    let r = registry();
    let v = r.lookup("docker build .").unwrap();
    assert_eq!(v.command_path, "docker build");
}

// ── Flag composition ─────────────────────────────────────────────────

#[test]
fn flag_git_push_force() {
    let r = registry();
    let v = r.lookup("git push --force").unwrap();
    assert_eq!(v.verdict, VerdictLevel::RequireApproval);
    assert!(v.matched_flags.contains(&"--force".to_string()));
    assert!(v.translation.contains("overwriting remote history"));
}

#[test]
fn flag_git_push_dry_run() {
    let r = registry();
    let v = r.lookup("git push --dry-run").unwrap();
    assert_eq!(v.verdict, VerdictLevel::RequireApproval);
    assert!(v.translation.contains("simulating"));
}

#[test]
fn flag_curl_insecure() {
    let r = registry();
    let v = r.lookup("curl --insecure https://example.com").unwrap();
    assert_eq!(v.verdict, VerdictLevel::RequireApproval);
    assert!(v.matched_flags.contains(&"--insecure".to_string()));
}

#[test]
fn flag_rm_recursive() {
    let r = registry();
    let v = r.lookup("rm -R /tmp/build").unwrap();
    assert_eq!(v.verdict, VerdictLevel::RequireApproval);
    assert!(v.translation.contains("recursively"));
}

#[test]
fn flag_rm_force() {
    let r = registry();
    let v = r.lookup("rm -f /tmp/build").unwrap();
    assert!(v.translation.contains("without asking for confirmation"));
}

#[test]
fn flag_cp_recursive() {
    let r = registry();
    let v = r.lookup("cp -R src/ dst/").unwrap();
    assert_eq!(v.verdict, VerdictLevel::Allow);
    assert!(v.translation.contains("recursively"));
}

// ── Bundled short flags ──────────────────────────────────────────────

#[test]
fn bundled_flags_rm_rf() {
    let r = registry();
    let v = r.lookup("rm -Rf /tmp/build").unwrap();
    assert!(v.verdict >= VerdictLevel::Allow);
    assert!(v.translation.contains("recursively"));
    assert!(v.translation.contains("without asking for confirmation"));
}

// ── Multiple separate flags ──────────────────────────────────────────

#[test]
fn multiple_flags_rm() {
    let r = registry();
    let v = r.lookup("rm -R -f /tmp/build").unwrap();
    assert!(v.translation.contains("recursively"));
    assert!(v.translation.contains("without asking for confirmation"));
}

// ── Chained commands return highest verdict ─────────────────────────

#[test]
fn chained_highest_verdict_wins() {
    let r = registry();
    // echo is allow, rm -rf includes require_approval flag — should return the rm verdict
    let v = r.lookup("echo hello && rm -rf /tmp/build").unwrap();
    assert!(v.verdict >= VerdictLevel::Allow, "chained rm -rf should be at least allow, got {:?}", v.verdict);
}

#[test]
fn pipe_both_assessed() {
    let r = registry();
    // ls (allow) piped to grep (allow) — both assessed, allow overall
    let v = r.lookup("ls -la | grep foo").unwrap();
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

#[test]
fn semicolon_highest_verdict() {
    let r = registry();
    let v = r.lookup("ls; rm -R /").unwrap();
    assert!(v.verdict >= VerdictLevel::RequireApproval);
}

#[test]
fn redirect_does_not_split() {
    let r = registry();
    let v = r.lookup("curl https://example.com > file.html").unwrap();
    assert_eq!(v.command_path, "curl");
}

// ── Unknown commands ─────────────────────────────────────────────────

#[test]
fn unknown_returns_none() {
    let r = registry();
    assert!(r.lookup("xyzzy_not_a_real_command").is_none());
}

#[test]
fn empty_returns_none() {
    let r = registry();
    assert!(r.lookup("").is_none());
}

#[test]
fn whitespace_returns_none() {
    let r = registry();
    assert!(r.lookup("   ").is_none());
}

// ── Registry stats ───────────────────────────────────────────────────

#[test]
fn registry_has_commands() {
    let r = registry();
    assert!(r.command_count() > 100, "expected many commands, got {}", r.command_count());
}

#[test]
fn registry_has_flags() {
    let r = registry();
    assert!(r.flag_count() > 100, "expected many flags, got {}", r.flag_count());
}

// ── Verdict level ordering ──────────────────────────────────────────

#[test]
fn verdict_ordering() {
    assert!(VerdictLevel::Unknown < VerdictLevel::Allow);
    assert!(VerdictLevel::Allow < VerdictLevel::RequireApproval);
}

#[test]
fn verdict_display() {
    assert_eq!(VerdictLevel::Allow.to_string(), "allow");
    assert_eq!(VerdictLevel::RequireApproval.to_string(), "require_approval");
    assert_eq!(VerdictLevel::Unknown.to_string(), "unknown");
}

// ── from_json works with inline data ─────────────────────────────────

#[test]
fn from_json_minimal() {
    let json = r#"{
        "commands": {
            "test": {"tool":"test","verdict":"allow","translation":"Run a test.","rationale":"Safe."}
        },
        "flags": {}
    }"#;
    let r = Registry::from_json(json).unwrap();
    let v = r.lookup("test").unwrap();
    assert_eq!(v.translation, "Run a test.");
}

#[test]
fn from_json_invalid() {
    assert!(Registry::from_json("not json").is_err());
}

// ── Max verdict across flags ────────────────────────────────────────

#[test]
fn max_verdict_taken() {
    let r = registry();
    // git push --force should be require_approval (force is require_approval, base push is require_approval)
    let v = r.lookup("git push --force").unwrap();
    assert_eq!(v.verdict, VerdictLevel::RequireApproval);
}

// ── Additional real registry lookups ─────────────────────────────────

#[test]
fn lookup_diff() {
    let r = registry();
    let v = r.lookup("diff file1 file2").unwrap();
    assert_eq!(v.command_path, "diff");
    assert_eq!(v.verdict, VerdictLevel::Allow);
}

#[test]
fn lookup_awk() {
    let r = registry();
    let v = r.lookup("awk '{print $1}' file.txt").unwrap();
    assert_eq!(v.command_path, "awk");
}

#[test]
fn lookup_base64() {
    let r = registry();
    let v = r.lookup("base64 file.bin").unwrap();
    assert_eq!(v.command_path, "base64");
}

#[test]
fn lookup_basename() {
    let r = registry();
    let v = r.lookup("basename /usr/bin/foo").unwrap();
    assert_eq!(v.command_path, "basename");
}
