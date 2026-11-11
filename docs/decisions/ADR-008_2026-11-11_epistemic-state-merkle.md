# ADR-008: Two-Tier Merkle Epistemic State Root and O(1) Verification Cascade

| Field | Value |
| :--- | :--- |
| **Filename** | `ADR-008_2026-11-11_epistemic-state-merkle.md` |
| **Status** | `Pending` |
| **Date** | `2026-11-11` |
| **Domain** | `epistemic-state` |
| **Scope** | `TOKENME.txt`, `AGENTS.md`, `docs/decisions/*.md`, `tokenme-sync.py` |
| **Dependencies** | `ADR-002` (Plain-Text `.txt` Convention), `ADR-006` (Zero-Dependency Python Sync CLI) |
| **Leaf Digest** | `PENDING` (Populated by `tokenme-sync.py` upon acceptance) |

---

## 1. Context and Problem Statement

As the `TOKENME (.txt)` specification scales into multi-developer and multi-agent environments (such as distributed protocol engineering and concurrent branch workflows), autonomous coding agents and CI/CD pipelines require a deterministic mechanism to verify that a repository's declarative context snapshot (`TOKENME.txt`) and imperative constraint vectors (`AGENTS.md`) are strictly synchronized with the underlying Architecture Decision Record (ADR) ledger (`docs/decisions/`).

However, naive cryptographic verification introduces two critical failure modes:

1. **Filesystem I/O Compute Tax:** Recursively opening and hashing an entire repository tree—or repeatedly re-reading dozens of historical ADR files on every agent turn or file-save hook—incurs severe OS syscall overhead (`open()` / `read()` latency on NTFS, APFS, and ext4 filesystems).
2. **Cross-Platform Line-Ending Divergence:** Git repositories operating across heterogeneous developer environments (Windows CRLF `\r\n` vs. Linux/macOS LF `\n`) produce divergent raw SHA-256 digests for identical semantic text when `core.autocrlf` is active, causing false-positive integrity failures ($P(\text{mismatch}) = 100\%$ across mixed-OS teams).

We need a zero-dependency cryptographic state verification architecture that detects epistemic drift and unindexed ADR mutations in under **2 milliseconds** while remaining completely invariant across operating systems.

---

## 2. Decision

We will implement a **Two-Tier Merkle Epistemic State Cascade** managed by `tokenme-sync.py` using only Python's standard library (`hashlib`, `os`, `pathlib`).

### 2.1 Canonical Byte Normalization (Cross-OS Invariance)
Before computing any leaf or root digest, all text payloads must be normalized in memory to strip carriage returns and trailing whitespace:

