<!-- Target Path: docs/decisions/ADR-013_2026-11-13_Hysteresis-Shard-Compaction-And-Byte-Bounded-Guardbands.md -->
# ADR-013: Hysteresis-Gated Shard Compaction and Cross-Model Byte-Bounded Token Guardbands

* **Status:** Proposed
* **Date:** 2026-11-13
* **Author:** Elijah N. Dean, BSME (`endean-eng` / Dean Innovative Design LLC)
* **Target Specification:** `TOKENME` v2.0 (Hierarchical Sharding & Deterministic Sync Engine)
* **Supersedes / Refines:** Refines ADR-006 (`tokenme-sync.py` Zero-Dependency CLI), ADR-011 (Tiered Token Budget Matrix & Declarative Verification), and ADR-012 (Hop-Distance Sharding Threshold Relaxation & Cascade Guards)

---

## 1. Context & Problem Statement

As `TOKENME` v2.0 scales across heterogeneous repositories and multi-provider agentic workflows, two structural boundary problems emerge in the sharding and budget validation lifecycle:

### 1.1 Asymmetric Repository Growth and Post-Refactor Shard Fragmentation
File systems and source repositories exhibit overwhelmingly monotonic growth, making forward sharding (splitting a parent `TOKENME.txt` into child `TOKENME.<subsystem>.txt` shards when token capacity exceeds $T_{\text{split}}$) the dominant topological operation. However, major architectural refactors, subtree deletions, or the archival of heavy supporting documentation can drastically contract a directory's footprint.

Without a reverse coalescing mechanism ("de-sharding"), contracted subtrees leave behind fragmented, low-density "zombie shards" that force autonomous agents to execute unnecessary file-hop reads. Conversely, implementing naive automatic de-sharding whenever a shard drops below $T_{\text{split}}$ introduces two severe failure modes:
1. **Boundary Thrashing (State Oscillation):** If the coalescing threshold $T_{\text{merge}}$ is contiguous with the splitting threshold ($T_{\text{merge}} \approx T_{\text{split}}$), routine commits that add or remove a few lines of documentation near the boundary will cause `tokenme-sync.py` to repeatedly split and coalesce the shard across consecutive commits, polluting version control history with high-entropy file creation/deletion diffs.
2. **External Pointer Invalidation (URI Churn):** Active agent continuity briefs, parent manifests, and cross-shard references rely on stable relative paths (`@path/to/TOKENME.<subsystem>.txt`). Silent automatic deletion of a shard during a routine incremental sync invalidates external references mid-session.

### 1.2 Cross-Model Tokenizer Variance vs. Deterministic Zero-Dependency Validation
Prior `TOKENME` specifications (including ADR-011 and ADR-012) defined file blurb capacities and shard split thresholds strictly in terms of "token weight." While token counts map directly to LLM context-window consumption, relying on raw token counts as the primary unit of specification violates zero-dependency determinism and cross-provider portability:
1. **BPE Fertility Dispersion Across Model Families:** Byte-Pair Encoding (BPE) vocabulary sizes and pre-tokenization regexes vary widely across LLM providers (e.g., OpenAI `o200k_base` at 200k vocabulary vs. Llama 3 / DeepSeek at 128k vs. Anthropic Claude proprietary tokenizers vs. legacy 32k tokenizers). While standard English prose varies by only $\sim 8\%–21\%$, source code identifiers, file paths, JSON schemas, and mathematical notation exhibit **$15\%$ to $53\%$ token-count dispersion** for the exact same UTF-8 byte sequence.
2. **Autoregressive Token-Counting Blindness:** LLMs generate text autoregressively and cannot introspectively count their own exact BPE token output during generation within better than $\pm 15\%$ accuracy. Instructing an agent to author a blurb bounded strictly by a single token ceiling causes either premature self-truncation (information starvation on granular tokenizers) or frequent validation rejection loops.
3. **Zero-Dependency Standard Library Constraint:** By ADR-006, `tokenme-sync.py` must execute exclusively within the Python 3 standard library without requiring external compiled C/Rust BPE libraries (`tiktoken`, `tokenizers`) or network API calls to proprietary tokenization endpoints.

