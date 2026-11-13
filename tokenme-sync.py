#!/usr/bin/env python3
"""
tokenme-sync.py (v2.1.1)
Zero-dependency, fail-closed structural reference scaffolder, polymorphic AST/structural
signature locker, hop-distance sharding & hysteresis engine, deterministic agent triage
dispatcher, and Multi-Tier Merkle state synchronizer for the TOKENME (v2.1) specification.

Implements & Harmonizes:
  - ADR-001..010: Context Triad, .txt Coordinate Grammar, Mipmap Shards, AST & Opaque L4 Sidecars
  - ADR-011: Self-Consuming Bootstrap Prompts, Polymorphic [#sig:xxxxxx] & Archetype Token Budgets
  - ADR-012: Clamped Hop-Distance Threshold Relaxation & Cascade Sharding Guards
  - ADR-013: Hysteresis-Gated --compact Coalescing & UTF-8 Byte-Bounded Guardbands
  - ADR-014: Declarative Maintenance Execution Profiles (Profile A Default / Profile B Opt-In)
  - ADR-015: Deterministic Agent Triage Queue (--triage) & Zero-Edit Hash Acknowledgment (--ack)
  - ADR-016: v2.1 Specification Harmonization, Unified # === [FILES] === Schema & Errata

Changelog (v2.1.1 Audit Remediation):
  - Fixed unescaped end-of-line ($) anchors in STATE_ROOT_PATTERN, CANONICAL_3TUPLE_PATTERN, and RE_TOPOLOGY_EDGE.
  - Restored ADR-010 ERR-01 PNG IHDR byte slices (hdr[12:16] / hdr[16:24]) and ERR-02 unscrambled .l3.txt stubs.
  - Enforced ADR-010 HC-03 primary/fallback decision directory resolution (docs/adr/ primary, docs/decisions/ fallback).
  - Implemented ADR-012 ATOMIC_MONOLITH guard, hop-depth ceiling evaluation, and R_max=1 child overflow warnings.
  - Implemented ADR-013 Condition 2 Parent Absorption Headroom (<= 65%) and [WARN: COMPACT_ELIGIBLE] diagnostic.
  - Implemented ADR-014 AGENTS.md dormant HTML comment isolation check and Profile A default bootstrapper.
  - Added ADR-015 DISK_HASH field, contiguous header block grouping, and owning-shard routing for UNTRACKED_ARTIFACT.
  - Added full child shard STATE_ROOT & L4 sidecar hash verification to --check.

Requires: Python >= 3.9 (Standard Library Only)
License: MIT / CC-BY 4.0
Repository: https://github.com/endean-eng/tokenme
"""

from __future__ import annotations

import argparse
import ast
import csv
import datetime
import fnmatch
import hashlib
import io
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

VERSION = "2.1.1"
SPEC_VERSION = "2.1"

# --- ADR-013 & ADR-016 HC-03 Conservative UTF-8 Byte-to-Token Divisor ---
BYTES_PER_TOKEN_SAFE = 2.8             # k_safe = 2.8 UTF-8 bytes per token (Zero tiktoken)
HARD_BYTE_GUARDBAND = 1.25             # B_hard = ceil(1.25 * B_target)

# --- ADR-012, ADR-013 & ADR-016 HC-04 Hop-Distance & Hysteresis Constants ---
HOP_BASE_TOKENS_S0 = 1500              # d=0 Sharded Root Router ceiling (4,200 B / 150 lines)
MONOLITH_MAX_TOKENS = 3000             # d=0 Unsharded Monolithic ceiling (8,400 B / 250 lines)
HOP_RELAXATION_ALPHA = 0.50            # +50% per hop step
HOP_ASYMPTOTIC_CAP_SMAX = 4000         # d>=4 Clamped Terminal Leaf ceiling (11,200 B)
HYSTERESIS_MERGE_RATIO = 0.35          # Reverse merge floor: <= 35% of T_split(d)
PARENT_ABSORPTION_RATIO = 0.65         # Parent post-merge cap: <= 65% of T_split(d-1)
MIN_SPLIT_SECTIONS = 2                 # ADR-012 Gate 1: Minimum split groups required
MIN_CHILD_VIABILITY_RATIO = 0.25       # ADR-012 Gate 2: Child >= 25% of S_0 (375 tok)
OPAQUE_SHARD_COUNT_THRESHOLD = 8       # Pass 1 trigger: >= 8 qualifying opaque assets
SHARD_TRIGGER_SYMBOLS = 75             # Pass 1 trigger: > 75 extracted symbols
DIFF_EFFICIENCY_GATE = 0.60            # ADR-015: rho_diff <= 0.60 uses git diff; > 0.60 reads file

# --- ADR-006 & ADR-010 HC-06 Fail-Closed Quarantine Constants ---
DEFAULT_MAX_FILE_SIZE_KB = 1024        # 1 MiB ceiling for text/source pipeline
BINARY_SNIFF_BYTES = 8192
STREAM_CHUNK_BYTES = 65536             # 64 KiB streaming chunk for opaque/L4 hashing

# --- ADR-009 Opaque, Vector & L4 Demotion Constants ---
OPAQUE_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".gif", ".svg", ".pdf"
}
RASTER_CAD_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".gif"
}
MIN_RASTER_BYTES = 512
MIN_RASTER_DIM_PX = 128
MIN_SVG_ICON_BYTES = 2048
FLAT_PDF_PAGE_LIMIT = 5
FLAT_PDF_BYTE_LIMIT = 5 * 1024 * 1024        # 5 MB
NATIVE_PDF_PAGE_LIMIT = 15
NATIVE_PDF_BYTE_LIMIT = 10 * 1024 * 1024     # 10 MB
RASTER_CAD_BYTE_LIMIT = 10 * 1024 * 1024     # 10 MB

# --- ADR-008, ADR-011 & ADR-016 Merkle & Signature Constants ---
DEFAULT_LEAF_HASH_LEN = 6
DEFAULT_ROOT_HASH_LEN = 8
FILE_CONTENT_HASH_LEN = 8
STRUCT_SIG_HASH_LEN = 6

STATE_ROOT_PATTERN = re.compile(
    r"^(#\s*STATE_ROOT:\s*)([0-9a-fA-F]{6,64}|PENDING|MASKED_STATE_ROOT)(\s*)$",
    re.MULTILINE,
)
ADVISORY_ID_PATTERN = re.compile(r"^([a-zA-Z0-9-]+)_")
CANONICAL_3TUPLE_PATTERN = re.compile(
    r"^((?:ADR|IDR)-[A-Za-z0-9]{3,6})_(\d{4}-\d{2}-\d{2})_([A-Za-z0-9-]+)\.md$"
)
IGNORED_DECISION_FILES: Set[str] = {"readme.md", "template.md"}

# ADR-011 & ADR-016 Polymorphic Topology Edge Grammar
RE_TOPOLOGY_EDGE = re.compile(
    r"^(?P<src_file>[a-zA-Z0-9_./-]+)::(?P<src_sym>[a-zA-Z0-9_][a-zA-Z0-9_.-]*|@[a-zA-Z0-9_.-]+|\[[a-zA-Z0-9_.: -]+\]|\*)"
    r"\s*->\s*"
    r"(?P<dst_file>[a-zA-Z0-9_./-]+)::(?P<dst_sym>[a-zA-Z0-9_][a-zA-Z0-9_.-]*|@[a-zA-Z0-9_.-]+|\[[a-zA-Z0-9_.: -]+\]|\*)"
    r"\s*:\s*(?P<mech>.{1,160}?)(?:\s*\[#sig:(?P<sig>[0-9a-fA-F]{6})\])?$"
)

# ADR-012 Atomic Monolith Directive Detector
ATOMIC_MONOLITH_PATTERN = re.compile(
    r"(?:<!--\s*TOKENME:ATOMIC_MONOLITH=true\s*-->|^#\s*ATOMIC_MONOLITH:\s*true\b)",
    re.IGNORECASE | re.MULTILINE,
)

# ADR-016 HC-06 Unified Unfilled Placeholder Detector
UNFILLED_PLACEHOLDER_PATTERNS: Tuple[str, ...] = (
    "[BOOTSTRAP_REQUIRED",
    "[TODO: AGENT_FILL",
    "[AGENT_POPULATE_SYMBOLS]",
    "[NEEDS_HYDRATION",
    "<PENDING:",
    "[TODO]",
)

# ADR-014 & ADR-016 Canonical Default AGENTS.md Governance Block (Profile A — Decoupled Cold Triage)
DEFAULT_AGENTS_MD_TEMPLATE = """# AGENTS.md — Agentic Governance & Epistemic Routing Laws

### Epistemic State & Declarative Sync (`TOKENME` v2.1)
- Read `./TOKENME.txt` (and any mounted child shards relevant to your scope) BEFORE executing broad directory searches (`grep`, `find`) or full-file reads. Use `[Lstart-Lend]` coordinates for surgical L3 reads.
- Run `python tokenme-sync.py --triage` to locate `[BOOTSTRAP_REQUIRED]`, `[STALE_EDGE]`, `[SIG_DRIFT]`, `[BUDGET_EXCEEDED]`, or `STALE_HASH` items across shards without reading clean manifests.
- When a code edit is strictly internal and preserves the file's public contract and `[TOPOLOGY]` edges, run `python tokenme-sync.py --ack <path>` to re-seal its hash without rewriting prose.
- Never write freeform prose in `[PURPOSE]` or `[TOPOLOGY]`; strictly obey the inline `SYSTEM:`/`BOUNDARY:`/`RUNTIME:` and `<File::Anchor> -> <File::Anchor> : <Mechanism>` grammars. Never manually write `[#sig:xxxxxx]` tags; let `python tokenme-sync.py` auto-stamp cryptographic locks.
"""

DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".roo", ".cursor",
    "node_modules", "bower_components", "jspm_packages",
    "venv", ".venv", "env", ".env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "site-packages",
    "dist", "build", "out", "target", "bin", "obj", "coverage",
    ".next", ".nuxt", ".svelte-kit", ".vercel", ".output", "vendor",
    "thumbnails", "raw_dataset",
}

DEFAULT_IGNORE_PATTERNS: List[str] = [
    "assets/icons/*", "*/assets/icons/*", "icons/*", "*/thumbnails/*", "*/raw_dataset/*",
    "*.min.js", "*.min.css", "*.map", "*.lock", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock",
    "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.dylib", "*.exe",
    "*.o", "*.a", "*.lib", "*.class", "*.jar", "*.war", "*.ear",
    "*.zip", "*.tar", "*.gz", "*.tgz", "*.bz2", "*.7z", "*.rar",
    "*.ico", "*.mp3", "*.mp4", "*.wav", "*.avi", "*.mov", "*.doc",
    "*.docx", "*.xls", "*.xlsx", "*.ppt", "*.pptx", "*.woff", "*.woff2",
    "*.ttf", "*.eot", "*.otf", "*.db", "*.sqlite", "*.sqlite3",
    "TOKENME*.txt", "*/TOKENME*.txt", "*.l3.txt", "llms*.txt",
    ".DS_Store", "Thumbs.db", ".tokenme-sync.*.tmp",
]

RUNTIME_MANIFESTS: Dict[str, str] = {
    "package.json": "Node.js / JavaScript / TypeScript",
    "tsconfig.json": "TypeScript",
    "pyproject.toml": "Python (pyproject)",
    "requirements.txt": "Python (pip)",
    "setup.py": "Python (setuptools)",
    "Cargo.toml": "Rust (Cargo)",
    "go.mod": "Go (Modules)",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java / Kotlin (Gradle)",
    "Gemfile": "Ruby (Bundler)",
    "composer.json": "PHP (Composer)",
    "CMakeLists.txt": "C / C++ (CMake)",
    "Makefile": "Make / Native Build",
    "Dockerfile": "Docker Container",
}

PYTHON_AST_EXTS: Set[str] = {".py", ".pyi"}


# --- ADR-011 & ADR-016 HC-04 / HC-05 Tier & Archetype Specifications ---

@dataclass(frozen=True)
class StateTierSpec:
    tier_id: str
    purpose_max_bytes: int
    topology_min_edges: int
    topology_max_edges: int
    topology_max_bytes: int


STATE_TIERS: Dict[str, StateTierSpec] = {
    "L1_MONO": StateTierSpec("L1_MONO", purpose_max_bytes=360, topology_min_edges=4, topology_max_edges=8, topology_max_bytes=672),
    "L1_ROOT": StateTierSpec("L1_ROOT", purpose_max_bytes=360, topology_min_edges=3, topology_max_edges=6, topology_max_bytes=504),
    "L2_SHARD": StateTierSpec("L2_SHARD", purpose_max_bytes=270, topology_min_edges=2, topology_max_edges=6, topology_max_bytes=504),
}


