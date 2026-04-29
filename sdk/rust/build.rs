use std::path::PathBuf;

fn main() {
    let out_dir = PathBuf::from(std::env::var("OUT_DIR").unwrap());
    let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());

    // Walk up from sdk/rust/ to find registry.json at repo root
    let mut search = manifest_dir.clone();
    let mut found = None;
    for _ in 0..5 {
        let candidate = search.join("registry.json");
        if candidate.exists() {
            found = Some(candidate);
            break;
        }
        if !search.pop() {
            break;
        }
    }

    let registry_path = found.unwrap_or_else(|| {
        panic!(
            "Could not find registry.json by walking up from {}",
            manifest_dir.display()
        );
    });

    let dest = out_dir.join("registry.json");
    std::fs::copy(&registry_path, &dest).unwrap_or_else(|e| {
        panic!(
            "Failed to copy {} to {}: {}",
            registry_path.display(),
            dest.display(),
            e
        );
    });

    // Re-run build script if registry changes
    println!("cargo:rerun-if-changed={}", registry_path.display());
}
