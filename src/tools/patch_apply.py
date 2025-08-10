from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Tuple
import unicodedata


class DiffError(Exception):
    pass


# Patch format markers (V4A-style)
PATCH_PREFIX = "*** Begin Patch"
PATCH_SUFFIX = "*** End Patch"
ADD_FILE_PREFIX = "*** Add File: "
DELETE_FILE_PREFIX = "*** Delete File: "
UPDATE_FILE_PREFIX = "*** Update File: "
END_OF_FILE_PREFIX = "*** End of File"
HUNK_ADD_LINE_PREFIX = "+"


@dataclass
class Chunk:
    orig_index: int
    del_lines: List[str]
    ins_lines: List[str]


@dataclass
class PatchAction:
    type: str  # "add" | "delete" | "update"
    new_file: str | None = None
    chunks: List[Chunk] = field(default_factory=list)


@dataclass
class Patch:
    actions: Dict[str, PatchAction] = field(default_factory=dict)


def _is_done(lines: List[str], index: int, prefixes: List[str] | None = None) -> bool:
    if index >= len(lines):
        return True
    if prefixes and any(lines[index].startswith(p.strip()) for p in prefixes):
        return True
    return False


def _startswith(lines: List[str], index: int, prefix: str | List[str]) -> bool:
    prefixes = [prefix] if isinstance(prefix, str) else prefix
    return any(lines[index].startswith(p) for p in prefixes)


def _read_str(lines: List[str], index: int, prefix: str = "", return_everything: bool = False) -> Tuple[str, int]:
    if index >= len(lines):
        raise DiffError(f"Index: {index} >= {len(lines)}")
    if lines[index].startswith(prefix):
        text = lines[index] if return_everything else lines[index][len(prefix) :]
        return (text or ""), index + 1
    return "", index


def _canon_punct(s: str) -> str:
    punct_equiv = {
        "-": "-",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u0022": '"',
        "\u201C": '"',
        "\u201D": '"',
        "\u201E": '"',
        "\u00AB": '"',
        "\u00BB": '"',
        "\u0027": "'",
        "\u2018": "'",
        "\u2019": "'",
        "\u201B": "'",
        "\u00A0": " ",
        "\u202F": " ",
    }
    # Normalize Unicode punctuation, quotes, spaces, ellipsis, zero-width and superscripts
    out = unicodedata.normalize("NFC", s)
    for src, dst in punct_equiv.items():
        out = out.replace(src, dst)
    # Ellipsis
    out = out.replace("\u2026", "...")
    # Zero-width and BOM
    out = out.replace("\u200B", "").replace("\ufeff", "")
    # Superscript digits → ASCII digits (captures O(n²) cases)
    supers_map = {
        "\u00B9": "1", "\u00B2": "2", "\u00B3": "3",
        "\u2070": "0", "\u2074": "4", "\u2075": "5", "\u2076": "6",
        "\u2077": "7", "\u2078": "8", "\u2079": "9",
    }
    for src, dst in supers_map.items():
        out = out.replace(src, dst)
    return out


def _find_context_core(lines: List[str], context: List[str], start: int) -> Tuple[int, int]:
    if len(context) == 0:
        return start, 0
    def canon(s: str) -> str:
        return _canon_punct(s)

    canonical_context = canon("\n".join(context))
    # Pass 1: exact after canonicalization
    for i in range(start, len(lines)):
        segment = canon("\n".join(lines[i : i + len(context)]))
        if segment == canonical_context:
            return i, 0
    # Pass 2: ignore trailing whitespace
    for i in range(start, len(lines)):
        segment = canon("\n".join([s.rstrip() for s in lines[i : i + len(context)]]))
        ctx = canon("\n".join([s.rstrip() for s in context]))
        if segment == ctx:
            return i, 1
    # Pass 3: ignore surrounding whitespace
    for i in range(start, len(lines)):
        segment = canon("\n".join([s.strip() for s in lines[i : i + len(context)]]))
        ctx = canon("\n".join([s.strip() for s in context]))
        if segment == ctx:
            return i, 100
    # Pass 4: anchor by first and last context lines (fuzzy window match)
    if len(context) >= 2:
        first_c = canon(context[0])
        last_c = canon(context[-1])
        for i in range(max(start, 0), len(lines) - len(context) + 1):
            if canon(lines[i]) == first_c and canon(lines[i + len(context) - 1]) == last_c:
                return i, 200
    return -1, 0


