# ADR-011: Self-Consuming Bootstrap Prompts, Polymorphic Structural Hashing, and Tiered Token Budgets

* **Status:** Proposed
* **Date:** 2026-11-12
* **Author:** Elijah N. Dean, BSME (`endean-eng` / Dean Innovative Design LLC)
* **Target Specification:** `TOKENME` v2.0 & `tokenme-sync.py` CLI
* **Supersedes / Refines:** Extends ADR-002 (Plain-Text `.txt` Convention), ADR-003 (Hierarchical Sharding), ADR-006 (`tokenme-sync.py` Zero-Dependency CLI), ADR-008 (Multi-Tier Merkle Epistemic State Root), and ADR-010 (HC-02 Subsystem Shard Naming)

---

## 1. Context & Problem Statement

Deterministic AST scanners (`tokenme-sync.py`) extract static symbol signatures (`def`, `class`, module constants) with $O(N)$ reliability and zero hallucination risk. However, purely syntactic symbol catalogs leave four structural gaps across software, hardware/engineering, and enterprise repositories:

1. **Missing Macro-Boundary Context (`[PURPOSE]`):** Static file and symbol lists do not declare a repository's overarching physical, logical, or operational transformation, input/output boundary, or runtime/regulatory constraints. Without a bounded declarative summary inside `TOKENME.txt`, an autonomous agent must either guess system boundaries from filenames or ingest `README.md`—which mixes marketing prose and onboarding tutorials into the active context window.
2. **Invisible Cross-Artifact Coupling (`[TOPOLOGY]`):** Isolated file inspection cannot capture non-obvious cross-file control flow, implicit state mutations, or governing constraint propagation (e.g., a hydraulic pressure ceiling in a config file governing wall-thickness equations in an engineering calculation sheet, or an ADR clause governing an `AGENTS.md` rule).
3. **Domain Lock-In from Code-Only Endpoint Grammars:** While software repositories are the primary target where peak AST analysis lives, restricting `[TOPOLOGY]` endpoints strictly to Python/C identifier syntax (`[a-zA-Z_][a-zA-Z0-9_]*`) prevents `TOKENME` from indexing engineering bills of materials (BOM part numbers), technical specification clauses, CAD/schematic surrogates, and enterprise policy dossiers.
4. **Uncalibrated Token Allocation Across Logic Levels and File Archetypes:** Applying a uniform token cap across all `TOKENME` files and source artifacts wastes tokens on boilerplate files (`__init__.py`, test suites) while starving high-complexity orchestrators, and fails to distinguish between a Pure L1 Root Router (`TOKENME.txt`), an L2 Subsystem Shard (`TOKENME.<subsystem>.txt`), and an L3 Binary Surrogate Sidecar (`<asset>.l3.txt`).

Integrating LLM-authored semantic blocks (`[PURPOSE]` and `[TOPOLOGY]`) into a deterministic state file also introduces a severe epistemic hazard: **Stale Declarative Drift vs. The Avalanche Re-Hydration Problem**.

* **The Loose Existence Trap:** If `tokenme-sync.py` only checks whether a function name, section heading, or BOM row key still exists (`key in symbol_set`), a developer can rewrite `process_data()`—changing its parameters, return type, and outbound call graph—or alter a pressure value in a BOM row while the identifier name remains unchanged. The declarative edge in `[TOPOLOGY]` silently becomes a lie.
* **The Raw Byte-Hash Avalanche Trap:** Conversely, if `tokenme-sync.py` locks declarative fields to raw file byte hashes (`SHA-256` per ADR-008), fixing a typo in a comment, editing narrative prose in a specification, or running a code formatter changes the file hash and triggers staleness flags all the way up and down the shard tree—forcing expensive, unnecessary LLM I/O when zero structural or behavioral boundaries changed.
* **Redundant Multi-Pass Overhead & `AGENTS.md` Token Tax:** Layering a structural hash validator on top of a separate symbol-existence checker duplicates AST traversals and memory state, while storing lengthy initialization schemas inside `AGENTS.md` permanently taxes every subsequent coding turn ($T \ge 1$).

---

## 2. Decision & Governing Mechanics

We introduce two bounded semantic blocks—`[PURPOSE]` and `[TOPOLOGY]`—and a **3-Tier Token Budget Matrix** into the `TOKENME` v2.0 specification, governed by a **Unified Single-Pass Polymorphic Scanner & Structural Hasher** in `tokenme-sync.py`:

