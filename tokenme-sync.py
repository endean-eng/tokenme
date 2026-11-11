#!/usr/bin/env python3
"""
tokenme-sync.py (v0.0.3)
Zero-dependency, fail-closed structural reference scaffolder and coordinate
synchronizer for the TOKENME.txt (v2.0) epistemic specification.

Implements:
  - ADR-004: Vertical Domain Sharding with Root L2 Eviction & Flat-Repo Fallback
  - ADR-005: Canonical Symbol Ownership & Qualified Class Scoping
  - ADR-006: Reference Scaffolder Functional Boundaries & Fail-Closed Hardening
  - Inverted CLI UX: Default execution updates existing TOKENME.txt; `--init` scaffolds cold repos.

Requires: Python >= 3.9 (Standard Library Only)
License: MIT / CC-BY 4.0
Repository: https://github.com/endean-eng/tokenme
"""

from __future__ import annotations

import argparse
import ast
import datetime
import fnmatch
import math
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

VERSION = "0.0.3"
SPEC_VERSION = "2.0"

# --- Canonical v2.0 & ADR-004 Sharding Thresholds ---
SHARD_TRIGGER_TOKENS = 3000
SHARD_TRIGGER_LINES = 250
SHARD_TRIGGER_SYMBOLS = 75
SHARD_TRIGGER_RUNTIMES = 2
MAX_SHARD_TOKENS = 2000

# --- ADR-006 Fail-Closed Quarantine Constants ---
DEFAULT_MAX_FILE_SIZE_KB = 1024  # 1 MiB default ceiling
BINARY_SNIFF_BYTES = 8192
TOKEN_SAFETY_MARGIN = 1.15  # 15% conservative buffer when tiktoken is absent

# Optional dynamic tiktoken import (ADR-006 Sec 3: zero hard dependency)
try:
    import tiktoken  # type: ignore
    _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TIKTOKEN_ENC = None

# --- Hardcoded Exclusions (Always ignored regardless of .gitignore) ---
DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".roo", ".cursor",
    "node_modules", "bower_components", "jspm_packages",
    "venv", ".venv", "env", ".env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "site-packages",
    "dist", "build", "out", "target", "bin", "obj", "coverage",
    ".next", ".nuxt", ".svelte-kit", ".vercel", ".output", "vendor",
}

DEFAULT_IGNORE_PATTERNS: List[str] = [
    "*.min.js", "*.min.css", "*.map", "*.lock", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock",
    "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.dylib", "*.exe",
    "*.o", "*.a", "*.lib", "*.class", "*.jar", "*.war", "*.ear",
    "*.zip", "*.tar", "*.gz", "*.tgz", "*.bz2", "*.7z", "*.rar",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.svg", "*.webp",
    "*.mp3", "*.mp4", "*.wav", "*.avi", "*.mov", "*.pdf", "*.doc",
    "*.docx", "*.xls", "*.xlsx", "*.ppt", "*.pptx", "*.woff", "*.woff2",
    "*.ttf", "*.eot", "*.otf", "*.db", "*.sqlite", "*.sqlite3",
    "TOKENME*.txt", "llms*.txt", ".DS_Store", "Thumbs.db",
    ".tokenme-sync.*.tmp",
]

# --- Manifest Fingerprinting Table ---
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
    "build.gradle.kts": "Java / Kotlin (Gradle KTS)",
    "Gemfile": "Ruby (Bundler)",
    "composer.json": "PHP (Composer)",
    "appsscript.json": "Google Apps Script (V8)",
    "CMakeLists.txt": "C / C++ (CMake)",
    "Makefile": "Make / Native Build",
    "Dockerfile": "Docker Container",
    "docker-compose.yml": "Docker Compose",
}

PYTHON_AST_EXTS: Set[str] = {".py", ".pyi"}


def estimate_tokens(text: str) -> int:
    """
    Computes token count using tiktoken (if available) or a conservative
    heuristic with a 15% safety margin (ADR-006 Invariant 2/4).
    """
    if not text:
        return 0
    if _TIKTOKEN_ENC is not None:
        try:
            return max(1, len(_TIKTOKEN_ENC.encode(text)))
        except Exception:
            pass
    # Conservative heuristic: punctuation-dense source averages ~3.5 chars/token + 15% buffer
    return max(1, math.ceil((len(text) / 3.5) * TOKEN_SAFETY_MARGIN))


@dataclass
class SymbolSpan:
    kind: str  # 'class', 'def', 'async def', or preserved agent symbol kind
    name: str  # Qualified name, e.g., 'ClassName.method_name'
    start_line: int
    end_line: int
    overload_idx: int = 0
    description: str = "[TODO: AGENT_FILL]"

    @property
    def coord(self) -> str:
        return f"[L{self.start_line}-L{self.end_line}]"

    @property
    def unqualified_name(self) -> str:
        return self.name.split(".")[-1]


@dataclass
class FileRecord:
    rel_path: str
    subsystem: str
    byte_size: int
    line_count: int
    tokens_est: int
    is_python: bool
    symbols: List[SymbolSpan] = field(default_factory=list)
    preserved_raw_symbols: List[str] = field(default_factory=list)
    reexports: List[str] = field(default_factory=list)
    fault_status: Optional[str] = None  # e.g., '[UNPARSEABLE: SyntaxError at L14]'
    stale_coord_warning: Optional[str] = None
    role_summary: str = "[TODO: AGENT_FILL - Summarize file responsibility & invariants]"
    assigned_shard: str = "TOKENME.txt"


@dataclass
class QuarantineEntry:
    rel_path: str
    reason: str


