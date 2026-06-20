"""
analyzer/file_analyzer.py
CodeMAP 文件层分析器

实现：
  - analyze_file_language : 检测每个文件的编程语言，写入 file:language
  - analyze_file_func     : 解析每个文件中的所有函数，写入：
                              file:funclist / func:name / func:place / func:io

语言策略
--------
  Python      → ast 模块（精确，零依赖）
  C / C++     → tree-sitter 专用提取器（精确签名和类型信息）
  其他已支持   → tree-sitter-languages 通用提取器（130+ 语言）
  兜底         → ctags（只拿名称和行号，io 留空）
  真正无解      → language=Unknown，跳过函数提取
"""

import ast
import json as _json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, FileDB, FuncDB
from config import DB_PATH, DATA_DIR


# ==================================================================
# 0. tree-sitter 可用性检测（延迟导入，避免强依赖）
# ==================================================================

try:
    from tree_sitter_languages import get_parser as _ts_get_parser
    _ts_get_parser('c')
    _TREE_SITTER_OK = True
except ImportError:
    _TREE_SITTER_OK = False


# ==================================================================
# 1. 语言映射常量
# ==================================================================

_EXT_TO_LANG: dict[str, str] = {
    # C / C++
    '.c': 'C', '.h': 'C',
    '.cpp': 'C++', '.cxx': 'C++', '.cc': 'C++',
    '.hpp': 'C++', '.hxx': 'C++',
    # Python
    '.py': 'Python',
    # Java
    '.java': 'Java',
    # JS / TS
    '.js': 'JavaScript', '.jsx': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript',
    # Go
    '.go': 'Go',
    # Rust
    '.rs': 'Rust',
    # Shell
    '.sh': 'Shell', '.bash': 'Shell', '.zsh': 'Shell',
    # 构建脚本
    '.cmake': 'CMake',
    # 其他
    '.rb': 'Ruby',
    '.swift': 'Swift',
    '.kt': 'Kotlin', '.kts': 'Kotlin',
    '.scala': 'Scala',
    '.hs': 'Haskell',
    '.asm': 'Assembly', '.s': 'Assembly',
    '.lua': 'Lua',
    '.pl': 'Perl', '.pm': 'Perl',
    '.f': 'Fortran', '.f90': 'Fortran', '.f95': 'Fortran',
    '.r': 'R',
    '.m': 'MATLAB', '.mm': 'Objective-C',
    # 文档 / 配置
    '.md': 'Markdown', '.rst': 'reStructuredText',
    '.yaml': 'YAML', '.yml': 'YAML',
    '.json': 'JSON', '.xml': 'XML',
    '.html': 'HTML', '.htm': 'HTML',
    '.css': 'CSS', '.sql': 'SQL',
    '.toml': 'TOML', '.ini': 'INI', '.cfg': 'INI',
}

_SPECIAL_NAMES: dict[str, str] = {
    'makefile':        'Makefile',
    'gnumakefile':     'Makefile',
    'cmakelists.txt':  'CMake',
    'dockerfile':      'Dockerfile',
    'gemfile':         'Ruby',
    'rakefile':        'Ruby',
    'vagrantfile':     'Ruby',
    'podfile':         'Ruby',
    'brewfile':        'Ruby',
}

# 显示名 → tree-sitter grammar 名
_LANG_TO_TS: dict[str, str] = {
    'C':           'c',
    'C++':         'cpp',
    'Python':      'python',
    'Java':        'java',
    'JavaScript':  'javascript',
    'TypeScript':  'typescript',
    'Go':          'go',
    'Rust':        'rust',
    'Ruby':        'ruby',
    'Swift':       'swift',
    'Kotlin':      'kotlin',
    'Lua':         'lua',
    'Shell':       'bash',
    'Haskell':     'haskell',
    'Scala':       'scala',
}