1. **In-Place Self-Consuming Bootstrap Prompts ($T=0 \rightarrow T=1$ Ephemeral Instruction State)**
2. **Polymorphic `<Artifact::Anchor>` Grammar & Unified Structural Hashing (`[#sig:xxxxxx]`)**
3. **Macro-Topology Digest Insulation for `[PURPOSE]` (Zero Tree-Cascade)**
4. **Archetype- and LOC-Calibrated Token Budgets with 3-Stage Progressive AST Pruning**

### 2.1 In-Place Self-Consuming Bootstrap Mechanism

Rather than bloating `AGENTS.md` with multi-line formatting schemas and token tables for `[PURPOSE]` and `[TOPOLOGY]`, `tokenme-sync.py` dynamically computes the target file's token and edge budget based on its logic tier (Root vs. Shard) and injects domain-inclusive constraints directly into `TOKENME.txt` as comment blocks tagged with `[BOOTSTRAP_REQUIRED]` whenever a section is uninitialized.

```mermaid
%%{init: {'theme': 'base', 'flowchart': {'wrappingWidth': 380, 'nodeSpacing': 38, 'rankSpacing': 42, 'curve': 'basis'}, 'themeVariables': { 'primaryColor': '#1e293b', 'primaryTextColor': '#f8fafc', 'primaryBorderColor': '#64748b', 'lineColor': '#94a3b8', 'edgeLabelBackground': '#1e293b', 'fontFamily': 'Consolas, monospace', 'fontSize': '15px'}}}%%
flowchart TB
    Start(["🚀 Run tokenme-sync.py"]) --> SinglePass["Single-Pass Scan: Build Unified Polymorphic workspace_sig_map & 3-Stage Pruned [SYMBOLS]"]
    SinglePass --> DecPopulated{"Are [PURPOSE] & [TOPOLOGY]<br/>Blocks Populated?"}

    DecPopulated -- "NO (State T=0)" --> InjectBootstrap["Inject Tier-Calibrated [BOOTSTRAP_REQUIRED] Prompts"]
    InjectBootstrap --> AgentPass["Agent Consumes Prompt & Writes Plain KV / Edge Lines (No Manual Hashes)"]
    AgentPass --> ReSync["Next tokenme-sync.py Pass Auto-Stamps [#sig:xxxxxx] Locks"]
    ReSync ==> CleanState(["✅ State T=1: Cryptographically Locked & Zero Prompt Overhead"])

    DecPopulated -- "YES (State T>=1)" --> LookupMap{"Are <Artifact::Anchor> Endpoints<br/>in workspace_sig_map?"}
    LookupMap -- "NO (Deleted / Renamed)" --> HardFail["Inject # [STALE_EDGE]<br/>Exit Code 2 (Hard Fail)"]
    LookupMap -- "YES (Anchor Exists)" --> CompareSig{"Does Embedded [#sig:xxxxxx]<br/>Match Live Structural Sig?"}

    CompareSig -- "YES (Comments / Prose Typos / Local Edits)" ==> ZeroIO(["✅ Zero LLM I/O: Keep Declarative & Update Line-1 STATE_ROOT"])
    CompareSig -- "NO (AST Call Graph, Equation, or BOM Row Changed)" --> SoftDrift["Inject # [SIG_DRIFT: old -> new]<br/>Agent Verifies & Deletes [#sig] to Re-Lock"]

    style DecPopulated fill:#2e2310,stroke:#f59e0b,stroke-width:2px,color:#fde68a
    style LookupMap fill:#2e2310,stroke:#f59e0b,stroke-width:2px,color:#fde68a
    style CompareSig fill:#2e2310,stroke:#f59e0b,stroke-width:2px,color:#fde68a
    style CleanState fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5
    style ZeroIO fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5
    style HardFail fill:#450a0a,stroke:#ef4444,stroke-width:2px,color:#fef2f2
    style SoftDrift fill:#3b2f0b,stroke:#eab308,stroke-width:2px,color:#fef08a
```

#### State $T=0$ Template (Emitted by `tokenme-sync.py` for Root `TOKENME.txt`)

