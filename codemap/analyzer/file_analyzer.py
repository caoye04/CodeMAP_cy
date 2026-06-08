"""
analyzer/file_analyzer.py
CodeMAP File 层分析器

实现：
  - analyze_file_language : 根据文件扩展名确定编程语言，批量写入 file.language
  - analyze_file_func     : 提取文件中所有函数/方法，写入 func 表并更新 file.funclist

函数提取策略（按优先级）：
  Python       → Python ast 模块（精确，覆盖嵌套函数/方法）
  C/C++/其他   → Universal Ctags（若可用）+ 源码签名解析补充 io
  兜底          → LLM 全文提取（文件 ≤ _MAX_LINES_LLM 行时）
"""

import ast
import json as _json
import os
import re
import subprocess
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, FileDB, FuncDB
from config import DB_PATH, DATA_DIR


# ══════════════════════════════════════════════════════════════════
#  常量与映射表
# ══════════════════════════════════════════════════════════════════

_EXT_TO_LANG: dict[str, str] = {
    # C / C++
    '.c': 'C', '.h': 'C',
    '.cpp': 'C++', '.cxx': 'C++', '.cc': 'C++',
    '.hpp': 'C++', '.hxx': 'C++',
    # Python
    '.py': 'Python',
    # Java
    '.java': 'Java',
    # JavaScript / TypeScript
    '.js': 'JavaScript', '.jsx': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript',
    # Go
    '.go': 'Go',
    # Rust
    '.rs': 'Rust',
    # Shell
    '.sh': 'Shell', '.bash': 'Shell', '.zsh': 'Shell',
    # CMake
    '.cmake': 'CMake',
    # Ruby
    '.rb': 'Ruby',
    # Swift
    '.swift': 'Swift',
    # Kotlin
    '.kt': 'Kotlin', '.kts': 'Kotlin',
    # Scala
    '.scala': 'Scala',
    # Haskell
    '.hs': 'Haskell',
    # Assembly
    '.asm': 'Assembly', '.s': 'Assembly',
    # Lua
    '.lua': 'Lua',
    # Perl
    '.pl': 'Perl', '.pm': 'Perl',
    # Fortran
    '.f': 'Fortran', '.f90': 'Fortran', '.f95': 'Fortran',
    # MATLAB / Objective-C
    '.m': 'MATLAB', '.mm': 'Objective-C',
    # 配置 / 文档类
    '.md': 'Markdown', '.rst': 'reStructuredText',
    '.yaml': 'YAML', '.yml': 'YAML',
    '.json': 'JSON', '.xml': 'XML',
    '.html': 'HTML', '.htm': 'HTML',
    '.css': 'CSS', '.sql': 'SQL',
    '.toml': 'TOML', '.ini': 'INI', '.cfg': 'INI',
}

# 通常不含函数定义的语言 → 跳过函数提取
_NO_FUNC_LANGS: frozenset[str] = frozenset({
    'Markdown', 'reStructuredText', 'YAML', 'JSON', 'XML',
    'HTML', 'CSS', 'SQL', 'TOML', 'INI',
    'CMake', 'Makefile', 'Assembly', 'Unknown',
})

# ctags 语言名映射（Universal Ctags --languages 参数）
_CTAGS_LANG_MAP: dict[str, str] = {
    'C': 'C', 'C++': 'C++', 'Objective-C': 'ObjectiveC',
    'Python': 'Python', 'Java': 'Java',
    'JavaScript': 'JavaScript', 'TypeScript': 'TypeScript',
    'Go': 'Go', 'Rust': 'Rust', 'Ruby': 'Ruby',
    'Swift': 'Swift', 'Kotlin': 'Kotlin',
    'Scala': 'Scala', 'Lua': 'Lua', 'Shell': 'Sh',
}

# ctags kind 字符集合 → 视为"函数"
_FUNC_KINDS: frozenset[str] = frozenset({
    'f', 'function',
    'm', 'method',
    'p', 'prototype',
    's', 'subroutine',
    'procedure',
})

_MAX_LINES_LLM   = 3000       # 超过此行数时截断发给 LLM
_MAX_BYTES_READ  = 1_000_000  # 单文件最大读取字节（1 MB）

# ctags 可用性缓存（None = 未检测）
_ctags_ok: bool | None = None


# ══════════════════════════════════════════════════════════════════
#  语言检测
# ══════════════════════════════════════════════════════════════════