# tree-sitter grammar 名 → 函数定义节点类型列表
_TS_FUNC_TYPES: dict[str, list[str]] = {
    'c':           ['function_definition'],
    'cpp':         ['function_definition'],
    'python':      ['function_definition'],      # ast 优先；此为备用
    'java':        ['method_declaration', 'constructor_declaration'],
    'javascript':  ['function_declaration', 'method_definition', 'function_expression'],
    'typescript':  ['function_declaration', 'method_definition', 'function_expression'],
    'go':          ['function_declaration', 'method_declaration'],
    'rust':        ['function_item'],
    'ruby':        ['method', 'singleton_method'],
    'swift':       ['function_declaration'],
    'kotlin':      ['function_declaration'],
    'lua':         ['function_declaration', 'local_function'],
    'bash':        ['function_definition'],
    'haskell':     [],                            # 语法较特殊，暂不提取
    'scala':       ['function_declaration', 'function_definition'],
}

# 不提取函数的语言（文档、配置、数据类）
_NO_FUNC_LANGS: frozenset[str] = frozenset({
    'Markdown', 'reStructuredText', 'YAML', 'JSON', 'XML',
    'HTML', 'CSS', 'SQL', 'TOML', 'INI', 'CMake', 'Makefile',
    'Dockerfile', 'Assembly', 'MATLAB', 'R', 'Fortran', 'Unknown',
})

# 单文件解析大小上限（超出则跳过函数提取）
_MAX_FILE_BYTES = 5 * 1024 * 1024   # 5 MB


# ==================================================================
# 2. 语言检测
# ==================================================================

def _read_shebang(abs_path: str) -> Optional[str]:
    """读取文件首行 shebang，返回对应语言名或 None。"""
    try:
        with open(abs_path, 'rb') as f:
            first = f.read(128)
        line = first.split(b'\n', 1)[0].decode('utf-8', errors='ignore')
        if not line.startswith('#!'):
            return None
        lower = line.lower()
        if 'python'             in lower: return 'Python'
        if 'ruby'               in lower: return 'Ruby'
        if 'node'               in lower: return 'JavaScript'
        if 'perl'               in lower: return 'Perl'
        if 'lua'                in lower: return 'Lua'
        if '/bash' in lower or '/sh' in lower or '/zsh' in lower:
            return 'Shell'
    except OSError:
        pass
    return None


def _detect_language(filename: str, abs_path: str) -> str:
    """
    检测文件编程语言。

    优先级：
      1. 特殊文件名（Makefile / CMakeLists.txt 等）
      2. 扩展名映射
      3. shebang（#!）行
      4. 返回 'Unknown'
    """
    lower = filename.lower()
    if lower in _SPECIAL_NAMES:
        return _SPECIAL_NAMES[lower]

    _, ext = os.path.splitext(filename)
    lang = _EXT_TO_LANG.get(ext.lower())
    if lang:
        return lang

    shebang = _read_shebang(abs_path)
    if shebang:
        return shebang

    return 'Unknown'


# ==================================================================
# 3. 文件内容读取
# ==================================================================

def _read_source(abs_path: str) -> Optional[str]:
    """
    读取源文件文本，自动处理编码（UTF-8 → latin-1 兜底）。
    超过大小上限返回 None。
    """
    try:
        if os.path.getsize(abs_path) > _MAX_FILE_BYTES:
            return None
    except OSError:
        return None

    for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'gbk'):
        try:
            with open(abs_path, 'r', encoding=enc, errors='strict') as f:
                return f.read()
        except (UnicodeDecodeError, ValueError):
            continue
        except OSError:
            return None
    return None


# ==================================================================
# 4. Python 函数提取（ast 模块）
# ==================================================================

def _ast_unparse(node) -> str:
    """安全地反序列化 AST 注解节点；失败返回空字符串。"""
    if node is None:
        return ''
    try:
        return ast.unparse(node)
    except Exception:
        return ''