@dataclass(frozen=True)
class ArchetypeSpec:
    name: str
    base_tok: int
    k_factor: int
    max_tok: int


ARCHETYPES: Dict[str, ArchetypeSpec] = {
    "ORCHESTRATOR": ArchetypeSpec("ORCHESTRATOR", base_tok=35, k_factor=20, max_tok=140),
    "DOMAIN_CODE":  ArchetypeSpec("DOMAIN_CODE",  base_tok=25, k_factor=16, max_tok=110),
    "DATA_SCHEMA":  ArchetypeSpec("DATA_SCHEMA",  base_tok=20, k_factor=14, max_tok=90),
    "SPEC_DOC":     ArchetypeSpec("SPEC_DOC",     base_tok=25, k_factor=12, max_tok=85),
    "BUILD_CONFIG": ArchetypeSpec("BUILD_CONFIG", base_tok=15, k_factor=8,  max_tok=55),
    "TEST_SUITE":   ArchetypeSpec("TEST_SUITE",   base_tok=15, k_factor=10, max_tok=60),
    "BARREL_INIT":  ArchetypeSpec("BARREL_INIT",  base_tok=12, k_factor=6,  max_tok=40),
    "OPAQUE_ASSET": ArchetypeSpec("OPAQUE_ASSET", base_tok=25, k_factor=10, max_tok=75),
}


# --- Core Math, Token, Byte & Hash Helpers ---

def utf8_byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def estimate_tokens(text: str) -> int:
    """ADR-013 & ADR-016 HC-03: Deterministic UTF-8 byte-bounded token equivalent (k_safe = 2.8)."""
    if not text:
        return 0
    return max(1, math.ceil(utf8_byte_len(text) / BYTES_PER_TOKEN_SAFE))


def hop_split_token_ceiling(hop_depth: int, is_monolith: bool = False) -> int:
    """ADR-012 & ADR-016 HC-04: Clamped hop-distance threshold S_trigger(d)."""
    if hop_depth <= 0 and is_monolith:
        return MONOLITH_MAX_TOKENS
    raw = math.floor(HOP_BASE_TOKENS_S0 * (1.0 + HOP_RELAXATION_ALPHA * max(0, hop_depth)))
    return min(HOP_ASYMPTOTIC_CAP_SMAX, raw)


def hop_split_byte_ceiling(hop_depth: int, is_monolith: bool = False) -> int:
    return math.ceil(BYTES_PER_TOKEN_SAFE * hop_split_token_ceiling(hop_depth, is_monolith))


def hop_merge_token_floor(hop_depth: int) -> int:
    """ADR-013 & ADR-016 HC-04: Reverse hysteresis merge floor (35% of T_split(d))."""
    return math.floor(HYSTERESIS_MERGE_RATIO * hop_split_token_ceiling(max(1, hop_depth)))


def canonical_bytes(path: Path) -> bytes:
    """ADR-008 Sec 2.1: Normalizes CRLF to LF and strips outer whitespace for cross-OS invariance."""
    return path.read_bytes().replace(b"\r\n", b"\n").strip()


def compute_content_hash_8hex(path: Path) -> str:
    """ADR-015 & ADR-016 HC-02: 8-hex lowercase SHA-256 of LF-normalized file content."""
    return hashlib.sha256(canonical_bytes(path)).hexdigest()[:FILE_CONTENT_HASH_LEN]


