# ADR-009: Opaque & Vector Asset L2 Mandate, In-Place L4 Demotion Sidecars, and Two-Pass Opaque/Root Sharding

* **Status:** Implemented (Amended by ADR-010)
* **Date:** 2026-11-11
* **Author:** Elijah N. Dean, BSME (`endean-eng` / Dean Innovative Design LLC)
* **Target Specification:** `TOKENME` v2.0
* **Supersedes / Refines:** Extends ADR-002 (Plain-Text `.txt` Convention), ADR-006 (`tokenme-sync.py` Zero-Dependency CLI), and ADR-008 (Multi-Tier Merkle Epistemic State Root Verification)

---

## 1. Context & Problem Statement

In multi-disciplinary engineering, hardware, and software repositories, operational entropy in non-code files is decoupled from raw file byte size:
1. **Small High-Entropy Opaque Assets:** A 45 KB 1-bit monochrome wiring schematic, a 60 KB scanned thermal receipt, or an equipment nameplate photograph contains critical operational specs (part numbers, pinouts, tolerances) but falls below byte-size heuristics designed for source code files.
2. **Vector Coordinate Soup (`.svg`):** Electrical schematics (KiCad), hydraulic diagrams, and 2D CAD exports frequently use `.svg`. Treating `.svg` files as raw XML text floods context windows with tens of thousands of floating-point `<path>` coordinates or misses text entirely when CAD exporters convert fonts to Bézier curves ("Text-as-Paths").
3. **Heavy / Multi-Page PDFs:** Loading a 150-page scanned equipment service manual (30 MB flat PDF) or a 60-page MCU datasheet (600 KB native vector PDF) directly at `L3` exhausts agent context windows or triggers synchronous OCR compute walls.
4. **Zero-Dependency Constraint vs. Semantic Extraction:** Per ADR-006, `tokenme-sync.py` must remain a fast, deterministic, zero-dependency Python 3 standard-library CLI tool. It cannot bundle external OCR engines (`tesseract`), PDF parsers (`pypdf`), or LLM API dependencies.
5. **Unbounded Opaque Directory & Root Spillover:** Because unhydrated binary images contain zero lines of code and zero AST symbols, existing code-centric sharding triggers fail to shard image-heavy folders (e.g., 25 inspection photos) or flat repositories, causing the root `TOKENME.txt` to breach its $\le 1,000$-token router ceiling.

---

## 2. Decision

We standardize a five-part protocol governing how opaque binary assets, vector diagrams, and heavy PDFs are filtered, scaffolded by `tokenme-sync.py`, hydrated by repository agents, tiered into `L4` via adjacent `.l3.txt` sidecars, and sharded across the `TOKENME` Merkle tree.

---

### Part A: The Gated Opaque & Vector Asset `L2` Mandate

