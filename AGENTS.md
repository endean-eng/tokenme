# AGENTS.md — Imperative Governance & Execution Contract (`endean-eng/tokenme`)

> **Scope:** Authoritative behavioral constraints for all coding agents (`architect`, `code`, `auditor`, `docs-maintainer`) operating in this repository [Ref: `ADR-001`..`ADR-010`].

---

## 1. Context Triad & Turn-1 Mipmap Routing [Ref: `ADR-001`, `ADR-003`, `ADR-008`, `ADR-010`]

1. **Strict Separation of Epistemic Modality (`ADR-001`):**
   - `README.md` = Human narrative onboarding and white paper prose. NEVER dump live symbol tables here.
   - `AGENTS.md` = Imperative behavioral rules (`DO` / `DO NOT`), capped at 60–150 lines. NEVER stuff file trees or symbol maps here.
   - `TOKENME.txt` = Declarative epistemic state, `STATE_ROOT` Merkle provenance, and `[Lstart-Lend]` symbol/asset coordinates.
2. **Turn-1 `STATE_ROOT` & Mipmap Read (`ADR-003`, `ADR-008`):**
   - On Turn 1, read the top header of `TOKENME.txt` (`# STATE_ROOT: <hex>`) and its L0/L1 tables BEFORE executing broad `grep`, `find`, or full-file reads.
   - Use `[Lstart-Lend]` spans from `TOKENME.txt` (or mounted `<subdir>/TOKENME.<subsystem>.txt` shards) to issue surgical L3 line-range reads.
   - Where `ADR-010` amends an earlier ADR (flagged `[Amended by ADR-010]` in `TOKENME.txt`), **`ADR-010` strictly governs**.

---

## 2. Decision Record Taxonomy & Merkle Synchronization [Ref: `ADR-007`, `ADR-008`, `ADR-010`]

1. **Hierarchical 3-Tuple Filename Grammar (`ADR-007`, `ADR-010` HC-04):**
   - All Architecture Decision Records in `docs/adr/` (and internal records in `.roo/decisions-internal/`) MUST obey:
     `RecordID "_" ISODate "_" TitleSlug ".md"` (where `RecordID` is `ADR-` or `IDR-` followed by 3 digits `001`–`999` or a 3-to-6 char alphanumeric ID, e.g., `ADR-010_2026-11-11_Ledger-Harmonization-Supersession.md`).
   - NEVER use underscores (`_`) inside individual fields; ALWAYS wrap raw ADR filenames in backticks (`` `...` ``) in Markdown prose to prevent `_YYYY-MM-DD_` italicization traps.
2. **Append-Only Ledger & Dual-Layer Supersession (`ADR-010` AMB-03):**
   - NEVER retroactively rewrite historical ADR body text when scope evolves. Create a new superseding ADR, update the amended ADR's header line to `* **Status:** Accepted (Amended by ADR-NNN)`, and sync `TOKENME.txt`.
3. **Mandatory Post-Mutation Merkle Sync (`ADR-006`, `ADR-008`):**
   - `tokenme-sync.py` MUST remain a zero-dependency Python $\ge 3.9$ standard-library script (`ast`, `hashlib`, `pathlib`, `struct`, `re`). NEVER add third-party `pip` packages or non-Python regex symbol scrapers.
   - After mutating any source file, `AGENTS.md`, `docs/adr/*.md`, or `.l3.txt` sidecar, run `python3 tokenme-sync.py` (or `--sync`) to update coordinates and recompute `STATE_ROOT`, and verify with `python3 tokenme-sync.py --check`.

---

## 3. Code Symbol & Non-Python Stub Hydration [Ref: `ADR-005`, `ADR-006`, `ADR-010`]

1. **Canonical Symbol Ownership (`ADR-005`, `ADR-010` HC-01):**
   - `tokenme-sync.py` extracts Python (`.py`, `.pyi`) AST symbols (`ClassName.method_name`) automatically. Agents only fill `[TODO: AGENT_FILL]` prose descriptions.
   - Where `[AGENT_POPULATE_SYMBOLS]` or `[COORDS_STALE_CHECK]` appears on non-Python files, inspect the file once and populate `- `<kind> <Class.method>` [Lstart-Lend]: <summary>` entries (using `-> impl: <target_file> [Lstart-Lend] (Shard: <shard>)` on header prototypes).

---

## 4. Opaque Assets, L3 Sidecar Hydration, & L4 Cold Storage [Ref: `ADR-009`, `ADR-010`]

1. **Hydration Queue Priority (`[NEEDS_HYDRATION]` / `UNHYDRATED_STUB`):**
   - When `TOKENME.txt` (or any mounted shard) flags an asset with `[NEEDS_HYDRATION]` or a `<filename>.<ext>.l3.txt` sidecar carries `# STATUS: UNHYDRATED_STUB` (or `STALE_BINARY_CHANGED`), hydrate it before relying on that asset or when running repository maintenance.
   - **Standard `L3` Opaque Assets ($\le$ threshold):** Inspect the image/SVG (pairing rendered view with pre-scraped DOM/metadata strings) and populate the inline `L2` fields (`Asset_Class`, `Meta_Context`, `Visual_Summary`, `OCR_Payload`) inside its governing `TOKENME` shard. Set `OCR_Payload: NONE` for non-text photos—never hallucinate characters from surface textures.
   - **Demoted `L4` Assets ($>$ threshold):** Populate the adjacent `<filename>.<ext>.l3.txt` sidecar (`Asset_Class`, `Visual_Or_Content_Summary`, `Page_Map_And_TOC`, `Key_Specs_And_OCR`), change `# STATUS:` to `HYDRATED`, and update `Visual_Summary` in the governing `TOKENME` shard.
   - **Multi-Page Flat PDF Cap:** When hydrating a scanned/flat PDF (`MODALITY: FLAT_PDF`) exceeding 5 pages, inspect **only** Front Matter (Pages 1–5) and Back Matter (last 2 index pages) to build `Page_Map_And_TOC`. Mark body pages as `[L4_UNINDEXED_RASTER: Pages X..Y]`—never synchronously OCR the entire document during initial hydration.
2. **Immutable Sidecar Header Lock:**
   - NEVER delete or manually alter Lines 1–4 of any `.l3.txt` sidecar (`# L4_SOURCE_FILE`, `# L4_SOURCE_HASH`, `# L4_BYTES`). `tokenme-sync.py` uses `# L4_SOURCE_HASH` to cryptographically bind the `L3` summary to the raw `L4` binary inside the `ADR-008` Merkle tree.
3. **`L4` Cold-Storage Access Prohibition (`[L4_DEMOTED]`):**
   - NEVER ingest a raw `[L4_DEMOTED]` binary or multi-page PDF whole into context, and NEVER move `L4` files into subdirectories on disk.
   - **Mandatory Access Sequence:** Read the adjacent `<filename>.<ext>.l3.txt` sidecar first $\rightarrow$ identify exact target page numbers from `Page_Map_And_TOC` $\rightarrow$ extract/inspect **only** that bounded page slice ($\le 5$ pages per query).
4. **Two-Pass Shard Navigation (`PURE_L1_MERKLE_ROUTER` & Sub-Shards):**
   - Treat the root `TOKENME.txt` as the `L1` router. Only pull mounted directory shards (`<subdir>/TOKENME.<subsystem>.txt`) or root-overflow modality shards (`TOKENME.code.txt`, `TOKENME.assets.txt`, `TOKENME.root-l2.txt`) that directly intersect your active task scope.