| Content Archetype | OpenAI (`o200k_base`) | Llama 3 / DeepSeek (128k BPE) | Anthropic (Claude 3.5 / 4 Est.) | Legacy / Compact (32k BPE) | Cross-Model Token Spread ($\Delta_{\max}$) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Dense Technical Prose** | $\sim 4.0\text{ chars/tok}$ ($1.00\times$) | $\sim 3.9\text{ chars/tok}$ ($1.03\times$) | $\sim 3.7\text{ chars/tok}$ ($1.08\times$) | $\sim 3.3\text{ chars/tok}$ ($1.21\times$) | **$8\% - 21\%$** |
| **Source Code / File Paths / JSON** | $\sim 3.1\text{ chars/tok}$ ($1.00\times$) | $\sim 2.9\text{ chars/tok}$ ($1.07\times$) | $\sim 2.7\text{ chars/tok}$ ($1.15\times$) | $\sim 2.2\text{ chars/tok}$ ($1.41\times$) | **$15\% - 41\%$** |
| **Mathematical / Regex / Symbolic** | $\sim 2.3\text{ chars/tok}$ ($1.00\times$) | $\sim 2.1\text{ chars/tok}$ ($1.10\times$) | $\sim 1.9\text{ chars/tok}$ ($1.21\times$) | $\sim 1.5\text{ chars/tok}$ ($1.53\times$) | **$21\% - 53\%$** |

> [!WARNING]
> Because proprietary model providers do not publish static open-weights BPE merge tables for all production checkpoints, exact single-integer token parity across heterogeneous agent swarms is mathematically unattainable without runtime API round-trips.

---

## 2. Decision & Governing Mechanics

`TOKENME` v2.0 resolves both vulnerabilities by adopting **(A) Hysteresis-Gated Explicit Shard Compaction** and **(B) Dual-Unit Byte-Primary / Conservative-Token-Secondary Guardbands**.

### 2.1 Hysteresis Deadband & Explicit `--compact` Shard Coalescing
Shard splitting and shard coalescing are governed by an asymmetric control-theory hysteresis deadband coupled with an explicit CLI execution gate:

1. **Forward Split Threshold ($T_{\text{split}}$):** A directory or subsystem triggers forward sharding when its aggregate conservative equivalent token load $T_{\text{eq}}$ exceeds $100\%$ of the hop-adjusted shard capacity defined in ADR-012.
2. **Reverse Merge Threshold ($T_{\text{merge}}$):** A child shard becomes eligible for coalescing back into its parent manifest only when **both** of the following conditions hold simultaneously:
   $$\text{(Condition 1: Local Underflow)} \quad T_{\text{eq}}(\text{shard}) \le 0.35 \times T_{\text{split}}$$
   $$\text{(Condition 2: Parent Absorption Headroom)} \quad T_{\text{eq}}(\text{parent}) + T_{\text{eq}}(\text{shard}) \le 0.65 \times T_{\text{split}}(\text{parent})$$
3. **Hysteresis Deadband ($0.35 \times T_{\text{split}} < T_{\text{eq}} \le 1.00 \times T_{\text{split}}$):** Within this $65\%$ deadband, existing shards remain structurally invariant regardless of minor fluctuations in file count or blurb length.
4. **Non-Destructive Default vs. Explicit `--compact` Mutation:**
   * **Standard Runs (`tokenme-sync.py` without `--compact`):** Never delete or coalesce an existing shard file automatically. If a shard satisfies Conditions 1 and 2, the CLI preserves the shard on disk to guarantee pointer stability and emits a non-blocking diagnostic warning:
     `[WARN: COMPACT_ELIGIBLE] Shard '<path>' is at <=35% capacity and fits within parent headroom (<=65%). Run with '--compact' to coalesce.`
   * **Explicit Compaction Runs (`tokenme-sync.py --compact`):** Splices all valid child blurb entries back into the parent `TOKENME.txt` in deterministic lexicographical path order, rewrites the parent routing pointers, deletes the redundant child `TOKENME.<subsystem>.txt` file, and recomputes the ADR-008 Merkle `STATE_ROOT` in a single atomic pass.