```ini
# === [PURPOSE] ===
# [BOOTSTRAP_REQUIRED: POPULATE_PURPOSE | TIER=L1_ROOT | MAX_TOKENS=60 | MAX_CHARS=360]
# INSTRUCTION: Replace this comment block with declarative lines (omit [#sig:...]; auto-stamped on sync).
# CONSTRAINTS: Zero marketing prose. Strict key-value format:
#   SYSTEM: <1-sentence physical, logical, or operational transformation>
#   BOUNDARY: <Primary inputs / upstream specs> -> <Primary outputs / deliverables>
#   RUNTIME: <Execution environment, target hardware, or governing standard>

# === [TOPOLOGY] ===
# [BOOTSTRAP_REQUIRED: POPULATE_TOPOLOGY | TIER=L1_ROOT | TARGET_EDGES=4..8 | MAX_TOKENS=240]
# INSTRUCTION: Trace non-obvious cross-file coupling, execution flow, state mutations,
# or governing constraint propagation not visible in isolated file listings.
# CONSTRAINTS: Max 8 edges (<=140 chars/mechanism). Omit [#sig:...]; auto-stamped on sync.
# ANCHOR SYNTAX: Symbol (file.py::func), Section (doc.md::[slug-name]), Record (bom.csv::@PART-ID), or Wildcard (file.ext::*).
# FORMAT: <SourceFile::Anchor> -> <TargetFile::Anchor> : <Coupling mechanism / constraint / side-effect>
```

#### State $T=1$ Artifact (Post-LLM Pass + Auto-Stamped by `tokenme-sync.py`)

```ini
# === [PURPOSE] ===
SYSTEM: Deterministic AST scanner and declarative context compiler for multi-agent repositories.
BOUNDARY: Source directory tree + existing TOKENME.txt -> Sharded symbol catalog + Merkle STATE_ROOT. [#sig:4b9e1a]
RUNTIME: Python >=3.10 standard library (zero external pip dependencies).

# === [TOPOLOGY] ===
tokenme-sync.py::scan_and_hash_python_ast -> TOKENME.txt::[SYMBOLS] : Single-pass AST walk builds unpruned sig map and 3-stage pruned display entry. [#sig:a4f9c1]
tokenme-sync.py::validate_and_lock_topology -> TOKENME.txt::[TOPOLOGY] : Verifies polymorphic <File::Anchor> endpoints, auto-stamps [#sig], and flags drift. [#sig:c82d09]
```

#### Minimal `AGENTS.md` Maintenance Hook

Because tier-specific budgets and formatting schemas live inline at $T=0$ and self-destruct upon completion, `AGENTS.md` requires only a compact $O(1)$ maintenance directive:

> `- **TOKENME Bootstrap, Topology Drift & Signature Locks (ADR-011):** If any TOKENME file contains [BOOTSTRAP_REQUIRED], [STALE_EDGE], [SIG_DRIFT], or [BUDGET_EXCEEDED], execute the inline repair before concluding the task. Never manually write [#sig:xxxxxx] tags; write clean declarative lines (or delete an outdated [#sig:xxxxxx] tag after verifying a [SIG_DRIFT] warning) and run python tokenme-sync.py to auto-stamp the cryptographic lock.`

### 2.2 Polymorphic `<Artifact::Anchor>` Grammar & Unified Structural Hashing (`[#sig:xxxxxx]`)

To support code repositories at peak AST fidelity while accommodating engineering, hardware, and enterprise file trees, `tokenme-sync.py` builds a single unified dictionary during its workspace scan—`workspace_sig_map: Dict[FileRelPath, Dict[AnchorKey, 6HexSig]]`—which simultaneously governs **Anchor Existence** (`anchor in workspace_sig_map[file]`) and **Structural Stability** (`workspace_sig_map[file][anchor]`).

#### A. The 4 Polymorphic Anchor Classes