def _find_context(lines: List[str], context: List[str], start: int, eof: bool) -> Tuple[int, int]:
    if eof:
        new_index, fuzz = _find_context_core(lines, context, max(0, len(lines) - len(context)))
        if new_index != -1:
            return new_index, fuzz
        new_index, fuzz = _find_context_core(lines, context, start)
        return new_index, fuzz + 10000
    return _find_context_core(lines, context, start)


def _peek_next_section(lines: List[str], initial_index: int) -> Tuple[List[str], List[Chunk], int, bool]:
    index = initial_index
    old: List[str] = []
    del_lines: List[str] = []
    ins_lines: List[str] = []
    chunks: List[Chunk] = []
    mode: str = "keep"  # keep | add | delete

    while index < len(lines):
        s = lines[index]
        if any(
            s.startswith(p.strip())
            for p in [
                "@@",
                PATCH_SUFFIX,
                UPDATE_FILE_PREFIX,
                DELETE_FILE_PREFIX,
                ADD_FILE_PREFIX,
                END_OF_FILE_PREFIX,
            ]
        ):
            break
        if s == "***":
            break
        if s.startswith("***"):
            raise DiffError(f"Invalid Line: {s}")
        index += 1
        last_mode = mode
        line = s
        if line[:1] == HUNK_ADD_LINE_PREFIX:
            mode = "add"
        elif line[:1] == "-":
            mode = "delete"
        elif line[:1] == " ":
            mode = "keep"
        else:
            # tolerate missing space for context line
            mode = "keep"
            line = " " + line

        line = line[1:]
        if mode == "keep" and last_mode != mode:
            if ins_lines or del_lines:
                chunks.append(Chunk(orig_index=len(old) - len(del_lines), del_lines=del_lines, ins_lines=ins_lines))
            del_lines = []
            ins_lines = []
        if mode == "delete":
            del_lines.append(line)
            old.append(line)
        elif mode == "add":
            ins_lines.append(line)
        else:
            old.append(line)
    if ins_lines or del_lines:
        chunks.append(Chunk(orig_index=len(old) - len(del_lines), del_lines=del_lines, ins_lines=ins_lines))
    if index < len(lines) and lines[index] == END_OF_FILE_PREFIX:
        index += 1
        return old, chunks, index, True
    return old, chunks, index, False