```mermaid
%%{init: {'theme': 'base', 'flowchart': {'wrappingWidth': 420, 'nodeSpacing': 40, 'rankSpacing': 45, 'curve': 'basis'}, 'themeVariables': { 'primaryColor': '#1e293b', 'primaryTextColor': '#f8fafc', 'primaryBorderColor': '#64748b', 'lineColor': '#94a3b8', 'edgeLabelBackground': '#1e293b', 'fontFamily': 'Consolas, monospace', 'fontSize': '16px'}}}%%
flowchart TB
    Start(["🚀 Invoke tokenme-sync.py on Repository Tree"])
    Calc["Compute UTF-8 Byte Length (B_utf8) &<br/>Conservative Equivalent Tokens (T_eq = ceil(B_utf8 / 2.8))"]
    DecSplit{"T_eq > 1.00 * T_split?<br/>(Forward Split Gate)"}
    ExecSplit["Execute Forward Sharding:<br/>Spawn Child TOKENME.&lt;subsystem&gt;.txt"]
    DecMerge{"T_eq(shard) <= 0.35 * T_split<br/>AND<br/>T_eq(parent + shard) <= 0.65 * T_split?"}
    Deadband["Hysteresis Deadband (35% - 100%):<br/>Preserve Existing Topology Unchanged"]
    DecFlag{"Is --compact CLI<br/>Flag Present?"}
    EmitWarn["Preserve Child Shard URI for Pointer Stability;<br/>Emit [WARN: COMPACT_ELIGIBLE] Advisory"]
    ExecCompact["Coalesce Child Blurbs into Parent TOKENME.txt,<br/>Delete Child Shard & Recompute Merkle STATE_ROOT"]
    Done(["✅ Sync Complete (Deterministic Tree State)"])

    Start ==> Calc
    Calc --> DecSplit
    DecSplit -- "YES (>100%)" --> ExecSplit
    DecSplit -- "NO (<=100%)" --> DecMerge
    DecMerge -- "NO (Inside Deadband)" --> Deadband
    DecMerge -- "YES (<=35% & Fits Parent)" --> DecFlag
    DecFlag -- "NO (Default Run)" --> EmitWarn
    DecFlag -- "YES (--compact)" ==> ExecCompact

    ExecSplit ==> Done
    Deadband ==> Done
    EmitWarn ==> Done
    ExecCompact ==> Done

    style DecSplit fill:#2e2310,stroke:#f59e0b,stroke-width:2px,color:#fde68a
    style DecMerge fill:#2e2310,stroke:#f59e0b,stroke-width:2px,color:#fde68a
    style DecFlag fill:#2e2310,stroke:#f59e0b,stroke-width:2px,color:#fde68a
    style ExecCompact fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5
    style ExecSplit fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#eff6ff
```

### 2.2 Dual-Unit Blurb & Shard Budgeting (UTF-8 Bytes Primary, $T_{\text{eq}}$ Secondary)
To eliminate external tokenizer dependencies while guaranteeing that no provider's context budget overflows, `TOKENME` v2.0 decouples **Agent Generation Constraints** (specified in UTF-8 bytes/characters) from **Shard Context Budgeting** (computed via a conservative worst-case code conversion factor $k_{\text{safe}}$):

1. **Deterministic Conservative Token Estimator ($T_{\text{eq}}$):**
   Instead of invoking model-specific BPE tables, `tokenme-sync.py` measures exact UTF-8 byte length $B_{\text{utf8}} = \text{len}(\text{text.encode('utf-8')})$ and computes Conservative Equivalent Tokens ($T_{\text{eq}}$) using a fixed worst-case technical/code fertility divisor of $k_{\text{safe}} = 2.8\text{ bytes/token}$:
   $$T_{\text{eq}} = \left\lceil \frac{B_{\text{utf8}}}{2.8} \right\rceil$$
   Because standard modern tokenizers achieve $3.1–4.0\text{ chars/token}$ on mixed technical markdown and $2.7–3.1\text{ chars/token}$ on dense code paths, budgeting shards via $k_{\text{safe}} = 2.8$ guarantees an automatic **$10\%$ to $30\%$ safety buffer** across OpenAI, Anthropic, Meta, and DeepSeek models with zero runtime dependencies.

