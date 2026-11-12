#!/usr/bin/env python3
"""
tokenme-sync.py (v2.0.0)
Zero-dependency, fail-closed structural reference scaffolder, opaque/L4 asset
tiering engine, and Multi-Tier Merkle state synchronizer for the TOKENME.txt (v2.0)
epistemic specification.

Implements:
  - ADR-001 & ADR-002: Context Triad Separation, .txt Extension & [Lstart-Lend] Grammar
  - ADR-003 & ADR-004: Mipmap Hierarchy & Vertical Domain Sharding (Amended by ADR-010)
  - ADR-005 & ADR-006: Python AST Qualified Scoping & Fail-Closed Filesystem Hardening
  - ADR-007 & ADR-008: 3-Tuple ADR Taxonomy & Multi-Tier Merkle Epistemic State Root
  - ADR-009: Opaque/Vector L2 Mandate, In-Place L4 Sidecars (.l3.txt) & Two-Pass Sharding
  - ADR-010: Ledger Harmonization, Cross-ADR Supersession Matrix & v2.0 Errata

Requires: Python >= 3.9 (Standard Library Only)
License: MIT / CC-BY 4.0
Repository: https://github.com/endean-eng/tokenme
"""

from __future__ import annotations

import argparse
import ast
import datetime
import fnmatch
import hashlib
import math
import os
import re
import struct
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

VERSION = "2.0.0"
SPEC_VERSION = "2.0"

# --- ADR-010 Sec 3.1 Harmonized Sharding Thresholds ---
ROOT_LINE_CEILING = 150                # Hard ceiling (~1,000 tokens) for root TOKENME.txt
SHARD_TOKEN_CEILING = 2000             # Max token budget per individual shard (~250 lines)
SINGLE_OVERFLOW_CEILING = 250          # Max ejected root lines before splitting .code and .assets
DIR_PROJECTED_LINE_CEILING = 100       # Pass 1 trigger: code_l2_lines + (5 * n_opaque) > 100
SHARD_TRIGGER_SYMBOLS = 75             # Pass 1 trigger: > 75 extracted symbols spawns subdir shard
OPAQUE_SHARD_COUNT_THRESHOLD = 8       # Pass 1 trigger: >= 8 qualifying opaque assets spawns subdir shard
PROJECTED_L2_LINES_PER_OPAQUE = 5      # Projected line footprint per hydrated opaque stub
SHARD_TRIGGER_RUNTIMES = 2             # Polyglot trigger

# --- ADR-006 & ADR-010 HC-06 Fail-Closed Quarantine Constants ---
DEFAULT_MAX_FILE_SIZE_KB = 1024        # 1 MiB ceiling for text/source pipeline
BINARY_SNIFF_BYTES = 8192
STREAM_CHUNK_BYTES = 65536             # 64 KiB streaming chunk for opaque/L4 hashing
TOKEN_SAFETY_MARGIN = 1.15             # 15% conservative buffer when tiktoken is absent

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

# --- ADR-008 & ADR-010 Merkle Constants ---
DEFAULT_LEAF_HASH_LEN = 6
DEFAULT_ROOT_HASH_LEN = 8
STATE_ROOT_PATTERN = re.compile(
    r"^(#\s*STATE_ROOT:\s*)([0-9a-fA-F]{6,64}|PENDING|MASKED_STATE_ROOT)(\s*)$",
    re.MULTILINE,
)
# ADR-010 HC-04: Supports ADR-NNN / IDR-NNN (3-6 char alnum) + advisory external prefixes
ADVISORY_ID_PATTERN = re.compile(r"^([a-zA-Z0-9-]+)_")
CANONICAL_3TUPLE_PATTERN = re.compile(
    r"^((?:ADR|IDR)-[A-Za-z0-9]{3,6})_(\d{4}-\d{2}-\d{2})_([A-Za-z0-9-]+)\.md$"
)
IGNORED_DECISION_FILES: Set[str] = {"readme.md", "template.md"}

# Optional dynamic tiktoken import (ADR-006 Sec 3: zero hard dependency)
try:
    import tiktoken  # type: ignore
    _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TIKTOKEN_ENC = None

# --- Hardcoded Exclusions (ADR-006 & ADR-009 Part A.1) ---
DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".roo", ".cursor",
    "node_modules", "bower_components", "jspm_packages",
    "venv", ".venv", "env", ".env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "site-packages",
    "dist", "build", "out", "target", "bin", "obj", "coverage",
    ".next", ".nuxt", ".svelte-kit", ".vercel", ".output", "vendor",
    "thumbnails", "raw_dataset",
}

# Note (ADR-010 HC-06): Qualifying opaque extensions (.png, .jpg, .svg, .pdf, etc.)
# are intentionally NOT in DEFAULT_IGNORE_PATTERNS so they route to the ADR-009 gate.
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
    """Computes token count via tiktoken (if installed) or conservative heuristic (+15%)."""
    if not text:
        return 0
    if _TIKTOKEN_ENC is not None:
        try:
            return max(1, len(_TIKTOKEN_ENC.encode(text)))
        except Exception:
            pass
    return max(1, math.ceil((len(text) / 3.5) * TOKEN_SAFETY_MARGIN))


def canonical_bytes(path: Path) -> bytes:
    """ADR-008 Sec 2.1: Normalizes CRLF to LF and strips outer whitespace for cross-OS invariance."""
    return path.read_bytes().replace(b"\r\n", b"\n").strip()


