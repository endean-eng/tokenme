# ADR-008: Multi-Tier Merkle Epistemic State Root and O(1) Verification Cascade

| Field | Value |
| :--- | :--- |
| **Filename** | `ADR-008_2026-11-11_epistemic-state_merkle.md` |
| **Status** | `Pending` |
| **Date** | `2026-11-11` |
| **Domain** | `epistemic-state` |
| **Scope** | `TOKENME.txt`, `AGENTS.md`, `docs/decisions/*.md`, `tokenme-sync.py` |
| **Dependencies** | `ADR-002` (Plain-Text `.txt` Convention), `ADR-006` (Zero-Dependency Python Sync CLI) |

---

## 1. Context and Problem Statement

As the `TOKENME (.txt)` specification scales into multi-developer, multi-agent, and monorepo/compendium environments, autonomous coding agents and CI/CD pipelines require a deterministic mechanism to verify that a repository's declarative context snapshot (`TOKENME.txt`) and imperative constraint vectors (`AGENTS.md`) are strictly synchronized with the underlying Architecture Decision Record (ADR) ledger (`docs/decisions/`) and any nested sub-module shards.

However, naive cryptographic verification and rigid file-parsing rules introduce four critical failure modes:

1. **Unnecessary Context & Re-Read Overhead:** Repeatedly reading dozens of historical ADR files or crawling deep subdirectory trees on every agent turn wastes context tokens and I/O cycles when an $O(1)$ root digest check can prove state equivalence immediately.
2. **Cross-Platform Line-Ending Divergence:** Git repositories operating across heterogeneous developer environments (Windows CRLF `\r\n` vs. Linux/macOS LF `\n`) produce divergent raw SHA-256 digests for identical semantic text when `core.autocrlf` is active, causing false-positive integrity failures ($P(\text{mismatch}) = 100\%$ across mixed-OS teams).
3. **Repository Scale vs. Birthday Bound Collisions:** A fixed short hash length suitable for a 20-ADR repository may experience elevated birthday-paradox collision risk in a massive enterprise monorepo with thousands of tracked artifacts, requiring configurable truncation bounds without breaking parser regexes.
4. **Rigid Filename Coupling:** While the `ADR-<ID>_<domain>_<slug>.md` naming grammar is recommended for human and agent ergonomics, enforcing it as a hard parser requirement would break compatibility with existing repositories that use alternative alphanumeric prefixes (`ADR-123a`, `DEC-01`) or freeform decision filenames.

We need a zero-dependency cryptographic state verification architecture that detects epistemic drift across both flat repositories and nested `TOKENME.txt` shards in under **2 milliseconds**, supports configurable hash truncation lengths, treats ADR naming conventions as advisory, and remains 100% invariant across operating systems.

---

## 2. Decision

We will implement a **Multi-Tier Merkle Epistemic State Cascade** managed by `tokenme-sync.py` using only Python's standard library (`hashlib`, `pathlib`, `re`).

### 2.1 Canonical Byte Normalization (Cross-OS Invariance)
Before computing any leaf, shard, or root digest, all text payloads must be normalized in memory to strip carriage returns and leading/trailing whitespace:

