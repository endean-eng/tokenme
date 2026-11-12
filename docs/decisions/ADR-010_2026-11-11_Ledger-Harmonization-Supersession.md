# ADR-010: Ledger Harmonization, Cross-ADR Supersession Matrix, and v2.0 Implementation Errata

* **Status:** Implemented
* **Date:** 2026-11-11
* **Filename:** `ADR-010_2026-11-11_Ledger-Harmonization-Supersession.md`
* **Component:** Core Specification (`TOKENME.txt` v2.0) & Reference CLI (`tokenme-sync.py`)
* **Amends / Partially Supersedes:** `ADR-003`, `ADR-004`, `ADR-005`, `ADR-006`, `ADR-007`, `ADR-008`, `ADR-009`

---

## 1. Context and Problem Statement

`ADR-001` through `ADR-009` were authored chronologically as the `TOKENME` architecture evolved from an early polyglot prototype (`init_tokenme.py`) into a fail-closed, Merkle-verified v2.0 epistemic specification (`tokenme-sync.py`). To preserve the historical engineering ledger without revisionist edits to past decision bodies, this record establishes:
1. **A Dual-Layer Supersession Signaling Protocol:** Historical ADR bodies remain immutable; supersession is signaled via (a) a single-line status tag (`Accepted (Amended by ADR-010)`) in the header metadata of affected ADRs, and (b) explicit `[Amended by ADR-010]` annotations in the root `TOKENME.txt` ADR Index Table.
2. **The Authoritative v2.0 Supersession Matrix (`HC-01`–`HC-06`)** resolving structural contradictions across `ADR-003` through `ADR-009`.
3. **Harmonized Sharding Constants, Directive Tokens, and Merkle Rules (`AMB-01`–`AMB-04`)**.
4. **Mandatory Reference Implementation Errata (`ERR-01`–`ERR-02`)** patching two defects in `ADR-009`.

---

## 2. Decision: Authoritative Supersession Matrix (Hard Collisions)

Where any clause in `ADR-001` through `ADR-009` conflicts with this section, **`ADR-010` governs**.