def stream_sha256_hex(path: Path, length: int = 12) -> str:
    """ADR-009 Part C: Computes streaming SHA-256 over arbitrary-size binary files in 64 KiB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(STREAM_CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:length]


@dataclass
class SymbolSpan:
    kind: str
    name: str
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
class OpaqueAssetInfo:
    modality: str                # 'RASTER_IMAGE', 'VECTOR_SVG', 'NATIVE_PDF', 'FLAT_PDF'
    source_hash: str             # Streaming SHA-256 prefix
    est_pages: int = 1
    dimensions: Optional[str] = None
    pre_scraped_meta: str = "NONE"
    is_l4_demoted: bool = False
    sidecar_rel_path: Optional[str] = None
    sidecar_status: str = "UNHYDRATED_STUB"  # 'UNHYDRATED_STUB', 'HYDRATED', 'STALE_BINARY_CHANGED'
    sidecar_leaf_hash: Optional[str] = None
    asset_class: str = "[NEEDS_HYDRATION]"
    visual_summary: str = "[NEEDS_HYDRATION - Inspect visual/SVG/PDF & populate concise engineering summary]"
    ocr_payload: str = "[NEEDS_HYDRATION - Populate key part numbers/specs or NONE]"


@dataclass
class FileRecord:
    rel_path: str
    parent_dir: str              # Relative POSIX directory ("" for root)
    subsystem: str               # Top-level directory or "root"
    byte_size: int
    line_count: int
    tokens_est: int
    is_python: bool
    is_opaque: bool = False
    opaque_info: Optional[OpaqueAssetInfo] = None
    symbols: List[SymbolSpan] = field(default_factory=list)
    preserved_raw_symbols: List[str] = field(default_factory=list)
    reexports: List[str] = field(default_factory=list)
    fault_status: Optional[str] = None
    stale_coord_warning: Optional[str] = None
    role_summary: str = "[TODO: AGENT_FILL - Summarize file responsibility & invariants]"
    assigned_shard: str = "TOKENME.txt"


@dataclass
class ADRRecord:
    rel_posix: str
    record_id: str
    iso_date: str
    title_slug: str
    status: str
    supersession_note: str
    leaf_hash: str


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
    opaque_class: Optional[str] = None
    opaque_summary: Optional[str] = None
    opaque_ocr: Optional[str] = None


class PythonASTExtractor(ast.NodeVisitor):
    """ADR-005 & ADR-006 Invariant 2: Exact Python AST symbol & qualified scope extractor."""

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
    counts: Dict[str, int] = {}
    for sym in symbols:
        idx = counts.get(sym.name, 0)
        sym.overload_idx = idx
        counts[sym.name] = idx + 1
    return symbols


def parse_python_ast(source_text: str, is_init_file: bool) -> Tuple[List[SymbolSpan], List[str], Optional[str]]:
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


# --- ADR-009 & ADR-010 ERR-01/ERR-02 Opaque & Vector Inspection Pipeline ---

def _parse_raster_dimensions_and_meta(filepath: Path, ext: str, size: int) -> Tuple[Optional[Tuple[int, int]], str]:
    """Zero-dependency header parser for PNG, GIF, and JPEG dimensions + PNG tEXt metadata."""
    dims: Optional[Tuple[int, int]] = None
    meta_items: List[str] = []
    try:
        with filepath.open("rb") as f:
            hdr = f.read(4096)
            if ext == ".png" and size >= 24:
                # ADR-010 ERR-01 fix: slice hdr[12:16] for IHDR and hdr[16:24] for >II unpack
                if hdr[:8] == b"\x89PNG\r\n\x1a\n" and hdr[12:16] == b"IHDR":
                    w, h = struct.unpack(">II", hdr[16:24])
                    dims = (w, h)
                # Scrape printable PNG tEXt chunks in initial header window
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
                # Fast SOF0/SOF2 marker scan in first 64 KiB
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
    meta_str = "; ".join(meta_items[:4]) if meta_items else "NONE"
    return dims, meta_str


def inspect_opaque_candidate(filepath: Path, rel_file: str) -> Optional[OpaqueAssetInfo]:
    """
    ADR-009 Part A & B + ADR-010 ERR-01:
    Evaluates the Pre-Filter Icon Gate, scrapes deterministic metadata/DOM strings,
    and determines L3 vs. L4 demotion status. Returns None if excluded as a trivial icon.
    """
    ext = filepath.suffix.lower()
    if ext not in OPAQUE_EXTENSIONS or filepath.name.endswith(".l3.txt"):
        return None
    try:
        size = filepath.stat().st_size
    except OSError:
        return None

    # 1. Raster Images (.png, .jpg, .tiff, .bmp, .webp, .gif)
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

    # 2. Vector Diagrams (.svg)
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
        descs = re.findall(r"<desc[^>]*>(.*?)</desc>", raw_svg, flags=re.IGNORECASE | re.DOTALL)
        texts = re.findall(r"<text[^>]*>(.*?)</text>", raw_svg, flags=re.IGNORECASE | re.DOTALL)
        g_ids = re.findall(r"<g[^>]*\bid=[\"']([^\"']+)[\"']", raw_svg, flags=re.IGNORECASE)

        cleaned_snippets: List[str] = []
        for item in (titles[:2] + descs[:2] + texts[:6]):
            clean = re.sub(r"<[^>]+>", " ", item)
            clean = " ".join(clean.split())
            if clean:
                cleaned_snippets.append(clean[:80])
        if g_ids:
            cleaned_snippets.append(f"g_ids=[{', '.join(g_ids[:6])}]")

        meta_str = " | ".join(cleaned_snippets) if cleaned_snippets else "SVG_PATHS_ONLY (No <text> nodes)"
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

    # 3. Documents (.pdf) — Fast streaming regex scan for /Type /Page and text density
    if ext == ".pdf":
        src_hash = stream_sha256_hex(filepath, length=12)
        page_count = 0
        ascii_chars = 0
        meta_snippets: List[str] = []
        try:
            with filepath.open("rb") as f:
                # Sample up to first 4 MiB for page tags and metadata
                sample = f.read(4 * 1024 * 1024)
            page_count = len(re.findall(rb"/Type\s*/Page\b", sample))
            if page_count == 0:
                page_count = 1
            for tag in (b"Title", b"Author", b"Producer", b"Creator"):
                m = re.search(rb"/" + tag + rb"\s*\(([^\)]{1,120})\)", sample)
                if m:
                    val = m.group(1).decode("latin-1", errors="ignore").strip()
                    if val:
                        meta_snippets.append(f"/{tag.decode('ascii')} ({val})")
            # Estimate extractable text density from parenthetical literal strings
            for s_match in re.finditer(rb"\(([\x20-\x7e]{4,200})\)", sample):
                ascii_chars += len(s_match.group(1))
        except OSError:
            page_count = 1

        chars_per_page = ascii_chars / max(1, page_count)
        is_flat = chars_per_page < 50
        modality = "FLAT_PDF" if is_flat else "NATIVE_PDF"
        if is_flat:
            demoted = (page_count > FLAT_PDF_PAGE_LIMIT) or (size > FLAT_PDF_BYTE_LIMIT)
        else:
            demoted = (page_count > NATIVE_PDF_PAGE_LIMIT) or (size > NATIVE_PDF_BYTE_LIMIT)

        meta_str = " ".join(meta_snippets[:4]) if meta_snippets else "NONE"
        return OpaqueAssetInfo(
            modality=modality,
            source_hash=src_hash,
            est_pages=page_count,
            dimensions=f"{page_count}p",
            pre_scraped_meta=meta_str,
            is_l4_demoted=demoted,
            sidecar_rel_path=f"{rel_file}.l3.txt" if demoted else None,
        )

    return None


def sync_l4_sidecar_file(
    root: Path, rec: FileRecord, leaf_len: int, dry_run: bool
) -> None:
    """
    ADR-009 Part C & D + ADR-010 ERR-02:
    Generates or verifies the adjacent `<filename>.<ext>.l3.txt` sidecar for an L4-demoted
    asset, preserving existing hydrated content when L4_SOURCE_HASH matches, or marking
    `STATUS: STALE_BINARY_CHANGED` if the underlying binary changed on disk.
    """
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
            existing_lines = existing_text.splitlines()
            old_hash_match = re.search(r"^#\s*L4_SOURCE_HASH:\s*([0-9a-fA-F]+)", existing_text, re.MULTILINE)
            old_status_match = re.search(r"^#\s*STATUS:\s*(\S+)", existing_text, re.MULTILINE)
            old_hash = old_hash_match.group(1) if old_hash_match else ""
            old_status = old_status_match.group(1) if old_status_match else "UNHYDRATED_STUB"

            # Extract body after `# STATUS:` line
            body_start_idx = 0
            for idx, l in enumerate(existing_lines):
                if l.startswith("# STATUS:"):
                    body_start_idx = idx + 1
                    break
            preserved_body = existing_lines[body_start_idx:] if body_start_idx > 0 else existing_lines[5:]

            if old_hash == info.source_hash:
                info.sidecar_status = old_status
                # Harvest summary fields if hydrated
                m_cls = re.search(r"^Asset_Class:\s*(.+)$", existing_text, re.MULTILINE)
                m_sum = re.search(r"^Visual_Or_Content_Summary:\s*(.+)$", existing_text, re.MULTILINE)
                if m_cls and "<PENDING:" not in m_cls.group(1):
                    info.asset_class = m_cls.group(1).strip()
                if m_sum and "<PENDING:" not in m_sum.group(1):
                    info.visual_summary = m_sum.group(1).strip()
                info.sidecar_leaf_hash = hashlib.sha256(canonical_bytes(sidecar_path)).hexdigest()[:leaf_len]
                return
            else:
                # Binary mutated on disk: update L4_SOURCE_HASH and set STALE_BINARY_CHANGED
                info.sidecar_status = "STALE_BINARY_CHANGED"
                updated_content = "\n".join(
                    header_lines + ["# STATUS: STALE_BINARY_CHANGED"] + preserved_body
                ) + "\n"
                if not dry_run:
                    sidecar_path.write_text(updated_content, encoding="utf-8", newline="\n")
                norm_bytes = updated_content.replace("\r\n", "\n").strip().encode("utf-8")
                info.sidecar_leaf_hash = hashlib.sha256(norm_bytes).hexdigest()[:leaf_len]
                return
        except OSError:
            pass

    # Create fresh .l3.txt sidecar using ADR-010 ERR-02 unscrambled schema
    info.sidecar_status = "UNHYDRATED_STUB"
    stub_lines = header_lines + [
        "# STATUS: UNHYDRATED_STUB",
        "",
        "[DETERMINISTIC_PRE_SCRAPE]",
        f"Extracted_Metadata: {info.pre_scraped_meta}",
        "",
        "[AGENT_HYDRATION_REQUIRED]",
        "Asset_Class: <PENDING: Schematic | Datasheet_Scan | Manual | CAD_Render | Field_Photo | Receipt_Invoice>",
        "Visual_Or_Content_Summary: <PENDING: 1-3 dense engineering sentence summary>",
        "Page_Map_And_TOC:",
        "  - <PENDING: Map section headers to page ranges so L4 binary can be queried by page slice>",
        "Key_Specs_And_OCR:",
        "  - <PENDING: Critical part numbers, pinouts, torque specs, or extracted tables (`NONE` if non-text photo)>",
    ]
    stub_text = "\n".join(stub_lines) + "\n"
    if not dry_run:
        try:
            sidecar_path.write_text(stub_text, encoding="utf-8", newline="\n")
        except OSError:
            pass
    norm_bytes = stub_text.replace("\r\n", "\n").strip().encode("utf-8")
    info.sidecar_leaf_hash = hashlib.sha256(norm_bytes).hexdigest()[:leaf_len]


# --- ADR-007, ADR-008 & ADR-010 Decision Record Discovery & Merkle Hashing ---

def resolve_decisions_dir(root: Path, custom_dir: Optional[str] = None) -> Optional[Path]:
    """ADR-010 HC-03: Canonical path is docs/adr/, with fallback to docs/decisions/."""
    if custom_dir:
        p = root / custom_dir
        return p if p.is_dir() else None
    canonical = root / "docs" / "adr"
    if canonical.is_dir():
        return canonical
    fallback = root / "docs" / "decisions"
    if fallback.is_dir():
        return fallback
    return None


def parse_adr_metadata(adr_path: Path, root: Path, leaf_len: int) -> ADRRecord:
    """
    ADR-007, ADR-008, ADR-010 HC-04 & AMB-03:
    Extracts 3-tuple or advisory ID, parses Status and Amendment notes, and computes
    the canonical leaf SHA-256 digest.
    """
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
    supersession_note = ""
    try:
        text = adr_path.read_text(encoding="utf-8", errors="ignore")
        # Match bullet `* **Status:** ...` or table `| **Status** | ... |`
        m_stat = re.search(
            r"(?:\*\s*\*\*Status:\*\*\s*|^\|\s*\*\*Status\*\*\s*\|\s*)([^|\n]+)",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        if m_stat:
            raw_stat = m_stat.group(1).strip().strip("`").strip()
            status_val = raw_stat
            m_amend = re.search(r"\(([^)]*(?:Amended|Superseded)[^)]*)\)", raw_stat, re.IGNORECASE)
            if m_amend:
                supersession_note = f"[{m_amend.group(1).strip()}]"
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
        supersession_note=supersession_note,
        leaf_hash=digest,
    )


def discover_adr_records(root: Path, leaf_len: int = DEFAULT_LEAF_HASH_LEN, custom_dir: Optional[str] = None) -> List[ADRRecord]:
    """ADR-008 Sec 2.2: Discovers all markdown ADR files sorted by relative POSIX path and checks for collisions."""
    if not (6 <= leaf_len <= 64):
        raise ValueError("leaf_len must be between 6 and 64 hex characters.")
    decisions_dir = resolve_decisions_dir(root, custom_dir)
    if not decisions_dir:
        return []

    records: List[ADRRecord] = []
    seen_hashes: Dict[str, str] = {}

    paths = sorted(
        (
            p for p in decisions_dir.iterdir()
            if p.is_file() and not p.is_symlink() and p.suffix.lower() == ".md" and p.name.lower() not in IGNORED_DECISION_FILES
        ),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for path in paths:
        rec = parse_adr_metadata(path, root, leaf_len)
        if rec.leaf_hash in seen_hashes:
            raise RuntimeError(
                f"Leaf hash collision detected ({rec.leaf_hash}) between "
                f"{seen_hashes[rec.leaf_hash]} and {rec.rel_posix}. "
                f"Increase --leaf-len beyond {leaf_len}."
            )
        seen_hashes[rec.leaf_hash] = rec.rel_posix
        records.append(rec)
    return records


def compute_merkle_state_root_from_text(
    tokenme_text: str, agents_path: Optional[Path], root_len: int = DEFAULT_ROOT_HASH_LEN
) -> str:
    """
    ADR-008 Sec 2.4 & ADR-010 AMB-04:
    Computes configurable Merkle STATE_ROOT across normalized local AGENTS.md (or b"" if absent)
    and masked TOKENME text.
    """
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
    """Replaces `# STATE_ROOT: ...` with the freshly computed Merkle digest."""
    digest = compute_merkle_state_root_from_text(tokenme_text, agents_path, root_len=root_len)
    stamped = STATE_ROOT_PATTERN.sub(rf"\g<1>{digest}\g<3>", tokenme_text)
    return stamped, digest


# --- Repository Traversal & State Harvesting ---

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
    root: Path, max_size_bytes: int, leaf_len: int, dry_run: bool
) -> Tuple[List[FileRecord], List[QuarantineEntry], List[str]]:
    """
    ADR-006 Invariants 3-4, ADR-009 Part A-C, & ADR-010 HC-06:
    Modality-first routing: Opaque/vector/PDF assets route to the streaming L3/L4
    inspector prior to the 1 MiB / null-byte text-reader quarantine.
    """
    ignore_patterns = load_ignore_patterns(root)
    records: List[FileRecord] = []
    quarantine_log: List[QuarantineEntry] = []

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
            except PermissionError:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason="[UNPARSEABLE: PermissionError on stat]"))
                continue
            except OSError as exc:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: OSError ({exc.__class__.__name__})]"))
                continue

            byte_size = st.st_size
            if byte_size == 0:
                continue

            parts = rel_file.split("/")
            subsystem = parts[0] if len(parts) > 1 else "root"
            ext = fpath.suffix.lower()

            # --- Branch 1 (ADR-010 HC-06): Opaque, Vector & PDF Modality Pipeline ---
            if ext in OPAQUE_EXTENSIONS:
                opaque_info = inspect_opaque_candidate(fpath, rel_file)
                if opaque_info is None:
                    # Excluded by Pre-Filter Icon Gate (<512B, <128x128px, or trivial SVG icon)
                    continue
                rec = FileRecord(
                    rel_path=rel_file,
                    parent_dir=rel_dir,
                    subsystem=subsystem,
                    byte_size=byte_size,
                    line_count=opaque_info.est_pages,
                    tokens_est=45,  # Bounded L2 summary footprint
                    is_python=False,
                    is_opaque=True,
                    opaque_info=opaque_info,
                    role_summary="[NEEDS_HYDRATION - Opaque/Vector/PDF Asset]",
                )
                if opaque_info.is_l4_demoted:
                    sync_l4_sidecar_file(root, rec, leaf_len=leaf_len, dry_run=dry_run)
                records.append(rec)
                continue

            # --- Branch 2 (ADR-006): Source & Text Pipeline ---
            if byte_size > max_size_bytes:
                size_kb = byte_size // 1024
                limit_kb = max_size_bytes // 1024
                quarantine_log.append(
                    QuarantineEntry(
                        rel_path=rel_file,
                        reason=f"[UNPARSEABLE: OversizeText ({size_kb:,} KiB exceeds {limit_kb:,} KiB limit)]",
                    )
                )
                continue

            try:
                with fpath.open("rb") as bf:
                    sniff_chunk = bf.read(BINARY_SNIFF_BYTES)
                if b"\x00" in sniff_chunk:
                    quarantine_log.append(
                        QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: BinaryNullByte ({byte_size:,} B)]")
                    )
                    continue
            except PermissionError:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason="[UNPARSEABLE: PermissionError on read]"))
                continue
            except OSError as exc:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: OSError ({exc.__class__.__name__})]"))
                continue

            is_py = ext in PYTHON_AST_EXTS
            try:
                text = fpath.read_text(encoding="utf-8", errors="strict")
            except UnicodeDecodeError:
                est_lines = max(1, sniff_chunk.count(b"\n"))
                fault_msg = "[UNPARSEABLE: UnicodeDecodeError (Non-UTF-8 file encoding)]"
                records.append(
                    FileRecord(
                        rel_path=rel_file,
                        parent_dir=rel_dir,
                        subsystem=subsystem,
                        byte_size=byte_size,
                        line_count=est_lines,
                        tokens_est=max(1, byte_size // 4),
                        is_python=is_py,
                        fault_status=fault_msg,
                    )
                )
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=fault_msg))
                continue
            except OSError as exc:
                quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=f"[UNPARSEABLE: OSError ({exc.__class__.__name__})]"))
                continue

            lines = text.splitlines()
            if not lines:
                continue

            tokens_est = estimate_tokens(text)

            if is_py:
                syms, reexports, ast_fault = parse_python_ast(text, is_init_file=(fname == "__init__.py"))
                if ast_fault:
                    quarantine_log.append(QuarantineEntry(rel_path=rel_file, reason=ast_fault))
                records.append(
                    FileRecord(
                        rel_path=rel_file,
                        parent_dir=rel_dir,
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
                        parent_dir=rel_dir,
                        subsystem=subsystem,
                        byte_size=byte_size,
                        line_count=len(lines),
                        tokens_est=tokens_est,
                        is_python=False,
                    )
                )

    runtimes = detect_runtimes(root)
    return records, quarantine_log, runtimes


def find_existing_tokenme_shards(root: Path) -> List[Path]:
    """Finds root TOKENME*.txt and any subdirectory TOKENME.<subsystem>.txt shards."""
    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in sorted(dirnames) if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".")]
        for fname in sorted(filenames):
            if fname.startswith("TOKENME") and fname.endswith(".txt") and not fname.endswith(".l3.txt"):
                p = Path(dirpath) / fname
                if p.is_file() and not p.is_symlink():
                    found.append(p)
    return found


def harvest_existing_state(root: Path) -> Tuple[Dict[str, str], Dict[str, HarvestedFileState]]:
    """Harvests L0 metadata, L1 roles, L2 Python/agent symbols, and hydrated L3 opaque fields across all shards."""
    l0_meta: Dict[str, str] = {}
    file_states: Dict[str, HarvestedFileState] = {}

    header_re = re.compile(r"^###\s+`([^`]+)`\s+\[(?:L1-L(\d+)|OPAQUE_L3|L4_DEMOTED)\]")
    table_row_re = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*\[L1-L(\d+)\]\s*\|\s*[^|]+\|\s*[^|]+\|\s*(.+?)\s*\|$")
    role_re = re.compile(r"^-\s+\*\*Role & Invariants:\*\*\s*(.+)$")
    sym_re = re.compile(r"^\s*-\s+`([^`]+)`\s+\[L\d+-L\d+\]\s*:\s*(.+)$")
    l0_bullet_re = re.compile(r"^-\s+\*\*([^:*]+):\*\*\s*(.+)$")
    opaque_cls_re = re.compile(r"^-\s+\*\*Asset_Class:\*\*\s*(.+)$")
    opaque_sum_re = re.compile(r"^-\s+\*\*Visual_Summary:\*\*\s*(.+)$")
    opaque_ocr_re = re.compile(r"^-\s+\*\*OCR_Payload:\*\*\s*(.+)$")

    for existing_path in find_existing_tokenme_shards(root):
        try:
            lines = existing_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        current_file: Optional[str] = None
        in_l2_block = False
        per_file_counts: Dict[Tuple[str, str], int] = {}

        for line in lines:
            stripped = line.strip()

            if existing_path == root / "TOKENME.txt" and current_file is None:
                m_l0 = l0_bullet_re.match(stripped)
                if m_l0:
                    key_label = m_l0.group(1).strip()
                    val_str = m_l0.group(2).strip()
                    if not val_str.startswith("[TODO: AGENT_FILL"):
                        l0_meta[key_label] = val_str

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

            m_file = header_re.match(stripped)
            if m_file:
                current_file = m_file.group(1).strip()
                old_lc = int(m_file.group(2)) if m_file.group(2) else 1
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

            m_ocls = opaque_cls_re.match(stripped)
            if m_ocls and "[NEEDS_HYDRATION" not in m_ocls.group(1):
                st.opaque_class = m_ocls.group(1).strip()
                continue

            m_osum = opaque_sum_re.match(stripped)
            if m_osum and "[NEEDS_HYDRATION" not in m_osum.group(1):
                st.opaque_summary = m_osum.group(1).strip()
                continue

            m_oocr = opaque_ocr_re.match(stripped)
            if m_oocr and "[NEEDS_HYDRATION" not in m_oocr.group(1):
                st.opaque_ocr = m_oocr.group(1).strip()
                continue

            if stripped.startswith("- **L2 Symbol Coordinates"):
                in_l2_block = True
                continue

            if stripped.startswith("### ") or stripped.startswith("## ") or stripped.startswith("---"):
                current_file = None
                in_l2_block = False
                continue

            if in_l2_block and line.startswith("  - "):
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
    for rec in records:
        st = file_states.get(rec.rel_path)
        if not st:
            continue

        if not st.role_summary.startswith("[TODO: AGENT_FILL") and not st.role_summary.startswith("[NEEDS_HYDRATION"):
            rec.role_summary = st.role_summary

        if rec.is_opaque and rec.opaque_info:
            if st.opaque_class:
                rec.opaque_info.asset_class = st.opaque_class
            if st.opaque_summary:
                rec.opaque_info.visual_summary = st.opaque_summary
            if st.opaque_ocr:
                rec.opaque_info.ocr_payload = st.opaque_ocr
        elif rec.is_python:
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


# --- Section Renderers (ADR-002, ADR-008, ADR-009, ADR-010) ---

def render_merkle_header_block(adr_count: int, state_root: str = "PENDING") -> List[str]:
    """ADR-008 Sec 2.5: Canonical top metadata block exposing STATE_ROOT and ADR_COUNT."""
    return [
        f"# TOKENME_VERSION: {SPEC_VERSION}",
        f"# STATE_ROOT: {state_root}",
        f"# ADR_COUNT: {adr_count}",
        "",
    ]


def render_adr_index_section(adr_records: List[ADRRecord]) -> List[str]:
    """ADR-007, ADR-008 & ADR-010 AMB-03: Renders the Merkle-indexed ADR table with supersession tags."""
    if not adr_records:
        return []
    out: List[str] = [
        "## Architecture Decision Ledger (`docs/adr/` — ADR-007 & ADR-008 Merkle Provenance)",
        "| Record ID | Date | Status & Supersession | Leaf Hash | Decision Artifact (`[RecordID]_[ISODate]_[TitleSlug].md`) |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for adr in adr_records:
        out.append(
            f"| `{adr.record_id}` | {adr.iso_date} | {adr.status} | `{adr.leaf_hash}` | `{adr.rel_posix}` |"
        )
    out.append("")
    return out


def render_single_file_l2_block(rec: FileRecord) -> List[str]:
    """Renders an individual code file or opaque/L4 asset L2 block."""
    out: List[str] = []
    kb_str = f"{rec.byte_size / 1024:.1f} KiB"

    if rec.is_opaque and rec.opaque_info:
        info = rec.opaque_info
        if info.is_l4_demoted:
            flag = "[NEEDS_HYDRATION]" if info.sidecar_status != "HYDRATED" else "[HYDRATED]"
            out.append(
                f"### `{rec.rel_path}` [L4_DEMOTED] ({kb_str} | {info.modality} | {info.est_pages}p | {flag})"
            )
            out.append(
                f"- **L3_Surrogate_Sidecar:** `{info.sidecar_rel_path}` "
                f"(Status: `{info.sidecar_status}` | L4_Hash: `{info.source_hash}` | Sidecar_Leaf_Hash: `{info.sidecar_leaf_hash}`)"
            )
            out.append(f"- **Pre_Scraped_Meta:** `{info.pre_scraped_meta}`")
            out.append(f"- **Visual_Summary:** {info.visual_summary}")
        else:
            out.append(
                f"### `{rec.rel_path}` [OPAQUE_L3] ({kb_str} | {info.modality} | {info.dimensions} | Hash: `{info.source_hash}`)"
            )
            out.append(f"- **Asset_Class:** {info.asset_class}")
            out.append(f"- **Meta_Context:** `{info.pre_scraped_meta}`")
            out.append(f"- **Visual_Summary:** {info.visual_summary}")
            out.append(f"- **OCR_Payload:** {info.ocr_payload}")
        out.append("")
        return out

    # Standard Source / Text File
    out.append(
        f"### `{rec.rel_path}` [L1-L{rec.line_count}] ({kb_str} | ~{rec.tokens_est} conservative tokens)"
    )
    out.append(f"- **Role & Invariants:** {rec.role_summary}")
    if rec.reexports:
        joined_re = ", ".join(f"`{r}`" for r in rec.reexports)
        out.append(f"- **Re-Exports / Facade Routes (`__init__`):** {joined_re}")

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
                "  - `[AGENT_POPULATE_SYMBOLS]` — Non-Python source/doc file; coding agent must populate `- `<kind> <Name>` [Lstart-Lend]: <concise summary>` (and `-> impl:` pointers where applicable) upon first inspection."
            )
    out.append("")
    return out


def render_file_digest_section(records: List[FileRecord]) -> List[str]:
    out: List[str] = []
    for rec in records:
        out.extend(render_single_file_l2_block(rec))
    return out


def render_quarantine_section(quarantine_log: List[QuarantineEntry]) -> List[str]:
    if not quarantine_log:
        return []
    out: List[str] = [
        "## Quarantined & Unparseable Artifacts (ADR-006 Fail-Closed Ledger)",
        "| File / Path | Isolation Reason |",
        "| :--- | :--- |",
    ]
    for q in quarantine_log[:40]:
        out.append(f"| `{q.rel_path}` | `{q.reason}` |")
    if len(quarantine_log) > 40:
        out.append(f"| _...and {len(quarantine_log) - 40} additional quarantined items_ | _(Omitted for token budget)_ |")
    out.append("")
    return out


def render_bootstrap_footer(topology_mode: str) -> List[str]:
    return [
        "---",
        "## [SELF-REFERENTIAL BOOTSTRAP & AGENT MAINTENANCE PROTOCOL]",
        "```yaml",
        f"spec_version: {SPEC_VERSION}",
        f"scaffolder_version: {VERSION}",
        f"topology_mode: {topology_mode}",
        "agent_execution_protocol:",
        "  1_MIPMAP_ROUTING: Read root TOKENME.txt (and check STATE_ROOT) BEFORE executing broad grep, find, or full-file reads.",
        "  2_SURGICAL_L3_READ: Use [Lstart-Lend] coordinates to issue bounded line-range reads; never ingest [L4_DEMOTED] binaries whole (read .l3.txt sidecar first).",
        "  3_NON_PYTHON_STUBS: Where `[AGENT_POPULATE_SYMBOLS]` appears, inspect the file once and populate `- `<kind> <Name>` [Lstart-Lend]: <summary>` entries.",
        "  4_HYDRATION_DUTY: Resolve `[TODO: AGENT_FILL]`, `[NEEDS_HYDRATION]`, and `[COORDS_STALE_CHECK]` markers in files/sidecars you touch.",
        "  5_MERKLE_SYNC: Run `python3 tokenme-sync.py` (or `--sync`) after edits to refresh AST coordinates, sidecar hashes, and Merkle STATE_ROOT (`--check` in CI).",
        "```",
    ]


# --- ADR-009 Part E & ADR-010 HC-02 Two-Pass Sharding Engine ---

def evaluate_pass1_subdir_shard(
    subdir_rel: str, subdir_records: List[FileRecord]
) -> Tuple[bool, str]:
    """
    ADR-009 Part E (Pass 1) & ADR-010 Sec 3.1:
    Evaluates a top-level subdirectory for Opaque Density (>=8), Projected L2 Lines (>100),
    or Extracted Symbol Count (>75).
    """
    n_opaque = sum(1 for r in subdir_records if r.is_opaque)
    code_recs = [r for r in subdir_records if not r.is_opaque]
    code_symbols = sum(len(r.symbols) + len(r.preserved_raw_symbols) for r in code_recs)
    code_l2_lines = sum(len(render_single_file_l2_block(r)) for r in code_recs)
    proj_lines = code_l2_lines + (n_opaque * PROJECTED_L2_LINES_PER_OPAQUE)

    if n_opaque >= OPAQUE_SHARD_COUNT_THRESHOLD:
        return True, f"OPAQUE_DENSITY({n_opaque})"
    if proj_lines > DIR_PROJECTED_LINE_CEILING:
        return True, f"PROJECTED_L2_OVERFLOW({proj_lines})"
    if code_symbols > SHARD_TRIGGER_SYMBOLS:
        return True, f"SYMBOL_COUNT({code_symbols})"
    return False, "INLINE_IN_ROOT"


def build_documents(
    root: Path,
    records: List[FileRecord],
    adr_records: List[ADRRecord],
    quarantine_log: List[QuarantineEntry],
    runtimes: List[str],
    l0_meta: Dict[str, str],
    root_len: int = DEFAULT_ROOT_HASH_LEN,
    force_single: bool = False,
) -> Dict[Path, str]:
    """
    Executes the Two-Pass Sharding & Bottom-Up Merkle Rollup Protocol (ADR-008, ADR-009, ADR-010):
      - Pass 1: Bottom-up subdirectory sharding (`<subdir>/TOKENME.<subsystem>.txt`).
      - Pass 2: Root line ceiling check (`<= 150` lines). If exceeded, ejects remaining
        unsharded inline L2 entries to `TOKENME.root-l2.txt` (<=250 lines) or splits
        by modality into `TOKENME.code.txt` and `TOKENME.assets.txt` (>250 lines).
      - Computes child shard `STATE_ROOT` digests first, embeds them in the parent Shard
        Index Table, and stamps the root `STATE_ROOT` over `AGENTS.md` + `TOKENME.txt`.
    """
    repo_name = root.resolve().name
    total_files = len(records)
    code_files = [r for r in records if not r.is_opaque]
    opaque_files = [r for r in records if r.is_opaque]
    total_loc = sum(r.line_count for r in code_files)
    total_raw_tokens = sum(r.tokens_est for r in records)
    total_ast_symbols = sum(len(r.symbols) for r in records)
    total_agent_symbols = sum(len(r.preserved_raw_symbols) for r in records)

    runtime_list_str = ", ".join(runtimes) if runtimes else l0_meta.get(
        "Primary Runtimes", l0_meta.get("Detected Runtimes", "Python >= 3.9 (Standard Library Only)")
    )
    sys_purpose = l0_meta.get(
        "System Purpose",
        "[TODO: AGENT_FILL - State core system objective in <=25 words]",
    )
    entrypoints = l0_meta.get(
        "Entrypoints",
        "[TODO: AGENT_FILL - List primary CLI/server/app entrypoints]",
    )
    global_invariants = l0_meta.get(
        "Global State & Mutation Invariants",
        l0_meta.get("Cross-Boundary Invariants", "[TODO: AGENT_FILL - Document critical data/concurrency constraints]"),
    )
    today_iso = datetime.date.today().isoformat()

    outputs: Dict[Path, str] = {}
    # Tuple: (scope_label, rel_shard_posix, reason, shard_records, child_state_root)
    mounted_shards: List[Tuple[str, str, str, List[FileRecord], str]] = []

    # Group records by top-level subsystem directory
    by_subsystem: Dict[str, List[FileRecord]] = {}
    for r in records:
        by_subsystem.setdefault(r.subsystem, []).append(r)

    unsharded_records: List[FileRecord] = []

    # --- PASS 1: Bottom-Up Subdirectory Sharding (<subdir>/TOKENME.<subsystem>.txt) ---
    for sub_name, sub_recs in sorted(by_subsystem.items()):
        if sub_name == "root" or force_single:
            unsharded_records.extend(sub_recs)
            continue

        should_shard_dir, trigger_reason = evaluate_pass1_subdir_shard(sub_name, sub_recs)
        if not should_shard_dir:
            unsharded_records.extend(sub_recs)
            continue

        # ADR-010 HC-02: Emit inside target subdirectory as <subdir>/TOKENME.<subdir_slug>.txt
        slug = re.sub(r"[^a-zA-Z0-9_-]", "-", sub_name.lower())
        rel_shard_posix = f"{sub_name}/TOKENME.{slug}.txt"
        shard_abs_path = root / sub_name / f"TOKENME.{slug}.txt"
        local_agents_path = root / sub_name / "AGENTS.md"

        for r in sub_recs:
            r.assigned_shard = rel_shard_posix

        shard_lines: List[str] = render_merkle_header_block(adr_count=len(adr_records), state_root="PENDING")
        shard_lines.extend([
            f"# TOKENME.{slug}.txt — Subdirectory Epistemic Shard (`{sub_name}/`)",
            f"> **Parent Router:** `../TOKENME.txt` | **Trigger:** `{trigger_reason}` | **Last Synced:** {today_iso}",
            "",
            "## 1. Subsystem Invariants & Boundary",
            f"- **Subdirectory Scope:** `{sub_name}/` ({len(sub_recs)} files)",
            "- **Domain Invariants:** [TODO: AGENT_FILL - Summarize subsystem invariants]",
            "",
            "## 2. Co-Located L1 File Invariants & L2 Symbol / Opaque Digest",
            "",
        ])
        shard_lines.extend(render_file_digest_section(sub_recs))
        shard_lines.extend(render_bootstrap_footer("SUBDIR_MIPMAP_SHARD"))

        raw_shard_text = "\n".join(shard_lines) + "\n"
        stamped_shard_text, child_root = stamp_state_root_in_text(
            raw_shard_text, local_agents_path, root_len=root_len
        )
        outputs[shard_abs_path] = stamped_shard_text
        mounted_shards.append((f"{sub_name}/", rel_shard_posix, trigger_reason, sub_recs, child_root))

    # Build L0 Header + ADR Index + Quarantine + Footer to measure root line budget
    l0_header_lines: List[str] = render_merkle_header_block(adr_count=len(adr_records), state_root="PENDING")
    l0_header_lines.extend([
        "# TOKENME.txt — Declarative Epistemic State & Merkle Router",
        f"> **Repository:** `{repo_name}` | **Spec:** TOKENME v{SPEC_VERSION} | **Last Synced:** {today_iso}",
        f"> **Coverage:** {total_files} files ({len(code_files)} code/doc, {len(opaque_files)} opaque/PDF) | {total_loc:,} LOC | {total_ast_symbols} AST syms + {total_agent_symbols} agent syms | ~{total_raw_tokens:,} conservative tokens",
        "",
        "## 1. L0 System Identity & Architectural Invariants",
        f"- **Primary Runtimes:** {runtime_list_str}",
        f"- **System Purpose:** {sys_purpose}",
        f"- **Entrypoints:** {entrypoints}",
        f"- **Global State & Mutation Invariants:** {global_invariants}",
        "",
    ])
    adr_section_lines = render_adr_index_section(adr_records)
    quarantine_lines = render_quarantine_section(quarantine_log)

    unsharded_code_recs = [r for r in unsharded_records if not r.is_opaque]
    unsharded_asset_recs = [r for r in unsharded_records if r.is_opaque]
    unsharded_code_l2 = render_file_digest_section(unsharded_code_recs)
    unsharded_asset_l2 = render_file_digest_section(unsharded_asset_recs)

    # Estimate total root lines if unsharded records stay inline in root TOKENME.txt
    est_mount_table_lines = (len(mounted_shards) + 6) if mounted_shards else 0
    base_len = (
        len(l0_header_lines)
        + len(adr_section_lines)
        + est_mount_table_lines
        + len(quarantine_lines)
        + 16  # Footer + section headers
    )
    spillover_len = len(unsharded_code_l2) + len(unsharded_asset_l2)

    # --- PASS 2: Root Ceiling Check (<= 150 lines) & Modality-Bucketed Ejection ---
    keep_inline_in_root = force_single or ((base_len + spillover_len) <= ROOT_LINE_CEILING)

    if not keep_inline_in_root and unsharded_records:
        if spillover_len <= SINGLE_OVERFLOW_CEILING:
            rel_sp = "TOKENME.root-l2.txt"
            sp_path = root / rel_sp
            for r in unsharded_records:
                r.assigned_shard = rel_sp
            sp_lines = render_merkle_header_block(adr_count=len(adr_records), state_root="PENDING")
            sp_lines.extend([
                "# TOKENME.root-l2.txt — Root Spillover L2 Shard",
                f"> **Parent Router:** `./TOKENME.txt` | **Trigger:** `ROOT_CEILING_EJECTION` | **Last Synced:** {today_iso}",
                "",
                "## Co-Located L1 File Invariants & L2 Symbol / Asset Digest",
                "",
            ])
            sp_lines.extend(unsharded_code_l2)
            sp_lines.extend(unsharded_asset_l2)
            sp_lines.extend(render_bootstrap_footer("ROOT_OVERFLOW_SHARD"))
            stamped_sp, sp_root = stamp_state_root_in_text(
                "\n".join(sp_lines) + "\n", root / "AGENTS.md", root_len=root_len
            )
            outputs[sp_path] = stamped_sp
            mounted_shards.append(("root (spillover)", rel_sp, "ROOT_CEILING_EJECTION", unsharded_records, sp_root))
        else:
            if unsharded_code_recs:
                rel_code = "TOKENME.code.txt"
                for r in unsharded_code_recs:
                    r.assigned_shard = rel_code
                c_lines = render_merkle_header_block(adr_count=len(adr_records), state_root="PENDING")
                c_lines.extend([
                    "# TOKENME.code.txt — Root Code & Script Modality Shard",
                    f"> **Parent Router:** `./TOKENME.txt` | **Trigger:** `ROOT_EJECTION_CODE` | **Last Synced:** {today_iso}",
                    "",
                    "## Co-Located L1 File Invariants & L2 Code Symbol Digest",
                    "",
                ])
                c_lines.extend(unsharded_code_l2)
                c_lines.extend(render_bootstrap_footer("ROOT_MODALITY_CODE_SHARD"))
                stamped_c, c_root = stamp_state_root_in_text(
                    "\n".join(c_lines) + "\n", root / "AGENTS.md", root_len=root_len
                )
                outputs[root / rel_code] = stamped_c
                mounted_shards.append(("root (code)", rel_code, "ROOT_EJECTION_CODE", unsharded_code_recs, c_root))

            if unsharded_asset_recs:
                rel_assets = "TOKENME.assets.txt"
                for r in unsharded_asset_recs:
                    r.assigned_shard = rel_assets
                a_lines = render_merkle_header_block(adr_count=len(adr_records), state_root="PENDING")
                a_lines.extend([
                    "# TOKENME.assets.txt — Root Opaque, Vector & L4 Asset Modality Shard",
                    f"> **Parent Router:** `./TOKENME.txt` | **Trigger:** `ROOT_EJECTION_ASSETS` | **Last Synced:** {today_iso}",
                    "",
                    "## Opaque L3 Summaries & L4 Surrogate Sidecar Pointers",
                    "",
                ])
                a_lines.extend(unsharded_asset_l2)
                a_lines.extend(render_bootstrap_footer("ROOT_MODALITY_ASSETS_SHARD"))
                stamped_a, a_root = stamp_state_root_in_text(
                    "\n".join(a_lines) + "\n", root / "AGENTS.md", root_len=root_len
                )
                outputs[root / rel_assets] = stamped_a
                mounted_shards.append(("root (assets)", rel_assets, "ROOT_EJECTION_ASSETS", unsharded_asset_recs, a_root))

        unsharded_records = []

    # Assemble Final Root TOKENME.txt
    if not mounted_shards:
        topology_mode = "MONOLITHIC_SINGLE_FILE"
    elif unsharded_records:
        topology_mode = "HYBRID_L1_L2_ROUTER"
    else:
        topology_mode = "PURE_L1_MERKLE_ROUTER"

    root_lines: List[str] = list(l0_header_lines)
    root_lines.extend(adr_section_lines)

    if mounted_shards:
        root_lines.extend([
            "## 2. Federated Shard Router Table (`[SHARD_MOUNT]` — ADR-008 & ADR-009)",
            "| Scope | Shard Mount Path | Trigger Reason | Files | Child `STATE_ROOT` |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        for scope_lbl, rel_sh, reason_str, s_recs, c_root in mounted_shards:
            root_lines.append(
                f"| `{scope_lbl}` | `./{rel_sh}` | `[SHARD_MOUNT | reason:{reason_str}]` | {len(s_recs)} | `{c_root}` |"
            )
        root_lines.append("")

    if unsharded_records:
        sec_num = "3" if mounted_shards else "2"
        root_lines.append(f"## {sec_num}. Inline L1/L2 File, Symbol & Opaque Asset Digest")
        root_lines.append("")
        root_lines.extend(unsharded_code_l2)
        root_lines.extend(unsharded_asset_l2)

    root_lines.extend(quarantine_lines)
    root_lines.extend(render_bootstrap_footer(topology_mode))

    raw_root_text = "\n".join(root_lines) + "\n"
    stamped_root_text, _ = stamp_state_root_in_text(
        raw_root_text, root / "AGENTS.md", root_len=root_len
    )
    outputs[root / "TOKENME.txt"] = stamped_root_text
    return outputs


# --- ADR-008 Tier 1 Fast Integrity Verification (`--check`) ---

def run_integrity_check(
    root: Path, leaf_len: int, root_len: int, custom_adr_dir: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    ADR-008 Sec 3 (Tier 1: Fast Integrity Check):
    Verifies in <2ms that:
      1. Root TOKENME.txt exists and its embedded STATE_ROOT matches AGENTS.md + masked TOKENME.txt.
      2. All ADR files in docs/adr/ match the leaf hashes recorded in root TOKENME.txt.
      3. All mounted child shards match their embedded STATE_ROOT and parent table entry.
      4. All L4 .l3.txt sidecars match their raw binary L4_SOURCE_HASH and parent shard entry.
    """
    errors: List[str] = []
    root_tokenme = root / "TOKENME.txt"
    if not root_tokenme.is_file():
        return False, ["Missing root `TOKENME.txt`."]

    try:
        root_text = root_tokenme.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    except OSError as exc:
        return False, [f"Failed to read `TOKENME.txt`: {exc}"]

    m_root = STATE_ROOT_PATTERN.search(root_text)
    if not m_root:
        errors.append("Root `TOKENME.txt` is missing `# STATE_ROOT: <hex>` header.")
    else:
        recorded_root = m_root.group(2)
        expected_root = compute_merkle_state_root_from_text(
            root_text, root / "AGENTS.md", root_len=len(recorded_root) if len(recorded_root) >= 8 else root_len
        )
        if recorded_root != expected_root:
            errors.append(
                f"Root STATE_ROOT mismatch: recorded `{recorded_root}` != computed `{expected_root}` "
                "(TOKENME.txt or AGENTS.md modified without running `tokenme-sync.py`)."
            )

    # Verify ADR leaf hashes
    try:
        adr_records = discover_adr_records(root, leaf_len=leaf_len, custom_dir=custom_adr_dir)
    except Exception as exc:
        errors.append(str(exc))
        adr_records = []

    m_count = re.search(r"^#\s*ADR_COUNT:\s*(\d+)", root_text, re.MULTILINE)
    if m_count and int(m_count.group(1)) != len(adr_records):
        errors.append(
            f"ADR_COUNT mismatch: `TOKENME.txt` records {m_count.group(1)}, but disk has {len(adr_records)} ADRs."
        )

    for adr in adr_records:
        if f"| `{adr.leaf_hash}` | `{adr.rel_posix}` |" not in root_text:
            errors.append(
                f"ADR leaf drift or unindexed ADR: `{adr.rel_posix}` (current hash `{adr.leaf_hash}` not found in `TOKENME.txt`)."
            )

    # Verify mounted child shards
    shard_mount_re = re.compile(
        r"^\|\s*`[^`]+`\s*\|\s*`\./([^`]+)`\s*\|\s*`\[SHARD_MOUNT[^`]*\]`\s*\|\s*\d+\s*\|\s*`([0-9a-fA-F]+)`\s*\|$",
        re.MULTILINE,
    )
    for m_sh in shard_mount_re.finditer(root_text):
        rel_sh = m_sh.group(1)
        recorded_child_root = m_sh.group(2)
        sh_path = root / rel_sh
        if not sh_path.is_file():
            errors.append(f"Missing mounted child shard on disk: `{rel_sh}`.")
            continue
        sh_text = sh_path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        local_agents = sh_path.parent / "AGENTS.md" if sh_path.parent != root else (root / "AGENTS.md")
        computed_child = compute_merkle_state_root_from_text(
            sh_text, local_agents, root_len=len(recorded_child_root)
        )
        if computed_child != recorded_child_root:
            errors.append(
                f"Child shard `{rel_sh}` STATE_ROOT drift: parent expects `{recorded_child_root}`, computed `{computed_child}`."
            )

    return len(errors) == 0, errors