@dataclass
class HarvestedFileState:
    old_line_count: int
    role_summary: str
    exact_symbols: Dict[Tuple[str, int], str] = field(default_factory=dict)
    fallback_symbols: Dict[str, str] = field(default_factory=dict)
    raw_symbol_lines: List[str] = field(default_factory=list)


class PythonASTExtractor(ast.NodeVisitor):
    """
    ADR-006 Invariant 2: Exact Python symbol & scope extraction via native `ast`.
    Tracks enclosing classes and module/package re-exports without regex guessing.
    """

    def __init__(self, is_init_file: bool = False) -> None:
        self.symbols: List[SymbolSpan] = []
        self.reexports: Set[str] = set()
        self.is_init_file = is_init_file
        self._class_stack: List[str] = []
        self._func_depth: int = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self._func_depth == 0:
            qual_name = ".".join(self._class_stack + [node.name])
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start) or start
            self.symbols.append(SymbolSpan(kind="class", name=qual_name, start_line=start, end_line=end))
            self._class_stack.append(node.name)
            self.generic_visit(node)
            self._class_stack.pop()
        else:
            # Skip nested classes declared inside function bodies
            pass

    def _handle_function(self, node: ast.AST, kind_label: str, name: str) -> None:
        if self._func_depth == 0:
            qual_name = ".".join(self._class_stack + [name])
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start) or start
            self.symbols.append(SymbolSpan(kind=kind_label, name=qual_name, start_line=start, end_line=end))
        self._func_depth += 1
        self.generic_visit(node)
        self._func_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node, "def", node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node, "async def", node.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self.is_init_file and self._func_depth == 0 and not self._class_stack:
            mod_prefix = "." * (node.level or 0) + (node.module or "")
            imported = ", ".join(alias.name for alias in node.names[:5])
            if len(node.names) > 5:
                imported += ", ..."
            self.reexports.add(f"{mod_prefix} ({imported})")

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.is_init_file and self._func_depth == 0 and not self._class_stack:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                        exports = [
                            elt.value for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        ]
                        if exports:
                            joined = ", ".join(exports[:8])
                            if len(exports) > 8:
                                joined += ", ..."
                            self.reexports.add(f"__all__: [{joined}]")


def assign_overload_indices(symbols: List[SymbolSpan]) -> List[SymbolSpan]:
    """Assigns sequential overload_idx values for identical qualified names in a file."""
    counts: Dict[str, int] = {}
    for sym in symbols:
        idx = counts.get(sym.name, 0)
        sym.overload_idx = idx
        counts[sym.name] = idx + 1
    return symbols


def parse_python_ast(source_text: str, is_init_file: bool) -> Tuple[List[SymbolSpan], List[str], Optional[str]]:
    """
    Parses Python source strictly via `ast.parse()`.
    Never falls back to regex on SyntaxError (ADR-006 Invariant 2).
    """
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        line_info = f" at L{exc.lineno}" if exc.lineno else ""
        return [], [], f"[UNPARSEABLE: SyntaxError{line_info}]"
    except ValueError as exc:
        return [], [], f"[UNPARSEABLE: ValueError ({exc})]"
    except RecursionError:
        return [], [], "[UNPARSEABLE: AST RecursionError]"

    extractor = PythonASTExtractor(is_init_file=is_init_file)
    extractor.visit(tree)
    return assign_overload_indices(extractor.symbols), sorted(extractor.reexports), None


def load_ignore_patterns(root: Path) -> List[str]:
    """Loads .gitignore, .rooignore, and .dockerignore patterns if present."""
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
    """Evaluates whether a file or directory matches exclusion rules."""
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
    """Scans root and immediate children for runtime manifests (ignoring symlinks)."""
    found: Set[str] = set()
    try:
        children = sorted(root.iterdir(), key=lambda p: p.name)
        search_dirs = [root] + [
            d for d in children
            if d.is_dir() and not d.is_symlink() and d.name not in DEFAULT_IGNORE_DIRS and not d.name.startswith(".")
        ]
    except OSError:
        search_dirs = [root]

    for d in search_dirs:
        try:
            for item in sorted(d.iterdir(), key=lambda p: p.name):
                if item.is_symlink() or not item.is_file():
                    continue
                if item.name in RUNTIME_MANIFESTS:
                    found.add(RUNTIME_MANIFESTS[item.name])
                elif item.suffix in {".csproj", ".sln"}:
                    found.add(".NET / C#")
        except OSError:
            continue
    return sorted(found)