def stream_sha256_hex(path: Path, length: int = 12) -> str:
    """ADR-009 Part C: Computes streaming SHA-256 over binary files in 64 KiB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(STREAM_CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:length]


def short_sig_hex(payload: str, length: int = STRUCT_SIG_HASH_LEN) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def classify_archetype(rel_path: str, is_opaque: bool = False, source_text: str = "") -> str:
    """ADR-011 & ADR-016 HC-05: Classifies a file into one of the 8 canonical archetypes."""
    if is_opaque:
        return "OPAQUE_ASSET"
    p = Path(rel_path)
    fname = p.name.lower()
    ext = p.suffix.lower()

    if fname in ("__init__.py", "index.ts", "index.js", "mod.rs", "lib.rs"):
        return "BARREL_INIT"
    if fname.startswith("test_") or fname.endswith("_test.py") or ".spec." in fname or "/tests/" in f"/{rel_path.lower()}/":
        return "TEST_SUITE"
    if p.name in RUNTIME_MANIFESTS or ext in (".toml", ".yaml", ".yml", ".json", ".ini", ".cfg"):
        if "schema" in fname:
            return "DATA_SCHEMA"
        return "BUILD_CONFIG"
    if ext in (".md", ".rst", ".txt"):
        return "SPEC_DOC"
    if ext in (".sql", ".proto", ".graphql") or "schema" in fname or "models" in fname:
        return "DATA_SCHEMA"
    if "argparse" in source_text or "if __name__" in source_text or fname in ("main.py", "cli.py", "app.py", "tokenme-sync.py"):
        return "ORCHESTRATOR"
    return "DOMAIN_CODE"


def compute_file_budget_bytes(archetype_name: str, effective_loc: int) -> Tuple[int, int, int]:
    """
    ADR-016 HC-05: Returns (T_target_tok, B_target_bytes, B_hard_bytes) for a file.
    """
    spec = ARCHETYPES.get(archetype_name, ARCHETYPES["DOMAIN_CODE"])
    ratio = max(1.0, effective_loc / 50.0)
    t_target = min(spec.max_tok, spec.base_tok + math.floor(spec.k_factor * math.log2(ratio)))
    b_target = math.ceil(BYTES_PER_TOKEN_SAFE * t_target)
    b_hard = math.ceil(HARD_BYTE_GUARDBAND * b_target)
    return t_target, b_target, b_hard


# --- Data Structures ---

@dataclass
class SymbolSpan:
    kind: str
    name: str
    start_line: int
    end_line: int
    arity: int = 0
    struct_sig: str = "000000"
    bound_adr: Optional[str] = None


@dataclass
class OpaqueAssetInfo:
    modality: str
    source_hash: str
    est_pages: int = 1
    dimensions: Optional[str] = None
    pre_scraped_meta: str = "NONE"
    is_l4_demoted: bool = False
    sidecar_rel_path: Optional[str] = None
    sidecar_status: str = "UNHYDRATED_STUB"
    sidecar_leaf_hash: Optional[str] = None
    asset_class: str = "[BOOTSTRAP_REQUIRED]"
    visual_summary: str = "[BOOTSTRAP_REQUIRED]"


@dataclass
class FileRecord:
    rel_path: str
    parent_dir: str
    subsystem: str
    byte_size: int
    line_count: int
    effective_loc: int
    tokens_est: int
    archetype: str
    b_target: int
    b_hard: int
    content_hash: str
    struct_sig: str
    ast_signature_str: str
    anchor_sigs: Dict[str, str] = field(default_factory=dict)
    is_python: bool = False
    is_opaque: bool = False
    is_atomic_monolith: bool = False
    opaque_info: Optional[OpaqueAssetInfo] = None
    symbols: List[SymbolSpan] = field(default_factory=list)
    fault_status: Optional[str] = None
    role_summary: str = "[BOOTSTRAP_REQUIRED]"
    assigned_shard: str = "TOKENME.txt"


@dataclass
class ADRRecord:
    rel_posix: str
    record_id: str
    iso_date: str
    title_slug: str
    status: str
    leaf_hash: str


@dataclass
class QuarantineEntry:
    rel_path: str
    reason: str


@dataclass
class HarvestedRow:
    rel_path: str
    old_line_count: int
    content_hash: str
    struct_sig: str
    role_summary: str
    shard_rel_posix: str
    line_number: int
    raw_row: str


@dataclass
class HarvestedShardState:
    rel_shard_posix: str
    is_atomic_monolith: bool = False
    purpose_lines: List[str] = field(default_factory=list)
    topology_lines: List[str] = field(default_factory=list)
    rows: Dict[str, HarvestedRow] = field(default_factory=dict)


@dataclass
class TriageItem:
    item_type: str
    target_shard: str
    line_anchor: str
    tracked_file: Optional[str] = None
    block_id: Optional[str] = None
    current_text: Optional[str] = None
    disk_hash: Optional[str] = None
    hash_delta: Optional[str] = None
    diff_metrics: Optional[str] = None
    current_row: Optional[str] = None
    git_diff_cmd: Optional[str] = None
    recommended_action: str = ""


# --- ADR-011 & ADR-016 Polymorphic Structural Hashing & 3-Stage AST Pruning ---

def _compute_ast_node_structural_sig(node: ast.AST) -> str:
    """
    ADR-011 Sec 2.2: Computes a 6-hex structural signature over an AST node that is invariant
    to comments, docstrings, and constant literal values, capturing args, return annotations,
    decorators, outgoing call names, and state effects.
    """
    parts: List[str] = [type(node).__name__]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = [a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        parts.append(f"args=({','.join(args)})")
        if node.returns:
            try:
                parts.append(f"ret={ast.unparse(node.returns)}")
            except Exception:
                parts.append(f"ret={type(node.returns).__name__}")
        decs = []
        for d in node.decorator_list:
            try:
                decs.append(ast.unparse(d))
            except Exception:
                decs.append(type(d).__name__)
        if decs:
            parts.append(f"dec={','.join(decs)}")
    elif isinstance(node, ast.ClassDef):
        bases = []
        for b in node.bases:
            try:
                bases.append(ast.unparse(b))
            except Exception:
                bases.append(type(b).__name__)
        parts.append(f"bases=({','.join(bases)})")

    calls: List[str] = []
    effects: Set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)
        elif isinstance(child, ast.Global):
            effects.add(f"global:{','.join(sorted(child.names))}")
        elif isinstance(child, (ast.Yield, ast.YieldFrom)):
            effects.add("yield")
        elif isinstance(child, ast.Await):
            effects.add("await")
        elif isinstance(child, ast.Raise):
            effects.add("raise")
    if calls:
        parts.append(f"calls={','.join(sorted(set(calls)))}")
    if effects:
        parts.append(f"fx={','.join(sorted(effects))}")
    return short_sig_hex("|".join(parts))


class PolymorphicPythonScanner(ast.NodeVisitor):
    """Extracts symbols, arities, structural signatures, and @bound ADR tags in one pass."""

    def __init__(self, source_lines: List[str]) -> None:
        self.symbols: List[SymbolSpan] = []
        self.anchor_sigs: Dict[str, str] = {}
        self._class_stack: List[str] = []
        self._func_depth: int = 0
        self._source_lines = source_lines

    def _find_bound_tag(self, start_line: int, end_line: int) -> Optional[str]:
        window = self._source_lines[max(0, start_line - 2) : min(len(self._source_lines), start_line + 4)]
        for l in window:
            m = re.search(r"@bound\s+((?:ADR|IDR)-[A-Za-z0-9]{3,6})", l)
            if m:
                return m.group(1)
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self._func_depth == 0:
            qual_name = ".".join(self._class_stack + [node.name])
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start) or start
            sig = _compute_ast_node_structural_sig(node)
            self.anchor_sigs[qual_name] = sig
            self.symbols.append(
                SymbolSpan(
                    kind="class",
                    name=qual_name,
                    start_line=start,
                    end_line=end,
                    arity=len(node.bases),
                    struct_sig=sig,
                    bound_adr=self._find_bound_tag(start, end),
                )
            )
            self._class_stack.append(node.name)
            self.generic_visit(node)
            self._class_stack.pop()

    def _handle_func(self, node: ast.AST, kind: str, name: str, args_obj: ast.arguments) -> None:
        if self._func_depth == 0:
            qual_name = ".".join(self._class_stack + [name])
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start) or start
            raw_args = [a.arg for a in args_obj.posonlyargs + args_obj.args + args_obj.kwonlyargs if a.arg not in ("self", "cls")]
            arity = len(raw_args) + (1 if args_obj.vararg else 0) + (1 if args_obj.kwarg else 0)
            sig = _compute_ast_node_structural_sig(node)
            self.anchor_sigs[qual_name] = sig
            self.symbols.append(
                SymbolSpan(
                    kind=kind,
                    name=qual_name,
                    start_line=start,
                    end_line=end,
                    arity=arity,
                    struct_sig=sig,
                    bound_adr=self._find_bound_tag(start, end),
                )
            )
        self._func_depth += 1
        self.generic_visit(node)
        self._func_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_func(node, "def", node.name, node.args)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_func(node, "async def", node.name, node.args)


def format_pruned_ast_column(symbols: List[SymbolSpan], b_target: int, effective_loc: int) -> str:
    """
    ADR-011 Sec 3 & ADR-016 HC-05: 3-Stage Progressive AST Pruning to fit within B_target bytes.
    """
    if not symbols:
        return "module_script (no top-level class/def)"

    def _render_stage(syms: List[SymbolSpan], fold_methods: bool) -> str:
        classes = [s for s in syms if s.kind == "class"]
        top_funcs = [s for s in syms if s.kind != "class" and "." not in s.name]
        methods_by_cls: Dict[str, List[SymbolSpan]] = {}
        for s in syms:
            if s.kind != "class" and "." in s.name:
                cls_prefix = s.name.rsplit(".", 1)[0]
                methods_by_cls.setdefault(cls_prefix, []).append(s)

        parts: List[str] = []
        if classes:
            cls_strs: List[str] = []
            for c in classes:
                m_list = methods_by_cls.get(c.name, [])
                if fold_methods and len(m_list) > 4:
                    cls_strs.append(f"{c.name}[{len(m_list)}m]")
                elif m_list:
                    m_names = ",".join(
                        f".{m.name.split('.')[-1]}/{m.arity}" + (f"[{m.bound_adr}]" if m.bound_adr else "")
                        for m in m_list[:6]
                    )
                    if len(m_list) > 6:
                        m_names += ",..."
                    cls_strs.append(f"{c.name}({m_names})")
                else:
                    cls_strs.append(f"{c.name}:{c.start_line}-{c.end_line}")
            parts.append("classes=" + ", ".join(cls_strs))

        if top_funcs:
            fn_strs = [
                f"{f.name}/{f.arity}:{f.start_line}-{f.end_line}" + (f"[{f.bound_adr}]" if f.bound_adr else "")
                for f in top_funcs
            ]
            if fold_methods and len(fn_strs) > 8:
                fn_strs = [f"{f.name}/{f.arity}" for f in top_funcs[:8]] + [f"+{len(top_funcs) - 8}_more"]
            parts.append("defs=" + ", ".join(fn_strs))
        return " ; ".join(parts) if parts else "module_script"

    # Stage 0: Full resolution (<150 LOC)
    s0 = _render_stage(symbols, fold_methods=False)
    if effective_loc < 150 and utf8_byte_len(s0) <= b_target:
        return s0

    # Stage 1: Public API resolution (strip _private except __init__ and __call__)
    pub_syms = [
        s for s in symbols
        if not s.name.split(".")[-1].startswith("_") or s.name.split(".")[-1] in ("__init__", "__call__")
    ]
    s1 = _render_stage(pub_syms or symbols, fold_methods=False)
    if utf8_byte_len(s1) <= b_target:
        return s1

    # Stage 2: Arity & method folding
    s2 = _render_stage(pub_syms or symbols, fold_methods=True)
    if utf8_byte_len(s2) <= b_target:
        return s2
    return s2[: max(32, b_target - 3)] + "..."


def scan_non_python_structural_sigs(rel_path: str, text: str) -> Tuple[Dict[str, str], str]:
    """
    ADR-011 Sec 3: Extracts structural anchors and 6-hex signatures for Markdown, JSON, CSV/TSV,
    and generic source/config files so [TOPOLOGY] edges and Dual-Hash Auto-Ack work across modalities.
    """
    ext = Path(rel_path).suffix.lower()
    sigs: Dict[str, str] = {}

    if ext in (".md", ".txt"):
        current_heading = "[ROOT]"
        section_skeletons: Dict[str, List[str]] = {current_heading: []}
        heading_order: List[str] = []
        in_fence = False
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                section_skeletons.setdefault(current_heading, []).append(stripped[:20])
                continue
            if not in_fence:
                m_h = re.match(r"^(#{1,4})\s+(.+)$", stripped)
                if m_h:
                    raw_title = m_h.group(2).strip()
                    bracket_anchor = f"[{raw_title}]"
                    slug = "[" + re.sub(r"[^a-z0-9]+", "-", raw_title.lower()).strip("-") + "]"
                    current_heading = bracket_anchor
                    heading_order.append(raw_title[:28])
                    section_skeletons.setdefault(bracket_anchor, [])
                    section_skeletons.setdefault(slug, section_skeletons[bracket_anchor])
                    continue
                if stripped.startswith("|") or stripped.startswith("$$") or stripped.startswith("# ==="):
                    section_skeletons.setdefault(current_heading, []).append(stripped)
            else:
                section_skeletons.setdefault(current_heading, []).append(stripped)

        for anchor, skel in section_skeletons.items():
            sigs[anchor] = short_sig_hex("\n".join(skel) if skel else anchor)
        sigs["*"] = short_sig_hex("|".join(f"{k}:{v}" for k, v in sorted(sigs.items())))
        summary_col = "secs=" + ", ".join(heading_order[:5]) + ("..." if len(heading_order) > 5 else "")
        return sigs, (summary_col if heading_order else "doc_text")

    if ext == ".json":
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    sigs[str(k)] = short_sig_hex(json.dumps(v, sort_keys=True))
                sigs["*"] = short_sig_hex("|".join(sorted(sigs.keys())))
                keys_preview = ", ".join(list(obj.keys())[:6])
                return sigs, f"json_keys=[{keys_preview}]"
        except Exception:
            pass

    if ext in (".csv", ".tsv"):
        delim = "\t" if ext == ".tsv" else ","
        try:
            reader = csv.reader(io.StringIO(text), delimiter=delim)
            rows = list(reader)
            if rows:
                headers = [h.strip() for h in rows[0] if h.strip()]
                for h in headers:
                    sigs[h] = short_sig_hex(h)
                for r in rows[1:]:
                    if r and r[0].strip():
                        row_id = f"@{r[0].strip()}"
                        sigs[row_id] = short_sig_hex("|".join(c.strip() for c in r))
                sigs["*"] = short_sig_hex("|".join(f"{k}:{v}" for k, v in sorted(sigs.items())))
                return sigs, f"cols=[{', '.join(headers[:5])}] ({max(0, len(rows)-1)} rows)"
        except Exception:
            pass

    # Fallback for generic code/config files: strip # and // comments for structural hash
    structural_lines: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        structural_lines.append(s)
    wildcard_sig = short_sig_hex("\n".join(structural_lines))
    sigs["*"] = wildcard_sig
    return sigs, "[AGENT_POPULATE_SYMBOLS]"


# --- ADR-009 & ADR-010 Opaque & Vector Inspection Pipeline ---

def _parse_raster_dimensions_and_meta(filepath: Path, ext: str, size: int) -> Tuple[Optional[Tuple[int, int]], str]:
    dims: Optional[Tuple[int, int]] = None
    meta_items: List[str] = []
    try:
        with filepath.open("rb") as f:
            hdr = f.read(4096)
            if ext == ".png" and size >= 24:
                # ADR-010 ERR-01 Fix: Exact slice hdr[12:16] for IHDR and hdr[16:24] for >II width/height unpack
                if hdr[:8] == b"\x89PNG\r\n\x1a\n" and hdr[12:16] == b"IHDR":
                    w, h = struct.unpack(">II", hdr[16:24])
                    dims = (w, h)
                for m in re.finditer(b"tEXt([A-Za-z0-9_ -]{1,32})\x00([\x20-\x7e]{1,120})", hdr):
                    k = m.group(1).decode("ascii", errors="ignore").strip()
                    v = m.group(2).decode("ascii", errors="ignore").strip()
                    if k and v:
                        meta_items.append(f"{k}={v}")
            elif ext == ".gif" and size >= 10:
                if hdr[:6] in (b"GIF87a", b"GIF89a"):
                    w, h = struct.unpack("<HH", hdr[6:10])
                    dims = (w, h)
            elif ext in (".jpg", ".jpeg") and size >= 4 and hdr[:2] == b"\xff\xd8":
                f.seek(2)
                buf = f.read(65536)
                idx = 0
                while idx < len(buf) - 8:
                    if buf[idx] != 0xFF:
                        idx += 1
                        continue
                    marker = buf[idx + 1]
                    if marker == 0xFF:
                        idx += 1
                        continue
                    if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                        h, w = struct.unpack(">HH", buf[idx + 5 : idx + 9])
                        dims = (w, h)
                        break
                    if marker in (0xD8, 0xD9) or (0xD0 <= marker <= 0xD7):
                        idx += 2
                        continue
                    seg_len = struct.unpack(">H", buf[idx + 2 : idx + 4])[0]
                    if seg_len < 2:
                        break
                    idx += 2 + seg_len
    except OSError:
        pass
    return dims, ("; ".join(meta_items[:3]) if meta_items else "NONE")


def inspect_opaque_candidate(filepath: Path, rel_file: str) -> Optional[OpaqueAssetInfo]:
    ext = filepath.suffix.lower()
    if ext not in OPAQUE_EXTENSIONS or filepath.name.endswith(".l3.txt"):
        return None
    try:
        size = filepath.stat().st_size
    except OSError:
        return None

    if ext in RASTER_CAD_EXTENSIONS:
        if size < MIN_RASTER_BYTES:
            return None
        dims, png_meta = _parse_raster_dimensions_and_meta(filepath, ext, size)
        if dims is not None:
            w, h = dims
            if w < MIN_RASTER_DIM_PX and h < MIN_RASTER_DIM_PX:
                return None
            dim_str = f"{w}x{h}px"
        else:
            dim_str = "unknown_dim"
        src_hash = stream_sha256_hex(filepath, length=12)
        demoted = size > RASTER_CAD_BYTE_LIMIT
        return OpaqueAssetInfo(
            modality="RASTER_IMAGE",
            source_hash=src_hash,
            est_pages=1,
            dimensions=dim_str,
            pre_scraped_meta=png_meta,
            is_l4_demoted=demoted,
            sidecar_rel_path=f"{rel_file}.l3.txt" if demoted else None,
        )

    if ext == ".svg":
        try:
            raw_svg = filepath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        has_text = "<text" in raw_svg
        has_id = "id=" in raw_svg
        if size < MIN_SVG_ICON_BYTES and not has_text and not has_id:
            return None
        titles = re.findall(r"<title[^>]*>(.*?)</title>", raw_svg, flags=re.IGNORECASE | re.DOTALL)
        texts = re.findall(r"<text[^>]*>(.*?)</text>", raw_svg, flags=re.IGNORECASE | re.DOTALL)
        cleaned: List[str] = []
        for item in (titles[:2] + texts[:4]):
            c = " ".join(re.sub(r"<[^>]+>", " ", item).split())
            if c:
                cleaned.append(c[:60])
        meta_str = " ; ".join(cleaned) if cleaned else "SVG_PATHS_ONLY"
        src_hash = stream_sha256_hex(filepath, length=12)
        demoted = size > RASTER_CAD_BYTE_LIMIT
        return OpaqueAssetInfo(
            modality="VECTOR_SVG",
            source_hash=src_hash,
            est_pages=1,
            dimensions="vector",
            pre_scraped_meta=meta_str,
            is_l4_demoted=demoted,
            sidecar_rel_path=f"{rel_file}.l3.txt" if demoted else None,
        )

    if ext == ".pdf":
        src_hash = stream_sha256_hex(filepath, length=12)
        page_count = 1
        ascii_chars = 0
        try:
            with filepath.open("rb") as f:
                sample = f.read(4 * 1024 * 1024)
            page_count = max(1, len(re.findall(rb"/Type\s*/Page\b", sample)))
            for s_match in re.finditer(rb"\(([\x20-\x7e]{4,200})\)", sample):
                ascii_chars += len(s_match.group(1))
        except OSError:
            pass
        is_flat = (ascii_chars / max(1, page_count)) < 50
        modality = "FLAT_PDF" if is_flat else "NATIVE_PDF"
        demoted = (
            (page_count > FLAT_PDF_PAGE_LIMIT or size > FLAT_PDF_BYTE_LIMIT)
            if is_flat
            else (page_count > NATIVE_PDF_PAGE_LIMIT or size > NATIVE_PDF_BYTE_LIMIT)
        )
        return OpaqueAssetInfo(
            modality=modality,
            source_hash=src_hash,
            est_pages=page_count,
            dimensions=f"{page_count}p",
            pre_scraped_meta=f"{modality}:{page_count}p",
            is_l4_demoted=demoted,
            sidecar_rel_path=f"{rel_file}.l3.txt" if demoted else None,
        )
    return None


def sync_l4_sidecar_file(root: Path, rec: FileRecord, leaf_len: int, dry_run: bool) -> None:
    """ADR-009 & ADR-010 ERR-02 Fix: Emits unscrambled natural-English .l3.txt surrogate stubs."""
    info = rec.opaque_info
    if not info or not info.is_l4_demoted or not info.sidecar_rel_path:
        return
    sidecar_path = root / info.sidecar_rel_path
    header_lines = [
        "# TOKENME L3 SURROGATE STUB",
        f"# L4_SOURCE_FILE: {rec.rel_path}",
        f"# L4_SOURCE_HASH: {info.source_hash}",
        f"# L4_BYTES: {rec.byte_size} | EST_PAGES: {info.est_pages} | MODALITY: {info.modality}",
    ]
    if sidecar_path.is_file() and not sidecar_path.is_symlink():
        try:
            existing_text = sidecar_path.read_text(encoding="utf-8", errors="ignore")
            old_hash_m = re.search(r"^#\s*L4_SOURCE_HASH:\s*([0-9a-fA-F]+)", existing_text, re.MULTILINE)
            old_hash = old_hash_m.group(1) if old_hash_m else ""
            if old_hash == info.source_hash:
                info.sidecar_leaf_hash = hashlib.sha256(canonical_bytes(sidecar_path)).hexdigest()[:leaf_len]
                return
        except OSError:
            pass

    stub_lines = header_lines + [
        "# STATUS: UNHYDRATED_STUB",
        "",
        "[DETERMINISTIC_PRE_SCRAPE]",
        f"Extracted_Metadata: {info.pre_scraped_meta}",
        "",
        "[AGENT_HYDRATION_REQUIRED]",
        "Asset_Class: <PENDING: CAD_Render | Datasheet_Scan | Field_Photo | Manual | Receipt_Invoice | Schematic>",
        "Visual_Or_Content_Summary: <PENDING: 1-3 dense engineering sentence summary>",
        "Page_Map_And_TOC:",
        "  - <PENDING: Map page ranges to section headers so L4 binary can be queried by page slice>",
        "Key_Specs_And_OCR:",
        "  - <PENDING: Critical extracted tables, pinouts, part numbers, or torque specs (`NONE` if non-text photo)>",
    ]
    stub_text = "\n".join(stub_lines) + "\n"
    if not dry_run:
        try:
            sidecar_path.write_text(stub_text, encoding="utf-8", newline="\n")
        except OSError:
            pass
    norm_bytes = stub_text.replace("\r\n", "\n").strip().encode("utf-8")
    info.sidecar_leaf_hash = hashlib.sha256(norm_bytes).hexdigest()[:leaf_len]


# --- ADR-007, ADR-008, ADR-010 HC-03 & ADR-016 Decision Record Discovery ---

def resolve_decisions_dirs(root: Path, custom_dir: Optional[str] = None) -> List[Path]:
    """
    ADR-010 HC-03 & ADR-016 HC-06: Scans docs/adr/ as primary and falls back to
    docs/decisions/ only if docs/adr/ is absent (or when overridden via --adr-dir).
    """
    if custom_dir:
        p = root / custom_dir
        return [p] if p.is_dir() else []
    primary = root / "docs" / "adr"
    if primary.is_dir():
        return [primary]
    fallback = root / "docs" / "decisions"
    return [fallback] if fallback.is_dir() else []


def parse_adr_metadata(adr_path: Path, root: Path, leaf_len: int) -> ADRRecord:
    """ADR-016 COL-07 Fix: Supports YAML frontmatter status:, bulleted, bold, and table status fields."""
    rel_posix = adr_path.relative_to(root).as_posix()
    fname = adr_path.name
    m_3tuple = CANONICAL_3TUPLE_PATTERN.match(fname)
    if m_3tuple:
        rec_id, iso_date, title_slug = m_3tuple.group(1), m_3tuple.group(2), m_3tuple.group(3)
    else:
        m_adv = ADVISORY_ID_PATTERN.match(adr_path.stem)
        rec_id = m_adv.group(1) if m_adv else adr_path.stem
        iso_date = "N/A"
        title_slug = adr_path.stem[len(rec_id) + 1 :] if m_adv else adr_path.stem

    status_val = "Proposed"
    try:
        text = adr_path.read_text(encoding="utf-8", errors="ignore")
        m_stat = re.search(
            r"(?:^\*\s*\*\*Status:\*\*\s*|^\*\*Status:\*\*\s*|^\|\s*\*\*Status\*\*\s*\|\s*|^status:\s*)([^|\n]+)",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        if m_stat:
            status_val = m_stat.group(1).strip().strip("`").strip()
        if iso_date == "N/A":
            m_date = re.search(r"(\d{4}-\d{2}-\d{2})", text)
            if m_date:
                iso_date = m_date.group(1)
    except OSError:
        pass

    digest = hashlib.sha256(canonical_bytes(adr_path)).hexdigest()[:leaf_len]
    return ADRRecord(
        rel_posix=rel_posix,
        record_id=rec_id,
        iso_date=iso_date,
        title_slug=title_slug,
        status=status_val,
        leaf_hash=digest,
    )


def discover_adr_records(root: Path, leaf_len: int = DEFAULT_LEAF_HASH_LEN, custom_dir: Optional[str] = None) -> List[ADRRecord]:
    if not (6 <= leaf_len <= 64):
        raise ValueError("leaf_len must be between 6 and 64 hex characters.")
    dirs = resolve_decisions_dirs(root, custom_dir)
    if not dirs:
        return []

    records: List[ADRRecord] = []
    seen_hashes: Dict[str, str] = {}
    seen_ids: Dict[str, str] = {}

    candidate_paths: List[Path] = []
    for d in dirs:
        for p in d.iterdir():
            if p.is_file() and not p.is_symlink() and p.suffix.lower() == ".md" and p.name.lower() not in IGNORED_DECISION_FILES:
                candidate_paths.append(p)

    for path in sorted(candidate_paths, key=lambda p: p.relative_to(root).as_posix()):
        rec = parse_adr_metadata(path, root, leaf_len)
        if rec.record_id in seen_ids:
            raise RuntimeError(
                f"Duplicate ADR record_id collision ({rec.record_id}) between "
                f"{seen_ids[rec.record_id]} and {rec.rel_posix}."
            )
        seen_ids[rec.record_id] = rec.rel_posix
        if rec.leaf_hash in seen_hashes:
            raise RuntimeError(
                f"Leaf hash collision detected ({rec.leaf_hash}) between "
                f"{seen_hashes[rec.leaf_hash]} and {rec.rel_posix}."
            )
        seen_hashes[rec.leaf_hash] = rec.rel_posix
        records.append(rec)
    return records


def compute_merkle_state_root_from_text(
    tokenme_text: str, agents_path: Optional[Path], root_len: int = DEFAULT_ROOT_HASH_LEN
) -> str:
    if not (8 <= root_len <= 64):
        raise ValueError("root_len must be between 8 and 64 hex characters.")
    norm_tokenme = tokenme_text.replace("\r\n", "\n").strip()
    masked_tokenme = STATE_ROOT_PATTERN.sub(r"\g<1>MASKED_STATE_ROOT\g<3>", norm_tokenme).encode("utf-8")
    agents_payload = canonical_bytes(agents_path) if (agents_path and agents_path.is_file()) else b""
    combined = agents_payload + b"\n---\n" + masked_tokenme
    return hashlib.sha256(combined).hexdigest()[:root_len]


def stamp_state_root_in_text(
    tokenme_text: str, agents_path: Optional[Path], root_len: int = DEFAULT_ROOT_HASH_LEN
) -> Tuple[str, str]:
    digest = compute_merkle_state_root_from_text(tokenme_text, agents_path, root_len=root_len)
    stamped = STATE_ROOT_PATTERN.sub(rf"\g<1>{digest}\g<3>", tokenme_text)
    return stamped, digest


# --- Repository Scanning & Polymorphic Extraction ---

def load_ignore_patterns(root: Path) -> List[str]:
    patterns = list(DEFAULT_IGNORE_PATTERNS)
    for ignore_file in (".gitignore", ".rooignore", ".dockerignore"):
        p = root / ignore_file
        if p.is_file() and not p.is_symlink():
            try:
                for raw_line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or line.startswith("!"):
                        continue
                    patterns.append(line.rstrip("/"))
            except OSError:
                pass
    return patterns


def is_ignored(rel_path: str, name: str, is_dir: bool, patterns: List[str]) -> bool:
    if is_dir and name in DEFAULT_IGNORE_DIRS:
        return True
    if name.startswith(".") and name not in {".github", ".eslintrc.js"}:
        if is_dir:
            return True
    for pat in patterns:
        if "/" in pat:
            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(rel_path, f"*/{pat}"):
                return True
        else:
            if fnmatch.fnmatch(name, pat):
                return True
    return False


def detect_runtimes(root: Path) -> List[str]:
    found: Set[str] = set()
    try:
        for item in sorted(root.iterdir(), key=lambda p: p.name):
            if item.is_file() and not item.is_symlink() and item.name in RUNTIME_MANIFESTS:
                found.add(RUNTIME_MANIFESTS[item.name])
    except OSError:
        pass
    return sorted(found)


def scan_repository(
    root: Path, max_size_bytes: int, leaf_len: int, dry_run: bool
) -> Tuple[List[FileRecord], List[QuarantineEntry], List[str], Dict[str, Dict[str, str]]]:
    """
    Scans the repository, building FileRecords and the global workspace_sig_map[rel_path][anchor] = 6-hex.
    """
    ignore_patterns = load_ignore_patterns(root)
    records: List[FileRecord] = []
    quarantine_log: List[QuarantineEntry] = []
    workspace_sig_map: Dict[str, Dict[str, str]] = {}

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""

        kept_dirs: List[str] = []
        for d in sorted(dirnames):
            rel_d = f"{rel_dir}/{d}".lstrip("/")
            if is_ignored(rel_d, d, True, ignore_patterns):
                continue
            full_d = Path(dirpath) / d
            if full_d.is_symlink():
                quarantine_log.append(QuarantineEntry(rel_path=f"{rel_d}/", reason="[UNPARSEABLE: SkippedSymlinkDir]"))
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in sorted(filenames):
            rel_file = f"{rel_dir}/{fname}".lstrip("/")
            if is_ignored(rel_file, fname, False, ignore_patterns):
                continue
            fpath = Path(dirpath) / fname
            if fpath.is_symlink():
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason="[UNPARSEABLE: SkippedSymlinkFile]"))
                continue

            try:
                st = fpath.stat()
            except OSError as exc:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: StatError ({exc.__class__.__name__})]"))
                continue

            byte_size = st.st_size
            if byte_size == 0:
                continue

            parts = rel_file.split("/")
            subsystem = parts[0] if len(parts) > 1 else "root"
            ext = fpath.suffix.lower()

            # Branch 1: Opaque / Vector / PDF Pipeline
            if ext in OPAQUE_EXTENSIONS:
                opaque_info = inspect_opaque_candidate(fpath, rel_file)
                if opaque_info is None:
                    continue
                arch = "OPAQUE_ASSET"
                _, b_target, b_hard = compute_file_budget_bytes(arch, opaque_info.est_pages * 25)
                c_hash = opaque_info.source_hash[:FILE_CONTENT_HASH_LEN]
                s_sig = short_sig_hex(f"{opaque_info.modality}:{opaque_info.dimensions}:{opaque_info.pre_scraped_meta}")
                ast_col = f"{opaque_info.modality} ({opaque_info.dimensions}) ; meta={opaque_info.pre_scraped_meta}"
                rec = FileRecord(
                    rel_path=rel_file,
                    parent_dir=rel_dir,
                    subsystem=subsystem,
                    byte_size=byte_size,
                    line_count=opaque_info.est_pages,
                    effective_loc=opaque_info.est_pages,
                    tokens_est=45,
                    archetype=arch,
                    b_target=b_target,
                    b_hard=b_hard,
                    content_hash=c_hash,
                    struct_sig=s_sig,
                    ast_signature_str=ast_col,
                    anchor_sigs={"*": s_sig},
                    is_python=False,
                    is_opaque=True,
                    opaque_info=opaque_info,
                )
                if opaque_info.is_l4_demoted:
                    sync_l4_sidecar_file(root, rec, leaf_len=leaf_len, dry_run=dry_run)
                workspace_sig_map[rel_file] = {"*": s_sig}
                records.append(rec)
                continue

            # Branch 2: Source & Text Pipeline
            if byte_size > max_size_bytes:
                quarantine_log.append(
                    QuarantineEntry(
                        rel_path=rel_file,
                        reason=f"[UNPARSEABLE: OversizeText ({byte_size // 1024:,} KiB > {max_size_bytes // 1024:,} KiB)]",
                    )
                )
                continue

            try:
                with fpath.open("rb") as bf:
                    sniff = bf.read(BINARY_SNIFF_BYTES)
                if b"\x00" in sniff:
                    quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: BinaryNullByte ({byte_size:,} B)]"))
                    continue
                text = fpath.read_text(encoding="utf-8", errors="strict")
            except UnicodeDecodeError:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason="[UNPARSEABLE: UnicodeDecodeError]"))
                continue
            except OSError as exc:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: ReadError ({exc.__class__.__name__})]"))
                continue

            lines = text.splitlines()
            if not lines:
                continue

            eff_loc = sum(1 for l in lines if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("//"))
            eff_loc = max(1, eff_loc)
            arch = classify_archetype(rel_file, is_opaque=False, source_text=text)
            _, b_target, b_hard = compute_file_budget_bytes(arch, eff_loc)
            c_hash = compute_content_hash_8hex(fpath)
            tokens_est = estimate_tokens(text)
            is_atomic = bool(ATOMIC_MONOLITH_PATTERN.search(text))

            if ext in PYTHON_AST_EXTS:
                try:
                    tree = ast.parse(text)
                    scanner = PolymorphicPythonScanner(lines)
                    scanner.visit(tree)
                    syms = scanner.symbols
                    anchor_sigs = dict(scanner.anchor_sigs)
                    wildcard_sig = short_sig_hex("|".join(f"{k}:{v}" for k, v in sorted(anchor_sigs.items())) if anchor_sigs else "empty_py")
                    anchor_sigs["*"] = wildcard_sig
                    ast_col = format_pruned_ast_column(syms, b_target=b_target, effective_loc=eff_loc)
                    workspace_sig_map[rel_file] = anchor_sigs
                    records.append(
                        FileRecord(
                            rel_path=rel_file,
                            parent_dir=rel_dir,
                            subsystem=subsystem,
                            byte_size=byte_size,
                            line_count=len(lines),
                            effective_loc=eff_loc,
                            tokens_est=tokens_est,
                            archetype=arch,
                            b_target=b_target,
                            b_hard=b_hard,
                            content_hash=c_hash,
                            struct_sig=wildcard_sig,
                            ast_signature_str=ast_col,
                            anchor_sigs=anchor_sigs,
                            is_python=True,
                            is_atomic_monolith=is_atomic,
                            symbols=syms,
                        )
                    )
                except SyntaxError as exc:
                    fault = f"[UNPARSEABLE: SyntaxError at L{exc.lineno or 1}]"
                    quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=fault))
            else:
                anchor_sigs, ast_col = scan_non_python_structural_sigs(rel_file, text)
                wildcard_sig = anchor_sigs.get("*", "000000")
                workspace_sig_map[rel_file] = anchor_sigs
                records.append(
                    FileRecord(
                        rel_path=rel_file,
                        parent_dir=rel_dir,
                        subsystem=subsystem,
                        byte_size=byte_size,
                        line_count=len(lines),
                        effective_loc=eff_loc,
                        tokens_est=tokens_est,
                        archetype=arch,
                        b_target=b_target,
                        b_hard=b_hard,
                        content_hash=c_hash,
                        struct_sig=wildcard_sig,
                        ast_signature_str=ast_col,
                        anchor_sigs=anchor_sigs,
                        is_python=False,
                        is_atomic_monolith=is_atomic,
                    )
                )

    return records, quarantine_log, detect_runtimes(root), workspace_sig_map


# --- State Harvesting & Dual-Hash Auto-Ack (ADR-016 HC-01 & HC-02) ---

FILE_TABLE_ROW_RE = re.compile(
    r"^\|\s*`([^`]+)`\s*`\[(?:L1-L(\d+)|OPAQUE_L3|L4_DEMOTED)\]`\s*\|\s*`([A-Z_]+)`[^|]*\|\s*`([0-9a-fA-F]{6,12})(?::([0-9a-fA-F]{6}))?`\s*\|\s*`([^`]*)`\s*\|\s*(.+?)\s*\|$"
)


def find_existing_tokenme_shards(root: Path) -> List[Path]:
    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in sorted(dirnames) if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".")]
        for fname in sorted(filenames):
            if fname.startswith("TOKENME") and fname.endswith(".txt") and not fname.endswith(".l3.txt"):
                p = Path(dirpath) / fname
                if p.is_file() and not p.is_symlink():
                    found.append(p)
    return found


def harvest_existing_shards(root: Path) -> Tuple[Dict[str, HarvestedShardState], Dict[str, HarvestedRow]]:
    shard_states: Dict[str, HarvestedShardState] = {}
    all_rows: Dict[str, HarvestedRow] = {}

    for shard_path in find_existing_tokenme_shards(root):
        rel_shard = shard_path.relative_to(root).as_posix()
        st = HarvestedShardState(rel_shard_posix=rel_shard)
        try:
            raw_text = shard_path.read_text(encoding="utf-8", errors="ignore")
            lines = raw_text.splitlines()
        except OSError:
            continue

        st.is_atomic_monolith = bool(ATOMIC_MONOLITH_PATTERN.search(raw_text))
        section = ""
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("# === [PURPOSE] ==="):
                section = "PURPOSE"
                continue
            if stripped.startswith("# === [TOPOLOGY] ==="):
                section = "TOPOLOGY"
                continue
            if stripped.startswith("# === ["):
                section = "OTHER"
                continue

            if section == "PURPOSE" and stripped and not stripped.startswith("#"):
                st.purpose_lines.append(stripped)
            elif section == "TOPOLOGY" and stripped:
                if not stripped.startswith("# [BOOTSTRAP_REQUIRED"):
                    st.topology_lines.append(stripped)

            m_row = FILE_TABLE_ROW_RE.match(stripped)
            if m_row:
                f_path = m_row.group(1).strip()
                old_lc = int(m_row.group(2)) if m_row.group(2) else 1
                c_hash = m_row.group(4).strip()
                s_sig = (m_row.group(5) or "000000").strip()
                role_val = m_row.group(7).strip()
                h_row = HarvestedRow(
                    rel_path=f_path,
                    old_line_count=old_lc,
                    content_hash=c_hash,
                    struct_sig=s_sig,
                    role_summary=role_val,
                    shard_rel_posix=rel_shard,
                    line_number=idx,
                    raw_row=stripped,
                )
                st.rows[f_path] = h_row
                all_rows[f_path] = h_row

        shard_states[rel_shard] = st
    return shard_states, all_rows


def merge_harvested_rows_into_records(records: List[FileRecord], all_rows: Dict[str, HarvestedRow]) -> None:
    """Preserves hydrated role summaries across sync passes."""
    for rec in records:
        h = all_rows.get(rec.rel_path)
        if not h:
            continue
        if not any(tok in h.role_summary for tok in UNFILLED_PLACEHOLDER_PATTERNS):
            rec.role_summary = h.role_summary


# --- ADR-011 & ADR-016 Purpose & Topology Validation & Locking ---

def render_and_lock_purpose_block(
    tier_id: str,
    existing_purpose_lines: List[str],
    default_runtime_str: str,
    scope_label: str,
) -> List[str]:
    spec = STATE_TIERS[tier_id]
    out: List[str] = ["# === [PURPOSE] ==="]

    if not existing_purpose_lines or any("[BOOTSTRAP_REQUIRED" in l for l in existing_purpose_lines):
        out.append(
            f"# [BOOTSTRAP_REQUIRED: POPULATE_PURPOSE | SCOPE={scope_label} | MAX_BYTES={spec.purpose_max_bytes} | "
            "Write 3 lines: SYSTEM:, BOUNDARY:, RUNTIME: then run `python tokenme-sync.py` to lock [#sig] and self-consume this prompt]"
        )
        out.append("SYSTEM: [BOOTSTRAP_REQUIRED]")
        out.append("BOUNDARY: [BOOTSTRAP_REQUIRED]")
        out.append(f"RUNTIME: {default_runtime_str}")
        out.append("")
        return out

    cleaned: List[str] = []
    for l in existing_purpose_lines[:3]:
        cleaned.append(re.sub(r"\s*\[#sig:[0-9a-fA-F]{6}\]\s*$", "", l).strip())
    joined = "\n".join(cleaned)
    sig = short_sig_hex(joined)
    byte_len = utf8_byte_len(joined)
    if byte_len > spec.purpose_max_bytes:
        out.append(f"# [BUDGET_EXCEEDED: PURPOSE block is {byte_len} B > {spec.purpose_max_bytes} B ceiling. Condense prose.]")
    for idx, l in enumerate(cleaned):
        if idx == len(cleaned) - 1:
            out.append(f"{l} [#sig:{sig}]")
        else:
            out.append(l)
    out.append("")
    return out


def validate_and_lock_topology_block(
    tier_id: str,
    existing_topology_lines: List[str],
    workspace_sig_map: Dict[str, Dict[str, str]],
    scope_label: str,
) -> List[str]:
    spec = STATE_TIERS[tier_id]
    out: List[str] = ["# === [TOPOLOGY] ==="]

    raw_edges = [l for l in existing_topology_lines if not l.startswith("#")]
    if not raw_edges:
        out.append(
            f"# [BOOTSTRAP_REQUIRED: POPULATE_TOPOLOGY | SCOPE={scope_label} | "
            f"TARGET_EDGES={spec.topology_min_edges}..{spec.topology_max_edges} | MAX_BYTES={spec.topology_max_bytes} | "
            "Format: `<src_file>::<anchor> -> <dst_file>::<anchor> : <mechanism>`]"
        )
        out.append("")
        return out

    valid_rendered: List[str] = []
    for line in raw_edges:
        m = RE_TOPOLOGY_EDGE.match(line.strip())
        if not m:
            out.append(f"# [STALE_EDGE: Malformed topology edge syntax: {line.strip()}]")
            out.append(line.strip())
            continue

        src_f, src_s = m.group("src_file"), m.group("src_sym")
        dst_f, dst_s = m.group("dst_file"), m.group("dst_sym")
        mech = m.group("mech").strip()
        old_sig = m.group("sig")

        src_map = workspace_sig_map.get(src_f, {})
        dst_map = workspace_sig_map.get(dst_f, {})

        # Allow TOKENME*.txt section targets
        src_sig = "tokenme" if Path(src_f).name.startswith("TOKENME") else src_map.get(src_s)
        dst_sig = "tokenme" if Path(dst_f).name.startswith("TOKENME") else dst_map.get(dst_s)

        if src_sig is None or dst_sig is None:
            missing = f"{src_f}::{src_s}" if src_sig is None else f"{dst_f}::{dst_s}"
            out.append(f"# [STALE_EDGE: Anchor '{missing}' missing from workspace AST/structure. Update or remove edge.]")
            out.append(line.strip())
            continue

        live_edge_sig = short_sig_hex(f"{src_f}::{src_s}={src_sig}->{dst_f}::{dst_s}={dst_sig}")
        if old_sig and old_sig.lower() != live_edge_sig.lower():
            out.append(
                f"# [SIG_DRIFT: Structural signature shifted ({old_sig} -> {live_edge_sig}). "
                "Verify edge accuracy, then run `--ack` or delete [#sig:old] to re-lock.]"
            )
            valid_rendered.append(f"{src_f}::{src_s} -> {dst_f}::{dst_s} : {mech} [#sig:{old_sig}]")
        else:
            valid_rendered.append(f"{src_f}::{src_s} -> {dst_f}::{dst_s} : {mech} [#sig:{live_edge_sig}]")

    total_bytes = utf8_byte_len("\n".join(valid_rendered))
    if len(valid_rendered) > spec.topology_max_edges or total_bytes > spec.topology_max_bytes:
        out.append(
            f"# [BUDGET_EXCEEDED: TOPOLOGY has {len(valid_rendered)} edges ({total_bytes} B); "
            f"ceiling is {spec.topology_max_edges} edges ({spec.topology_max_bytes} B).]"
        )
    out.extend(valid_rendered)
    out.append("")
    return out


# --- ADR-016 HC-01 Section Renderers ---

def render_merkle_header_block(adr_count: int, state_root: str = "PENDING") -> List[str]:
    return [
        f"# TOKENME_VERSION: {SPEC_VERSION}",
        f"# STATE_ROOT: {state_root}",
        f"# ADR_COUNT: {adr_count}",
        "",
    ]


def render_adr_section(adr_records: List[ADRRecord]) -> List[str]:
    if not adr_records:
        return []
    out: List[str] = [
        "# === [ADRS] ===",
        "| Record ID | Date | Status & Supersession | Leaf Hash | Decision Artifact (`[RecordID]_[ISODate]_[TitleSlug].md`) |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for adr in adr_records:
        out.append(f"| `{adr.record_id}` | {adr.iso_date} | {adr.status} | `{adr.leaf_hash}` | `{adr.rel_posix}` |")
    out.append("")
    return out


def render_files_table_section(records: List[FileRecord]) -> List[str]:
    """ADR-016 HC-01: Unified 5-Column GFM Pipe Table for # === [FILES] ===."""
    if not records:
        return []
    out: List[str] = [
        "# === [FILES] ===",
        "| Path & Span | Archetype & Budget | Hash (`content:struct`) | Deterministic AST / Structural Signature | Declarative Role & Invariants |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for rec in records:
        if rec.is_opaque and rec.opaque_info:
            span_tag = "[L4_DEMOTED]" if rec.opaque_info.is_l4_demoted else "[OPAQUE_L3]"
        else:
            span_tag = f"[L1-L{rec.line_count}]"

        role_clean = rec.role_summary.replace("|", ";").strip()
        role_bytes = utf8_byte_len(role_clean)
        if role_bytes > rec.b_hard and not role_clean.startswith("[BUDGET_EXCEEDED"):
            role_clean = f"[BUDGET_EXCEEDED: {role_bytes}B > {rec.b_hard}B] {role_clean}"

        ast_clean = rec.ast_signature_str.replace("|", ";").strip()
        out.append(
            f"| `{rec.rel_path}` `{span_tag}` | `{rec.archetype}` (<={rec.b_hard} B) | "
            f"`{rec.content_hash}:{rec.struct_sig}` | `{ast_clean}` | {role_clean} |"
        )
    out.append("")
    return out


def render_quarantine_section(quarantine_log: List[QuarantineEntry]) -> List[str]:
    if not quarantine_log:
        return []
    out: List[str] = [
        "# === [QUARANTINE] ===",
        "| File / Path | Isolation Reason |",
        "| :--- | :--- |",
    ]
    for q in quarantine_log[:40]:
        out.append(f"| `{q.rel_path}` | `{q.reason}` |")
    out.append("")
    return out


# --- ADR-012, ADR-013 & ADR-016 HC-04 / HC-06 Hop-Distance Sharding & Compaction ---

def evaluate_subdir_shard_trigger(
    subdir_records: List[FileRecord],
    hop_depth: int = 1,
    is_atomic_override: bool = False,
) -> Tuple[bool, str]:
    """
    Evaluates ADR-012 / ADR-016 forward sharding gates with Multi-Modal Splitability check,
    ATOMIC_MONOLITH override, and R_max=1 single-pass child overflow warning.
    """
    if is_atomic_override or any(r.is_atomic_monolith for r in subdir_records):
        return False, "ATOMIC_MONOLITH"
    if len(subdir_records) < MIN_SPLIT_SECTIONS:
        return False, "ATOMIC_MONOLITH"

    n_opaque = sum(1 for r in subdir_records if r.is_opaque)
    total_syms = sum(len(r.symbols) for r in subdir_records)
    table_preview = "\n".join(render_files_table_section(subdir_records))
    est_tok = estimate_tokens(table_preview)
    min_viable_tok = math.ceil(MIN_CHILD_VIABILITY_RATIO * HOP_BASE_TOKENS_S0)

    parent_split_ceiling = hop_split_token_ceiling(max(0, hop_depth - 1), is_monolith=False)
    child_split_ceiling = hop_split_token_ceiling(hop_depth, is_monolith=False)
    overflow_suffix = ":SHARD_OVERFLOW_WARN" if est_tok > child_split_ceiling else ""

    if n_opaque >= OPAQUE_SHARD_COUNT_THRESHOLD:
        return True, f"OPAQUE_DENSITY({n_opaque}){overflow_suffix}"
    if total_syms > SHARD_TRIGGER_SYMBOLS and est_tok >= min_viable_tok:
        return True, f"SYMBOL_COUNT({total_syms}){overflow_suffix}"
    if est_tok > parent_split_ceiling and est_tok >= min_viable_tok:
        return True, f"HOP_BUDGET_SPLIT({est_tok}t){overflow_suffix}"
    return False, "INLINE_IN_ROOT"


def build_documents(
    root: Path,
    records: List[FileRecord],
    adr_records: List[ADRRecord],
    quarantine_log: List[QuarantineEntry],
    runtimes: List[str],
    harvested_shards: Dict[str, HarvestedShardState],
    workspace_sig_map: Dict[str, Dict[str, str]],
    root_len: int = DEFAULT_ROOT_HASH_LEN,
    force_single: bool = False,
    compact_mode: bool = False,
) -> Dict[Path, str]:
    runtime_str = ", ".join(runtimes) if runtimes else "Python >= 3.9 (Standard Library Only)"
    outputs: Dict[Path, str] = {}
    mounted_shards: List[Tuple[str, str, str, int, int, str]] = []

    by_subsystem: Dict[str, List[FileRecord]] = {}
    for r in records:
        by_subsystem.setdefault(r.subsystem, []).append(r)

    unsharded_records: List[FileRecord] = []
    promoted_topology_edges: List[str] = []

    prev_root = harvested_shards.get("TOKENME.txt")
    root_atomic_monolith = bool(prev_root and prev_root.is_atomic_monolith)

    # Pre-check whole-repo monolith ceiling (d=0 MONOLITH_MAX_TOKENS = 3,000t)
    full_table_tok = estimate_tokens("\n".join(render_files_table_section(records))) + 250
    monolith_exceeded = full_table_tok > hop_split_token_ceiling(0, is_monolith=True)

    # Pass 1: Evaluate Subdirectory Shards (d >= 1)
    for sub_name, sub_recs in sorted(by_subsystem.items()):
        if sub_name == "root" or force_single or root_atomic_monolith:
            unsharded_records.extend(sub_recs)
            continue

        slug = re.sub(r"[^a-zA-Z0-9_-]", "-", sub_name.lower())
        rel_shard_posix = f"{sub_name}/TOKENME.{slug}.txt"
        prev_shard_state = harvested_shards.get(rel_shard_posix)

        # Compute effective hop depth from directory nesting
        max_rel_depth = max(1, max(len(r.rel_path.split("/")) - 1 for r in sub_recs))
        hop_d = min(4, max_rel_depth)

        should_shard, reason = evaluate_subdir_shard_trigger(
            sub_recs,
            hop_depth=hop_d,
            is_atomic_override=bool(prev_shard_state and prev_shard_state.is_atomic_monolith),
        )

        # If total monolith exceeds 3,000t and subsystem is viable, eject as shard
        if not should_shard and monolith_exceeded and len(sub_recs) >= MIN_SPLIT_SECTIONS:
            sub_tok = estimate_tokens("\n".join(render_files_table_section(sub_recs)))
            if sub_tok >= math.ceil(MIN_CHILD_VIABILITY_RATIO * HOP_BASE_TOKENS_S0):
                should_shard = True
                reason = f"MONOLITH_EJECT({sub_tok}t)"

        # Hysteresis Preservation & --compact Coalescing (ADR-013 & ADR-016 HC-04 / HC-06)
        if prev_shard_state is not None and not should_shard:
            preview_lines = render_files_table_section(sub_recs)
            est_shard_tok = estimate_tokens("\n".join(preview_lines)) + 160
            merge_floor = hop_merge_token_floor(hop_d)
            root_preview_tok = estimate_tokens("\n".join(render_files_table_section(unsharded_records + sub_recs))) + 250
            parent_headroom_cap = math.floor(PARENT_ABSORPTION_RATIO * hop_split_token_ceiling(0, is_monolith=False))
            fits_parent = root_preview_tok <= parent_headroom_cap

            if est_shard_tok <= merge_floor and fits_parent:
                if not compact_mode:
                    print(
                        f"[WARN: COMPACT_ELIGIBLE] Shard '{rel_shard_posix}' is at <=35% capacity ({est_shard_tok}t <= {merge_floor}t) "
                        f"and fits within parent headroom ({root_preview_tok}t <= {parent_headroom_cap}t). Run with '--compact' to coalesce.",
                        file=sys.stderr,
                    )
                    should_shard = True
                    reason = f"HYSTERESIS_RETENTION({est_shard_tok}t<={merge_floor}t)"
                else:
                    # Coalesce child shard back into root and preserve cross-module topology edges
                    for edge_line in prev_shard_state.topology_lines:
                        m_e = RE_TOPOLOGY_EDGE.match(edge_line.strip())
                        if m_e:
                            sf, df, ds = m_e.group("src_file"), m_e.group("dst_file"), m_e.group("dst_sym")
                            if not df.startswith(f"{sub_name}/"):
                                promoted_topology_edges.append(edge_line)
                            else:
                                for r in sub_recs:
                                    if r.rel_path == sf and f"-> {df}::{ds}" not in r.role_summary:
                                        r.role_summary = f"{r.role_summary} [Coupling: -> {df}::{ds}]"
            else:
                should_shard = True
                reason = f"HYSTERESIS_RETENTION({est_shard_tok}t>{merge_floor}t)"

        if not should_shard:
            unsharded_records.extend(sub_recs)
            continue

        for r in sub_recs:
            r.assigned_shard = rel_shard_posix

        shard_lines = render_merkle_header_block(adr_count=len(adr_records), state_root="PENDING")
        shard_lines.extend(
            render_and_lock_purpose_block(
                "L2_SHARD",
                prev_shard_state.purpose_lines if prev_shard_state else [],
                runtime_str,
                scope_label=f"{sub_name}/",
            )
        )
        shard_lines.extend(
            validate_and_lock_topology_block(
                "L2_SHARD",
                prev_shard_state.topology_lines if prev_shard_state else [],
                workspace_sig_map,
                scope_label=f"{sub_name}/",
            )
        )
        shard_lines.extend(render_files_table_section(sub_recs))

        raw_shard_text = "\n".join(shard_lines).rstrip() + "\n"
        local_agents = root / sub_name / "AGENTS.md"
        stamped_shard_text, child_root = stamp_state_root_in_text(raw_shard_text, local_agents, root_len=root_len)
        outputs[root / rel_shard_posix] = stamped_shard_text
        mounted_shards.append(
            (f"{sub_name}/", rel_shard_posix, reason, len(sub_recs), estimate_tokens(stamped_shard_text), child_root)
        )

    # Assemble Root TOKENME.txt (d=0)
    unsharded_records.sort(key=lambda r: r.rel_path)
    root_tier = "L1_ROOT" if mounted_shards else "L1_MONO"
    combined_root_edges = list(prev_root.topology_lines if prev_root else [])
    for pe in promoted_topology_edges:
        if pe not in combined_root_edges and len(combined_root_edges) < STATE_TIERS[root_tier].topology_max_edges:
            combined_root_edges.append(pe)

    root_lines = render_merkle_header_block(adr_count=len(adr_records), state_root="PENDING")
    if root_atomic_monolith:
        root_lines.append("# ATOMIC_MONOLITH: true")
        root_lines.append("")
    root_lines.extend(
        render_and_lock_purpose_block(
            root_tier,
            prev_root.purpose_lines if prev_root else [],
            runtime_str,
            scope_label="root",
        )
    )
    root_lines.extend(
        validate_and_lock_topology_block(
            root_tier,
            combined_root_edges,
            workspace_sig_map,
            scope_label="root",
        )
    )

    if mounted_shards:
        root_lines.extend([
            "# === [SHARDS] ===",
            "| Scope | Shard Mount Path | Trigger Reason | Files | Est. Tokens | Child `STATE_ROOT` |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for sc, rel_sh, rsn, f_cnt, tok_cnt, c_root in mounted_shards:
            root_lines.append(f"| `{sc}` | `./{rel_sh}` | `{rsn}` | {f_cnt} | ~{tok_cnt}t | `{c_root}` |")
        root_lines.append("")

    root_lines.extend(render_adr_section(adr_records))
    root_lines.extend(render_files_table_section(unsharded_records))
    root_lines.extend(render_quarantine_section(quarantine_log))

    raw_root_text = "\n".join(root_lines).rstrip() + "\n"
    stamped_root_text, _ = stamp_state_root_in_text(raw_root_text, root / "AGENTS.md", root_len=root_len)
    outputs[root / "TOKENME.txt"] = stamped_root_text
    return outputs


# --- ADR-015 & ADR-016 HC-02 / HC-06 Triage Dispatcher (--triage) & Atomic Ack (--ack) ---

def _resolve_git_diff_metrics(
    root: Path, rel_file: str, shard_rel_posix: str, file_line_count: int
) -> Tuple[Optional[int], Optional[int], Optional[float], Optional[str]]:
    """
    ADR-015 Sec 2.3 & ADR-016 HC-06 Edge Case 4 Fix:
    Resolves GIT_DIFF_CMD across working tree or last shard commit, guarding against '-' binary numstat.
    """
    try:
        st_proc = subprocess.run(
            ["git", "status", "--porcelain", "--", rel_file],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if st_proc.returncode != 0:
            return None, None, None, None

        if st_proc.stdout.strip():
            diff_base = "HEAD"
            git_cmd = f"git diff HEAD -- {rel_file}"
            num_args = ["git", "diff", "HEAD", "--numstat", "--", rel_file]
        else:
            log_proc = subprocess.run(
                ["git", "log", "-n", "1", "--format=%H", "--", shard_rel_posix],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            shard_commit = log_proc.stdout.strip()
            if shard_commit:
                diff_base = f"{shard_commit}..HEAD"
                git_cmd = f"git diff {diff_base} -- {rel_file}"
                num_args = ["git", "diff", diff_base, "--numstat", "--", rel_file]
            else:
                return None, None, None, None

        num_proc = subprocess.run(num_args, cwd=str(root), capture_output=True, text=True, timeout=5)
        if num_proc.returncode != 0 or not num_proc.stdout.strip():
            return 0, 0, 0.0, git_cmd

        first_line = num_proc.stdout.strip().splitlines()[0]
        parts = first_line.split("\t")
        if len(parts) < 2 or parts[0] == "-" or parts[1] == "-":
            # Binary or un-diffable file guard (ADR-016 HC-06)
            return None, None, 1.0, None

        added, deleted = int(parts[0]), int(parts[1])
        ratio = (added + deleted) / max(1, file_line_count)
        return added, deleted, ratio, git_cmd
    except Exception:
        return None, None, None, None


def run_triage_dispatcher(
    root: Path,
    max_size_bytes: int,
    leaf_len: int,
    strict_bytes: bool = False,
) -> Tuple[List[TriageItem], int]:
    """
    ADR-015 & ADR-016: Scans all shards and disk files in memory, emitting the deterministic
    maintenance queue without requiring the LLM agent to read clean manifests.
    """
    records, _, _, _ = scan_repository(root, max_size_bytes=max_size_bytes, leaf_len=leaf_len, dry_run=True)
    shard_states, all_rows = harvest_existing_shards(root)
    disk_map: Dict[str, FileRecord] = {r.rel_path: r for r in records}
    items: List[TriageItem] = []

    # 1. Scan existing shards for contiguous [BOOTSTRAP_REQUIRED], [STALE_EDGE], [SIG_DRIFT], [BUDGET_EXCEEDED]
    for rel_shard, st in sorted(shard_states.items()):
        shard_path = root / rel_shard
        try:
            lines = shard_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        idx = 1
        n_lines = len(lines)
        while idx <= n_lines:
            stripped = lines[idx - 1].strip()
            if stripped.startswith("# [BOOTSTRAP_REQUIRED:"):
                start_line = idx
                end_line = idx
                block_id = "PURPOSE" if "POPULATE_PURPOSE" in stripped else "TOPOLOGY"
                while end_line + 1 <= n_lines and lines[end_line].strip() and not lines[end_line].strip().startswith("# === ["):
                    end_line += 1
                anchor_str = f"Lines {start_line}-{end_line}" if end_line > start_line else f"Line {start_line}"
                items.append(
                    TriageItem(
                        item_type="UNFILLED_BOOTSTRAP",
                        target_shard=rel_shard,
                        line_anchor=anchor_str,
                        block_id=block_id,
                        current_text=stripped,
                        recommended_action=f"Populate {block_id} block at {anchor_str} in {rel_shard} and run `python tokenme-sync.py`.",
                    )
                )
                idx = end_line + 1
                continue

            if stripped.startswith("# [STALE_EDGE:") or stripped.startswith("# [SIG_DRIFT:") or stripped.startswith("# [BUDGET_EXCEEDED:"):
                items.append(
                    TriageItem(
                        item_type="TOPOLOGY_OR_BUDGET_ALERT",
                        target_shard=rel_shard,
                        line_anchor=f"Line {idx}",
                        block_id="HEADER_DIRECTIVE",
                        current_text=stripped,
                        recommended_action=f"Resolve directive at Line {idx} in {rel_shard} and run `python tokenme-sync.py`.",
                    )
                )
            idx += 1

    # 2. Check tracked rows vs. live disk state
    for rel_path, h_row in sorted(all_rows.items()):
        rec = disk_map.get(rel_path)
        if rec is None:
            items.append(
                TriageItem(
                    item_type="ORPHANED_ENTRY",
                    target_shard=h_row.shard_rel_posix,
                    line_anchor=f"Line {h_row.line_number}",
                    tracked_file=rel_path,
                    current_row=h_row.raw_row,
                    recommended_action=f"Run `python tokenme-sync.py` to prune deleted file {rel_path} from {h_row.shard_rel_posix}.",
                )
            )
            continue

        if any(tok in h_row.role_summary for tok in UNFILLED_PLACEHOLDER_PATTERNS):
            items.append(
                TriageItem(
                    item_type="UNFILLED_BOOTSTRAP",
                    target_shard=h_row.shard_rel_posix,
                    line_anchor=f"Line {h_row.line_number}",
                    tracked_file=rel_path,
                    current_row=h_row.raw_row,
                    recommended_action=f"Inspect {rel_path} and populate Declarative Role at Line {h_row.line_number} in {h_row.shard_rel_posix}.",
                )
            )
            continue

        if h_row.content_hash != rec.content_hash:
            # ADR-016 HC-02 Dual-Hash Auto-Ack Check: if structural sig is identical, skip unless --strict-bytes
            if h_row.struct_sig == rec.struct_sig and not strict_bytes:
                continue

            added, deleted, ratio, git_cmd = _resolve_git_diff_metrics(
                root, rel_path, h_row.shard_rel_posix, rec.line_count
            )
            delta_str = f"{h_row.content_hash}:{h_row.struct_sig} (manifest) -> {rec.content_hash}:{rec.struct_sig} (disk)"
            if ratio is not None and ratio <= DIFF_EFFICIENCY_GATE and git_cmd:
                items.append(
                    TriageItem(
                        item_type="STALE_HASH (MINOR_DELTA)",
                        target_shard=h_row.shard_rel_posix,
                        line_anchor=f"Line {h_row.line_number}",
                        tracked_file=rel_path,
                        hash_delta=delta_str,
                        diff_metrics=f"+{added} / -{deleted} lines (File Total: {rec.line_count} lines | Ratio: {ratio:.2f} <= 0.60)",
                        current_row=h_row.raw_row,
                        git_diff_cmd=git_cmd,
                        recommended_action=(
                            f"Run GIT_DIFF_CMD. If CURRENT_ROW blurb remains accurate, run "
                            f"`python tokenme-sync.py --ack {rel_path}`. Otherwise update Line {h_row.line_number} in {h_row.shard_rel_posix}."
                        ),
                    )
                )
            else:
                ratio_str = f"{ratio:.2f} > 0.60" if ratio is not None else "N/A (no git baseline)"
                metrics_str = (
                    f"+{added} / -{deleted} lines (File Total: {rec.line_count} lines | Ratio: {ratio_str})"
                    if added is not None
                    else f"File Total: {rec.line_count} lines | Ratio: {ratio_str}"
                )
                items.append(
                    TriageItem(
                        item_type="STALE_HASH (MAJOR_DELTA)",
                        target_shard=h_row.shard_rel_posix,
                        line_anchor=f"Line {h_row.line_number}",
                        tracked_file=rel_path,
                        hash_delta=delta_str,
                        diff_metrics=metrics_str,
                        current_row=h_row.raw_row,
                        recommended_action=f"READ_FILE_DIRECTLY. Inspect {rel_path} and update Line {h_row.line_number} in {h_row.shard_rel_posix}.",
                    )
                )

    # 3. Check for untracked files on disk & route to owning subsystem shard if present (ADR-015 Sec 2.2)
    for rel_path, rec in sorted(disk_map.items()):
        if rel_path not in all_rows:
            slug = re.sub(r"[^a-zA-Z0-9_-]", "-", rec.subsystem.lower())
            candidate_shard = f"{rec.subsystem}/TOKENME.{slug}.txt"
            owning_shard = candidate_shard if candidate_shard in shard_states else "TOKENME.txt"
            items.append(
                TriageItem(
                    item_type="UNTRACKED_ARTIFACT",
                    target_shard=owning_shard,
                    line_anchor="APPEND_ROW",
                    tracked_file=rel_path,
                    disk_hash=f"{rec.content_hash}:{rec.struct_sig}",
                    hash_delta=f"NONE -> {rec.content_hash}:{rec.struct_sig}",
                    recommended_action=(
                        f"Read first 30 lines of {rel_path}, run `python tokenme-sync.py` to scaffold row in "
                        f"{owning_shard}, and populate its Declarative Role."
                    ),
                )
            )

    if not items:
        print("=== TOKENME MAINTENANCE QUEUE (STATE: CLEAN | ITEMS: 0) ===")
        return items, 0

    print(f"=== TOKENME MAINTENANCE QUEUE (STATE: DIRTY | ITEMS: {len(items)}) ===\n")
    for idx, it in enumerate(items, start=1):
        print(f"[{idx}] TYPE: {it.item_type}")
        print(f"    TARGET_SHARD:       {it.target_shard}")
        print(f"    LINE_ANCHOR:        {it.line_anchor}")
        if it.tracked_file:
            print(f"    TRACKED_FILE:       {it.tracked_file}")
        if it.block_id:
            print(f"    BLOCK_ID:           {it.block_id}")
        if it.current_text:
            print(f"    CURRENT_TEXT:       {it.current_text}")
        if it.disk_hash:
            print(f"    DISK_HASH:          {it.disk_hash}")
        if it.hash_delta:
            print(f"    HASH_DELTA:         {it.hash_delta}")
        if it.diff_metrics:
            print(f"    DIFF_METRICS:       {it.diff_metrics}")
        if it.current_row:
            print(f"    CURRENT_ROW:        {it.current_row}")
        if it.git_diff_cmd:
            print(f"    GIT_DIFF_CMD:       {it.git_diff_cmd}")
        print(f"    RECOMMENDED_ACTION: {it.recommended_action}\n")
    return items, 0


def run_atomic_ack(
    root: Path,
    ack_files: List[str],
    max_size_bytes: int,
    leaf_len: int,
    root_len: int,
    custom_adr_dir: Optional[str] = None,
) -> int:
    """
    ADR-015 Sec 2.4 & ADR-016 HC-02:
    Validates that target files are tracked, filled, and free of [STALE_EDGE] errors,
    then updates their hashes, re-locks [TOPOLOGY] [#sig] tags, and recomputes STATE_ROOTs.
    """
    _, all_rows = harvest_existing_shards(root)
    records, quarantine_log, runtimes, workspace_sig_map = scan_repository(
        root, max_size_bytes=max_size_bytes, leaf_len=leaf_len, dry_run=False
    )
    rec_map = {r.rel_path: r for r in records}

    normalized_targets: List[str] = []
    for raw_f in ack_files:
        norm_p = Path(raw_f)
        if norm_p.is_absolute():
            try:
                rel_s = norm_p.resolve().relative_to(root).as_posix()
            except ValueError:
                print(f"[ERROR] File outside repository root: {raw_f}", file=sys.stderr)
                return 2
        else:
            rel_s = raw_f.replace("\\", "/").lstrip("./")
        normalized_targets.append(rel_s)

    for target in normalized_targets:
        if target not in all_rows or target not in rec_map:
            print(
                f"[ACK REJECTED] Exit 2: Cannot acknowledge untracked artifact `{target}`; run `tokenme-sync.py` first.",
                file=sys.stderr,
            )
            return 2
        row = all_rows[target]
        if any(tok in row.role_summary for tok in UNFILLED_PLACEHOLDER_PATTERNS):
            print(
                f"[ACK REJECTED] Exit 2: Cannot acknowledge unfilled `[BOOTSTRAP_REQUIRED]` entry for `{target}`; supply a declarative summary first.",
                file=sys.stderr,
            )
            return 2

    # Check that no topology edge referencing target has a missing anchor ([STALE_EDGE])
    shard_states, _ = harvest_existing_shards(root)
    for st in shard_states.values():
        cleaned_edges: List[str] = []
        for edge_line in st.topology_lines:
            m = RE_TOPOLOGY_EDGE.match(edge_line.strip())
            if not m:
                continue
            sf, ss = m.group("src_file"), m.group("src_sym")
            df, ds = m.group("dst_file"), m.group("dst_sym")
            if sf in normalized_targets or df in normalized_targets:
                s_ok = Path(sf).name.startswith("TOKENME") or (ss in workspace_sig_map.get(sf, {}))
                d_ok = Path(df).name.startswith("TOKENME") or (ds in workspace_sig_map.get(df, {}))
                if not (s_ok and d_ok):
                    print(
                        f"[ACK REJECTED] Exit 2: `{sf}::{ss} -> {df}::{ds}` references a deleted symbol (`[STALE_EDGE]`). Fix `[TOPOLOGY]` before `--ack`.",
                        file=sys.stderr,
                    )
                    return 2
                # Strip old [#sig:...] so validate_and_lock_topology_block stamps the new live signature
                edge_line = re.sub(r"\s*\[#sig:[0-9a-fA-F]{6}\]\s*$", "", edge_line)
            cleaned_edges.append(edge_line)
        st.topology_lines = cleaned_edges

    merge_harvested_rows_into_records(records, all_rows)
    adr_records = discover_adr_records(root, leaf_len=leaf_len, custom_dir=custom_adr_dir)
    outputs = build_documents(
        root=root,
        records=records,
        adr_records=adr_records,
        quarantine_log=quarantine_log,
        runtimes=runtimes,
        harvested_shards=shard_states,
        workspace_sig_map=workspace_sig_map,
        root_len=root_len,
    )
    atomic_commit_outputs(root, outputs, clean_stale_shards=True)
    print(f"[OK] Acknowledged {len(normalized_targets)} file(s) and cascaded Merkle STATE_ROOTs.")
    return 0


# --- ADR-008, ADR-014 & ADR-016 HC-06 Integrity Verification (--check) ---

def run_integrity_check(
    root: Path, leaf_len: int, root_len: int, custom_adr_dir: Optional[str] = None
) -> Tuple[int, List[str]]:
    """
    Returns (exit_code, errors):
      0 = Clean
      2 = Merkle drift, child shard STATE_ROOT drift, ADR-014 AGENTS.md comment violation,
          unfilled [BOOTSTRAP_REQUIRED], [STALE_EDGE], or [BUDGET_EXCEEDED]
    """
    errors: List[str] = []
    root_tokenme = root / "TOKENME.txt"
    if not root_tokenme.is_file():
        return 2, ["Missing root `TOKENME.txt`."]

    try:
        root_text = root_tokenme.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    except OSError as exc:
        return 1, [f"Failed to read `TOKENME.txt`: {exc}"]

    # ADR-014 Single-State Instruction Isolation Check on AGENTS.md
    agents_file = root / "AGENTS.md"
    if agents_file.is_file():
        try:
            agents_txt = agents_file.read_text(encoding="utf-8", errors="ignore")
            if "<!--" in agents_txt:
                errors.append(
                    "ADR-014 Single-State Isolation violation in `AGENTS.md`: Dormant HTML comments (`<!-- ... -->`) "
                    "are prohibited to prevent BPE token waste and semantic priming."
                )
        except OSError:
            pass

    m_root = STATE_ROOT_PATTERN.search(root_text)
    if not m_root:
        errors.append("Root `TOKENME.txt` is missing `# STATE_ROOT: <hex>` header.")
    else:
        recorded_root = m_root.group(2)
        expected_root = compute_merkle_state_root_from_text(
            root_text, agents_file, root_len=len(recorded_root) if len(recorded_root) >= 8 else root_len
        )
        if recorded_root != expected_root:
            errors.append(f"Root STATE_ROOT mismatch: recorded `{recorded_root}` != computed `{expected_root}`.")

    try:
        adr_records = discover_adr_records(root, leaf_len=leaf_len, custom_dir=custom_adr_dir)
    except Exception as exc:
        errors.append(str(exc))
        adr_records = []

    m_count = re.search(r"^#\s*ADR_COUNT:\s*(\d+)", root_text, re.MULTILINE)
    if m_count and int(m_count.group(1)) != len(adr_records):
        errors.append(f"ADR_COUNT mismatch: `TOKENME.txt` records {m_count.group(1)}, disk has {len(adr_records)}.")

    for adr in adr_records:
        if f"| `{adr.leaf_hash}` | `{adr.rel_posix}` |" not in root_text:
            errors.append(f"ADR leaf drift or unindexed ADR: `{adr.rel_posix}` (`{adr.leaf_hash}`).")

    for shard_path in find_existing_tokenme_shards(root):
        rel_sh = shard_path.relative_to(root).as_posix()
        txt = shard_path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").strip()
        if rel_sh != "TOKENME.txt":
            m_sr = STATE_ROOT_PATTERN.search(txt)
            if not m_sr:
                errors.append(f"Child shard `{rel_sh}` is missing `# STATE_ROOT: <hex>` header.")
            else:
                rec_sr = m_sr.group(2)
                exp_sr = compute_merkle_state_root_from_text(
                    txt, shard_path.parent / "AGENTS.md", root_len=len(rec_sr) if len(rec_sr) >= 8 else root_len
                )
                if rec_sr != exp_sr:
                    errors.append(f"Child shard `{rel_sh}` STATE_ROOT mismatch: recorded `{rec_sr}` != computed `{exp_sr}`.")
                if f"| `./{rel_sh}` |" in root_text and f"| `{rec_sr}` |" not in root_text:
                    errors.append(f"Root `# === [SHARDS] ===` table has stale Child `STATE_ROOT` for `{rel_sh}`.")
        for marker in ("# [BOOTSTRAP_REQUIRED", "# [STALE_EDGE:", "# [BUDGET_EXCEEDED:", "| `[BOOTSTRAP_REQUIRED]` |"):
            if marker in txt:
                errors.append(f"Validation gate failed in `{rel_sh}`: contains `{marker}`.")

    # Verify L4 sidecar source hashes if any .l3.txt files exist
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in sorted(dirnames) if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".")]
        for fname in sorted(filenames):
            if fname.endswith(".l3.txt"):
                sp = Path(dirpath) / fname
                try:
                    stxt = sp.read_text(encoding="utf-8", errors="ignore")
                    m_src = re.search(r"^#\s*L4_SOURCE_FILE:\s*(.+)$", stxt, re.MULTILINE)
                    m_hsh = re.search(r"^#\s*L4_SOURCE_HASH:\s*([0-9a-fA-F]+)$", stxt, re.MULTILINE)
                    if m_src and m_hsh:
                        raw_src_path = root / m_src.group(1).strip()
                        if raw_src_path.is_file():
                            live_h = stream_sha256_hex(raw_src_path, length=len(m_hsh.group(1).strip()))
                            if live_h != m_hsh.group(1).strip():
                                errors.append(f"L4 sidecar `{sp.relative_to(root).as_posix()}` L4_SOURCE_HASH drift.")
                        else:
                            errors.append(f"L4 sidecar `{sp.relative_to(root).as_posix()}` points to missing source `{m_src.group(1).strip()}`.")
                except OSError:
                    pass

    return (0 if not errors else 2), errors


def atomic_commit_outputs(root: Path, outputs: Dict[Path, str], clean_stale_shards: bool = True) -> None:
    staged_pairs: List[Tuple[Path, Path]] = []
    pid = os.getpid()
    try:
        for final_path, content in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
            final_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_fd, tmp_raw_path = tempfile.mkstemp(
                prefix=f".tokenme-sync.{final_path.name}.{pid}.",
                suffix=".tmp",
                dir=str(final_path.parent),
                text=True,
            )
            tmp_path = Path(tmp_raw_path)
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
                raise
            staged_pairs.append((tmp_path, final_path))

        for tmp_path, final_path in staged_pairs:
            os.replace(str(tmp_path), str(final_path))

        if clean_stale_shards:
            for existing_file in find_existing_tokenme_shards(root):
                if existing_file not in outputs and not existing_file.is_symlink():
                    try:
                        existing_file.unlink()
                    except OSError:
                        pass
    except Exception:
        for tmp_path, _ in staged_pairs:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tokenme-sync.py",
        description="TOKENME v2.1 Epistemic State Compiler, Triage Dispatcher, and Merkle Verifier.",
    )
    parser.add_argument("root", nargs="?", default=".", help="Repository root directory.")
    parser.add_argument("--init", action="store_true", help="Scaffold a cold repository.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing TOKENME files when combined with --init.")
    parser.add_argument("--force-init", action="store_true", help="Alias for --init --force (ADR-011).")
    parser.add_argument("--sync", "--fix", dest="sync", action="store_true", help="Synchronize coordinates, hashes, and STATE_ROOT.")
    parser.add_argument("--check", action="store_true", help="Fast read-only Merkle & validation check (exits 2 on drift/unfilled).")
    parser.add_argument("--triage", action="store_true", help="Emit deterministic maintenance work queue (ADR-015).")
    parser.add_argument("--ack", nargs="+", metavar="FILE", help="Atomically acknowledge internal edits without prose changes (ADR-015).")
    parser.add_argument("--compact", action="store_true", help="Coalesce contracted shards below 35%% hysteresis floor (ADR-013).")
    parser.add_argument("--strict-bytes", action="store_true", help="Report comment-only byte changes in --triage even when struct_sig matches.")
    parser.add_argument("--single", action="store_true", help="Force monolithic single-file output.")
    parser.add_argument("--leaf-len", type=int, default=DEFAULT_LEAF_HASH_LEN, help="Hex length for ADR/sidecar leaf digests (6..64).")
    parser.add_argument("--root-len", type=int, default=DEFAULT_ROOT_HASH_LEN, help="Hex length for Merkle STATE_ROOT (8..64).")
    parser.add_argument("--adr-dir", type=str, default=None, help="Override ADR directory relative to root.")
    parser.add_argument("--max-size-kb", type=int, default=DEFAULT_MAX_FILE_SIZE_KB, help="Max text file size in KiB.")
    parser.add_argument("--dry-run", action="store_true", help="Compute state in memory without writing files.")

    args = parser.parse_args()
    if args.force_init:
        args.init = True
        args.force = True

    root_path = Path(args.root).resolve()
    if not root_path.is_dir():
        print(f"[ERROR] Target directory does not exist: {root_path}", file=sys.stderr)
        return 1

    max_size_bytes = max(1, args.max_size_kb) * 1024

    if args.triage:
        items, code = run_triage_dispatcher(
            root_path, max_size_bytes=max_size_bytes, leaf_len=args.leaf_len, strict_bytes=args.strict_bytes
        )
        if args.check and items:
            return 2
        return code

    if args.ack:
        return run_atomic_ack(
            root_path,
            ack_files=args.ack,
            max_size_bytes=max_size_bytes,
            leaf_len=args.leaf_len,
            root_len=args.root_len,
            custom_adr_dir=args.adr_dir,
        )

    if args.check:
        code, err_list = run_integrity_check(
            root_path, leaf_len=args.leaf_len, root_len=args.root_len, custom_adr_dir=args.adr_dir
        )
        if code == 0:
            print(f"[OK] TOKENME v{SPEC_VERSION} Merkle STATE_ROOT and epistemic gates verified CLEAN.")
            return 0
        print(f"[FAIL] Epistemic state check failed ({len(err_list)} issue(s)):", file=sys.stderr)
        for e in err_list:
            print(f"  - {e}", file=sys.stderr)
        return code

    target_root_file = root_path / "TOKENME.txt"
    tokenme_exists = target_root_file.is_file() and not target_root_file.is_symlink()

    if args.init:
        if tokenme_exists and not (args.force or args.dry_run):
            print("[ABORT] `TOKENME.txt` already exists. Use `--init --force` (or `--force-init`) to overwrite.", file=sys.stderr)
            return 1
        # ADR-014: Scaffold canonical Profile A AGENTS.md if missing during cold --init
        agents_target = root_path / "AGENTS.md"
        if not agents_target.exists() and not args.dry_run:
            try:
                agents_target.write_text(DEFAULT_AGENTS_MD_TEMPLATE, encoding="utf-8", newline="\n")
            except OSError:
                pass
    elif not tokenme_exists:
        print("[NOTICE] No `TOKENME.txt` found. Run `python tokenme-sync.py --init` to scaffold.", file=sys.stderr)
        return 1

    try:
        adr_records = discover_adr_records(root_path, leaf_len=args.leaf_len, custom_dir=args.adr_dir)
    except Exception as exc:
        print(f"[ERROR] ADR discovery failed: {exc}", file=sys.stderr)
        return 1

    records, quarantine_log, runtimes, workspace_sig_map = scan_repository(
        root_path, max_size_bytes=max_size_bytes, leaf_len=args.leaf_len, dry_run=args.dry_run
    )

    harvested_shards: Dict[str, HarvestedShardState] = {}
    if not args.init:
        harvested_shards, all_rows = harvest_existing_shards(root_path)
        merge_harvested_rows_into_records(records, all_rows)

    outputs = build_documents(
        root=root_path,
        records=records,
        adr_records=adr_records,
        quarantine_log=quarantine_log,
        runtimes=runtimes,
        harvested_shards=harvested_shards,
        workspace_sig_map=workspace_sig_map,
        root_len=args.root_len,
        force_single=args.single,
        compact_mode=args.compact,
    )

    if not args.dry_run:
        atomic_commit_outputs(root_path, outputs, clean_stale_shards=True)

    root_doc = outputs.get(root_path / "TOKENME.txt", "")
    m_sr = STATE_ROOT_PATTERN.search(root_doc)
    sr_str = m_sr.group(2) if m_sr else "UNKNOWN"
    print(
        f"[OK] tokenme-sync.py v{VERSION} (Spec v{SPEC_VERSION}) synced {len(records)} files across "
        f"{len(outputs)} shard(s) | STATE_ROOT: {sr_str}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())