def _detect_language(file_name: str) -> str:
    """根据文件名/扩展名推断编程语言，无法识别返回 'Unknown'。"""
    _, ext = os.path.splitext(file_name)
    lang = _EXT_TO_LANG.get(ext.lower())
    if lang is None:
        lower = file_name.lower()
        if lower in ('makefile', 'gnumakefile'):
            lang = 'Makefile'
        elif file_name == 'CMakeLists.txt':
            lang = 'CMake'
    return lang or 'Unknown'


# ══════════════════════════════════════════════════════════════════
#  analyze_file_language
# ══════════════════════════════════════════════════════════════════

def analyze_file_language(
    repo_id: int,
    db_path: str | None = None,
    file_id: int | None = None,
) -> dict[int, str]:
    """
    根据文件扩展名确定编程语言并持久化到 file.language。

    Parameters
    ----------
    repo_id : int
        目标仓库 id（由 init_repo 返回）
    db_path : str | None
        SQLite 路径；不传则使用 config.DB_PATH
    file_id : int | None
        若指定，则只处理该文件；否则处理 repo 下所有文件

    Returns
    -------
    dict[int, str]
        {file_id: language} 映射，language 如 "C" / "Python" / "Unknown"

    Raises
    ------
    ValueError
        repo_id 或 file_id 在数据库中不存在
    """
    _db = db_path or DB_PATH

    # ① 校验仓库
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_file_language] repo_id={repo_id} 不存在于数据库。"
        )

    # ② 确定目标文件列表
    if file_id is not None:
        file_rec = FileDB.get_by_id(file_id, db_path=_db)
        if file_rec is None:
            raise ValueError(
                f"[analyze_file_language] file_id={file_id} 不存在于数据库。"
            )
        files = [file_rec]
    else:
        files = FileDB.list_by_repo(repo_id, db_path=_db)

    if not files:
        print(
            f"[analyze_file_language] ⚠ repo_id={repo_id} 暂无文件记录，"
            "请先执行 analyze_area_file。"
        )
        return {}

    # ③ 批量检测并写库
    result: dict[int, str]      = {}
    lang_counter: dict[str, int] = {}

    for f in files:
        lang = _detect_language(f['name'])
        FileDB.update(f['id'], db_path=_db, language=lang)
        result[f['id']] = lang
        lang_counter[lang] = lang_counter.get(lang, 0) + 1

    # ④ 打印摘要
    total = len(files)
    print(f"[analyze_file_language] ✓ 处理 {total} 个文件，语言分布：")
    for lang, cnt in sorted(lang_counter.items(), key=lambda x: -x[1]):
        bar = '█' * min(cnt, 40)
        print(f"    {lang:22s}: {cnt:4d}  {bar}")

    return result


# ══════════════════════════════════════════════════════════════════
#  文件读取工具
# ══════════════════════════════════════════════════════════════════

def _read_file_safe(file_path: str) -> str | None:
    """
    安全读取文本文件。
    - 超过 _MAX_BYTES_READ 返回 None
    - 含大量 NUL 字节（二进制）返回 None
    - 依次尝试 utf-8 / latin-1 编码
    """
    try:
        if os.path.getsize(file_path) > _MAX_BYTES_READ:
            return None
    except OSError:
        return None

    for enc in ('utf-8', 'latin-1'):
        try:
            with open(file_path, 'r', encoding=enc, errors='replace') as fh:
                content = fh.read()
            if content.count('\x00') > 20:   # 粗判二进制文件
                return None
            return content
        except OSError:
            return None
    return None


def _add_line_numbers(content: str) -> tuple[str, int]:
    """
    给内容每行加行号前缀，超过 _MAX_LINES_LLM 时截断并追加提示。

    Returns
    -------
    (numbered_str, total_line_count)
    """
    lines = content.splitlines()
    total = len(lines)
    selected = lines[:_MAX_LINES_LLM]
    numbered = '\n'.join(f"{i + 1:5d} | {line}" for i, line in enumerate(selected))
    if total > _MAX_LINES_LLM:
        numbered += (
            f'\n... (文件共 {total} 行，已截断，仅展示前 {_MAX_LINES_LLM} 行)'
        )
    return numbered, total


# ══════════════════════════════════════════════════════════════════
#  策略 1：Python ast 提取
# ══════════════════════════════════════════════════════════════════