def scan_repository(
    root: Path, max_size_bytes: int
) -> Tuple[List[FileRecord], List[QuarantineEntry], List[str]]:
    """
    ADR-006 Invariant 3 & 4: Fail-closed, symlink-immune, lexicographically sorted
    filesystem walk with binary sniffing, size quarantine, and per-file fault isolation.
    """
    ignore_patterns = load_ignore_patterns(root)
    records: List[FileRecord] = []
    quarantine_log: List[QuarantineEntry] = []

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""

        # Filter and sort directories lexicographically (UTF-8 codepoint order)
        kept_dirs: List[str] = []
        for d in sorted(dirnames):
            rel_d = f"{rel_dir}/{d}".lstrip("/")
            if is_ignored(rel_d, d, True, ignore_patterns):
                continue
            full_d = Path(dirpath) / d
            if full_d.is_symlink():
                quarantine_log.append(QuarantineEntry(rel_path=f"{rel_d}/", reason="[SKIPPED_SYMLINK_DIR]"))
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in sorted(filenames):
            rel_file = f"{rel_dir}/{fname}".lstrip("/")
            if is_ignored(rel_file, fname, False, ignore_patterns):
                continue

            fpath = Path(dirpath) / fname

            # 1. Symlink immunity check
            if fpath.is_symlink():
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason="[SKIPPED_SYMLINK_FILE]"))
                continue

            # 2. Stat & Oversize quarantine check before reading into memory
            try:
                st = fpath.stat()
            except PermissionError:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason="[UNPARSEABLE: PermissionError on stat]"))
                continue
            except OSError as exc:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: OSError ({exc.__class__.__name__})]"))
                continue

            byte_size = st.st_size
            if byte_size == 0:
                continue

            if byte_size > max_size_bytes:
                size_kb = byte_size // 1024
                limit_kb = max_size_bytes // 1024
                quarantine_log.append(
                    QuarantineEntry(
                        rel_path=rel_file,
                        reason=f"[QUARANTINED_OVERSIZE: {size_kb:,} KiB exceeds {limit_kb:,} KiB limit]",
                    )
                )
                continue

            # 3. Binary inspection (first 8,192 bytes for null byte \x00)
            try:
                with fpath.open("rb") as bf:
                    sniff_chunk = bf.read(BINARY_SNIFF_BYTES)
                if b"\x00" in sniff_chunk:
                    quarantine_log.append(
                        QuarantineEntry(rel_path=rel_file, reason=f"[SKIPPED_BINARY: Null byte detected ({byte_size:,} B)]")
                    )
                    continue
            except PermissionError:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason="[UNPARSEABLE: PermissionError on read]"))
                continue
            except OSError as exc:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: OSError ({exc.__class__.__name__})]"))
                continue

            # 4. Strict UTF-8 read with per-file fault isolation (ADR-006 Invariant 3)
            parts = rel_file.split("/")
            subsystem = parts[0] if len(parts) > 1 else "root"
            ext = fpath.suffix.lower()
            is_py = ext in PYTHON_AST_EXTS

            try:
                text = fpath.read_text(encoding="utf-8", errors="strict")
            except UnicodeDecodeError:
                # Isolate encoding fault to this file and continue
                est_lines = max(1, sniff_chunk.count(b"\n"))
                records.append(
                    FileRecord(
                        rel_path=rel_file,
                        subsystem=subsystem,
                        byte_size=byte_size,
                        line_count=est_lines,
                        tokens_est=max(1, byte_size // 4),
                        is_python=is_py,
                        fault_status="[UNPARSEABLE: UnicodeDecodeError (Non-UTF-8 file encoding)]",
                    )
                )
                quarantine_log.append(
                    QuarantineEntry(rel_path=rel_file, reason="[UNPARSEABLE: UnicodeDecodeError (Non-UTF-8)]")
                )
                continue
            except PermissionError:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason="[UNPARSEABLE: PermissionError]"))
                continue
            except OSError as exc:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: OSError ({exc.__class__.__name__})]"))
                continue

            lines = text.splitlines()
            if not lines:
                continue

            tokens_est = estimate_tokens(text)

            # 5. ADR-006 Invariant 2: Exact AST for Python, Honest Structural Stubs elsewhere
            if is_py:
                syms, reexports, ast_fault = parse_python_ast(text, is_init_file=(fname == "__init__.py"))
                if ast_fault:
                    quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=ast_fault))
                records.append(
                    FileRecord(
                        rel_path=rel_file,
                        subsystem=subsystem,
                        byte_size=byte_size,
                        line_count=len(lines),
                        tokens_est=tokens_est,
                        is_python=True,
                        symbols=syms,
                        reexports=reexports,
                        fault_status=ast_fault,
                    )
                )
            else:
                records.append(
                    FileRecord(
                        rel_path=rel_file,
                        subsystem=subsystem,
                        byte_size=byte_size,
                        line_count=len(lines),
                        tokens_est=tokens_est,
                        is_python=False,
                    )
                )

    runtimes = detect_runtimes(root)
    return records, quarantine_log, runtimes