2. **Soft Target vs. Hard Ceiling Validation Band ($\pm 25\%$ Tolerance):**
   To prevent LLM validation retry loops caused by autoregressive length-estimation error, every ADR-011 archetype tier is governed by a two-stage boundary:
   * **Soft Prompt Target ($B_{\text{target}}$ / $T_{\text{target}}$):** The nominal length instructed in the bootstrap prompt so agents aim for the center of the information-density distribution.
   * **Hard Validation Ceiling ($B_{\text{max}} = 1.25 \times B_{\text{target}}$):** The strict programmatic rejection threshold enforced by `tokenme-sync.py`. Entries between $B_{\text{target}}$ and $B_{\text{max}}$ pass validation cleanly (emitting only an informational telemetry note if $>1.15 \times B_{\text{target}}$).

| File / Logic Archetype Tier (Refines ADR-011) | Prompt Soft Target ($B_{\text{target}}$) | Validator Hard Ceiling ($B_{\text{max}} = 1.25 \times B_{\text{target}}$) | Nominal OpenAI Token Range ($\sim 3.8\text{ B/tok}$) | Conservative Budget Weight ($T_{\text{eq}} = \lceil B / 2.8 \rceil$) | Max Structural Lines |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 0: Static Assets / Lockfiles / Fixtures** | $140\text{ B}$ | $175\text{ B}$ | $35 - 46\text{ tok}$ | $50\text{ tok}$ ($63\text{ tok max}$) | $1\text{ line}$ |
| **Tier 1: Standard Leaf Modules / Utilities / Configs** | $340\text{ B}$ | $425\text{ B}$ | $85 - 112\text{ tok}$ | $122\text{ tok}$ ($152\text{ tok max}$) | $2\text{ lines}$ |
| **Tier 2: Core Domain Engines / Stateful Services** | $680\text{ B}$ | $850\text{ B}$ | $175 - 224\text{ tok}$ | $243\text{ tok}$ ($304\text{ tok max}$) | $4\text{ lines}$ |
| **Tier 3: Root Orchestrators / Public API Contracts** | $1,120\text{ B}$ | $1,400\text{ B}$ | $290 - 368\text{ tok}$ | $400\text{ tok}$ ($500\text{ tok max}$) | $6\text{ lines}$ |
| **Shard Split Threshold ($T_{\text{split}}$, Hop $d=0$)** | $11,200\text{ B}$ | $14,000\text{ B}$ | $2,950 - 3,680\text{ tok}$ | $4,000\text{ tok}$ ($5,000\text{ tok max}$) | N/A |
| **Shard Merge Threshold ($T_{\text{merge}} = 0.35 \times T_{\text{split}}$)** | $\le 3,920\text{ B}$ | $\le 4,900\text{ B}$ | $\le 1,030 - 1,290\text{ tok}$ | $\le 1,400\text{ tok}$ | N/A |

> [!NOTE]
> By instructing agents in **UTF-8 characters/bytes and line counts** (e.g., *"Summarize Tier 1 modules in $\le 2$ lines and $\sim 340$ characters, hard cap $425$ bytes"*) rather than raw BPE tokens, any LLM from any vendor produces compliant, uniformly dense blurbs on Pass 1 while `tokenme-sync.py` enforces byte and $T_{\text{eq}}$ ceilings in $O(1)$ time via standard-library UTF-8 encoding.

---

## 3. Rejected Alternatives & Technical Postmortems (DO NOT RE-IMPLEMENT)