def _ann_str(node) -> str:
    """安全地将 ast 注解节点转为字符串，失败时返回空串。"""
    if node is None:
        return ''
    try:
        return ast.unparse(node)
    except Exception:
        return ''


def _build_py_signature(node: 'ast.FunctionDef | ast.AsyncFunctionDef') -> str:
    """从 ast 函数节点构建完整签名字符串。"""
    ao = node.args
    parts: list[str] = []
    defaults_offset = len(ao.args) - len(ao.defaults)

    for i, arg in enumerate(ao.args):
        ann = f': {_ann_str(arg.annotation)}' if arg.annotation else ''
        di  = i - defaults_offset
        try:
            default = f' = {ast.unparse(ao.defaults[di])}' if di >= 0 else ''
        except Exception:
            default = ''
        parts.append(f"{arg.arg}{ann}{default}")

    if ao.vararg:
        ann = f': {_ann_str(ao.vararg.annotation)}' if ao.vararg.annotation else ''
        parts.append(f"*{ao.vararg.arg}{ann}")
    elif ao.kwonlyargs:
        parts.append('*')

    for i, arg in enumerate(ao.kwonlyargs):
        ann = f': {_ann_str(arg.annotation)}' if arg.annotation else ''
        kd  = ao.kw_defaults[i]
        try:
            default = f' = {ast.unparse(kd)}' if kd is not None else ''
        except Exception:
            default = ''
        parts.append(f"{arg.arg}{ann}{default}")

    if ao.kwarg:
        ann = f': {_ann_str(ao.kwarg.annotation)}' if ao.kwarg.annotation else ''
        parts.append(f"**{ao.kwarg.arg}{ann}")

    ret_ann = f' -> {_ann_str(node.returns)}' if node.returns else ''
    prefix  = 'async def ' if isinstance(node, ast.AsyncFunctionDef) else 'def '
    return f"{prefix}{node.name}({', '.join(parts)}){ret_ann}"


def _build_py_params(node: 'ast.FunctionDef | ast.AsyncFunctionDef') -> list[dict]:
    """从 ast 函数节点提取参数列表。"""
    ao     = node.args
    params: list[dict] = []

    for arg in ao.args:
        params.append({'name': arg.arg, 'type': _ann_str(arg.annotation), 'desc': ''})
    if ao.vararg:
        params.append({
            'name': f'*{ao.vararg.arg}',
            'type': _ann_str(ao.vararg.annotation),
            'desc': '',
        })
    for arg in ao.kwonlyargs:
        params.append({'name': arg.arg, 'type': _ann_str(arg.annotation), 'desc': ''})
    if ao.kwarg:
        params.append({
            'name': f'**{ao.kwarg.arg}',
            'type': _ann_str(ao.kwarg.annotation),
            'desc': '',
        })
    return params


def _extract_funcs_python(file_path: str) -> list[dict]:
    """
    使用 Python 内置 ast 模块提取函数/方法定义（含嵌套）。

    Returns
    -------
    list[dict]  键: name, signature, start_line, end_line, params, returns
    """
    content = _read_file_safe(file_path)
    if content is None:
        return []

    try:
        tree = ast.parse(content, filename=os.path.basename(file_path))
    except SyntaxError as e:
        print(f"[file_analyzer] Python 语法错误，跳过 AST 提取：{e}")
        return []

    functions: list[dict] = []

    class _Visitor(ast.NodeVisitor):
        def _handle(self, node: 'ast.FunctionDef | ast.AsyncFunctionDef') -> None:
            end_line = getattr(node, 'end_lineno', node.lineno)
            functions.append({
                'name':       node.name,
                'signature':  _build_py_signature(node),
                'start_line': node.lineno,
                'end_line':   end_line,
                'params':     _build_py_params(node),
                'returns':    {'type': _ann_str(node.returns), 'desc': ''},
            })
            self.generic_visit(node)   # 继续遍历嵌套函数

        def visit_FunctionDef(self, node):
            self._handle(node)

        def visit_AsyncFunctionDef(self, node):
            self._handle(node)

    _Visitor().visit(tree)
    return functions


# ══════════════════════════════════════════════════════════════════
#  策略 2：Universal Ctags 提取
# ══════════════════════════════════════════════════════════════════