def harvest_existing_state(root: Path) -> Tuple[Dict[str, str], Dict[str, HarvestedFileState]]:
    """
    Parses existing TOKENME*.txt files during default sync mode to preserve:
      1. L0 global metadata (System Purpose, Entrypoints, Global/Cross-Boundary Invariants)
      2. L1 file Role & Invariants summaries
      3. L2 Python symbol descriptions (matched onto fresh AST coordinates)
      4. L2 Non-Python agent-populated symbol lines verbatim (with staleness detection)
    """
    l0_meta: Dict[str, str] = {}
    file_states: Dict[str, HarvestedFileState] = {}

    header_re = re.compile(r"^###\s+`([^`]+)`\s+\[L1-L(\d+)\]")
    table_row_re = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*\[L1-L(\d+)\]\s*\|\s*[^|]+\|\s*[^|]+\|\s*(.+?)\s*\|$")
    role_re = re.compile(r"^-\s+\*\*Role & Invariants:\*\*\s*(.+)$")
    sym_re = re.compile(r"^\s*-\s+`([^`]+)`\s+\[L\d+-L\d+\]\s*:\s*(.+)$")
    l0_bullet_re = re.compile(r"^-\s+\*\*([^:*]+):\*\*\s*(.+)$")

    for existing_path in sorted(root.glob("TOKENME*.txt")):
        if not existing_path.is_file() or existing_path.is_symlink():
            continue
        try:
            lines = existing_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        current_file: Optional[str] = None
        in_l2_block = False
        per_file_counts: Dict[Tuple[str, str], int] = {}

        for line in lines:
            stripped = line.strip()

            # Capture L0 header bullets from root TOKENME.txt
            if existing_path.name == "TOKENME.txt" and current_file is None:
                m_l0 = l0_bullet_re.match(stripped)
                if m_l0:
                    key_label = m_l0.group(1).strip()
                    val_str = m_l0.group(2).strip()
                    if not val_str.startswith("[TODO: AGENT_FILL"):
                        l0_meta[key_label] = val_str

            # Capture compact L1 table rows
            m_table = table_row_re.match(stripped)
            if m_table:
                t_path = m_table.group(1).strip()
                t_lines = int(m_table.group(2))
                t_role = m_table.group(3).strip()
                st = file_states.setdefault(
                    t_path, HarvestedFileState(old_line_count=t_lines, role_summary=t_role)
                )
                if not t_role.startswith("[TODO: AGENT_FILL"):
                    st.role_summary = t_role
                continue

            # Capture L1/L2 file section headers
            m_file = header_re.match(stripped)
            if m_file:
                current_file = m_file.group(1).strip()
                old_lc = int(m_file.group(2))
                if current_file not in file_states:
                    file_states[current_file] = HarvestedFileState(
                        old_line_count=old_lc,
                        role_summary="[TODO: AGENT_FILL - Summarize file responsibility & invariants]",
                    )
                else:
                    file_states[current_file].old_line_count = old_lc
                in_l2_block = False
                continue

            if current_file is None:
                continue

            st = file_states[current_file]
            m_role = role_re.match(stripped)
            if m_role:
                role_val = m_role.group(1).strip()
                if not role_val.startswith("[TODO: AGENT_FILL"):
                    st.role_summary = role_val
                continue

            if stripped.startswith("- **L2 Symbol Coordinates:**"):
                in_l2_block = True
                continue

            if stripped.startswith("### ") or stripped.startswith("## ") or stripped.startswith("---"):
                current_file = None
                in_l2_block = False
                continue

            if in_l2_block and line.startswith("  - "):
                # Ignore unpopulated stubs or system placeholders
                if "[AGENT_POPULATE_SYMBOLS]" in stripped or "[UNPARSEABLE:" in stripped:
                    continue
                st.raw_symbol_lines.append(line)

                m_sym = sym_re.match(line)
                if m_sym:
                    raw_sig = m_sym.group(1).strip()
                    sym_name = raw_sig.split()[-1] if " " in raw_sig else raw_sig
                    desc = m_sym.group(2).strip()
                    occ_key = (current_file, sym_name)
                    occ_idx = per_file_counts.get(occ_key, 0)
                    per_file_counts[occ_key] = occ_idx + 1
                    st.exact_symbols[(sym_name, occ_idx)] = desc
                    st.fallback_symbols.setdefault(sym_name, desc)

    return l0_meta, file_states


def merge_harvested_state(
    records: List[FileRecord], file_states: Dict[str, HarvestedFileState]
) -> None:
    """
    Applies harvested state onto freshly scanned FileRecords:
      - Restores L1 role summaries
      - Merges Python symbol descriptions onto updated AST spans
      - Preserves agent-authored non-Python L2 symbol lines verbatim and checks for line-count drift
    """
    for rec in records:
        st = file_states.get(rec.rel_path)
        if not st:
            continue

        if not st.role_summary.startswith("[TODO: AGENT_FILL"):
            rec.role_summary = st.role_summary

        if rec.is_python:
            for sym in rec.symbols:
                exact_desc = st.exact_symbols.get((sym.name, sym.overload_idx))
                fall_desc = st.fallback_symbols.get(sym.name) or st.fallback_symbols.get(sym.unqualified_name)
                if exact_desc:
                    sym.description = exact_desc
                elif fall_desc and sym.overload_idx == 0:
                    sym.description = fall_desc
        else:
            if st.raw_symbol_lines:
                rec.preserved_raw_symbols = list(st.raw_symbol_lines)
                if st.old_line_count > 0 and st.old_line_count != rec.line_count:
                    delta = rec.line_count - st.old_line_count
                    sign = "+" if delta > 0 else ""
                    rec.stale_coord_warning = (
                        f"[COORDS_STALE_CHECK: File line count shifted L{st.old_line_count}->L{rec.line_count} "
                        f"({sign}{delta} lines); agent must verify L2 spans below]"
                    )


def render_bootstrap_footer(topology_mode: str) -> List[str]:
    """Generates the canonical self-referential TOKENME v2.0 maintenance block."""
    return [
        "---",
        "## [SELF-REFERENTIAL BOOTSTRAP & AGENT MAINTENANCE PROTOCOL]",
        "```yaml",
        f"spec_version: {SPEC_VERSION}",
        f"scaffolder_version: {VERSION}",
        f"topology_mode: {topology_mode}",
        "agent_execution_protocol:",
        "  1_MIPMAP_ROUTING: Read this file BEFORE executing broad grep, find, or full-file reads.",
        "  2_SURGICAL_L3_READ: Use [Lstart-Lend] coordinates above to issue bounded line-range reads.",
        "  3_NON_PYTHON_STUBS: Where `[AGENT_POPULATE_SYMBOLS]` appears, inspect the file once and populate `- `<kind> <Name>` [Lstart-Lend]: <summary>` entries.",
        "  4_HYDRATION_DUTY: Replace `[TODO: AGENT_FILL]` and `[COORDS_STALE_CHECK]` markers in files you touch.",
        "  5_ATOMIC_SYNC: Run `python3 tokenme-sync.py` (default sync mode) after code edits to refresh line counts, Python AST spans, and shard budgets.",
        "```",
    ]