class Parser:
    def __init__(self, current_files: Dict[str, str], lines: List[str]):
        self.current_files = current_files
        self.lines = lines
        self.index = 0
        self.patch = Patch(actions={})
        self.fuzz = 0

    def parse(self) -> None:
        while not _is_done(self.lines, self.index, [PATCH_SUFFIX]):
            path, self.index = _read_str(self.lines, self.index, UPDATE_FILE_PREFIX)
            if path:
                if path in self.patch.actions:
                    raise DiffError(f"Update File Error: Duplicate Path: {path}")
                if path not in self.current_files:
                    raise DiffError(f"Update File Error: Missing File: {path}")
                text = self.current_files.get(path) or ""
                action = self._parse_update_file(text)
                self.patch.actions[path] = action
                continue
            path, self.index = _read_str(self.lines, self.index, DELETE_FILE_PREFIX)
            if path:
                if path in self.patch.actions:
                    raise DiffError(f"Delete File Error: Duplicate Path: {path}")
                if path not in self.current_files:
                    raise DiffError(f"Delete File Error: Missing File: {path}")
                self.patch.actions[path] = PatchAction(type="delete", chunks=[])
                continue
            path, self.index = _read_str(self.lines, self.index, ADD_FILE_PREFIX)
            if path:
                if path in self.patch.actions:
                    raise DiffError(f"Add File Error: Duplicate Path: {path}")
                if path in self.current_files:
                    raise DiffError(f"Add File Error: File already exists: {path}")
                self.patch.actions[path] = self._parse_add_file()
                continue
            raise DiffError(f"Unknown Line: {self.lines[self.index]}")
        if not _startswith(self.lines, self.index, PATCH_SUFFIX.strip()):
            raise DiffError("Missing End Patch")
        self.index += 1

    def _parse_update_file(self, text: str) -> PatchAction:
        action = PatchAction(type="update", chunks=[])
        file_lines = text.split("\n")
        index_in_file = 0
        while not _is_done(
            self.lines,
            self.index,
            [PATCH_SUFFIX, UPDATE_FILE_PREFIX, DELETE_FILE_PREFIX, ADD_FILE_PREFIX, END_OF_FILE_PREFIX],
        ):
            def_str, self.index = _read_str(self.lines, self.index, "@@ ")
            section_str = ""
            if not def_str and self.index < len(self.lines) and self.lines[self.index] == "@@":
                section_str = self.lines[self.index]
                self.index += 1
            if not (def_str or section_str or index_in_file == 0):
                raise DiffError(f"Invalid Line:\n{self.lines[self.index]}")

            # Attempt to align to the provided definition string (anchor)
            if def_str.strip():
                def canon_local(s: str) -> str:
                    return _canon_punct(s)
                found = False
                if not any(canon_local(s) == canon_local(def_str) for s in file_lines[: index_in_file]):
                    for i in range(index_in_file, len(file_lines)):
                        if canon_local(file_lines[i]) == canon_local(def_str):
                            index_in_file = i + 1
                            found = True
                            break
                if (not found) and (not any(canon_local(s.strip()) == canon_local(def_str.strip()) for s in file_lines[: index_in_file])):
                    for i in range(index_in_file, len(file_lines)):
                        if canon_local(file_lines[i].strip()) == canon_local(def_str.strip()):
                            index_in_file = i + 1
                            self.fuzz += 1
                            found = True
                            break

            next_ctx, chunks, end_patch_index, eof = _peek_next_section(self.lines, self.index)
            new_index, fuzz = _find_context(file_lines, next_ctx, index_in_file, eof)
            if new_index == -1:
                ctx_text = "\n".join(next_ctx)
                if eof:
                    raise DiffError(f"Invalid EOF Context {index_in_file}:\n{ctx_text}")
                raise DiffError(f"Invalid Context {index_in_file}:\n{ctx_text}")
            self.fuzz += fuzz
            for ch in chunks:
                ch.orig_index += new_index
                action.chunks.append(ch)
            index_in_file = new_index + len(next_ctx)
            self.index = end_patch_index
        return action

    def _parse_add_file(self) -> PatchAction:
        lines: List[str] = []
        while not _is_done(self.lines, self.index, [PATCH_SUFFIX, UPDATE_FILE_PREFIX, DELETE_FILE_PREFIX, ADD_FILE_PREFIX]):
            s, self.index = _read_str(self.lines, self.index)
            if not s.startswith(HUNK_ADD_LINE_PREFIX):
                raise DiffError(f"Invalid Add File Line: {s}")
            lines.append(s[1:])
        return PatchAction(type="add", new_file="\n".join(lines), chunks=[])


def _get_updated_file(text: str, action: PatchAction, path: str) -> str:
    if action.type != "update":
        raise DiffError("Expected UPDATE action")
    orig_lines = text.split("\n")
    dest_lines: List[str] = []
    orig_index = 0
    for chunk in action.chunks:
        if chunk.orig_index > len(orig_lines):
            raise DiffError(f"{path}: chunk.orig_index {chunk.orig_index} > len(lines) {len(orig_lines)}")
        if orig_index > chunk.orig_index:
            raise DiffError(f"{path}: orig_index {orig_index} > chunk.orig_index {chunk.orig_index}")
        dest_lines.extend(orig_lines[orig_index:chunk.orig_index])
        delta = chunk.orig_index - orig_index
        orig_index += delta
        # insertions
        if chunk.ins_lines:
            dest_lines.extend(chunk.ins_lines)
        # skip deletions
        orig_index += len(chunk.del_lines)
    dest_lines.extend(orig_lines[orig_index:])
    return "\n".join(dest_lines)