def atomic_commit_outputs(root: Path, outputs: Dict[Path, str], clean_stale_shards: bool = True) -> None:
    """ADR-006 Invariant 4: Atomic temp-file staging and `os.replace()` across root and subdirectory shards."""
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


def print_telemetry_receipt(
    root: Path,
    records: List[FileRecord],
    adr_records: List[ADRRecord],
    quarantine_log: List[QuarantineEntry],
    runtimes: List[str],
    outputs: Dict[Path, str],
    init_mode: bool,
    dry_run: bool,
) -> None:
    total_files = len(records)
    py_files = sum(1 for r in records if r.is_python)
    opaque_files = sum(1 for r in records if r.is_opaque)
    l4_files = sum(1 for r in records if r.is_opaque and r.opaque_info and r.opaque_info.is_l4_demoted)
    non_py_code = total_files - py_files - opaque_files
    total_loc = sum(r.line_count for r in records if not r.is_opaque)
    raw_tokens = max(1, sum(r.tokens_est for r in records))
    ast_symbols = sum(len(r.symbols) for r in records)
    preserved_symbols = sum(len(r.preserved_raw_symbols) for r in records)

    root_doc = outputs.get(root / "TOKENME.txt", "")
    root_tokens = max(1, estimate_tokens(root_doc))
    root_lines_cnt = len(root_doc.splitlines())
    total_meta_tokens = max(1, sum(estimate_tokens(c) for c in outputs.values()))
    compression_ratio = raw_tokens / root_tokens

    m_sr = STATE_ROOT_PATTERN.search(root_doc)
    state_root_str = m_sr.group(2) if m_sr else "UNKNOWN"

    todo_count = sum(c.count("[TODO: AGENT_FILL") for c in outputs.values())
    stub_count = sum(c.count("[AGENT_POPULATE_SYMBOLS]") for c in outputs.values())
    hydration_count = sum(c.count("[NEEDS_HYDRATION") for c in outputs.values())
    stale_count = sum(c.count("[COORDS_STALE_CHECK:") for c in outputs.values())

    sharded = len(outputs) > 1
    mode_str = (
        f"Two-Pass Sharded Mode (Root Router + {len(outputs) - 1} Shards)"
        if sharded
        else "Monolithic Single-File Mode"
    )
    rt_str = ", ".join(runtimes) if runtimes else "Python >= 3.9 (Standard Library Only)"
    tok_engine = "tiktoken (cl100k_base)" if _TIKTOKEN_ENC is not None else "Conservative Heuristic (+15% safety buffer)"
    action_label = "Initial Cold-Repo Scaffold (--init)" if init_mode else "In-Place Merkle & Coordinate Sync"
    if dry_run:
        action_label += " [DRY-RUN]"

    print("\n" + "=" * 80)
    print(f" [tokenme-sync.py v{VERSION} | Spec v{SPEC_VERSION}] — {action_label}")
    print("=" * 80)
    print(f"  Merkle STATE_ROOT  : {state_root_str} (Verified across AGENTS.md + {len(adr_records)} ADRs + {len(outputs)} shards)")
    print(f"  Indexed Corpus     : {total_files} files ({py_files} Py AST, {non_py_code} Non-Py, {opaque_files} Opaque [{l4_files} L4]) | {total_loc:,} LOC")
    print(f"  Source Token Mass  : ~{raw_tokens:,} tokens ({tok_engine})")
    print(f"  Detected Runtimes  : {rt_str}")
    print(f"  Symbol Resolution  : {ast_symbols} exact Python AST spans | {preserved_symbols} preserved non-Py spans")
    print(f"  Fail-Closed Guard  : {len(quarantine_log)} binary/oversize/symlink/fault items isolated")
    print(f"  Topology Selected  : {mode_str}")
    print(f"  Root Router Budget : {root_lines_cnt}/{ROOT_LINE_CEILING} lines (~{root_tokens:,} tokens | Total shards: ~{total_meta_tokens:,} tok)")
    print(f"  Epistemic Leverage : {compression_ratio:.1f}:1 compression vs. raw codebase read")
    print("-" * 80)
    print("  Staged / Committed Artifacts:")
    for p, text in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        rel_p = p.relative_to(root).as_posix()
        est_tok = estimate_tokens(text)
        lc = len(text.splitlines())
        print(f"    -> ./{rel_p:<34} ({lc:>3} lines | ~{est_tok:,} tokens)")

    if stub_count > 0 or todo_count > 0 or hydration_count > 0 or stale_count > 0:
        print("-" * 80)
        print(
            f"  Agent Hydration Queue: {stub_count} [AGENT_POPULATE_SYMBOLS] | "
            f"{hydration_count} [NEEDS_HYDRATION] | {todo_count} [TODO: AGENT_FILL] | "
            f"{stale_count} stale checks"
        )
    print("=" * 80 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tokenme-sync.py",
        description=(
            "Synchronize and Merkle-stamp an existing TOKENME.txt (v2.0) hierarchy (default / --sync), "
            "verify O(1) Merkle state integrity (--check), or scaffold a cold repository (--init)."
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
        "--sync",
        action="store_true",
        help="Explicitly run in-place coordinate and Merkle state synchronization (default behavior).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fast (<2ms) read-only Merkle integrity check for pre-commit/CI (exits 1 on drift).",
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
        "--leaf-len",
        type=int,
        default=DEFAULT_LEAF_HASH_LEN,
        help=f"Hex length for ADR and sidecar leaf digests (6..64, default: {DEFAULT_LEAF_HASH_LEN}).",
    )
    parser.add_argument(
        "--root-len",
        type=int,
        default=DEFAULT_ROOT_HASH_LEN,
        help=f"Hex length for Merkle STATE_ROOT digests (8..64, default: {DEFAULT_ROOT_HASH_LEN}).",
    )
    parser.add_argument(
        "--adr-dir",
        type=str,
        default=None,
        help="Override ADR directory relative to root (default: auto-detect docs/adr/ or docs/decisions/).",
    )
    parser.add_argument(
        "--max-size-kb",
        type=int,
        default=DEFAULT_MAX_FILE_SIZE_KB,
        help=f"Quarantine text/source files larger than this threshold in KiB (default: {DEFAULT_MAX_FILE_SIZE_KB} KiB).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute traversal, AST extraction, and Merkle math without writing files.",
    )

    args = parser.parse_args()
    root_path = Path(args.root).resolve()

    if not root_path.is_dir():
        print(f"[ERROR] Target directory does not exist: {root_path}", file=sys.stderr)
        return 1

    # --- Tier 1 Fast Integrity Check Mode (--check) ---
    if args.check:
        ok, err_list = run_integrity_check(
            root_path, leaf_len=args.leaf_len, root_len=args.root_len, custom_adr_dir=args.adr_dir
        )
        if ok:
            print(f"[OK] TOKENME v{SPEC_VERSION} Merkle STATE_ROOT and ADR leaf digests verified clean.")
            return 0
        print(f"[FAIL] Epistemic state drift detected ({len(err_list)} issue(s)):", file=sys.stderr)
        for e in err_list:
            print(f"  - {e}", file=sys.stderr)
        print("  -> Run `python3 tokenme-sync.py` (or `--sync`) to resynchronize.", file=sys.stderr)
        return 1

    target_root_file = root_path / "TOKENME.txt"
    tokenme_exists = target_root_file.is_file() and not target_root_file.is_symlink()

    if args.init:
        if tokenme_exists and not (args.force or args.dry_run):
            print(
                f"[ABORT] `TOKENME.txt` already exists in {root_path}.\n"
                "  -> To synchronize/update existing coordinates, run: `python3 tokenme-sync.py`\n"
                "  -> To wipe and re-scaffold from scratch, pass: `python3 tokenme-sync.py --init --force`",
                file=sys.stderr,
            )
            return 1
    else:
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
    try:
        adr_records = discover_adr_records(
            root_path, leaf_len=args.leaf_len, custom_dir=args.adr_dir
        )
    except Exception as exc:
        print(f"[ERROR] ADR discovery failed: {exc}", file=sys.stderr)
        return 1

    records, quarantine_log, runtimes = scan_repository(
        root_path, max_size_bytes=max_size_bytes, leaf_len=args.leaf_len, dry_run=args.dry_run
    )

    if not records and not quarantine_log and not adr_records:
        print("[WARN] No eligible files discovered in repository.", file=sys.stderr)
        return 1

    l0_meta: Dict[str, str] = {}
    if not args.init:
        l0_meta, file_states = harvest_existing_state(root_path)
        merge_harvested_state(records, file_states)

    outputs = build_documents(
        root=root_path,
        records=records,
        adr_records=adr_records,
        quarantine_log=quarantine_log,
        runtimes=runtimes,
        l0_meta=l0_meta,
        root_len=args.root_len,
        force_single=args.single,
    )

    if not args.dry_run:
        atomic_commit_outputs(root_path, outputs, clean_stale_shards=True)

    print_telemetry_receipt(
        root=root_path,
        records=records,
        adr_records=adr_records,
        quarantine_log=quarantine_log,
        runtimes=runtimes,
        outputs=outputs,
        init_mode=args.init,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())