def _check_ctags() -> bool:
    """检测 ctags 是否可用（结果进程生命周期内缓存）。"""
    global _ctags_ok
    if _ctags_ok is not None:
        return _ctags_ok
    try:
        r = subprocess.run(
            ['ctags', '--version'],
            capture_output=True, text=True, timeout=5,
        )
        _ctags_ok = (r.returncode == 0)
        if _ctags_ok:
            flavor = 'Universal Ctags' if 'Universal Ctags' in r.stdout else 'Exuberant/Unknown Ctags'
            print(f"[file_analyzer] ctags 可用（{flavor}）")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _ctags_ok = False
        print('[file_analyzer] ctags 不可用，将使用 LLM 兜底提取函数。')
    return _ctags_ok


def _parse_ctags_output(stdout: str) -> list[dict]:
    """
    解析 Universal Ctags u-ctags 格式输出，提取函数信息。

    字段格式（TAB 分隔）：
      name  filepath  pattern;"  kind  line:N  end:M  [signature:...]
    """
    functions: list[dict] = []
    seen: set[tuple[str, int]] = set()   # (name, start_line) 去重

    for raw_line in stdout.splitlines():
        if raw_line.startswith('!'):
            continue   # ctags 元信息行

        parts = raw_line.split('\t')
        if len(parts) < 4:
            continue

        name = parts[0].strip()
        if not name:
            continue

        # 解析后续字段（parts[3:] 之后为 "key:value" 或单字符 kind）
        fields: dict[str, str] = {}
        kind_raw = ''

        for part in parts[3:]:
            part = part.strip()
            if ':' in part:
                k, _, v = part.partition(':')
                k = k.strip()
                if k == 'kind':
                    kind_raw = v.strip()
                else:
                    fields[k] = v.strip()
            elif len(part) == 1 and part.isalpha() and not kind_raw:
                kind_raw = part

        # 过滤非函数类型
        if kind_raw.lower() not in _FUNC_KINDS:
            continue

        # 解析行号
        try:
            start_line = int(fields.get('line', 0))
        except (ValueError, TypeError):
            continue
        if start_line == 0:
            continue

        try:
            end_line = int(fields.get('end', start_line))
        except (ValueError, TypeError):
            end_line = start_line

        # 去重
        key = (name, start_line)
        if key in seen:
            continue
        seen.add(key)

        # ctags 的 signature 字段（不含返回类型，仅参数括号部分）
        ctags_sig = fields.get('signature', fields.get('S', ''))

        functions.append({
            'name':       name,
            'signature':  f"{name}{ctags_sig}".strip() if ctags_sig else name,
            'start_line': start_line,
            'end_line':   end_line,
            'params':     [],                           # 由 _enrich_ctags_io 补全
            'returns':    {'type': '', 'desc': ''},     # 由 _enrich_ctags_io 补全
        })

    return functions


def _extract_funcs_ctags(file_path: str, language: str) -> list[dict] | None:
    """
    用 Universal Ctags 提取函数列表。

    Returns
    -------
    list[dict]  成功时（可能为空列表）
    None        ctags 不可用或调用失败
    """
    if not _check_ctags():
        return None

    ctags_lang = _CTAGS_LANG_MAP.get(language)
    cmd: list[str] = [
        'ctags',
        '--fields=+neS',           # n=行号, e=结束行, S=签名（Universal Ctags）
        '--extras=-F',             # 排除文件级标签
        '--output-format=u-ctags', # Universal Ctags 格式（有明确 key:value 字段）
        '-f', '-',                 # 输出到 stdout
        file_path,
    ]
    if ctags_lang:
        cmd.insert(1, f'--languages={ctags_lang}')

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        print(f"[file_analyzer] ctags 超时：{os.path.basename(file_path)}")
        return None
    except Exception as e:
        print(f"[file_analyzer] ctags 执行异常：{e}")
        return None

    if result.returncode != 0:
        # --output-format=u-ctags 可能在 Exuberant Ctags 下失败
        return None

    return _parse_ctags_output(result.stdout)


# ══════════════════════════════════════════════════════════════════
#  C/C++ 签名解析 —— 为 ctags 结果补充 io 信息
# ══════════════════════════════════════════════════════════════════

# C/C++ 修饰符关键词，不属于返回类型本身
_C_QUALIFIERS: frozenset[str] = frozenset({
    'static', 'extern', 'inline', 'virtual', 'explicit',
    'constexpr', 'consteval', 'constinit', 'friend', 'override', 'final',
    '__inline__', '__forceinline', '__cdecl', '__stdcall',
    # 常见宏修饰（minizip-ng 风格）
    'ZEXPORT', 'ZEXPORTVA', 'MZ_EXPORT', 'MZ_EXTERN',
})