| Anchor Class | Syntax Pattern | Software Repo Target | Engineering / Enterprise Target | What `workspace_sig_map` Hashes (Triggers `# [SIG_DRIFT]`) | What is Ignored (Zero Churn / Zero LLM I/O) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Code / Schema Identifier** | `file.ext::Identifier` | AST `def`, `class`, `Class.method`, module constant, or JSON/YAML key. | Config parameter, CSV/TSV column name, or script target. | **Code:** Function/class name, arg names/types, return type, decorators, **sorted outbound `ast.Call` set**, and state effects (`global`, `yield`, `await`, `raise`).<br/>**Config:** Key name + value type/sub-keys. | Comments, docstrings, blank lines, code formatting (`black`/`ruff`), local variable renames, and literal string/number tweaks inside code bodies. |
| **2. Section / Clause Slug** | `file.ext::[Section-Slug]` | `TOKENME.txt::[SYMBOLS]` | Markdown/ADR/Spec section (`calc.md::[2.1-burst-margin]`) or L3 PDF page (`manual.l3.txt::[PAGE_04]`). | **Section Structural Skeleton:** Sub-headings, `$$...$$` display equations, GFM pipe table rows, fenced code blocks, and bold metadata bullets inside that section. | Narrative prose edits, spelling/grammar fixes, and line wrapping inside paragraphs. |
| **3. Record / BOM Row Key** | `file.ext::@KEY_ID` | Route or decorator target. | Specific BOM row (`bom.csv::@AFC-190-12V`) or inline spec requirement (`spec.md::@REQ-04`). | Normalized cell tuple of that specific CSV/TSV row or requirement definition line. | Edits to any *other* row in the CSV/BOM table or unrelated lines in the spec. |
| **4. Artifact Wildcard** | `file.ext::*` | Whole-module public API surface. | Opaque CAD model (`frame.step::*`), schematic PDF, or image. | Digest of all public module symbols/sections, or ADR-009 Opaque Gate metadata prefix. | Private `_helper` additions or internal comments. |

For every directed edge `<src_file>::<src_anchor> -> <dst_file>::<dst_anchor>` in `[TOPOLOGY]`, `tokenme-sync.py` computes the joint structural lock:

$$\text{EDGE\_SIG} = \text{SHA256}\Big(\text{src\_file::src\_anchor}=\text{SIG\_HASH}(\text{src}) \;\rightarrow\; \text{dst\_file::dst\_anchor}=\text{SIG\_HASH}(\text{dst})\Big)_{[0:6]}$$

#### B. Cascade Insulation for `[PURPOSE]`

To prevent leaf file edits from cascading up the directory tree and invalidating `[PURPOSE]` blocks, `tokenme-sync.py` locks the `BOUNDARY:` (or `SUMMARY:`) line of `[PURPOSE]` to a **Macro-Topology Digest** rather than file contents:

| Declarative Field | What its `[#sig:xxxxxx]` Locks Against | What Triggers `# [SIG_DRIFT]` | What is Ignored (Zero Cascade) |
| :--- | :--- | :--- | :--- |
| **`[TOPOLOGY]` Edge** | `SHA256(src_sig + "->" + dst_sig)[:6]` | Changing args, return types, outbound function calls, section equations/tables, or target BOM row values on `src` or `dst`. | Comments, docstrings, narrative prose fixes, or edits to unrelated functions/rows in the same file. |
| **Shard `[PURPOSE]`** (`L2_SHARD`) | `SHA256(SortedShardFilePaths)[:6]` | Adding, deleting, or renaming files within that subsystem shard. | All edits inside existing shard files. |
| **Root `[PURPOSE]`** (`L1_ROOT` / `L1_MONO`) | `SHA256(TopLevelDirs + EntrypointFiles + Manifests)[:6]` | Adding a new top-level directory, adding/renaming a CLI orchestrator file, or adding a dependency/BOM manifest. | **99% of routine commits.** Leaf file, function, and document edits never bubble up to Root `[PURPOSE]`. |

#### C. Two-Tier Diagnostic Severity & Touch-to-Acknowledge Workflow

1. **Initial Authoring ($T=0 \rightarrow T=1$):** The agent writes plain declarative text in `[PURPOSE]` and `[TOPOLOGY]` without any `[#sig:xxxxxx]` tag. Running `python tokenme-sync.py` validates the syntax and deterministically appends `[#sig:xxxxxx]`.
2. **Hard Fail (`# [STALE_EDGE]`):** If `src_file`, `dst_file`, `src_anchor`, or `dst_anchor` is deleted or renamed (`key not in workspace_sig_map`), `tokenme-sync.py` prepends `# [STALE_EDGE: Symbol '<file>::<anchor>' missing from AST/structure. Update or remove edge.]` and exits with code `2` under `--check`.
3. **Soft Audit (`# [SIG_DRIFT]`):** If both anchors still exist in `workspace_sig_map` but the embedded `[#sig:old]` mismatches the live `EDGE_SIG`, `tokenme-sync.py` prepends `# [SIG_DRIFT: Structural signature shifted (old -> new). Verify edge accuracy, then delete [#sig:old] to re-lock.]`. The agent inspects the target, updates the edge description if the mechanism changed (or leaves it unchanged if still accurate), **deletes `[#sig:old]`**, and re-runs `python tokenme-sync.py` to stamp `[#sig:new]`.