$$\text{CanonicalBytes}(F) = \text{strip}\left(\text{replace}(\text{read\_bytes}(F), \text{`\textbackslash r\textbackslash n'}, \text{`\textbackslash n'})\right)$$

### 2.2 Tier 1: Advisory File Discovery & Leaf Digest Calculation
`tokenme-sync.py` discovers decision records by scanning `docs/decisions/*.md` (excluding `README.md` and `TEMPLATE.md`) and sorting files lexicographically by their normalized relative POSIX path (`path.as_posix()`).

* **Advisory Naming Grammar:** The script supports the recommended `ADR-<alphanumeric>_<domain>_<slug>.md` convention (e.g., `ADR-008`, `ADR-123a`, `ADR-a123`) as well as arbitrary markdown filenames. If a file begins with an alphanumeric prefix followed by an underscore (`^([a-zA-Z0-9-]+)_`), that prefix is extracted as the display ID; otherwise, the full filename stem is used.
* **Configurable Leaf Digest ($L_{\text{leaf}}$):** Each decision file $F_i$ is hashed to produce a lowercase hexadecimal leaf digest of length $L_{\text{leaf}}$ (default $L_{\text{leaf}} = 6$, user-configurable from `6` to `64` via `--leaf-len`):

$$H_{\text{leaf}, i} = \text{SHA256}\left(\text{CanonicalBytes}(F_i)\right)_{[0:L_{\text{leaf}}]}$$

* **Non-Mutating Provenance:** To prevent self-referential hash invalidation, $H_{\text{leaf}, i}$ is **never** written back into the ADR file itself. Leaf digests are recorded exclusively inside the `TOKENME.txt` ADR Index Table and referenced in `AGENTS.md` constraint vectors.

### 2.3 Tier 2: Federated Shard Rollup (Optional N-Tier Hierarchy)
In repositories or compendiums containing nested `TOKENME.txt` shards (e.g., `packages/core/TOKENME.txt`), each child shard independently computes its own `STATE_ROOT` over its local scope. The parent `TOKENME.txt` records the relative POSIX path and active `STATE_ROOT` of each child shard in a deterministic Shard Index Table.

### 2.4 Tier 3: Merkle Epistemic State Root (`STATE_ROOT`)
The `STATE_ROOT` of any `TOKENME.txt` file (whether a leaf shard or the repository root) is computed as a lowercase hexadecimal digest of length $L_{\text{root}}$ (default $L_{\text{root}} = 8$, user-configurable from `8` to `64` via `--root-len`) over the concatenation of the normalized local `AGENTS.md` payload and the normalized `TOKENME.txt` payload (with the active `STATE_ROOT:` value replaced in memory by the length-agnostic sentinel token `MASKED_STATE_ROOT`):

$$H_{\text{root}} = \text{SHA256}\left(\text{CanonicalBytes}(\text{AGENTS.md}) \ \Vert \ \text{`\textbackslash n---\textbackslash n'} \ \Vert \ \text{CanonicalBytes}(\text{TOKENME}_{\text{masked}}\text{.txt})\right)_{[0:L_{\text{root}}]}$$

Because `TOKENME.txt` embeds the sorted tables of all local $H_{\text{leaf}, i}$ digests and all child shard `STATE_ROOT` digests, any mutation to a leaf ADR, a child shard, `AGENTS.md`, or `TOKENME.txt` transitively invalidates the root `STATE_ROOT` in a single pass.

```
[docs/decisions/*.md] --(SHA256[0:L_leaf])--> H_leaf_i  \
[Child Shard TOKENME] --(Child STATE_ROOT)--> H_shard_j  +--> [Root TOKENME.txt Index Tables]
                                                                            |
                                                       [AGENTS.md] + [TOKENME_masked.txt]
                                                                            |
                                                                  (SHA256[0:L_root])
                                                                            |
                                                                            v
                                                            [STATE_ROOT: L_root hex digest]
```

### 2.5 Header Schema in `TOKENME.txt`
The top metadata block of `TOKENME.txt` exposes the deterministic state root and active record counts:

```text
# TOKENME_VERSION: 2.0
# STATE_ROOT: a4f9c2e1
# ADR_COUNT: 8
```

---

## 3. Verification Lifecycle & Compute Boundaries

State verification is bound to three explicit lifecycle tiers:

| Tier | Invocation Context | Execution Mechanism | Target Latency | Failure Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 0: Passive Agent Read** | LLM / Agent Session Initialization | Agent reads `STATE_ROOT` string directly from `TOKENME.txt` header into working context; compares string against cached session/peer state. | **0.0 ms** (Zero CLI spawn) | Agent refreshes context only if `STATE_ROOT` differs from prior turn or peer state. |
| **Tier 1: Fast Integrity Check** | Git Pre-Commit Hook / CI (`tokenme-sync.py --check`) | Recomputes $H_{\text{leaf}, i}$ for all files in `docs/decisions/`, verifies child shard roots, and verifies `STATE_ROOT` against masked `TOKENME.txt` + `AGENTS.md`. | **< 2.0 ms** (for $\le 100$ ADRs on NVMe) | Exits with non-zero status code (`sys.exit(1)`) if unindexed ADR edits, shard drift, or stale `STATE_ROOT` are detected. |
| **Tier 2: Full Merkle Sync** | Explicit CLI Sync (`tokenme-sync.py --sync`) | Recomputes all $H_{\text{leaf}, i}$ digests (and child shards from bottom up), updates `TOKENME.txt` index tables, and stamps the new `STATE_ROOT`. | **< 15.0 ms** (for $\le 100$ ADRs) | Mutates `TOKENME.txt` deterministically in place; warns on any leaf hash collision. |

---

## 4. Reference Implementation (Python 3 Standard Library)

```python
import hashlib
import re
from pathlib import Path

# Length-agnostic regex matches any 6-to-64 char hex digest or PENDING sentinel
STATE_ROOT_PATTERN = re.compile(
    r"^(#\s*STATE_ROOT:\s*)([0-9a-fA-F]{6,64}|PENDING)(\s*)$",
    re.MULTILINE,
)

# Advisory ID extractor: captures prefix before first underscore (e.g., ADR-008, ADR-123a),
# or falls back to the full filename stem if no underscore delimiter is used.
ADVISORY_ID_PATTERN = re.compile(r"^([a-zA-Z0-9-]+)_")
IGNORED_DECISION_FILES = {"readme.md", "template.md"}


def canonical_bytes(path: Path) -> bytes:
    """Reads file and normalizes CRLF to LF for cross-OS hash invariance."""
    return path.read_bytes().replace(b"\r\n", b"\n").strip()


def extract_advisory_id(adr_path: Path) -> str:
    """Extracts prefix ID if present, otherwise returns filename stem."""
    match = ADVISORY_ID_PATTERN.match(adr_path.stem)
    return match.group(1) if match else adr_path.stem


def compute_leaf_hash(adr_path: Path, leaf_len: int = 6) -> str:
    """Returns configurable hex provenance digest for an individual decision file."""
    if not (6 <= leaf_len <= 64):
        raise ValueError("leaf_len must be between 6 and 64 hex characters.")
    return hashlib.sha256(canonical_bytes(adr_path)).hexdigest()[:leaf_len]


def discover_leaf_hashes(decisions_dir: Path, root_dir: Path, leaf_len: int = 6) -> dict[str, tuple[str, str]]:
    """
    Discovers all markdown decision files, sorted deterministically by POSIX path.
    Returns dict mapping {posix_rel_path: (advisory_id, leaf_hash)}.
    """
    if not decisions_dir.exists():
        return {}
    records: dict[str, tuple[str, str]] = {}
    seen_hashes: dict[str, str] = {}

    paths = sorted(
        (p for p in decisions_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md" and p.name.lower() not in IGNORED_DECISION_FILES),
        key=lambda p: p.relative_to(root_dir).as_posix(),
    )
    for path in paths:
        rel_posix = path.relative_to(root_dir).as_posix()
        adv_id = extract_advisory_id(path)
        digest = compute_leaf_hash(path, leaf_len=leaf_len)
        if digest in seen_hashes:
            raise RuntimeError(
                f"Leaf hash collision detected ({digest}) between {seen_hashes[digest]} and {rel_posix}. "
                f"Increase --leaf-len beyond {leaf_len}."
            )
        seen_hashes[digest] = rel_posix
        records[rel_posix] = (adv_id, digest)
    return records


def compute_state_root(tokenme_path: Path, agents_path: Path, root_len: int = 8) -> str:
    """Computes configurable Merkle state root across AGENTS.md and masked TOKENME.txt."""
    if not (8 <= root_len <= 64):
        raise ValueError("root_len must be between 8 and 64 hex characters.")
    raw_tokenme = tokenme_path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    masked_tokenme = STATE_ROOT_PATTERN.sub(r"\g<1>MASKED_STATE_ROOT\g<3>", raw_tokenme).encode("utf-8")

    agents_payload = canonical_bytes(agents_path) if agents_path.exists() else b""
    combined = agents_payload + b"\n---\n" + masked_tokenme
    return hashlib.sha256(combined).hexdigest()[:root_len]
```

---

## 5. Consequences & Trade-Offs

### Positive
* **Zero Filename Lock-In:** Teams following the recommended `ADR-<alphanumeric>_<domain>_<slug>.md` convention get clean shorthand IDs (`ADR-008`, `ADR-123a`), while teams with legacy or custom naming schemes work out-of-the-box via stem fallback and POSIX path sorting.
* **Arbitrary Repository Scaling:** Default 6-hex leaf and 8-hex root digests keep token overhead minimal for standard repos, while `--leaf-len` and `--root-len` scale up to 64 hex characters for massive repositories or multi-tier shard trees without modifying the parser regex.
* **Git Checkout Immunity:** Eliminating `st_mtime_ns` heuristics in favor of direct canonical byte hashing prevents false-positive failures after `git checkout`, `git clone`, or branch switches while still executing in `< 2.0 ms`.

### Negative / Risks & Mitigations
* **Short-Hash Birthday Bound at Default Length ($L_{\text{leaf}} = 6$):** In a repository with $k = 200$ ADRs, the birthday-paradox collision probability for 6-hex leaf hashes is $P \approx 0.12\%$.
  * *Mitigation:* `discover_leaf_hashes()` enforces a strict uniqueness check across all active leaf digests and raises an explicit actionable error instructing the user to increment `--leaf-len` (e.g., to `8` or `10`) if a collision ever occurs.
* **Manual Edits to `TOKENME.txt` Without Running Sync:** If a developer manually edits `TOKENME.txt` or an ADR and forgets to run `tokenme-sync.py --sync`, the embedded `STATE_ROOT` will no longer match the masked payload.
  * *Mitigation:* By design, this acts as a tamper-evident tripwire (`--check` fails closed in CI or pre-commit).