Any qualifying non-text-extractable binary asset (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`, `.webp`, `.gif`), vector diagram (`.svg`), or document (`.pdf`) **bypasses the standard `L3` byte-size floor** and requires a structured `L2` summary entry, subject to a deterministic **Pre-Filter Gate**:

1. **Path & Glob Exclusion:** Assets inside `node_modules/*`, `.git/*`, `build/*`, `dist/*`, `assets/icons/*`, `thumbnails/*`, and `raw_dataset/*` are excluded from `L2` indexing.
2. **Geometry & Node-Count Icon Filter (Zero-Dependency `stdlib` Check):**
   * **Raster Images:** Excluded as trivial UI icons if raw byte size $< 512\text{ B}$ OR header dimensions are $< 128 \times 128\text{ px}$.
   * **SVG Vector Files:** Excluded as trivial UI icons if byte size $< 2,048\text{ B}$ AND the XML DOM contains zero `<text>` elements and zero `id=` attributes.
3. **Hybrid SVG Handling:** Non-icon `.svg` files MUST NOT be ingested into LLM context as raw XML. `tokenme-sync.py` deterministically scrapes `<title>`, `<desc>`, `<text>`, and `<g id="...">` strings during scaffolding, while the hydrating agent inspects a rendered raster view alongside those scraped DOM strings to preserve spatial topology and defeat "Text-as-Paths" blindness.
4. **Whitelisted Metadata Pre-Scrape:** Before semantic hydration, deterministic file headers/metadata (`Title`, `Description`, `Author`/`CreatorTool`, `Software`, `DateTimeOriginal`, `GPSCoords`, and PNG `tEXt` chunks) are scraped to ground the `L2`/`L3` summary while stripping camera-internal EXIF bloat (`MakerNotes`, ICC profiles, binary thumbnails).

---

### Part B: Modality-Weighted `OR` Thresholds & In-Place `L4` Demotion

To prevent context window exhaustion and OCR compute walls, any PDF or heavy binary asset breaching a **Modality-Weighted Inclusive `OR` ($\lor$) Ceiling** is logically demoted to **`L4` (Cold / Slice-Only Storage)**:

$$\text{Demote}_{\text{Flat\_PDF}} = (\text{Pages} > 5) \;\lor\; (\text{Bytes} > 5\text{ MB})$$

$$\text{Demote}_{\text{Native\_PDF}} = (\text{Pages} > 15) \;\lor\; (\text{Bytes} > 10\text{ MB})$$

$$\text{Demote}_{\text{Raster\_CAD}} = (\text{Bytes} > 10\text{ MB})$$

*(Where a `Flat_PDF` is defined as yielding $< 50$ extractable ASCII/UTF-8 text characters per page on average, and a `Native_PDF` yields $\ge 50$ characters per page).*

#### Physical vs. Logical Topology on Disk:
1. **`L4` is an In-Place Logical Tier:** Demoted `L4` files **never move on disk**. Moving binary assets into subdirectories breaks relative links in Markdown, CAD assemblies, and build scripts. Instead, the raw file remains in place and is tagged `[L4_DEMOTED]` in `TOKENME.txt`, prohibiting agents from reading the raw binary whole.
2. **Co-Located `L3` Surrogate Sidecar (`<filename>.<ext>.l3.txt`):**
   * Every asset demoted to `L4` receives an adjacent plain-text surrogate file in the exact same directory, named by appending `.l3.txt` to the full filename (e.g., `docs/Service_Manual_GSI.pdf.l3.txt`).
   * Appending `.l3.txt` conforms to ADR-002 (Plain-Text `.txt` Convention), guarantees adjacent lexicographical sorting in IDEs and `ls`, survives `git mv` atomically, and avoids namespace collisions (e.g., `schematic.pdf.l3.txt` vs. `schematic.svg.l3.txt`).
   * **Constraint:** Standard opaque assets that remain at `L3` ($\le$ threshold) do **not** generate `.l3.txt` sidecar files on disk; their concise 3-line summary resides directly inline inside their governing `TOKENME.txt` (`L2`).

---

### Part C: Division of Labor (`tokenme-sync.py` Scaffolder vs. Agent Hydrator)

To strictly preserve ADR-006 (`tokenme-sync.py` as a zero-dependency Python 3 `stdlib` CLI tool), index generation is split into two distinct phases:

| Phase | Actor | Responsibilities |
| :--- | :--- | :--- |
| **Phase 1: Deterministic Scaffolding** | `tokenme-sync.py` (Python 3 `stdlib`) | 1. Scans directory tree, evaluates icon filters, and computes streaming SHA-256 (`L4_SOURCE_HASH`) and byte counts.<br>2. Estimates PDF page count via fast regex (`/Type\s*/Page\b`) and extracts whitelisted ASCII/XML header strings.<br>3. For `L4`-demoted assets, generates `<filename>.<ext>.l3.txt` with `STATUS: UNHYDRATED_STUB` (unless an existing `.l3.txt` already matches `L4_SOURCE_HASH` and is marked `HYDRATED`).<br>4. Registers `[NEEDS_HYDRATION]` pointers in `TOKENME.txt`. |
| **Phase 2: Semantic Hydration** | Active Repo Agent (e.g., Roo Code / Multimodal Agent) | 1. Detects `[NEEDS_HYDRATION]` flags in `TOKENME.txt` or `.l3.txt` stubs.<br>2. Performs OCR, vision inspection, and Table of Contents (TOC) extraction (for multi-page flat PDFs, inspecting Front Matter Pages 1–5 and Back Matter index pages rather than synchronously OCRing 100+ body pages).<br>3. Populates `Asset_Class`, `Visual_Or_Content_Summary`, `Page_Map_And_TOC`, and `Key_Specs_And_OCR`, flipping `STATUS: HYDRATED`. |

#### Coupled Merkle Hash Verification (ADR-008 Integration):
For any `L4`-demoted asset, Line 3 of `<filename>.<ext>.l3.txt` MUST record the immutable raw binary hash (`# L4_SOURCE_HASH: <hex>`). The governing `TOKENME.txt` Merkle tree hashes the **`.l3.txt` sidecar file**. Because the `.l3.txt` file embeds `L4_SOURCE_HASH`, a single hash in `TOKENME.txt` cryptographically binds **both** the raw `L4` binary on disk and the agent's `L3` semantic summary. If the raw binary changes on disk, `tokenme-sync.py` updates `L4_SOURCE_HASH` on Line 3 and sets `STATUS: STALE_BINARY_CHANGED`, automatically invalidating the Merkle branch.

---

### Part D: Standardized `.l3.txt` Sidecar Schema

```text
# TOKENME L3 SURROGATE STUB
# L4_SOURCE_FILE: docs/Service_Manual_GSI.pdf
# L4_SOURCE_HASH: a94f8c2e1b0d
# L4_BYTES: 29779456 | EST_PAGES: 142 | MODALITY: FLAT_PDF
# STATUS: UNHYDRATED_STUB

[DETERMINISTIC_PRE_SCRAPE]
Extracted_Metadata: /Title (GSI 110ft Grain Leg & Dryer Manual) /Producer (Adobe PDF Library)

[AGENT_HYDRATION_REQUIRED]
Asset_Class: <PENDING: CAD_Render Datasheet_Scan Field_Photo Manual Receipt_Invoice Schematic |>
Visual_Or_Content_Summary: <PENDING: 1-3 dense engineering sentence summary>
Page_Map_And_TOC:
  - <PENDING: L4 Page be binary by can mapped queried ranges sections slice so to>
Key_Specs_And_OCR:
  - <PENDING: (`NONE` Critical extracted if non-text numbers, or part photo) pinouts, specs, tables torque>
```

---

### Part E: Two-Pass Sharding (Opaque Density Trigger & Root Modality Ejection)

To guarantee that root `TOKENME.txt` never breaches its $\le 1,000$-token ($\le 150$-line) router ceiling—even in repositories with bulk photo folders or flat root directory structures—`tokenme-sync.py` enforces a two-pass sharding algorithm:

#### Pass 1: Bottom-Up Subdirectory Sharding (Trigger 5 — Opaque Asset Density)
In addition to existing code triggers ($>3,000$ tokens, $>250$ lines, $>100$ symbols, $\ge 2$ runtimes), any non-root subdirectory containing **$N_{\text{opaque}} \ge 8$ qualifying opaque/vector assets** OR exceeding a **Projected L2 Line Footprint** of:

$$L_{\text{proj}} = L_{\text{code\_lines}} + (5 \times N_{\text{opaque}}) > 100\text{ lines}$$

MUST automatically spawn a local `subdir/TOKENME.txt` shard. The parent `TOKENME.txt` collapses the entire subdirectory into a 2-line `[SHARD_MOUNT]` entry.

#### Pass 2: Root Ceiling Check & Modality-Bucketed Ejection ("Pure Router Mode")
After Pass 1 completes, `tokenme-sync.py` sums the lines of all `[SHARD_MOUNT]` entries plus all remaining **unsharded inline `L2` entries** still residing in the root `TOKENME.txt`:
1. **If Total Root Lines $\le 150$ ($\sim 1,000\text{ tokens}$):** Retain inline `L2` entries in root `TOKENME.txt` (Hybrid `L1+L2` Mode).
2. **If Total Root Lines $> 150$:** Trigger **Pure Router Mode**. Eject **all** remaining unsharded inline `L2` entries out of root `TOKENME.txt` (leaving only `[L1_ARCHITECTURE_OVERVIEW]` and `[L1_SHARD_ROUTER]` mounts in root `TOKENME.txt`):
   * **Single Spillover ($\le 250$ ejected lines):** Write all ejected root `L2` entries to a single co-located `TOKENME.root-l2.txt` shard to minimize agent hop count.
   * **Heavy Spillover ($> 250$ ejected lines):** Partition ejected unsharded entries by modality into `TOKENME.code.txt` (scripts, source, configs) and `TOKENME.assets.txt` (opaque visuals, SVGs, PDFs, `L4` pointers).
   * **Strict 1-to-1 Merkle Ownership:** Files already belonging to a Pass 1 subdirectory shard (`subdir/TOKENME.txt`) are NEVER duplicated in `TOKENME.code.txt` or `TOKENME.assets.txt`, preserving a strict tree topology (never a DAG) for ADR-008 Merkle verification.

---

## 3. Reference Implementation (`tokenme-sync.py` Stdlib Logic)

```python
import struct
from pathlib import Path

OPAQUE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".gif", ".svg", ".pdf"}
OPAQUE_SHARD_COUNT_THRESHOLD = 8       # >= 8 qualifying opaque files forces a local subdir shard
PROJECTED_L2_LINES_PER_OPAQUE = 5      # Projected line expansion per hydrated opaque stub
DIR_PROJECTED_LINE_CEILING = 100       # Max projected L2 lines per directory before sharding
ROOT_LINE_CEILING = 150                # Hard ceiling (~1,000 tokens) for root TOKENME.txt
SINGLE_OVERFLOW_CEILING = 250          # Max lines before splitting root overflow into .code and .assets
MIN_RASTER_DIM_PX = 128                # UI icon filter floor

def is_qualifying_opaque_asset(filepath: Path) -> bool:
    """Zero-dependency stdlib gate: filters out trivial UI icons and non-opaque files."""
    ext = filepath.suffix.lower()
    if ext not in OPAQUE_EXTENSIONS or filepath.name.endswith(".l3.txt"):
        return False
    try:
        size = filepath.stat().st_size
        if size < 512:
            return False
        if ext == ".png" and size >= 24:
            with filepath.open("rb") as f:
                hdr = f.read(24)
                if hdr[:8] == b"\x89PNG\r\n\x1a\n" and hdr == b"IHDR":
                    w, h = struct.unpack(">II", hdr)
                    if w < MIN_RASTER_DIM_PX and h < MIN_RASTER_DIM_PX:
                        return False
        if ext == ".svg" and size < 2048:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
            if "<text" not in text and "id=" not in text:
                return False
        return True
    except OSError:
        return False

def evaluate_pass1_subdir_shard(
    dir_path: Path, repo_root: Path, code_symbols: int, code_l2_lines: int
) -> tuple[bool, str]:
    """Pass 1: Evaluates directory-level code triggers AND Opaque Asset Density triggers."""
    if dir_path.resolve() == repo_root.resolve():
        return False, "ROOT_DIR"

    n_opaque = sum(
        1 for p in dir_path.iterdir()
        if p.is_file() and is_qualifying_opaque_asset(p)
    )
    proj_lines = code_l2_lines + (n_opaque * PROJECTED_L2_LINES_PER_OPAQUE)

    if n_opaque >= OPAQUE_SHARD_COUNT_THRESHOLD:
        return True, f"OPAQUE_DENSITY({n_opaque})"
    if proj_lines > DIR_PROJECTED_LINE_CEILING:
        return True, f"PROJECTED_L2_OVERFLOW({proj_lines})"
    if code_symbols > 100:
        return True, f"SYMBOL_COUNT({code_symbols})"
    return False, "INLINE_IN_PARENT"

def evaluate_pass2_root_ejection(
    header_lines: list[str],
    shard_mount_lines: list[str],
    unsharded_code_l2: list[str],
    unsharded_asset_l2: list[str],
) -> dict[str, list[str]]:
    """Pass 2: Enforces the <=150-line Root Ceiling by ejecting unsharded L2s if breached."""
    base_len = len(header_lines) + len(shard_mount_lines)
    spillover_len = len(unsharded_code_l2) + len(unsharded_asset_l2)

    if (base_len + spillover_len) <= ROOT_LINE_CEILING:
        return {
            "TOKENME.txt": header_lines + shard_mount_lines + unsharded_code_l2 + unsharded_asset_l2
        }

    if spillover_len <= SINGLE_OVERFLOW_CEILING:
        mount = ["TOKENME.root-l2.txt [SHARD_MOUNT | reason:ROOT_CEILING_EJECTION]"]
        return {
            "TOKENME.root-l2.txt": unsharded_code_l2 + unsharded_asset_l2,
            "TOKENME.txt": header_lines + shard_mount_lines + mount,
        }

    out: dict[str, list[str]] = {}
    mounts = list(shard_mount_lines)
    if unsharded_code_l2:
        out["TOKENME.code.txt"] = unsharded_code_l2
        mounts.append("TOKENME.code.txt [SHARD_MOUNT | reason:ROOT_EJECTION_CODE]")
    if unsharded_asset_l2:
        out["TOKENME.assets.txt"] = unsharded_asset_l2
        mounts.append("TOKENME.assets.txt [SHARD_MOUNT | reason:ROOT_EJECTION_ASSETS]")
    out["TOKENME.txt"] = header_lines + mounts
    return out
```

---

## 4. Consequences & Trade-Offs

### Positive
* **Zero Dependency Bloat:** `tokenme-sync.py` remains 100% compliant with ADR-006 (pure Python 3 standard library), executing in milliseconds while deferring heavy OCR/Vision interpretation to the repository's active agent.
* **Zero Broken Relative Paths:** Keeping `L4` as an in-place logical tier with adjacent `.l3.txt` sidecars preserves all existing Markdown, CAD, and build paths.
* **Single-Hash Merkle Integrity:** Embedding `L4_SOURCE_HASH` inside the `.l3.txt` sidecar allows ADR-008's Merkle tree to verify both the raw binary and its semantic summary with a single file hash.
* **Hard-Bounded Root Token Ceiling:** Pass 1 (`OPAQUE_DENSITY`) + Pass 2 (`ROOT_CEILING_EJECTION`) mathematically guarantees that the root `TOKENME.txt` stays under $\sim 1,000$ tokens regardless of bulk photo dumps or flat repository layouts.

### Negative / Mitigated Risks
* **Two-Step Hydration Latency:** Newly added opaque assets or heavy PDFs initially appear as `STATUS: UNHYDRATED_STUB` until the repository agent runs its hydration pass. *Mitigation:* `tokenme-sync.py` flags `[NEEDS_HYDRATION]` in `TOKENME.txt` and pre-scrapes deterministic metadata/SVG strings so basic provenance is immediately available even before agent hydration.
* **Sidecar File Visibility:** Every `L4`-demoted heavy PDF/binary adds one visible `.l3.txt` file alongside it in the working tree. *Mitigation:* Only heavy assets breaching the `L4` demotion thresholds generate `.l3.txt` sidecars; standard `L3` images store their 3-line summaries inline inside their governing `TOKENME.txt` shard.