def render_quarantine_section(quarantine_log: List[QuarantineEntry]) -> List[str]:
    """Renders the ADR-006 Fail-Closed Quarantine & Fault Isolation ledger if non-empty."""
    if not quarantine_log:
        return []
    out: List[str] = [
        "## Quarantined, Binary & Unparseable Artifacts (ADR-006 Fail-Closed Ledger)",
        "| File / Path | Isolation Reason |",
        "| :--- | :--- |",
    ]
    for q in quarantine_log[:50]:
        out.append(f"| `{q.rel_path}` | `{q.reason}` |")
    if len(quarantine_log) > 50:
        out.append(f"| _...and {len(quarantine_log) - 50} additional binary/quarantined items_ | _(Omitted for token budget)_ |")
    out.append("")
    return out


def render_file_digest_section(records: List[FileRecord], include_symbols: bool = True) -> List[str]:
    """
    Renders L1 file headers and L2 symbol blocks in compliance with ADR-006 Invariant 2:
      - Python files: Exact AST symbols (or `[UNPARSEABLE: ...]`)
      - Non-Python files: Preserved agent symbols OR `[AGENT_POPULATE_SYMBOLS]` directive stub
    """
    out: List[str] = []
    for rec in records:
        kb_str = f"{rec.byte_size / 1024:.1f} KiB"
        out.append(
            f"### `{rec.rel_path}` [L1-L{rec.line_count}] ({kb_str} | ~{rec.tokens_est} conservative tokens)"
        )
        out.append(f"- **Role & Invariants:** {rec.role_summary}")
        if rec.reexports:
            joined_re = ", ".join(f"`{r}`" for r in rec.reexports)
            out.append(f"- **Package Exports (`__init__`):** {joined_re}")

        if include_symbols:
            if rec.fault_status:
                out.append(f"- **L2 Symbol Coordinates:** `{rec.fault_status}` — Structural stub only; fix syntax/encoding to restore AST indexing.")
            elif rec.is_python:
                if rec.symbols:
                    out.append("- **L2 Symbol Coordinates (Python AST):**")
                    for sym in rec.symbols:
                        out.append(f"  - `{sym.kind} {sym.name}` {sym.coord}: {sym.description}")
                else:
                    out.append("- **L2 Symbol Coordinates (Python AST):** _(Module script / constants only; no top-level class or def declarations)_")
            else:
                if rec.stale_coord_warning:
                    out.append(f"- **L2 Symbol Coordinates:** `{rec.stale_coord_warning}`")
                else:
                    out.append("- **L2 Symbol Coordinates:**")

                if rec.preserved_raw_symbols:
                    for raw_line in rec.preserved_raw_symbols:
                        out.append(raw_line)
                else:
                    out.append(
                        "  - `[AGENT_POPULATE_SYMBOLS]` — Non-Python source/doc file; coding agent must populate `- `<kind> <Name>` [Lstart-Lend]: <concise summary>` upon first inspection."
                    )
        out.append("")
    return out


