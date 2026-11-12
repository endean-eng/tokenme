# ADR-006: Reference Scaffolder Functional Boundaries & Fail-Closed Filesystem Hardening

* **Status:** Implemented (Amended by ADR-010)
* **Date:** 2026-11-10
* **Component:** `init_tokenme.py` (Reference CLI Bootstrapper)
* **Supersedes / Refines:** Unbounded polyglot regex heuristics in early `v0.0.x` prototypes

---

## 1. Context & Problem Statement

To drive real-world adoption of the `TOKENME` (`v2.0`) epistemic specification, users require a frictionless, single-command CLI bootstrapper (`init_tokenme.py`) that converts an unindexed repository into a compliant shard hierarchy (`TOKENME.txt`, sub-shards, and `AGENTS.md` contracts).

However, building a static repository indexer introduces a severe strategic bifurcation:
1. **Polyglot Static Analysis Cliff:** Attempting to extract symbol ownership graphs across arbitrary languages (TypeScript, Rust, C++, Go, Java) using regular expressions guarantees false positives ("ghost symbols" from comments/strings) and missed multi-line/macro signatures. Conversely, adopting true polyglot AST parsers (e.g., `tree-sitter` C-bindings) destroys zero-dependency portability across Windows, macOS, and Linux, creating wheel-compilation failures and chronic maintenance drag.
2. **Epistemic Architectural Contradiction:** Building a brittle compiler to statically deduce repository semantics violates the core thesis of `TOKENME`—namely, that *coding agents* should maintain semantic epistemic state within deterministic structural boundaries.
3. **Hostile Filesystem Reality:** Real-world repositories contain circular symlinks, binary blobs masquerading behind text extensions, legacy non-UTF-8 encodings, syntax-broken test fixtures, and OS-dependent path/traversal ordering. Crashing or corrupting files on first contact permanently destroys adopter trust.

## 2. Decision

We intentionally bound `init_tokenme.py` as a **Zero-Dependency, Fail-Closed Structural Reference Scaffolder**, enforcing four hard invariants:

### Invariant 1: Strict Python Standard Library Only (Python >= 3.9)
`init_tokenme.py` MUST execute with zero third-party `pip` dependencies (`ast`, `pathlib`, `os`, `tempfile`, `hashlib`, `fnmatch` only). Any user must be able to download and run the single `.py` file cold without virtual environment setup or C-extension compilation.

### Invariant 2: Exact AST Where Native, Honest Structural Stubs Elsewhere
* **Python (`.py`, `.pyi`):** Extract canonical symbol definitions (`class`, `def`, `async def`) and qualified class scopes strictly via Python's native `ast` module. Never fall back to regex on `SyntaxError`; log a deterministic warning and downgrade the file to a structural stub.
* **Non-Python Source & Docs:** Do NOT execute regex symbol-guessing. Compute exact byte size, line count, conservative token budget estimate, and shard placement, then emit a standardized `[AGENT_POPULATE_SYMBOLS]` directive stub paired with a ready-to-run bootstrap prompt for the user's coding agent.

### Invariant 3: Fail-Closed Filesystem Traversal
* **Symlink Immunity:** Never follow directory symlinks (`followlinks=False`) or file symlinks pointing outside the repository root; detect and skip broken or circular links with an explicit log entry.
* **Binary & Oversize Quarantine:** Inspect the first 8,192 bytes of candidate files for null bytes (`\x00`) before full read, and skip files exceeding a configurable max size threshold (default `1 MiB`) with a sizing record rather than loading them into memory.
* **Per-File Encoding & Syntax Isolation:** Read text strictly as `utf-8` (`errors="strict"` inside an isolated per-file `try/except`). On `UnicodeDecodeError`, `PermissionError`, or `SyntaxError`, isolate the fault to that single file, record `[UNPARSEABLE: <Reason>]` in the manifest, and continue execution with exit code `0`.

### Invariant 4: Cross-Platform Determinism & Atomic Writes
* **Canonical Ordering & Paths:** Explicitly sort directory names and filenames lexicographically (UTF-8 codepoint order) at every `os.walk` step. Normalize all emitted shard paths and cross-shard pointers to POSIX forward slashes (`/`) regardless of host OS.
* **All-or-Nothing Persistence:** Stage all generated `TOKENME.txt` shards in memory or OS temporary files within the target directory and commit via atomic `os.replace()` only after 100% of traversal and shard-budgeting succeeds (unless `--dry-run` is passed).

## 3. Rejected Alternatives

* **Regex Polyglot Symbol Scrapers:** *Rejected.* High probability (>85%) of hallucinating symbols inside multiline comments, template literals, or complex TypeScript generics, undermining engineering credibility of the `TOKENME` specification.
* **`tree-sitter` / External Tokenizer (`tiktoken`) Dependencies:** *Rejected for core script.* Introduces `pip`/Rust/C-compiler friction that kills casual evaluation. (Optional `tiktoken` precision may be dynamically imported only if already present in the environment, with deterministic conservative fallback when absent.)
* **Fail-Fast Crash on Dirty Files:** *Rejected.* Legacy monorepos routinely contain broken test fixtures or Latin-1 artifacts; crashing mid-scan makes the tool unusable on the very codebases that need `TOKENME` most.

## 4. Consequences

* **Positive:** Near-zero ongoing maintenance burden; 100% cold-start portability; zero hallucinated symbols; natural dogfooding loop that immediately engages the user's local coding agent (`AGENTS.md`).
* **Negative / Trade-offs:** Non-Python repositories require a two-step initialization (`python init_tokenme.py` followed by a 1-turn agent pass) to populate granular function/type symbols. Heuristic token estimation without `tiktoken` requires a conservative safety margin (~15–20% buffer below shard ceiling) to prevent silent budget overruns on punctuation-dense files.