### 2.3 Formal Grammar & Regular Expression Validators

Freeform narrative paragraphs are strictly prohibited in both blocks. Using the standard approximation $1\text{ token} \approx 4.0\text{ ASCII characters}$ ($6.0\text{ chars/token}$ upper bound for dense identifiers), `tokenme-sync.py` enforces deterministic byte/character and line bounds via Python `re`:

| Target Block | Validation Rule | Python `re` Pattern / Enforcement |
| :--- | :--- | :--- |
| **`[PURPOSE]` Keys** | 3 lines (`SYSTEM:`, `BOUNDARY:`, `RUNTIME:`); `BOUNDARY:` auto-stamped with `[#sig:xxxxxx]`. | `^SYSTEM:\s+\S.*\$`<br/>`^BOUNDARY:\s+\S.*\s->\s\S.*(?:\s+\[#sig:[0-9a-f]{6}\])?$`<br/>`^RUNTIME:\s+\S.*$` |
| **`[TOPOLOGY]` Edge** | `<File::Anchor> -> <File::Anchor> : <Mechanism> [#sig:xxxxxx]` | `^(?P<src_file>[a-zA-Z0-9_./-]+)::(?P<src_sym>[a-zA-Z0-9_][a-zA-Z0-9_.-]*\|@[a-zA-Z0-9_.-]+\|\[[a-zA-Z0-9_.: -]+\]\|\*)\s->\s(?P<dst_file>[a-zA-Z0-9_./-]+)::(?P<dst_sym>[a-zA-Z0-9_][a-zA-Z0-9_.-]*\|@[a-zA-Z0-9_.-]+\|\[[a-zA-Z0-9_.: -]+\]\|\*)\s:\s(?P<mech>.{1,140}?)(?:\s*\[#sig:(?P<sig>[0-9a-f]{6})\])?\$` |

### 2.4 Tiered Token Budget Matrix & 3-Stage Progressive AST Pruning

#### A. Macro-File Budgets (`TOKENME` State Artifacts)

| State Artifact Tier | Logic Level | Target Token Range | Hard Ceiling (Tokens / Lines) | `[PURPOSE]` Ceiling (Excl. `#sig`) | `[TOPOLOGY]` Edge Range & Ceiling |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Monolithic `TOKENME.txt`** *(Unsharded repo)* | **L1 + L2 Combined** | $600\text{ – }2,000\text{ tok}$ | $\le 3,000\text{ tok}$ / $\le 250\text{ lines}$ *(Sharding Trigger)* | $\le 60\text{ tok}$ ($\le 360\text{ chars}$) | **4 – 8 edges** ($\le 240\text{ tok}$ total) |
| **Root Router `TOKENME.txt`** *(Sharded repo)* | **Pure L1 Router** | $350\text{ – }750\text{ tok}$ | $\le 1,000\text{ tok}$ / $\le 150\text{ lines}$ *(Pass-2 Ejection Trigger)* | $\le 60\text{ tok}$ ($\le 360\text{ chars}$) | **3 – 6 inter-shard edges** ($\le 180\text{ tok}$ total) |
| **Subsystem Shard** (`TOKENME.<subsystem>.txt`) | **L2 Domain Index** *(Default Shard Tier)* | $500\text{ – }1,500\text{ tok}$ | $\le 2,000\text{ tok}$ / $\le 200\text{ lines}$ | $\le 45\text{ tok}$ ($\le 270\text{ chars}$) | **2 – 6 intra-shard edges** ($\le 180\text{ tok}$ total) |
| **Surrogate Sidecar** (`<asset>.l3.txt`) | **L3 Binary Map** | $250\text{ – }800\text{ tok}$ | $\le 1,200\text{ tok}$ / $\le 120\text{ lines}$ | $\le 25\text{ tok}$ ($\le 150\text{ chars}$) | **0 edges** *(Uses Page/Section map)* |