def text_to_patch(text: str, orig: Dict[str, str]) -> Tuple[Patch, int]:
    lines = text.strip().split("\n")
    if len(lines) < 2 or not (lines[0] or "").startswith(PATCH_PREFIX.strip()) or lines[-1] != PATCH_SUFFIX.strip():
        reason = "Invalid patch text: "
        if len(lines) < 2:
            reason += "Patch text must have at least two lines."
        elif not (lines[0] or "").startswith(PATCH_PREFIX.strip()):
            reason += "Patch text must start with the correct patch prefix."
        elif lines[-1] != PATCH_SUFFIX.strip():
            reason += "Patch text must end with the correct patch suffix."
        raise DiffError(reason)
    parser = Parser(orig, lines)
    parser.index = 1
    parser.parse()
    return parser.patch, parser.fuzz


def identify_files_needed(text: str) -> List[str]:
    lines = text.strip().split("\n")
    result: set[str] = set()
    for line in lines:
        if line.startswith(UPDATE_FILE_PREFIX):
            result.add(line[len(UPDATE_FILE_PREFIX) :])
        if line.startswith(DELETE_FILE_PREFIX):
            result.add(line[len(DELETE_FILE_PREFIX) :])
    return list(result)


def identify_files_added(text: str) -> List[str]:
    lines = text.strip().split("\n")
    result: set[str] = set()
    for line in lines:
        if line.startswith(ADD_FILE_PREFIX):
            result.add(line[len(ADD_FILE_PREFIX) :])
    return list(result)


def patch_to_commit(patch: Patch, orig: Dict[str, str]) -> Dict[str, Dict[str, str | None]]:
    commit: Dict[str, Dict[str, str | None]] = {"changes": {}}  # shape mirrors TS, but not exported
    for path_key, action in patch.actions.items():
        if action.type == "delete":
            commit["changes"][path_key] = {"type": "delete", "old_content": orig.get(path_key)}
        elif action.type == "add":
            commit["changes"][path_key] = {"type": "add", "new_content": action.new_file or ""}
        elif action.type == "update":
            new_content = _get_updated_file(orig[path_key], action, path_key)
            commit["changes"][path_key] = {
                "type": "update",
                "old_content": orig.get(path_key),
                "new_content": new_content,
            }
    return commit


def apply_commit(commit: Dict[str, Dict[str, str | None]], write_fn: Callable[[str, str], None], remove_fn: Callable[[str], None]) -> None:
    for p, change in commit.get("changes", {}).items():
        ctype = change.get("type")
        if ctype == "delete":
            remove_fn(p)
        elif ctype == "add":
            write_fn(p, change.get("new_content") or "")
        elif ctype == "update":
            write_fn(p, change.get("new_content") or "")


def process_patch(text: str, open_fn: Callable[[str], str], write_fn: Callable[[str, str], None], remove_fn: Callable[[str], None]) -> str:
    if not text.startswith(PATCH_PREFIX):
        raise DiffError("Patch must start with *** Begin Patch\n")
    paths = identify_files_needed(text)
    orig: Dict[str, str] = {}
    for p in paths:
        try:
            orig[p] = open_fn(p)
        except Exception as e:
            raise DiffError(f"File not found: {p}") from e
    patch, _fuzz = text_to_patch(text, orig)
    commit = patch_to_commit(patch, orig)
    apply_commit(commit, write_fn, remove_fn)
    return "Done!"


def process_patch_in_repo(repo_dir: Path, patch_text: str) -> str:
    repo_dir = Path(repo_dir)

    def _assert_rel(p: str) -> Path:
        if Path(p).is_absolute():
            raise DiffError("We do not support absolute paths.")
        abs_p = (repo_dir / p).resolve()
        repo_dir_resolved = repo_dir.resolve()
        if repo_dir_resolved not in abs_p.parents and abs_p != repo_dir_resolved:
            raise DiffError("Path escapes repository root.")
        return abs_p

    def _open(p: str) -> str:
        ap = _assert_rel(p)
        return ap.read_text(encoding="utf-8")

    def _write(p: str, c: str) -> None:
        ap = _assert_rel(p)
        ap.parent.mkdir(parents=True, exist_ok=True)
        ap.write_text(c, encoding="utf-8")

    def _remove(p: str) -> None:
        ap = _assert_rel(p)
        ap.unlink(missing_ok=False)

    return process_patch(patch_text, _open, _write, _remove)