def _split_c_params(params_str: str) -> list[str]:
    """
    按逗号分割 C/C++ 参数字符串，正确处理括号/模板/函数指针嵌套。
    """
    result: list[str] = []
    depth   = 0
    current: list[str] = []
    for ch in params_str:
        if ch in '(<[{':
            depth += 1
            current.append(ch)
        elif ch in ')>]}':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            result.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        result.append(''.join(current).strip())
    return [p for p in result if p]


def _parse_c_io(signature: str) -> dict:
    """
    从 C/C++ 函数签名字符串解析参数列表和返回类型。

    示例输入：
      "int deflate_init(z_streamp strm, int level)"
      "static MZ_EXPORT void * mz_alloc(void *opaque, size_t items, size_t size)"

    Returns
    -------
    dict  {"params": [...], "returns": {"type": str, "desc": ""}}
    """
    io: dict = {'params': [], 'returns': {'type': '', 'desc': ''}}
    sig = signature.strip()

    # ── 找第一个 ( ──────────────────────────────────────────────────
    paren_open = sig.find('(')
    if paren_open == -1:
        return io

    before_paren = sig[:paren_open].strip()

    # ── 找对应的 ) ──────────────────────────────────────────────────
    depth = 1
    idx = paren_open + 1
    while idx < len(sig) and depth > 0:
        if sig[idx] == '(':
            depth += 1
        elif sig[idx] == ')':
            depth -= 1
        idx += 1
    params_str = sig[paren_open + 1: idx - 1].strip()

    # ── 提取返回类型 ─────────────────────────────────────────────────
    # before_paren 末尾的标识符是函数名，之前是返回类型（含修饰符）
    name_match = re.search(r'(\b\w+)\s*$', before_paren)
    if name_match:
        ret_raw = before_paren[: name_match.start()].strip()
    else:
        ret_raw = ''

    # 去掉存储类修饰符
    ret_parts = [t for t in ret_raw.split() if t not in _C_QUALIFIERS]
    io['returns']['type'] = ' '.join(ret_parts)

    # ── 参数解析 ─────────────────────────────────────────────────────
    if not params_str or params_str in ('void', ''):
        return io

    for param in _split_c_params(params_str):
        param = param.strip()
        if not param:
            continue
        if param == '...':
            io['params'].append({'name': '...', 'type': '...', 'desc': ''})
            continue

        # 处理数组形式：int arr[]  →  name=arr, type=int []
        arr_match = re.search(r'(\w+)\s*(\[\d*\])\s*$', param)
        if arr_match:
            pname = arr_match.group(1)
            ptype = (param[: arr_match.start()].strip()
                     + ' ' + arr_match.group(2)).strip()
        else:
            # 函数指针形式：void (*callback)(int) → 特殊处理
            fp_match = re.search(r'\(\s*\*\s*(\w+)\s*\)', param)
            if fp_match:
                pname = fp_match.group(1)
                ptype = param.replace(fp_match.group(0), '(*)', 1).strip()
            else:
                # 普通形式：最后一个标识符为参数名
                tokens = re.findall(r'\w+', param)
                if not tokens:
                    continue
                pname = tokens[-1]
                # 去掉末尾参数名（保留指针 * & 等符号）
                last_pos = param.rfind(pname)
                ptype = param[:last_pos].rstrip('*& \t')
                if not ptype:
                    ptype = pname
                    pname = ''

        io['params'].append({
            'name': pname,
            'type': ptype.strip(),
            'desc': '',
        })

    return io