#### B. Per-File Entry Budgets Inside `[SYMBOLS]` (Archetype & LOC Scaling)

For each repository file indexed inside a `[SYMBOLS]` block, `tokenme-sync.py` computes a dynamic token ceiling $B_{\text{file}}$ as a logarithmic function of effective non-blank, non-comment lines ($L_{\text{eff}}$):

$$B_{\text{file}} = \min\left( B_{\text{max}}, \; B_{\text{base}} + \left\lfloor k \cdot \log_2\left(\max\left(1, \frac{L_{\text{eff}}}{50}\right)\right) \right\rfloor \right)$$

| File Archetype & Common Extensions | Base Target ($B_{\text{base}}$, $<100\text{ LOC}$) | LOC Scaling Factor ($k$) | Hard Ceiling ($B_{\text{max}}$, $>500\text{ LOC}$) | Indexed Scope & Pruning Policy |
| :--- | :--- | :--- | :--- | :--- |
| **DEFAULT (Unclassified Source/Text)** | **$20\text{ – }35\text{ tok}$** | $+10\text{ tok}$ | **$\le 75\text{ tok}$** | Path + 1-line summary + exported top-level identifiers/anchors. |
| **1. Core Orchestrators & Entry Points** (`main.py`, `cli.py`, `*-sync.py`, `index.ts`, `App.tsx`) | **$45\text{ – }70\text{ tok}$** | $+20\text{ tok}$ | **$\le 140\text{ tok}$** | Full public signatures, CLI dispatch flags, and primary `[TOPOLOGY]` anchors. |
| **2. Standard Domain Modules** (`*.py`, `*.ts`, `*.js`, `*.rs`, `*.go`, `*.c`, `*.cpp`) | **$30\text{ – }50\text{ tok}$** | $+15\text{ tok}$ | **$\le 110\text{ tok}$** | Public classes, methods, functions, and constants (progressive pruning above $150\text{ LOC}$). |
| **3. Schemas, Configs, BOMs & Contracts** (`*.json`, `*.yaml`, `*.toml`, `*.sql`, `*.csv`, `types.ts`, `Parameters.gs`) | **$20\text{ – }40\text{ tok}$** | $+8\text{ tok}$ | **$\le 65\text{ tok}$** | Top-level keys/columns, row counts, schema invariants, and env bindings (raw bulk values omitted). |
| **4. Package Barrels & Glue** (`__init__.py`, `mod.rs`, `index.js` re-exports) | **$10\text{ – }20\text{ tok}$** | $0\text{ tok}$ *(Flat)* | **$\le 25\text{ tok}$** | Single-line re-export list (`Exports: [SymA, SymB]`). |
| **5. Automated Test Suites** (`test_*.py`, `*.spec.ts`, `*_test.go`) | **$10\text{ – }25\text{ tok}$** | $+5\text{ tok}$ | **$\le 40\text{ tok}$** | Tested target module + test case count (`[TEST_SUITE: 14 tests, 210 LOC]`). Individual `test_*` names stripped. |
| **6. Build, CI & Automation Scripts** (`Makefile`, `*.ps1`, `*.sh`, `Dockerfile`, `*.yml`) | **$15\text{ – }30\text{ tok}$** | $+5\text{ tok}$ | **$\le 45\text{ tok}$** | Exposed CLI targets/tasks and filesystem I/O boundary. |
| **7. Governance, Specs & Architecture Docs** (`ADR-*.md`, `AGENTS.md`, `README.md`, `*.md`) | **$15\text{ – }30\text{ tok}$** | $0\text{ tok}$ *(Flat)* | **$\le 35\text{ tok}$** | Record ID, Lifecycle Status, section slugs, and 1-line governing rule. |
| **8. Opaque Assets, CAD & Schematics** (`*.svg`, `*.png` $>128\text{px}$, `*.pdf`, `*.step`, `*.dxf`) | **$15\text{ – }35\text{ tok}$** | $0\text{ tok}$ *(Flat)* | **$\le 45\text{ tok}$** | SHA-256 prefix, dimensions/pages/bounding-box, scraped metadata, and `.l3.txt` pointer if demoted. |

#### C. 3-Stage Progressive AST Pruning & Unpruned Signature Retention