* **Rejected Option 1 (Automatic Real-Time Shard Coalescing on Every Sync Run):**
  * *Postmortem:* Automatically folding child shards into parent manifests whenever token count drops below a threshold during standard `tokenme-sync.py` runs violates URI permanence. Any external active brief, developer note, or in-flight agent context holding a pointer to `TOKENME.<subsystem>.txt` encounters a `FileNotFoundError` after a routine sync. Furthermore, dynamic B-tree rebalancing during standard check passes couples read-only verification with destructive file deletion. Coalescing must remain strictly opt-in via `--compact`.
* **Rejected Option 2 (Single-Threshold Split/Merge Boundary Without Hysteresis, $T_{\text{merge}} = T_{\text{split}}$):**
  * *Postmortem:* Without a wide deadband between $T_{\text{merge}}$ ($35\%$) and $T_{\text{split}}$ ($100\%$), a shard hovering near $100\%$ capacity will split when a single file is added and immediately re-merge if a blurb is edited down by a single sentence on the next commit. Additionally, checking only child shard size without verifying parent absorption headroom ($T_{\text{eq}}(\text{parent}) + T_{\text{eq}}(\text{shard}) \le 0.65 \times T_{\text{split}}(\text{parent})$) causes the parent to immediately re-exceed $T_{\text{split}}$ on the subsequent run, creating an infinite split-coalesce oscillation loop.
* **Rejected Option 3 (Bundling `tiktoken` or HuggingFace `tokenizers` in `tokenme-sync.py`):**
  * *Postmortem:* Importing compiled Rust/C BPE tokenizers directly violates the ADR-006 zero-dependency Python 3 standard-library invariant, breaks air-gapped portability on minimal environments, and still locks the specification to a single vendor's vocabulary (`o200k_base`), leaving Anthropic, Llama, and DeepSeek variance unaddressed.
* **Rejected Option 4 (Word-Count or Line-Count-Only Blurb Specifications):**
  * *Postmortem:* Whitespace-delimited word counts fail catastrophically on camelCase/snake_case identifiers, URLs, file paths, and inline JSON signatures, where a single 80-character path counts as "1 word" but consumes 25–35 BPE tokens. UTF-8 byte length combined with a structural line cap bounds both visual vertical footprint and worst-case BPE token expansion.

---

## 4. Consequences & Engineering Trade-Offs

### Positive Outcomes
* **Zero-Dependency Cross-Model Determinism:** `B_utf8 = len(text.encode('utf-8'))` and $T_{\text{eq}} = \lceil B_{\text{utf8}} / 2.8 \rceil$ produce identical integer results across every OS, Python 3.8+ runtime, and LLM provider with zero external packages.
* **Elimination of Validation Retry Loops:** The $25\%$ soft-to-hard guardband ($B_{\text{target}}$ vs. $B_{\text{max}}$) absorbs natural LLM length-estimation variance while preventing unconstrained context bloat.
* **Pointer Stability & Zero Thrashing:** The $35\% / 100\%$ hysteresis deadband plus the $65\%$ combined parent-absorption ceiling mathematically prevents split-merge oscillation, while gating execution behind `--compact` guarantees that shard URIs never vanish unexpectedly during routine syncs.

### Accepted Trade-Offs & Downstream Constraints
* **Conservative Context Utilization Under OpenAI Tokenizers:** Because $k_{\text{safe}} = 2.8\text{ B/tok}$ is calibrated for worst-case code/path tokenization across granular BPE vocabularies, a shard hitting $T_{\text{eq}} = 4,000$ ($11,200\text{ B}$) will consume only $\sim 2,950–3,200$ actual tokens under OpenAI `o200k_base`. This $\sim 20\%$ unused headroom under high-efficiency tokenizers is intentionally accepted as the cost of cross-model safety.
* **Manual Compaction Cadence:** Because `--compact` is opt-in, suboptimally small shards ($\le 35\%$) will persist as advisory warnings until an operator or maintenance agent explicitly invokes `python tokenme-sync.py --compact` during scheduled repository hygiene or post-refactor cleanup.