def _enrich_ctags_io(
    funcs: list[dict],
    file_path: str,
    repo_rel_path: str,
) -> list[dict]:
    """
    读取源文件，为 ctags 提取的函数补充完整签名及 io 信息。

    做法：从 start_line 向后最多扫描 40 行，收集到第一个 '{' 或 ';' 止，
    拼成完整函数声明行，再用 _parse_c_io 解析。

    适用语言：C / C++ / Objective-C
    """
    content = _read_file_safe(file_path)
    if content is None:
        return funcs

    lines       = content.splitlines()
    total_lines = len(lines)

    for func in funcs:
        start = func['start_line']
        if start < 1 or start > total_lines:
            continue

        # 向后收集行，直到遇到 '{' 或 ';'
        collected: list[str] = []
        for li in range(start - 1, min(start + 40, total_lines)):
            row = lines[li].rstrip()
            # 去掉行注释
            row_no_comment = re.sub(r'//.*$', '', row)
            collected.append(row_no_comment)
            if '{' in row_no_comment or ';' in row_no_comment:
                break

        sig_raw = ' '.join(collected)
        # 去掉 '{' 及其后内容
        sig_raw = re.sub(r'\s*\{.*', '', sig_raw, flags=re.DOTALL).strip()
        # 去掉行尾 ';'
        sig_raw = sig_raw.rstrip(';').strip()
        # 压缩多余空白
        sig_raw = re.sub(r'\s+', ' ', sig_raw)

        if sig_raw:
            func['signature'] = sig_raw
            io = _parse_c_io(sig_raw)
            func['params']  = io['params']
            func['returns'] = io['returns']

    return funcs


# ══════════════════════════════════════════════════════════════════
#  策略 3：LLM 提取（通用兜底）
# ══════════════════════════════════════════════════════════════════

def _extract_funcs_llm(
    file_path: str,
    file_name: str,
    language: str,
    repo_rel_path: str,
) -> list[dict]:
    """
    调用 LLM 提取函数列表，适用于任意语言。
    文件超过 _MAX_LINES_LLM 行时截断（末尾部分函数可能丢失）。

    Returns
    -------
    list[dict]  提取成功则返回函数列表；失败返回 []
    """
    from llm.client  import chat_completion_json
    from llm.prompts import ANALYZE_FILE_FUNC_SYSTEM, ANALYZE_FILE_FUNC_USER
    import config as _cfg

    content = _read_file_safe(file_path)
    if content is None:
        print(f"[file_analyzer] 文件过大或无法读取，跳过 LLM 提取：{file_name}")
        return []

    numbered, total_lines = _add_line_numbers(content)
    if total_lines > _MAX_LINES_LLM:
        print(
            f"[file_analyzer] {file_name} 共 {total_lines} 行，"
            f"超限（{_MAX_LINES_LLM}），LLM 仅处理前 {_MAX_LINES_LLM} 行。"
        )

    # lang_lower 用于 Markdown 代码块高亮标注（去掉特殊字符）
    lang_lower = language.lower().replace('+', 'p').replace('#', 'sharp')

    user_msg = ANALYZE_FILE_FUNC_USER.format(
        file_name        = file_name,
        language         = language,
        file_path        = repo_rel_path,
        lang_lower       = lang_lower,
        numbered_content = numbered,
    )

    messages = [
        {'role': 'system', 'content': ANALYZE_FILE_FUNC_SYSTEM},
        {'role': 'user',   'content': user_msg},
    ]

    print(
        f"[file_analyzer] 调用 LLM 提取函数（{file_name}，"
        f"模型 {_cfg.LLM_MODEL}）…"
    )
    try:
        data = chat_completion_json(
            messages=messages, temperature=0.1, max_tokens=8192
        )
    except Exception as e:
        print(f"[file_analyzer] LLM 调用失败（{file_name}）：{e}")
        return []

    # 解析 LLM 输出
    if isinstance(data, dict) and 'functions' in data:
        raw_funcs = data['functions']
    elif isinstance(data, list):
        raw_funcs = data
    else:
        print(f"[file_analyzer] LLM 输出结构异常（{file_name}）：{type(data)}")
        return []

    functions: list[dict] = []
    for item in raw_funcs:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name', '')).strip()
        if not name:
            continue

        try:
            start_line = int(item.get('start_line', 0))
        except (ValueError, TypeError):
            start_line = 0
        try:
            end_line = int(item.get('end_line', start_line))
        except (ValueError, TypeError):
            end_line = start_line

        signature = str(item.get('signature', name)).strip()

        # 规范化 params
        raw_params = item.get('params', [])
        params: list[dict] = []
        if isinstance(raw_params, list):
            for p in raw_params:
                if isinstance(p, dict):
                    params.append({
                        'name': str(p.get('name', '')),
                        'type': str(p.get('type', '')),
                        'desc': str(p.get('desc', '')),
                    })

        # 规范化 returns
        raw_ret = item.get('returns', {})
        if isinstance(raw_ret, dict):
            returns = {
                'type': str(raw_ret.get('type', '')),
                'desc': str(raw_ret.get('desc', '')),
            }
        else:
            returns = {'type': str(raw_ret), 'desc': ''}

        functions.append({
            'name':       name,
            'signature':  signature,
            'start_line': start_line,
            'end_line':   end_line,
            'params':     params,
            'returns':    returns,
        })

    return functions