def render_l1_compact_file_table(records: List[FileRecord]) -> List[str]:
    """
    ADR-004 Root L2 Eviction Table: Renders a compact L1 file summary table
    with zero L2 function bloat for the root TOKENME.txt router.
    """
    out: List[str] = [
        "| File Path | Line Span | Size / Est. Tokens | L2 Status | L1 Role & Architectural Invariants |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for rec in records:
        if rec.fault_status:
            status_str = f"`{rec.fault_status}`"
        elif rec.is_python:
            status_str = f"{len(rec.symbols)} AST syms"
        elif rec.preserved_raw_symbols:
            status_str = f"{len(rec.preserved_raw_symbols)} agent syms"
        else:
            status_str = "`[AGENT_POPULATE_SYMBOLS]`"
        out.append(
            f"| `{rec.rel_path}` | [L1-L{rec.line_count}] | ~{rec.tokens_est} tok | {status_str} | {rec.role_summary} |"
        )
    out.append("")
    return out


def chunk_records_by_token_budget(
    records: List[FileRecord], base_shard_prefix: str
) -> List[Tuple[str, List[FileRecord]]]:
    """
    Splits a list of FileRecords into one or more shard buckets if conservative
    token estimates exceed MAX_SHARD_TOKENS (ADR-004 & ADR-006).
    """
    rendered_all = "\n".join(render_file_digest_section(records, include_symbols=True))
    if estimate_tokens(rendered_all) <= MAX_SHARD_TOKENS or len(records) <= 1:
        return [(f"{base_shard_prefix}.txt", records)]

    chunks: List[Tuple[str, List[FileRecord]]] = []
    curr_list: List[FileRecord] = []
    curr_tokens = 250  # Header/footer budget reserve
    part_idx = 1

    for rec in records:
        rec_text = "\n".join(render_file_digest_section([rec], include_symbols=True))
        rec_weight = estimate_tokens(rec_text)
        if curr_list and (curr_tokens + rec_weight > MAX_SHARD_TOKENS):
            chunks.append((f"{base_shard_prefix}_{part_idx}.txt", curr_list))
            part_idx += 1
            curr_list = []
            curr_tokens = 250
        curr_list.append(rec)
        curr_tokens += rec_weight

    if curr_list:
        chunks.append((f"{base_shard_prefix}_{part_idx}.txt", curr_list))
    return chunks


def build_documents(
    root: Path,
    records: List[FileRecord],
    quarantine_log: List[QuarantineEntry],
    runtimes: List[str],
    l0_meta: Dict[str, str],
    force_single: bool = False,
) -> Dict[Path, str]:
    """
    Evaluates ADR-004 sharding triggers using conservative token estimates (ADR-006)
    and constructs either a monolithic TOKENME.txt or an L0/L1 Root Router + Shards.
    """
    repo_name = root.resolve().name
    total_files = len(records)
    total_loc = sum(r.line_count for r in records)
    total_raw_tokens = sum(r.tokens_est for r in records)
    total_ast_symbols = sum(len(r.symbols) for r in records)
    total_agent_symbols = sum(len(r.preserved_raw_symbols) for r in records)
    total_symbols = total_ast_symbols + total_agent_symbols

    runtime_list_str = ", ".join(runtimes) if runtimes else l0_meta.get(
        "Primary Runtimes", l0_meta.get("Detected Runtimes", "[TODO: AGENT_FILL - Specify primary runtime]")
    )
    sys_purpose = l0_meta.get("System Purpose", "[TODO: AGENT_FILL - State core system objective in <=25 words]")
    entrypoints = l0_meta.get("Entrypoints", "[TODO: AGENT_FILL - List primary CLI/server/app entrypoints]")
    global_invariants = l0_meta.get(
        "Global State & Mutation Invariants",
        l0_meta.get("Cross-Boundary Invariants", "[TODO: AGENT_FILL - Document critical data/concurrency constraints]"),
    )
    today_iso = datetime.date.today().isoformat()

    temp_digest_lines = render_file_digest_section(records, include_symbols=True)
    est_single_lines = 40 + len(temp_digest_lines) + len(quarantine_log)
    est_single_tokens = estimate_tokens("\n".join(temp_digest_lines)) + 400

    should_shard = not force_single and (
        est_single_tokens > SHARD_TRIGGER_TOKENS
        or est_single_lines > SHARD_TRIGGER_LINES
        or total_symbols > SHARD_TRIGGER_SYMBOLS
        or len(runtimes) >= SHARD_TRIGGER_RUNTIMES
    )

    subsystems: Dict[str, List[FileRecord]] = {}
    for r in records:
        subsystems.setdefault(r.subsystem, []).append(r)

    max_sub_files = max((len(recs) for recs in subsystems.values()), default=0)
    is_flat_repo = len(subsystems) == 1 or (total_files > 0 and (max_sub_files / total_files) >= 0.85 and len(subsystems) <= 2)

    shard_plan: List[Tuple[str, str, List[FileRecord]]] = []

    if not should_shard:
        for r in records:
            r.assigned_shard = "TOKENME.txt"
    elif is_flat_repo:
        chunks = chunk_records_by_token_budget(records, "TOKENME.symbols")
        for shard_fname, chunk_recs in chunks:
            label = (
                f"flat ({chunk_recs[0].rel_path} .. {chunk_recs[-1].rel_path})"
                if len(chunks) > 1
                else "all files (L2 coordinates)"
            )
            shard_plan.append((label, shard_fname, chunk_recs))
            for r in chunk_recs:
                r.assigned_shard = shard_fname
    else:
        for sub_name, sub_recs in sorted(subsystems.items()):
            if sub_name == "root":
                shard_fname = "TOKENME.root.txt"
                shard_plan.append(("root/", shard_fname, sub_recs))
                for r in sub_recs:
                    r.assigned_shard = shard_fname
            else:
                chunks = chunk_records_by_token_budget(sub_recs, f"TOKENME.{sub_name}")
                for idx, (shard_fname, chunk_recs) in enumerate(chunks):
                    label = f"{sub_name}/ (part {idx + 1})" if len(chunks) > 1 else f"{sub_name}/"
                    shard_plan.append((label, shard_fname, chunk_recs))
                    for r in chunk_recs:
                        r.assigned_shard = shard_fname

    outputs: Dict[Path, str] = {}

    if not should_shard:
        lines: List[str] = [
            "# TOKENME.txt — Declarative Epistemic State & Symbol Catalog",
            f"> **Repository:** `{repo_name}` | **Spec:** TOKENME v{SPEC_VERSION} | **Last Synced:** {today_iso}",
            f"> **Coverage:** {total_files} files | {total_loc:,} LOC | {total_ast_symbols} AST syms + {total_agent_symbols} agent syms | ~{total_raw_tokens:,} conservative source tokens",
            "",
            "## 1. L0 System Identity & Architectural Invariants",
            f"- **Primary Runtimes:** {runtime_list_str}",
            f"- **System Purpose:** {sys_purpose}",
            f"- **Entrypoints:** {entrypoints}",
            f"- **Global State & Mutation Invariants:** {global_invariants}",
            "",
            "## 2. L1/L2 File & Symbol Coordinate Digest",
            "",
        ]
        lines.extend(temp_digest_lines)
        lines.extend(render_quarantine_section(quarantine_log))
        lines.extend(render_bootstrap_footer("MONOLITHIC_SINGLE_FILE"))
        outputs[root / "TOKENME.txt"] = "\n".join(lines) + "\n"
        return outputs

    # Sharded Mode (ADR-004 Vertical Domain Shards OR Flat-Repo L2 Offload)
    topology_label = "FLAT_REPO_L2_SHARDED" if is_flat_repo else "VERTICAL_DOMAIN_MIPMAP_SHARDED"
    router_lines: List[str] = [
        "# TOKENME.txt — L0/L1 Epistemic Router & Mipmap Index",
        f"> **Repository:** `{repo_name}` | **Spec:** TOKENME v{SPEC_VERSION} ({topology_label}) | **Last Synced:** {today_iso}",
        f"> **Coverage:** {total_files} files | {total_loc:,} LOC | {total_ast_symbols} AST syms + {total_agent_symbols} agent syms | ~{total_raw_tokens:,} conservative source tokens",
        "",
        "## 1. L0 System Identity & Global Invariants",
        f"- **Detected Runtimes:** {runtime_list_str}",
        f"- **System Purpose:** {sys_purpose}",
        f"- **Entrypoints:** {entrypoints}",
        f"- **Cross-Boundary Invariants:** {global_invariants}",
        "",
        "## 2. L1 Subsystem & Symbol Shard Routing Table (Zero L2 Functions in Root)",
        "| Scope / Subsystem | Shard Pointer | Files | LOC | L2 Symbols / Stubs | Architectural Responsibility |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for scope_label, shard_fname, shard_recs in shard_plan:
        s_loc = sum(r.line_count for r in shard_recs)
        s_ast = sum(len(r.symbols) for r in shard_recs)
        s_agt = sum(len(r.preserved_raw_symbols) for r in shard_recs)
        s_stubs = sum(1 for r in shard_recs if not r.is_python and not r.preserved_raw_symbols and not r.fault_status)
        sym_summary = f"{s_ast + s_agt} syms ({s_stubs} stubs)" if s_stubs else f"{s_ast + s_agt} syms"

        router_lines.append(
            f"| `{scope_label}` | `./{shard_fname}` | {len(shard_recs)} | {s_loc:,} | {sym_summary} | [TODO: AGENT_FILL] |"
        )

        shard_digest = render_file_digest_section(shard_recs, include_symbols=True)
        shard_lines: List[str] = [
            f"# {shard_fname} — L1/L2 Coordinate Shard (`{scope_label}`)",
            f"> **Parent Router:** `./TOKENME.txt` | **Spec:** TOKENME v{SPEC_VERSION} | **Last Synced:** {today_iso}",
            "",
            "## 1. Shard Invariants & Public Boundary",
            "- **Scope Purpose:** [TODO: AGENT_FILL - Summarize domain and exported interface]",
            "- **State & Side-Effects:** [TODO: AGENT_FILL - Document I/O, DB, or hardware mutation rules]",
            "",
            "## 2. Co-Located L1 File Invariants & L2 Symbol Coordinates",
            "",
        ]
        shard_lines.extend(shard_digest)
        shard_lines.extend(render_bootstrap_footer(topology_label))
        outputs[root / shard_fname] = "\n".join(shard_lines) + "\n"

    router_lines.append("")

    if is_flat_repo:
        router_lines.append("## 3. L1 File Inventory & Invariants (L2 Symbols Offloaded to Shards Above)")
        router_lines.append("")
        router_lines.extend(render_l1_compact_file_table(records))
    else:
        root_records = subsystems.get("root", [])
        if root_records:
            router_lines.append("## 3. Root-Level L1 File Summary (L2 Symbols Offloaded to `./TOKENME.root.txt`)")
            router_lines.append("")
            router_lines.extend(render_l1_compact_file_table(root_records))

    router_lines.extend(render_quarantine_section(quarantine_log))
    router_lines.extend(render_bootstrap_footer(topology_label))
    outputs[root / "TOKENME.txt"] = "\n".join(router_lines) + "\n"

    return outputs


def atomic_commit_outputs(root: Path, outputs: Dict[Path, str], clean_stale_shards: bool = True) -> None:
    """
    ADR-006 Invariant 4: Stages all generated TOKENME*.txt artifacts in temporary
    files inside the target root and commits via atomic `os.replace()` only after
    100% of staging succeeds.
    """
    staged_pairs: List[Tuple[Path, Path]] = []
    pid = os.getpid()

    try:
        for final_path, content in sorted(outputs.items(), key=lambda item: item[0].name):
            tmp_fd, tmp_raw_path = tempfile.mkstemp(
                prefix=f".tokenme-sync.{final_path.name}.{pid}.",
                suffix=".tmp",
                dir=str(root),
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

        # All temp files staged cleanly; execute atomic replacements
        for tmp_path, final_path in staged_pairs:
            os.replace(str(tmp_path), str(final_path))

        # Remove stale shards only after atomic replacement succeeds
        if clean_stale_shards:
            for existing_file in sorted(root.glob("TOKENME*.txt")):
                if existing_file not in outputs and not existing_file.is_symlink():
                    try:
                        existing_file.unlink()
                    except OSError:
                        pass

    except Exception:
        # Clean up any leftover staged files on failure
        for tmp_path, _ in staged_pairs:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
        raise


def print_telemetry_receipt(
    records: List[FileRecord],
    quarantine_log: List[QuarantineEntry],
    runtimes: List[str],
    outputs: Dict[Path, str],
    init_mode: bool,
    dry_run: bool,
) -> None:
    """Prints the Epistemic Compression Receipt and ADR-006 Quarantine summary to stdout."""
    total_files = len(records)
    py_files = sum(1 for r in records if r.is_python)
    non_py_files = total_files - py_files
    total_loc = sum(r.line_count for r in records)
    raw_tokens = max(1, sum(r.tokens_est for r in records))
    ast_symbols = sum(len(r.symbols) for r in records)
    preserved_symbols = sum(len(r.preserved_raw_symbols) for r in records)

    root_doc = next((content for path, content in outputs.items() if path.name == "TOKENME.txt"), "")
    root_tokens = max(1, estimate_tokens(root_doc))
    total_meta_tokens = max(1, sum(estimate_tokens(c) for c in outputs.values()))
    compression_ratio = raw_tokens / root_tokens

    todo_count = sum(c.count("[TODO: AGENT_FILL") for c in outputs.values())
    stub_count = sum(c.count("[AGENT_POPULATE_SYMBOLS]") for c in outputs.values())
    stale_count = sum(c.count("[COORDS_STALE_CHECK:") for c in outputs.values())

    sharded = len(outputs) > 1
    mode_str = (
        f"Sharded Mipmap Mode (1 L0/L1 Root Router + {len(outputs) - 1} L2 Shards)"
        if sharded
        else "Monolithic Single-File Mode"
    )
    rt_str = ", ".join(runtimes) if runtimes else "Generic / Unspecified"
    tok_engine = "tiktoken (cl100k_base)" if _TIKTOKEN_ENC is not None else "Conservative Heuristic (+15% safety buffer)"
    action_label = "Initial Cold-Repo Scaffold (--init)" if init_mode else "In-Place Epistemic Sync (Default Update)"
    if dry_run:
        action_label += " [DRY-RUN]"

    print("\n" + "=" * 78)
    print(f" [tokenme-sync.py v{VERSION} | Spec v{SPEC_VERSION}] — {action_label}")
    print("=" * 78)
    print(f"  Indexed Corpus     : {total_files} files ({py_files} Python AST, {non_py_files} Non-Python) | {total_loc:,} LOC")
    print(f"  Source Token Mass  : ~{raw_tokens:,} tokens ({tok_engine})")
    print(f"  Detected Runtimes  : {rt_str}")
    print(f"  Symbol Resolution  : {ast_symbols} exact Python AST spans | {preserved_symbols} preserved non-Py spans")
    print(f"  Fail-Closed Guard  : {len(quarantine_log)} binary/oversize/symlink/fault items isolated")
    print(f"  Topology Selected  : {mode_str}")
    print(f"  Root Router Cost   : ~{root_tokens:,} tokens (Total index across shards: ~{total_meta_tokens:,} tokens)")
    print(f"  Epistemic Leverage : {compression_ratio:.1f}:1 compression vs. raw codebase read")
    print("-" * 78)
    print("  Staged / Committed Artifacts:")
    for p, text in sorted(outputs.items(), key=lambda item: item[0].name):
        est_tok = estimate_tokens(text)
        print(f"    -> ./{p.name:<28} (~{est_tok:,} tokens)")

    if stub_count > 0 or todo_count > 0 or stale_count > 0:
        print("-" * 78)
        print(
            f"  Agent Hydration Queue: {stub_count} [AGENT_POPULATE_SYMBOLS] stubs | "
            f"{todo_count} [TODO: AGENT_FILL] slots | {stale_count} stale-coord checks"
        )
        print("  Run this prompt in your coding agent (Roo Code, Cursor, Claude Code):")
        print('  > "Read TOKENME.txt (and any shards). Populate all [AGENT_POPULATE_SYMBOLS]')
        print('  >  blocks for non-Python files with exact [Lstart-Lend] spans, resolve')
        print('  >  [TODO: AGENT_FILL] and [COORDS_STALE_CHECK] markers, and preserve all')
        print('  >  Python AST coordinates."')
    print("=" * 78 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tokenme-sync.py",
        description=(
            "Synchronize an existing TOKENME.txt (v2.0) hierarchy (default), "
            "or scaffold a cold repository (--init)."
        ),
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Path to the repository root directory (default: current directory).",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Scaffold a new TOKENME.txt hierarchy in a cold repository.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="When combined with --init, overwrite an existing TOKENME.txt from scratch.",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Force monolithic single-file output even if sharding thresholds are exceeded.",
    )
    parser.add_argument(
        "--max-size-kb",
        type=int,
        default=DEFAULT_MAX_FILE_SIZE_KB,
        help=f"Quarantine files larger than this threshold in KiB (default: {DEFAULT_MAX_FILE_SIZE_KB} KiB).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute traversal, AST extraction, and sharding math without writing files.",
    )

    args = parser.parse_args()
    root_path = Path(args.root).resolve()

    if not root_path.is_dir():
        print(f"[ERROR] Target directory does not exist: {root_path}", file=sys.stderr)
        return 1

    target_root_file = root_path / "TOKENME.txt"
    tokenme_exists = target_root_file.is_file() and not target_root_file.is_symlink()

    # --- Inverted CLI State Machine ---
    if args.init:
        if tokenme_exists and not (args.force or args.dry_run):
            print(
                f"[ABORT] `TOKENME.txt` already exists in {root_path}.\n"
                "  -> To synchronize/update existing coordinates, run without flags: `python3 tokenme-sync.py`\n"
                "  -> To wipe and re-scaffold from scratch, pass: `python3 tokenme-sync.py --init --force`",
                file=sys.stderr,
            )
            return 1
    else:
        # Default mode: Sync/Update existing TOKENME.txt
        if not tokenme_exists:
            print(
                f"[NOTICE] No `TOKENME.txt` found in {root_path}.\n"
                "  -> Default execution updates an existing TOKENME index.\n"
                "  -> To scaffold a cold repository for the first time, run:\n"
                "       python3 tokenme-sync.py --init",
                file=sys.stderr,
            )
            return 1

    max_size_bytes = max(1, args.max_size_kb) * 1024
    records, quarantine_log, runtimes = scan_repository(root_path, max_size_bytes=max_size_bytes)

    if not records and not quarantine_log:
        print("[WARN] No eligible files discovered in repository.", file=sys.stderr)
        return 1

    l0_meta: Dict[str, str] = {}
    if not args.init:
        # Default Update/Sync pass: Harvest and merge existing descriptions & non-Python agent symbols
        l0_meta, file_states = harvest_existing_state(root_path)
        merge_harvested_state(records, file_states)

    outputs = build_documents(
        root=root_path,
        records=records,
        quarantine_log=quarantine_log,
        runtimes=runtimes,
        l0_meta=l0_meta,
        force_single=args.single,
    )

    if not args.dry_run:
        atomic_commit_outputs(root_path, outputs, clean_stale_shards=True)

    print_telemetry_receipt(
        records=records,
        quarantine_log=quarantine_log,
        runtimes=runtimes,
        outputs=outputs,
        init_mode=args.init,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