When a source module's raw AST symbol list exceeds $B_{\text{file}}$, `scan_and_hash_python_ast()` compresses its `[SYMBOLS]` display string across three stages while recording **all** symbols (including `_private` helpers) into `workspace_sig_map`:

1. **Stage 0 ($L_{\text{eff}} < 150$ and $\text{Tokens} \le B_{\text{file}}$ — Full Resolution):** Displays all constants, classes, methods (including `_protected` helpers), and arities.
2. **Stage 1 ($L_{\text{eff}} \ge 150$ or Stage 0 $> B_{\text{file}}$ — Public API Resolution):** Strips `_private` symbols from the display string (preserving `__init__` and `__call__`).
3. **Stage 2 (Stage 1 $> B_{\text{file}}$ — Arity Folding):** Folds classes with $>6$ public methods into compact summary notation (`ClassName[m1/1, m2/2, ..., +4 more]`) to guarantee compliance with $B_{\text{max}}$.

---

## 3. Rejected Alternatives & Technical Postmortems (DO NOT RE-IMPLEMENT)

* **Rejected Option 1 (Separate AST Existence Checker + Layered Hash Validator):** Implementing an AST symbol-existence pass (`Set[str]`) and subsequently layering a separate structural hash checker duplicates AST walks and memory state. Unifying both into `workspace_sig_map: Dict[str, Dict[str, str]]` makes the standalone existence-checker obsolete: key lookup (`anchor in workspace_sig_map[file]`) verifies existence, while value comparison (`workspace_sig_map[file][anchor]`) verifies structural stability in a single $O(1)$ lookup.
* **Rejected Option 2 (Code-Only Identifier Regex for `[TOPOLOGY]`):** Restricting endpoint symbols strictly to `[a-zA-Z_][a-zA-Z0-9_.]*` prevents `TOKENME` from linking Markdown specification sections (`[2.1-burst-margin]`) or engineering BOM records (`@AFC-190-12V`). The 4-class Polymorphic Anchor regex supports software AST symbols alongside section slugs, record keys, and wildcards without weakening deterministic validation.
* **Rejected Option 3 (Locking Declaratives to Raw File Byte Hashes):** Binding `[PURPOSE]` or `[TOPOLOGY]` staleness to raw file SHA-256 hashes causes every comment addition, narrative prose typo fix, or whitespace formatting pass to invalidate declarative blocks all the way up and down the shard tree. Hashing only normalized AST interface contracts, section structural skeletons (equations/tables/code), and specific BOM row tuples isolates declarative reviews strictly to genuine behavioral/structural mutations.
* **Rejected Option 4 (Permanent Schema Instructions in `AGENTS.md`):** Placing 40+ lines of `[PURPOSE]` and `[TOPOLOGY]` formatting examples inside `AGENTS.md` imposes a permanent per-turn token overhead across thousands of routine coding turns after initialization is already complete. The in-place `[BOOTSTRAP_REQUIRED]` pattern reduces steady-state `AGENTS.md` overhead by $>90\%$.
* **Rejected Option 5 (External Tokenizer Dependency like `tiktoken`):** Importing `tiktoken` or `transformers` to count exact BPE tokens violates ADR-006 (Zero-Dependency Python Standard Library CLI) and requires binary wheel compilation. Enforcing dual bounds—character-based token estimation ($\approx \text{chars} / 4.0$) paired with strict byte/character and line ceilings—achieves deterministic enforcement using pure Python `len()` and `re`.

---

## 4. Consequences & Engineering Trade-Offs

* **Cross-Domain Portability with Code-First Precision:** Software repositories receive full AST interface and outbound call-graph drift detection, while hardware, CAD/BOM, and enterprise document repositories use the exact same `tokenme-sync.py` CLI to lock cross-document sections (`[slug]`) and tabular part records (`@PartID`).
* **Zero False-Positive Re-Hydration Churn:** Developers and engineers can freely edit code comments, docstrings, and narrative specification prose without triggering `[SIG_DRIFT]` or spending LLM tokens re-verifying `[TOPOLOGY]` or `[PURPOSE]`.
* **Two-Step Touch-to-Acknowledge Lifecycle:** Freshly authored or repaired declarative lines omit `[#sig:xxxxxx]` and are automatically stamped by `tokenme-sync.py` on the subsequent sync pass before `python tokenme-sync.py --check` returns `\033[92mCLEAN\033[0m` (exit code `0`).