# ══════════════════════════════════════════════════════════════════
#  主调度：按语言选择最优提取策略
# ══════════════════════════════════════════════════════════════════

def _extract_functions(
    file_path: str,
    file_name: str,
    language: str,
    repo_rel_path: str,
) -> list[dict]:
    """
    函数提取入口，依次尝试：ast → ctags → LLM。

    Returns
    -------
    list[dict]  每项键：name, signature, start_line, end_line, params, returns
    """
    # ── ① 无函数类语言直接跳过 ──────────────────────────────────────
    if language in _NO_FUNC_LANGS:
        return []

    # ── ② Python：使用 ast 模块（精确） ─────────────────────────────
    if language == 'Python':
        funcs = _extract_funcs_python(file_path)
        print(f"[file_analyzer]   策略=ast  → {len(funcs)} 个函数")
        return funcs

    # ── ③ 尝试 ctags ─────────────────────────────────────────────────
    ctags_funcs = _extract_funcs_ctags(file_path, language)

    if ctags_funcs is not None:
        # ctags 可用
        if ctags_funcs:
            # 对 C/C++/Objective-C 补充 io 信息（从源码解析签名）
            if language in ('C', 'C++', 'Objective-C'):
                ctags_funcs = _enrich_ctags_io(ctags_funcs, file_path, repo_rel_path)
            print(f"[file_analyzer]   策略=ctags → {len(ctags_funcs)} 个函数")
            return ctags_funcs
        else:
            # ctags 返回空 → 对于 C/C++ 认为文件确实无函数；其他语言降级 LLM
            if language in ('C', 'C++', 'Objective-C'):
                print(f"[file_analyzer]   策略=ctags → 0 个函数（可信）")
                return []
            # 非 C/C++：ctags 可能不支持该语言格式，降级 LLM
            print(f"[file_analyzer]   ctags 无结果，降级 LLM")

    # ── ④ LLM 兜底 ───────────────────────────────────────────────────
    funcs = _extract_funcs_llm(file_path, file_name, language, repo_rel_path)
    print(f"[file_analyzer]   策略=LLM  → {len(funcs)} 个函数")
    return funcs


# ══════════════════════════════════════════════════════════════════
#  analyze_file_func
# ══════════════════════════════════════════════════════════════════