def _extract_python_funcs(source: str, rel_path: str) -> list[dict]:
    """
    用 ast 模块解析 Python 源文件，提取所有函数（含 async def、类方法、嵌套函数）。

    返回列表，每项：
    {
        name, signature, start_line, end_line,
        return_type, params[{name, type, desc}], file_path
    }
    """
    try:
        tree = ast.parse(source, filename=rel_path, type_comments=False)
    except SyntaxError:
        return []

    funcs: list[dict] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        func_name  = node.name
        start_line = node.lineno
        end_line   = getattr(node, 'end_lineno', node.lineno)

        params: list[dict] = []
        args = node.args

        # 普通位置参数
        for arg in args.args:
            params.append({
                'name': arg.arg,
                'type': _ast_unparse(arg.annotation),
                'desc': '',
            })

        # *args
        if args.vararg:
            params.append({
                'name': f'*{args.vararg.arg}',
                'type': _ast_unparse(args.vararg.annotation),
                'desc': '',
            })

        # keyword-only 参数
        for arg in args.kwonlyargs:
            params.append({
                'name': arg.arg,
                'type': _ast_unparse(arg.annotation),
                'desc': '',
            })

        # **kwargs
        if args.kwarg:
            params.append({
                'name': f'**{args.kwarg.arg}',
                'type': _ast_unparse(args.kwarg.annotation),
                'desc': '',
            })

        return_type = _ast_unparse(node.returns)

        # 构建签名字符串
        param_strs = []
        for p in params:
            param_strs.append(
                f"{p['name']}: {p['type']}" if p['type'] else p['name']
            )
        prefix    = 'async def ' if isinstance(node, ast.AsyncFunctionDef) else 'def '
        ret_hint  = f' -> {return_type}' if return_type else ''
        signature = f"{prefix}{func_name}({', '.join(param_strs)}){ret_hint}"

        funcs.append({
            'name':        func_name,
            'signature':   signature[:600],
            'start_line':  start_line,
            'end_line':    end_line,
            'return_type': return_type,
            'params':      params,
            'file_path':   rel_path,
        })

    return funcs


# ==================================================================
# 5. C/C++ 函数提取（tree-sitter 专用）
# ==================================================================