$$\text{CanonicalBytes}(F) = \text{strip}\left(\text{replace}(\text{read\_bytes}(F), \text{`\textbackslash r\textbackslash n'}, \text{`\textbackslash n'})\right)$$

### 2.2 Tier 1: Leaf Digest Calculation (6-Hex ADR Provenance)
Each individual file $F_i$ in `docs/decisions/ADR-*.md` is hashed once upon creation or modification to produce a 6-character lowercase hexadecimal leaf digest ($H_{\text{leaf}, i}$):

$$H_{\text{leaf}, i} = \text{SHA256}\left(\text{CanonicalBytes}(F_i)\right)_{[0:6]}$$

* These 6-hex leaf digests are written directly into the `TOKENME.txt` ADR Index Table and referenced in `AGENTS.md` constraint vectors for $O(1)$ provenance lookup.
* During routine verification (`--verify-fast`), `tokenme-sync.py` inspects OS inode metadata (`os.stat().st_mtime_ns` and `st_size`) before reading file blocks, avoiding redundant disk I/O when historical ADRs have not been modified.

### 2.3 Tier 2: Merkle Epistemic State Root (`STATE_ROOT`)
Rather than re-hashing every historical ADR file during state verification, the global `STATE_ROOT` is computed as an 8-character hexadecimal digest over the concatenation of the normalized `AGENTS.md` payload and the normalized `TOKENME.txt` payload (with the active `STATE_ROOT:` value masked as `00000000` during calculation):

$$H_{\text{root}} = \text{SHA256}\left(\text{CanonicalBytes}(\text{AGENTS.md}) \ \Vert \ \text{CanonicalBytes}(\text{TOKENME}_{\text{masked}}\text{.txt})\right)_{[0:8]}$$

Because `TOKENME.txt` contains the sorted index of all $H_{\text{leaf}, i}$ digests, any mutation to an underlying ADR file transitively invalidates $H_{\text{leaf}, i}$, which in turn invalidates $H_{\text{root}}$ in a single memory-buffer pass.

```
[ADR-001.md] --(SHA256[0:6])--> H_leaf_1 \
[ADR-002.md] --(SHA256[0:6])--> H_leaf_2  +--> [TOKENME.txt Index Table]
[ADR-008.md] --(SHA256[0:6])--> H_leaf_8 /             |
                                                       v
                              [AGENTS.md] + [TOKENME_masked.txt]
                                                       |
                                                (SHA256[0:8])
                                                       |
                                                       v
                                          [STATE_ROOT: 8-hex digest]
```

### 2.4 Header Schema in `TOKENME.txt`
The top metadata block of `TOKENME.txt` will expose the deterministic state root using the following key-value primitive:

```text
# TOKENME_VERSION: 2.0
# STATE_ROOT: a4f9c2e1
# ADR_COUNT: 8
```

---

## 3. Verification Lifecycle & Compute Boundaries

To prevent polling overhead, state verification is bound to three explicit lifecycle tiers:

| Tier | Invocation Context | Execution Mechanism | Target Latency | Failure Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 0: Passive Agent Read** | LLM / Agent Session Initialization | Agent reads `STATE_ROOT` string directly from `TOKENME.txt` header into working context; compares string against peer agent state. | **0.0 ms** (Zero CLI spawn) | Agent halts and requests context refresh if `STATE_ROOT` mismatches peer/session state. |
| **Tier 1: Fast Integrity Check** | Git Pre-Commit Hook (`tokenme-sync.py --check`) | Verifies `STATE_ROOT` against masked `TOKENME.txt` + `AGENTS.md` and compares `docs/decisions/` file count and max `st_mtime_ns` against `TOKENME.txt`. | **< 2.0 ms** (excluding Python boot) | Exits with non-zero status code (`sys.exit(1)`) if unindexed ADR edits or stale `STATE_ROOT` are detected. |
| **Tier 2: Full Merkle Sync** | Explicit CLI Sync / CI Merge (`tokenme-sync.py --sync`) | Recomputes $H_{\text{leaf}, i}$ for all ADRs, updates the `TOKENME.txt` index table, and stamps the new 8-hex `STATE_ROOT`. | **< 15.0 ms** (for $\le 100$ ADRs) | Mutates `TOKENME.txt` deterministically in place; fails closed on malformed ADR headers. |

---

## 4. Reference Implementation (Python 3 Standard Library)

```python
import hashlib
from pathlib import Path
import re

STATE_ROOT_PATTERN = re.compile(r"^(#\s*STATE_ROOT:\s*)([0-9a-fA-F]{8}|PENDING|00000000)(\s*)$", re.MULTILINE)

def canonical_bytes(path: Path) -> bytes:
    """Reads file and normalizes CRLF to LF for cross-OS hash invariance."""
    return path.read_bytes().replace(b"\r\n", b"\n").strip()

def compute_leaf_hash(adr_path: Path) -> str:
    """Returns 6-hex provenance digest for an individual ADR file."""
    return hashlib.sha256(canonical_bytes(adr_path)).hexdigest()[:6]

def compute_state_root(tokenme_path: Path, agents_path: Path) -> str:
    """Computes 8-hex Merkle state root across AGENTS.md and masked TOKENME.txt."""
    raw_tokenme = tokenme_path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    masked_tokenme = STATE_ROOT_PATTERN.sub(r"\g<1>00000000\g<3>", raw_tokenme).encode("utf-8")
    
    agents_payload = canonical_bytes(agents_path) if agents_path.exists() else b""
    combined = agents_payload + b"\n---\n" + masked_tokenme
    return hashlib.sha256(combined).hexdigest()[:8]
```

---

## 5. Consequences & Trade-Offs

### Positive
* **Sub-Millisecond Cryptographic Certainty:** Eliminates the need to re-hash unchanged files or walk source code directories during routine checks.
* **Cross-Platform Determinism:** Line-ending normalization guarantees identical hashes across Windows (NTFS), macOS (APFS), and Linux (ext4/Docker).
* **Distributed Consensus Alignment:** Provides multi-developer and blockchain/protocol engineering teams with a lightweight epistemic state root analogous to a block header state trie root.

### Negative / Risks & Mitigations
* **6-Hex Leaf Birthday Bound ($16^6 = 16,777,216$ states):** In a repository with $N = 200$ ADRs, the birthday-paradox collision probability for two 6-hex leaf hashes is $P(\text{collision}) \approx \frac{N^2}{2 \times 16^6} \approx 0.12\%$.
  * *Mitigation:* `tokenme-sync.py` will enforce a uniqueness assertion across all active leaf hashes during `--sync` and emit an explicit warning if a collision ever occurs.
* **Manual Edits to `TOKENME.txt` Without Running Sync:** If a developer manually edits `TOKENME.txt` in a text editor and forgets to run `tokenme-sync.py`, the embedded `STATE_ROOT` will no longer match the masked payload.
  * *Mitigation:* By design, this acts as a tamper-evident tripwire (`--check` fails closed in CI or pre-commit, prompting the user to run `tokenme-sync.py --sync`).