def analyze_file_func(
    repo_id: int,
    db_path: str | None = None,
    file_id: int | None = None,
    force: bool = False,
) -> dict[int, list[dict]]:
    """
    提取文件中所有函数/方法，写入 func 表并更新 file.funclist。

    流程
    ----
    1. 获取目标文件列表（全部或指定 file_id）
    2. 对每个文件调用 _extract_functions（ast / ctags / LLM 三档策略）
    3. 将提取结果写入 func 表，更新 file.funclist
    4. 支持 force 模式：已有记录时先清除再重建

    写入字段
    --------
    func.name      : 函数名
    func.signature : 完整签名字符串
    func.place     : {"file_path": str, "start_line": int, "end_line": int}
    func.io        : {"params": [...], "returns": {"type": str, "desc": str}}
    file.funclist  : [{"func_id": int, "name": str, "brief": ""}]

    Parameters
    ----------
    repo_id : int
        目标仓库 id
    db_path : str | None
        SQLite 路径；不传则使用 config.DB_PATH
    file_id : int | None
        若指定，则只处理该文件；否则处理 repo 下所有文件
    force : bool
        True = 若文件已有 func 记录则先全部删除再重建；
        False = 跳过已有记录（可用于断点续跑）

    Returns
    -------
    dict[int, list[dict]]
        {file_id: [{"func_id", "name", "start_line", "end_line"}, ...]}

    Raises
    ------
    ValueError
        repo_id 或 file_id 在数据库中不存在
    """
    _db = db_path or DB_PATH

    # ── ① 校验仓库 ──────────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_file_func] repo_id={repo_id} 不存在于数据库。"
        )
    repo_path = repo['path']

    # ── ② 确定目标文件列表 ──────────────────────────────────────────
    if file_id is not None:
        file_rec = FileDB.get_by_id(file_id, db_path=_db)
        if file_rec is None:
            raise ValueError(
                f"[analyze_file_func] file_id={file_id} 不存在于数据库。"
            )
        files = [file_rec]
    else:
        files = FileDB.list_by_repo(repo_id, db_path=_db)

    if not files:
        print(
            f"[analyze_file_func] ⚠ repo_id={repo_id} 暂无文件记录，"
            "请先执行 analyze_area_file。"
        )
        return {}

    total_funcs_all = 0
    result: dict[int, list[dict]] = {}

    for file_rec in files:
        fid       = file_rec['id']
        fname     = file_rec['name']
        fpath_rel = file_rec['path']
        area_id   = file_rec['area_id']

        # 优先取已分析的语言，否则实时推断
        language = file_rec.get('language') or _detect_language(fname)

        # 构建文件绝对路径
        file_abs = os.path.join(repo_path, fpath_rel.replace('/', os.sep))
        if not os.path.isfile(file_abs):
            print(f"[analyze_file_func] ⚠ 文件不存在，跳过：{fpath_rel}")
            result[fid] = []
            continue

        # ── ③ 处理已有 func 记录 ────────────────────────────────────
        existing_funcs = FuncDB.list_by_file(fid, db_path=_db)
        if existing_funcs:
            if force:
                for ef in existing_funcs:
                    FuncDB.delete(ef['id'], db_path=_db)
                print(
                    f"[analyze_file_func] force 模式：已清除 {len(existing_funcs)} 条旧记录"
                    f"（{fname}）"
                )
            else:
                # 断点续跑：保留已有数据
                result[fid] = [
                    {
                        'func_id':    ef['id'],
                        'name':       ef['name'],
                        'start_line': (ef.get('place') or {}).get('start_line', 0),
                        'end_line':   (ef.get('place') or {}).get('end_line',   0),
                    }
                    for ef in existing_funcs
                ]
                print(
                    f"[analyze_file_func] 跳过（已有 {len(existing_funcs)} 个 func）：{fname}"
                    " —— 传入 force=True 可强制重建"
                )
                total_funcs_all += len(existing_funcs)
                continue

        # ── ④ 提取函数 ──────────────────────────────────────────────
        print(f"[analyze_file_func] 处理：{fpath_rel}（{language}）")
        extracted = _extract_functions(file_abs, fname, language, fpath_rel)

        # ── ⑤ 写入 func 表 ──────────────────────────────────────────
        funclist:          list[dict] = []   # 写回 file.funclist
        file_func_results: list[dict] = []   # 供调用方使用

        for func_info in extracted:
            func_name  = func_info['name']
            signature  = func_info.get('signature') or func_name
            start_line = func_info.get('start_line', 0)
            end_line   = func_info.get('end_line', start_line)
            params     = func_info.get('params', [])
            returns    = func_info.get('returns', {'type': '', 'desc': ''})

            place: dict = {
                'file_path':  fpath_rel,
                'start_line': start_line,
                'end_line':   end_line,
            }
            io: dict = {
                'params':  params,
                'returns': returns,
            }

            try:
                func_id = FuncDB.create(
                    repo_id   = repo_id,
                    area_id   = area_id,
                    file_id   = fid,
                    name      = func_name,
                    signature = signature,
                    place     = place,
                    io        = io,
                    db_path   = _db,
                )
            except Exception as e:
                # UNIQUE 约束冲突（同名同签名同文件）→ 跳过，不终止整体流程
                print(
                    f"[analyze_file_func]   ⚠ 函数 '{func_name}' 写入失败"
                    f"（跳过）：{e}"
                )
                continue

            funclist.append({
                'func_id': func_id,
                'name':    func_name,
                'brief':   '',   # 留给 analyze_file_funclist_description（step14）填充
            })
            file_func_results.append({
                'func_id':    func_id,
                'name':       func_name,
                'start_line': start_line,
                'end_line':   end_line,
            })

        # ── ⑥ 更新 file.funclist ────────────────────────────────────
        FileDB.update(fid, db_path=_db, funclist=funclist)

        result[fid]      = file_func_results
        total_funcs_all += len(file_func_results)

        print(
            f"[analyze_file_func]   ✓ {fname}：{len(file_func_results)} 个函数已入库"
        )

    total_files = len(files)
    print(
        f"\n[analyze_file_func] ✓ 完成：处理 {total_files} 个文件，"
        f"共提取 {total_funcs_all} 个函数。"
    )
    return result