def _ts_text(node, src: bytes) -> str:
    """从 tree-sitter 节点提取对应源码字符串。"""
    return src[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _find_all_nodes(root, wanted: set) -> list:
    """
    DFS 遍历 tree-sitter 语法树，收集所有类型在 wanted 中的节点。
    不中止递归——以支持嵌套函数（如 C++ lambda、本地函数）。
    """
    result: list = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in wanted:
            result.append(node)
        # 反序入栈以保证左→右顺序
        for child in reversed(node.children):
            stack.append(child)
    return result


def _find_func_declarator(node):
    """
    在 C/C++ declarator 链中找到 function_declarator 节点。
    处理层：pointer_declarator / reference_declarator /
             parenthesized_declarator / abstract_declarator 等。
    """
    if node is None:
        return None
    if node.type == 'function_declarator':
        return node
    wrapping = {
        'pointer_declarator', 'reference_declarator',
        'parenthesized_declarator', 'abstract_declarator',
        'abstract_pointer_declarator', 'abstract_reference_declarator',
    }
    if node.type in wrapping:
        inner = node.child_by_field_name('declarator')
        if inner:
            r = _find_func_declarator(inner)
            if r:
                return r
        # 个别 grammar 版本 field 名不同：遍历直接子节点
        for child in node.children:
            r = _find_func_declarator(child)
            if r:
                return r
    return None


def _extract_decl_name(node, src: bytes) -> str:
    """
    从 C/C++ declarator 节点提取函数标识符名称。
    处理：identifier / qualified_identifier / destructor_name /
          operator_name / template_function / pointer_declarator 等。
    """
    if node is None:
        return ''
    t = node.type
    if t in ('identifier', 'field_identifier'):
        return _ts_text(node, src)
    if t in ('qualified_identifier', 'destructor_name',
             'operator_name', 'template_function', 'template_method'):
        return _ts_text(node, src)
    if t in ('pointer_declarator', 'reference_declarator',
             'abstract_pointer_declarator'):
        inner = node.child_by_field_name('declarator')
        if inner:
            return _extract_decl_name(inner, src)
    if t == 'parenthesized_declarator':
        for child in node.children:
            r = _extract_decl_name(child, src)
            if r:
                return r
    # 深度优先兜底：找第一个 identifier
    for child in node.children:
        r = _extract_decl_name(child, src)
        if r:
            return r
    return _ts_text(node, src)


def _extract_c_params(params_node, src: bytes) -> list[dict]:
    """从 C/C++ parameter_list 节点提取参数信息。"""
    if params_node is None:
        return []

    params: list[dict] = []
    for child in params_node.children:
        # 可变参数 ...
        raw = _ts_text(child, src).strip()
        if raw == '...':
            params.append({'name': '...', 'type': 'variadic', 'desc': ''})
            continue

        if child.type == 'variadic_parameter':
            params.append({'name': '...', 'type': 'variadic', 'desc': ''})
            continue

        if child.type not in ('parameter_declaration',
                               'optional_parameter_declaration'):
            continue

        type_node = child.child_by_field_name('type')
        decl_node = child.child_by_field_name('declarator')

        param_type = _ts_text(type_node, src).strip() if type_node else ''
        param_name = _extract_decl_name(decl_node, src).strip() if decl_node else ''

        # 跳过 void 单参数声明：`f(void)`
        if param_type == 'void' and not param_name:
            continue

        # 类型和名字都为空时，取整段文本作类型
        if not param_type and not param_name:
            if raw:
                params.append({'name': '', 'type': raw, 'desc': ''})
            continue

        params.append({'name': param_name, 'type': param_type, 'desc': ''})

    return params


def _extract_c_cpp_funcs(source: str, rel_path: str, lang: str = 'C') -> list[dict]:
    """
    用 tree-sitter 解析 C/C++ 源文件，仅提取有函数体的定义（跳过纯声明）。

    C++ 类内成员函数、模板函数、运算符重载均支持。
    """
    if not _TREE_SITTER_OK:
        return []

    ts_name = 'cpp' if lang == 'C++' else 'c'
    try:
        parser    = _ts_get_parser(ts_name)
        src_bytes = source.encode('utf-8', errors='replace')
        tree      = parser.parse(src_bytes)
    except Exception:
        print(f"[warn] tree-sitter 解析器加载失败（{ts_name}）：{e}")
        return []

    func_nodes = _find_all_nodes(tree.root_node, {'function_definition'})
    funcs: list[dict] = []

    for node in func_nodes:
        # 只提取有函数体的定义
        body = node.child_by_field_name('body')
        if body is None:
            continue

        # 返回类型
        type_node   = node.child_by_field_name('type')
        return_type = _ts_text(type_node, src_bytes).strip() if type_node else ''

        # 找 function_declarator
        declarator = node.child_by_field_name('declarator')
        func_decl  = _find_func_declarator(declarator)
        if func_decl is None:
            continue

        # 提取函数名
        inner_decl = func_decl.child_by_field_name('declarator')
        func_name  = _extract_decl_name(inner_decl, src_bytes).strip()
        if not func_name or func_name in ('(', ''):
            continue

        # 提取参数
        params_node = func_decl.child_by_field_name('parameters')
        params      = _extract_c_params(params_node, src_bytes)

        # 签名：body 之前的所有文本，合并为单行
        sig_raw  = src_bytes[node.start_byte:body.start_byte].decode('utf-8', errors='replace')
        signature = re.sub(r'\s+', ' ', sig_raw).strip()

        start_line = node.start_point[0] + 1   # tree-sitter 行号从 0 开始
        end_line   = node.end_point[0]   + 1

        funcs.append({
            'name':        func_name,
            'signature':   signature[:600],
            'start_line':  start_line,
            'end_line':    end_line,
            'return_type': return_type,
            'params':      params,
            'file_path':   rel_path,
        })

    return funcs


# ==================================================================
# 6. 通用 tree-sitter 函数提取（非 C/C++/Python）
# ==================================================================

def _ts_extract_name_generic(node, src: bytes, ts_lang: str) -> str:
    """
    通用策略提取函数名：先尝试 'name' field，再 DFS 找 identifier。
    """
    name_node = node.child_by_field_name('name')
    if name_node:
        return _ts_text(name_node, src).strip()

    # bash function_definition：name 在 word 子节点
    if ts_lang == 'bash':
        for child in node.children:
            if child.type == 'word':
                return _ts_text(child, src).strip()

    # DFS 找第一个 identifier（深度限 4 层）
    def _dfs(n, depth=0) -> str:
        if depth > 4:
            return ''
        if n.type in ('identifier', 'type_identifier', 'property_identifier',
                       'simple_identifier'):
            return _ts_text(n, src).strip()
        for ch in n.children:
            r = _dfs(ch, depth + 1)
            if r:
                return r
        return ''

    return _dfs(node)


def _ts_extract_params_generic(node, src: bytes) -> list[dict]:
    """
    通用策略提取函数参数：查找 parameters / formal_parameters /
    parameter_list 子节点，遍历其中的参数条目。
    """
    param_parent_names = (
        'parameters', 'formal_parameters', 'parameter_list',
        'params', 'lambda_parameters',
    )
    params_node = None
    for fname in param_parent_names:
        params_node = node.child_by_field_name(fname)
        if params_node:
            break
    if params_node is None:
        for child in node.children:
            if 'parameter' in child.type.lower():
                params_node = child
                break
    if params_node is None:
        return []

    param_types = {
        'parameter_declaration', 'formal_parameter', 'parameter',
        'required_parameter', 'optional_parameter', 'rest_parameter',
        'simple_parameter', 'typed_parameter', 'variadic_parameter',
        'self_parameter', 'receiver_parameter',
    }

    params: list[dict] = []
    for child in params_node.children:
        if child.type not in param_types:
            continue

        name_n = (child.child_by_field_name('name')
                  or child.child_by_field_name('pattern'))
        type_n = child.child_by_field_name('type')

        pname = _ts_text(name_n, src).strip() if name_n else ''
        ptype = _ts_text(type_n, src).strip() if type_n else ''

        if not pname and not ptype:
            raw = _ts_text(child, src).strip()
            if raw and raw not in (',', '(', ')'):
                params.append({'name': raw, 'type': '', 'desc': ''})
        else:
            params.append({'name': pname, 'type': ptype, 'desc': ''})

    return params


def _extract_generic_ts_funcs(source: str, rel_path: str, ts_lang: str) -> list[dict]:
    """
    用 tree-sitter 通用策略提取函数（适用于 Java / Go / Rust / Ruby 等）。
    """
    if not _TREE_SITTER_OK:
        return []

    func_node_types = _TS_FUNC_TYPES.get(ts_lang, [])
    if not func_node_types:
        return []

    try:
        parser    = _ts_get_parser(ts_lang)
        src_bytes = source.encode('utf-8', errors='replace')
        tree      = parser.parse(src_bytes)
    except Exception:
        return []

    func_nodes = _find_all_nodes(tree.root_node, set(func_node_types))
    funcs: list[dict] = []

    for node in func_nodes:
        func_name = _ts_extract_name_generic(node, src_bytes, ts_lang)
        if not func_name:
            continue

        params     = _ts_extract_params_generic(node, src_bytes)
        start_line = node.start_point[0] + 1
        end_line   = node.end_point[0]   + 1

        # 签名：取节点前几行（到函数体开始之前）
        raw_text   = _ts_text(node, src_bytes)
        lines      = raw_text.split('\n')
        sig_lines: list[str] = []
        for line in lines[:6]:
            sig_lines.append(line)
            stripped = line.rstrip()
            if stripped.endswith(('{', ':', '=>', 'do', '=')):
                break
        signature = ' '.join(l.strip() for l in sig_lines).strip()

        funcs.append({
            'name':        func_name,
            'signature':   signature[:600],
            'start_line':  start_line,
            'end_line':    end_line,
            'return_type': '',
            'params':      params,
            'file_path':   rel_path,
        })

    return funcs


# ==================================================================
# 7. ctags 兜底提取
# ==================================================================

def _extract_ctags_funcs(abs_path: str, rel_path: str) -> list[dict]:
    """
    用 Universal Ctags 提取函数名和行号（不依赖 tree-sitter）。
    需要系统已安装 ctags（支持 --output-format=json）。
    失败时静默返回空列表。
    """
    if not shutil.which('ctags'):
        return []

    try:
        proc = subprocess.run(
            [
                'ctags', '--output-format=json',
                '--fields=+ne', '--kinds-all=*',
                '--languages=all', '-f', '-', abs_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='replace',
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    func_kinds = {
        'function', 'method', 'constructor', 'destructor',
        'f', 'm', 'c', 'd',
    }

    funcs: list[dict] = []
    for line in proc.stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            entry = _json.loads(line)
        except _json.JSONDecodeError:
            continue

        kind = str(entry.get('kind', '')).lower()
        if kind not in func_kinds:
            continue

        name = entry.get('name', '').strip()
        if not name:
            continue

        start_line = int(entry.get('line', 0))
        if start_line == 0:
            continue

        end_data = entry.get('end', {})
        end_line = (
            int(end_data['line'])
            if isinstance(end_data, dict) and 'line' in end_data
            else start_line
        )

        sig = entry.get('signature', '')
        funcs.append({
            'name':        name,
            'signature':   f"{name}{sig}"[:600] if sig else name,
            'start_line':  start_line,
            'end_line':    end_line,
            'return_type': '',
            'params':      [],
            'file_path':   rel_path,
        })

    return funcs


# ==================================================================
# 8. 函数提取分发器
# ==================================================================

def _extract_funcs(abs_path: str, rel_path: str, language: str) -> list[dict]:
    """
    根据语言选择最合适的提取策略，按优先级降级：

      1. Python → ast（精确）
      2. C/C++  → tree-sitter 专用提取器
      3. 其他有 TS 支持 → 通用 tree-sitter 提取器
      4. ctags 兜底
      5. 放弃：返回 []

    返回列表每项：
    {name, signature, start_line, end_line, return_type, params, file_path}
    """
    if language in _NO_FUNC_LANGS:
        return []

    source = _read_source(abs_path)
    if source is None:
        return []

    # ── Python ──────────────────────────────────────────────────────
    if language == 'Python':
        return _extract_python_funcs(source, rel_path)

    # ── C / C++ / Objective-C ──────────────────────────────────────
    if language in ('C', 'C++', 'Objective-C'):
        if _TREE_SITTER_OK:
            result = _extract_c_cpp_funcs(source, rel_path, lang=language)
            if result:
                return result
        return _extract_ctags_funcs(abs_path, rel_path)

    # ── 通用 tree-sitter 语言 ───────────────────────────────────────
    ts_name = _LANG_TO_TS.get(language)
    if ts_name and _TREE_SITTER_OK:
        try:
            result = _extract_generic_ts_funcs(source, rel_path, ts_name)
            if result:
                return result
        except Exception:
            pass   # 降级到 ctags

    # ── ctags 兜底 ──────────────────────────────────────────────────
    return _extract_ctags_funcs(abs_path, rel_path)


# ==================================================================
# 9. analyze_file_language（Step 5a）
# ==================================================================

def analyze_file_language(
    repo_id: int,
    db_path: Optional[str] = None,
) -> dict[int, str]:
    """
    检测仓库内所有文件的编程语言，并写入 file.language 字段。

    幂等：对已写入 language 的文件也会覆盖更新（保证重跑一致性）。
    依赖：file 表中已有记录（请先执行 analyze_area_file）。

    Parameters
    ----------
    repo_id : int
        目标仓库 id（由 init_repo 返回）
    db_path : str | None
        SQLite 路径；不传则使用 config.DB_PATH

    Returns
    -------
    dict[int, str]
        {file_id → detected_language}

    Raises
    ------
    ValueError
        repo_id 在数据库中不存在
    """
    _db = db_path or DB_PATH

    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_file_language] repo_id={repo_id} 不存在于数据库。")

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[analyze_file_language] 目标仓库：{repo_name}（{repo_path}）")

    all_files = FileDB.list_by_repo(repo_id, db_path=_db)
    if not all_files:
        print("[analyze_file_language] ⚠ 无 file 记录，请先执行 analyze_area_file。")
        return {}

    result: dict[int, str] = {}

    for file_rec in all_files:
        file_id  = file_rec['id']
        filename = file_rec['name']
        rel_path = file_rec['path']
        abs_path = os.path.join(repo_path, rel_path)

        lang = _detect_language(filename, abs_path)
        FileDB.update(file_id, db_path=_db, language=lang)
        result[file_id] = lang

    # 打印语言分布摘要
    lang_dist = Counter(result.values())
    top = lang_dist.most_common(10)
    print(
        f"[analyze_file_language] ✓ 完成：{len(result)} 个文件已检测并写库。\n"
        f"[analyze_file_language]   语言分布（Top {len(top)}）："
    )
    for lang, cnt in top:
        bar = '█' * min(cnt, 40)
        print(f"    {lang:<22s} {cnt:>4} 个文件  {bar}")

    return result


# ==================================================================
# 10. analyze_file_func（Step 5b）
# ==================================================================

def analyze_file_func(
    repo_id: int,
    db_path: Optional[str] = None,
    force: bool = False,
    languages: Optional[list[str]] = None,
) -> dict[int, list[dict]]:
    """
    解析仓库内所有文件的函数，写入 func 表并更新 file.funclist。

    语言策略（按优先级）：
      Python      → ast 模块
      C / C++     → tree-sitter 专用提取器
      其他有支持   → tree-sitter 通用提取器
      兜底         → ctags（只含名称和行号，io 留空）
      无解         → 跳过

    依赖：
      - file 表已有记录（analyze_area_file 完成）
      - file.language 已填充（analyze_file_language 完成，否则降级用扩展名检测）

    Parameters
    ----------
    repo_id : int
        目标仓库 id
    db_path : str | None
        SQLite 路径；不传则使用 config.DB_PATH
    force : bool
        True  = 先清除仓库所有旧 func 记录再重建
        False = 已有 func 记录时抛出 ValueError
    languages : list[str] | None
        若提供，只处理指定语言的文件（如 ['C', 'C++']）；
        None 则处理全部文件

    Returns
    -------
    dict[int, list[dict]]
        键为 file_id，值为该文件已入库的函数列表，每项：
        {
            "func_id":     int,
            "name":        str,
            "signature":   str,
            "start_line":  int,
            "end_line":    int,
            "return_type": str,
            "params":      list[{name, type, desc}],
        }

    Raises
    ------
    ValueError
        · repo_id 不存在
        · force=False 且已存在 func 记录
    """
    _db = db_path or DB_PATH

    # ── 取仓库信息 ────────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_file_func] repo_id={repo_id} 不存在于数据库。")

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[analyze_file_func] 目标仓库：{repo_name}（{repo_path}）")

    # ── 处理已有 func 记录 ────────────────────────────────────────
    existing_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)
    if existing_funcs:
        if force:
            for fn in existing_funcs:
                FuncDB.delete(fn['id'], db_path=_db)
            print(f"[analyze_file_func] 已清除 {len(existing_funcs)} 条旧 func 记录。")
        else:
            raise ValueError(
                f"[analyze_file_func] repo_id={repo_id} 已有 {len(existing_funcs)} 条 func 记录。"
                " 如需重新提取，请传入 force=True。"
            )

    # ── 取 file 列表 ─────────────────────────────────────────────
    all_files = FileDB.list_by_repo(repo_id, db_path=_db)
    if not all_files:
        print("[analyze_file_func] ⚠ 无 file 记录，请先执行 analyze_area_file。")
        return {}

    # 按语言过滤（可选）
    if languages:
        lang_set  = set(languages)
        all_files = [f for f in all_files if f.get('language') in lang_set]
        print(f"[analyze_file_func] 语言过滤 {lang_set}，剩余 {len(all_files)} 个文件。")

    # ── 逐文件提取 ───────────────────────────────────────────────
    result:      dict[int, list[dict]] = {}
    total_funcs  = 0
    skip_count   = 0
    err_count    = 0

    for file_rec in all_files:
        file_id  = file_rec['id']
        area_id  = file_rec['area_id']
        filename = file_rec['name']
        rel_path = file_rec['path']
        abs_path = os.path.join(repo_path, rel_path)

        # file.language 可能尚未填写（analyze_file_language 未运行），此处兜底检测
        language = (
            file_rec.get('language')
            or _detect_language(filename, abs_path)
        )

        if not os.path.isfile(abs_path):
            print(f"[analyze_file_func] ⚠ 文件不存在，跳过：{rel_path}")
            skip_count += 1
            result[file_id] = []
            continue

        # 提取函数
        try:
            extracted = _extract_funcs(abs_path, rel_path, language)
        except Exception as exc:
            print(f"[analyze_file_func] ⚠ 提取异常（{rel_path}）：{exc}")
            err_count += 1
            extracted = []

        # ── 写入 func 表 ─────────────────────────────────────────
        file_func_records: list[dict] = []
        funclist_brief:    list[dict] = []
        seen_sigs:         set[tuple] = set()

        for fn in extracted:
            func_name = fn['name']
            signature = fn.get('signature', '')

            # 同文件内去重 key：(name, signature 前 200 字节)
            dedup = (func_name, signature[:200])
            if dedup in seen_sigs:
                continue
            seen_sigs.add(dedup)

            place: dict = {
                'file_path':  rel_path,
                'start_line': fn['start_line'],
                'end_line':   fn['end_line'],
            }
            io: dict = {
                'params':  fn.get('params', []),
                'returns': {
                    'type': fn.get('return_type', ''),
                    'desc': '',
                },
            }

            try:
                func_id = FuncDB.create(
                    repo_id   = repo_id,
                    area_id   = area_id,
                    file_id   = file_id,
                    name      = func_name,
                    signature = signature,
                    place     = place,
                    io        = io,
                    db_path   = _db,
                )
            except Exception as exc:
                # UNIQUE 冲突或其他 DB 错误 → 跳过该函数
                print(
                    f"[analyze_file_func]   ⚠ 函数入库失败 "
                    f"[{rel_path}:{fn['start_line']} {func_name}]: {exc}"
                )
                continue

            file_func_records.append({
                'func_id':     func_id,
                'name':        func_name,
                'signature':   signature,
                'start_line':  fn['start_line'],
                'end_line':    fn['end_line'],
                'return_type': fn.get('return_type', ''),
                'params':      fn.get('params', []),
            })
            funclist_brief.append({
                'func_id': func_id,
                'name':    func_name,
                'brief':   '',   # 后续 analyze_file_funclist_description 填充
            })

        # ── 更新 file.funclist ───────────────────────────────────
        FileDB.update(file_id, db_path=_db, funclist=funclist_brief)

        result[file_id] = file_func_records
        n = len(file_func_records)
        total_funcs += n

        if n > 0:
            print(
                f"[analyze_file_func]   ✓ {rel_path:<55s} "
                f"lang={language:<8s}  funcs={n}"
            )

    # ── 汇总输出 ─────────────────────────────────────────────────
    files_with_funcs = sum(1 for v in result.values() if v)
    print(
        f"\n[analyze_file_func] ✓ 完成：\n"
        f"  处理文件：{len(all_files)} 个\n"
        f"  含函数文件：{files_with_funcs} 个\n"
        f"  提取函数：{total_funcs} 个\n"
        f"  跳过文件：{skip_count} 个\n"
        f"  出错文件：{err_count} 个"
    )
    if not _TREE_SITTER_OK:
        print(
            "[analyze_file_func] ⚠ tree-sitter-languages 未安装，"
            "C/C++ 解析可能退化为 ctags 兜底。\n"
            "   建议：pip install tree-sitter tree-sitter-languages"
        )

    return result