| ID | Amended ADRs | Historical Conflict | Governing v2.0 Rule (`ADR-010`) |
| :--- | :--- | :--- | :--- |
| **HC-01** | `ADR-005` (§Decision 1, 3, 4)<br>`ADR-006` (§Invariant 2) | `ADR-005` specified brace-scoped lexical scanners and automated $O(N)$ C/C++/TS header-to-body linkers in the CLI script; `ADR-006` banned non-Python static/regex parsing. | **`tokenme-sync.py` parses AST symbols (`ClassName.method_name`, overload indices, and `__init__.py` barrel routes) exclusively for Python (`.py`, `.pyi`) via `ast`.** For non-Python languages, `ADR-005` qualified scoping and `-> impl: <target> [Lstart-Lend] (Shard: <shard>)` pointers remain mandatory **Specification Rules**, populated by the **Repository Agent during Phase 2 Hydration** (`[AGENT_POPULATE_SYMBOLS]`) and preserved during `tokenme-sync.py --sync`. |
| **HC-02** | `ADR-004` (§Decision 2–3)<br>`ADR-008` (§2.3)<br>`ADR-009` (§Part E) | `ADR-004` placed `TOKENME.<subsystem>.txt` in root alongside `TOKENME.symbols.txt`; `ADR-008` and `ADR-009` used generic `<subdir>/TOKENME.txt` names that collide with root `TOKENME.txt` in IDE tabs. | **Subdirectory-Scoped Named Shards (`<subdir>/TOKENME.<subsystem>.txt`):**<br>1. **Pass 1 (Subdirectory Shards):** Emitted *inside* the target subdirectory as **`<subdir>/TOKENME.<subdir_slug>.txt`** (e.g., `src/engine/TOKENME.engine.txt`), where `<subdir_slug>` is the lowercase normalized directory name. Only the repository root file is named bare `TOKENME.txt`.<br>2. **Pass 2 (Root Spillover Shards):** If root `TOKENME.txt` still exceeds `150` lines after Pass 1, unsharded root `L2` entries eject to root-level `TOKENME.root-l2.txt` ($\le 250$ ejected lines) or split by modality into `TOKENME.code.txt` and `TOKENME.assets.txt` ($> 250$ ejected lines). `TOKENME.symbols.txt` is retired. |
| **HC-03** | `ADR-007` (§2)<br>`ADR-008` (Scope, §1, §2.2, §3) | `ADR-007` mandated `docs/adr/`, while `ADR-008` referenced `docs/decisions/*.md`. | **Canonical ADR Path is `docs/adr/`** (with `.roo/decisions-internal/` for gitignored IDRs). `tokenme-sync.py` scans `docs/adr/` by default and falls back to `docs/decisions/` only if `docs/adr/` is absent (or when overridden via `--adr-dir`). |
| **HC-04** | `ADR-007` (§2 EBNF)<br>`ADR-008` (Header & §2.2) | `ADR-007` restricted `RecordID` to 3 digits (`Digit{3}`), while `ADR-008` permitted alphanumeric suffixes (`ADR-123a`) and had a pre-standardization filename in its internal table. | **Unified 3-Tuple EBNF with 3-to-6 Char Alphanumeric ID:**<br>`Filename := RecordID "_" ISODate "_" TitleSlug ".md" ;`<br>`RecordID := ("ADR" | "IDR") "-" Alnum{3,6} ;`<br>where `Alnum{3,6}` is `Digit Digit Digit` by default (`001`–`999`) or any 3-to-6 character alphanumeric identifier (e.g., `ADR-008`, `ADR-123a`, `ADR-a123`). `ADR-008`'s canonical filename is `ADR-008_2026-11-11_Multi-Tier-Merkle.md`. External repos remain advisory (`^([a-zA-Z0-9-]+)_`). |
| **HC-05** | `ADR-004`, `ADR-005`, `ADR-006` vs. `ADR-002`, `003`, `007`, `008`, `009` | Earlier ADRs named the CLI tool `init_tokenme.py`; later ADRs named it `tokenme-sync.py`. | **Unified CLI Nomenclature:** The single zero-dependency reference script is canonically named **`tokenme-sync.py`**, handling cold scaffolding (`--init`), coordinate/Merkle synchronization (`--sync`), and CI verification (`--check`). |
| **HC-06** | `ADR-006` (§Invariant 3)<br>`ADR-009` (§Part A–C) | `ADR-006` quarantined all files with `\x00` bytes or size `> 1 MiB`; `ADR-009` requires hashing and demoting multi-megabyte PDFs and raster images to `L4`. | **Modality-First Routing:** Candidate files matching `OPAQUE_EXTENSIONS` (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.webp`, `.gif`, `.svg`, `.pdf`) route directly to the **`ADR-009` Opaque/L4 Streaming Pipeline** (`64 KiB` read chunks, bypassing the `1 MiB` text ceiling). All other candidate files route to the **`ADR-006` Source/Text Pipeline** (`8,192`-byte null check and `1 MiB` ceiling). |

---

## 3. Canonical Constants, Directive Taxonomy, and Merkle Rules (Ambiguity Resolution)

### 3.1 Harmonized Sharding Thresholds (`AMB-01`)
To eliminate constant drift across `ADR-003`, `ADR-004`, and `ADR-009`, `tokenme-sync.py` enforces:

| Constant Name | Canonical Value | Governing Scope |
| :--- | :--- | :--- |
| `ROOT_LINE_CEILING` | `150` lines ($\approx 1,000$ tokens) | Hard ceiling for root `TOKENME.txt` before Pass 2 Root Ejection (`ADR-003`, `ADR-009`). |
| `SHARD_TOKEN_CEILING` | `2,000` tokens ($\approx 250$ lines) | Target max budget for any individual `<subdir>/TOKENME.<subsystem>.txt` shard (`ADR-003`). |
| `SINGLE_OVERFLOW_CEILING` | `250` lines | Max ejected root lines stored in `TOKENME.root-l2.txt` before splitting into `TOKENME.code.txt` + `TOKENME.assets.txt` (`ADR-009`). |
| `DIR_PROJECTED_LINE_CEILING` | `100` lines | Pass 1 trigger: `code_l2_lines + (5 * n_opaque) > 100` spawns `<subdir>/TOKENME.<subsystem>.txt` (`ADR-009`). |
| `SHARD_TRIGGER_SYMBOLS` | `75` symbols | Pass 1 trigger: $> 75$ extracted Python AST symbols in a directory spawns `<subdir>/TOKENME.<subsystem>.txt` (`ADR-003`, `ADR-004`). |
| `OPAQUE_SHARD_COUNT_THRESHOLD` | `8` qualifying assets | Pass 1 trigger: $\ge 8$ qualifying opaque/vector/PDF files in a directory spawns `<subdir>/TOKENME.<subsystem>.txt` (`ADR-009`). |

### 3.2 Canonical Agent Directive Tokens (`AMB-02`)
Machine-generated stubs emitted by `tokenme-sync.py` use four distinct, greppable tokens:
1. `[TODO: AGENT_FILL]` — Missing inline semantic description for an `L1` file role or Python `L2` symbol (`ADR-002`, `ADR-005`).
2. `[AGENT_POPULATE_SYMBOLS]` — Non-Python source file awaiting agent symbol extraction and `L2` coordinate population (`ADR-006`).
3. `[NEEDS_HYDRATION]` — Inline shard flag indicating an `L3` opaque/vector asset or `L4` `.l3.txt` sidecar awaits multimodal/OCR hydration (`ADR-009`).
4. `[UNPARSEABLE: <Reason>]` — Quarantined file (`SyntaxError`, `UnicodeDecodeError`, `OversizeText`, `BrokenSymlink`) logged in manifest (`ADR-006`).

### 3.3 ADR Lifecycle Status & Dual-Layer Supersession Tagging (`AMB-03`)
1. **Three-State Lifecycle:** All decision records follow **`Proposed` $\rightarrow$ `Accepted` $\rightarrow$ `Implemented`** (normalizing `ADR-008`'s `Pending` status).
2. **Dual-Layer Supersession Tagging:** When a later ADR amends an earlier ADR:
   * **Layer 1 (ADR Metadata Line):** The amended ADR's status line is updated to `* **Status:** Accepted (Amended by ADR-NNN)` without altering historical body text.
   * **Layer 2 (`TOKENME.txt` ADR Index Table):** The root `TOKENME.txt` ADR table appends `[Amended by ADR-NNN]` to the record's summary row so agents see the override on turn 1 before reading individual ADR files.

### 3.4 Child-Shard `STATE_ROOT` & `.l3.txt` Merkle Binding (`AMB-04`)
1. **Subdirectory Shard `STATE_ROOT` (`<subdir>/TOKENME.<subsystem>.txt`):** If `<subdir>/AGENTS.md` is absent, `compute_state_root()` uses `b""` for `agents_payload`, hashing `b"\n---\n" + CanonicalBytes(masked_subdir_tokenme)`.
2. **Sidecar Hash Rollup:** Every `.l3.txt` sidecar generated under `ADR-009` has its leaf digest ($H_{\text{leaf}, \text{l3}} = \text{SHA256}(\text{CanonicalBytes}(\text{file.l3.txt}))_{[0:L_{\text{leaf}}]}$) recorded in its governing `TOKENME` shard. Because `.l3.txt` embeds `# L4_SOURCE_HASH: <raw_binary_sha256>`, any edit to either the raw `L4` binary or the `.l3.txt` text mutates $H_{\text{leaf}, \text{l3}}$ and invalidates the shard and root `STATE_ROOT`.

---

## 4. Mandatory Implementation Errata for `ADR-009` (`ERR-01` & `ERR-02`)

### 4.1 `ERR-01`: Fix PNG `IHDR` Byte Slicing in `is_qualifying_opaque_asset()`
In `ADR-009` §3, `hdr = f.read(24)` was compared as `hdr == b"IHDR"` (always `False`) and passed whole to `struct.unpack(">II", hdr)` (raising `struct.error` on 24 bytes). Production code in `tokenme-sync.py` MUST slice `hdr[12:16]` for the chunk tag and `hdr[16:24]` for the 8-byte big-endian dimensions:

```python
if ext == ".png" and size >= 24:
    with filepath.open("rb") as f:
        hdr = f.read(24)
        if hdr[:8] == b"\x89PNG\r\n\x1a\n" and hdr == b"IHDR":
            w, h = struct.unpack(">II", hdr)
            if w < MIN_RASTER_DIM_PX and h < MIN_RASTER_DIM_PX:
                return False
```

### 4.2 `ERR-02`: Restore Unscrambled `.l3.txt` Template Placeholders
In `ADR-009` Part D, automated word sorting scrambled the `<PENDING: ...>` strings. `tokenme-sync.py` MUST emit the restored template:

```text
[AGENT_HYDRATION_REQUIRED]
Asset_Class: <PENDING: CAD_Render Datasheet_Scan Field_Photo Manual Receipt_Invoice Schematic |>
Visual_Or_Content_Summary: <PENDING: 1-3 dense engineering sentence summary>
Page_Map_And_TOC:
  - <PENDING: L4 Map be binary by can page queried ranges section slice so>
Key_Specs_And_OCR:
  - <PENDING: (`NONE` Critical extracted if non-text numbers, or part photo) pinouts, specs, tables torque>
```

---

## 5. Consequences

* **Positive:** Preserves 100% of the historical prose in `ADR-001` through `ADR-009`, eliminates IDE tab collisions via `<subdir>/TOKENME.<subsystem>.txt`, unifies the 3-to-6 char alphanumeric `RecordID` grammar, and gives `tokenme-sync.py` a deterministic, bug-free engineering specification.
* **Negative:** Requires a one-time single-line metadata status update across `ADR-003` through `ADR-009`.