"""
analyzer/func_analyzer.py
"""

import ast
import json as _json
import os
import re
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, FileDB, FuncDB
from config import DB_PATH

# ------------------------------------------------------------------
#  tree-sitter 可用性检测
# ------------------------------------------------------------------
try:
    from tree_sitter_languages import get_parser as _ts_get_parser
    _ts_get_parser('c')
    _TREE_SITTER_OK = True
except Exception:
    _TREE_SITTER_OK = False

# 单函数源码大小上限（超出跳过 SA，仍走 LLM 截断版）
_MAX_FUNC_BYTES = 512 * 1024   # 512 KB
# LLM 提示中函数源码的最大字符数
_MAX_SOURCE_IN_PROMPT = 4000

# LLM 调用重试策略
_LLM_MAX_RETRIES   = 3          # 最多重试次数（含第 1 次，共最多 3 次）
_LLM_RETRY_DELAYS  = [2, 5, 10] # 第 1/2/3 次失败后等待的秒数

# ==================================================================
# §1  正则常量
# ==================================================================

# C/C++：空指针 / 零值 guard 条件
_RE_C_NULL_GUARD = re.compile(
    r'\bif\s*\(([^{;\n]*?'
    r'(?:==\s*(?:NULL|Z_NULL|nullptr|0)\b|'
    r'!=\s*(?:NULL|Z_NULL|nullptr)\b|'
    r'!\s*[a-zA-Z_]\w*)'
    r'[^{;\n]*?)\)',
    re.MULTILINE,
)

# C/C++：数值范围 guard 条件
_RE_C_RANGE_GUARD = re.compile(
    r'\bif\s*\(([^{;\n]*?(?:[<>]=?\s*\d|[<>]=?\s*[A-Z_]+_(?:MAX|MIN|SIZE|LEN))'
    r'[^{;\n]*?)\)',
    re.MULTILINE,
)

# assert / 断言宏
_RE_ASSERT = re.compile(
    r'\b((?:MZ_ASSERT|ZASSERT|Z_ASSERT|assert|ASSERT|VERIFY|'
    r'MINIZIP_ASSERT|ZLIB_INTERNAL)\s*\((?:[^()]*|\([^()]*\))*\))\s*;',
    re.MULTILINE,
)

# return 语句（含返回值）
_RE_RETURN = re.compile(r'\breturn\s+([^;{]+?)\s*;', re.MULTILINE)

# 解引用赋值（输出参数写回）：*param = expr
_RE_DEREF_ASSIGN = re.compile(
    r'\*\s*([a-zA-Z_]\w*(?:\s*->\s*[a-zA-Z_]\w*)*)\s*=\s*([^;]+)\s*;',
    re.MULTILINE,
)

# 内存分配调用
_RE_ALLOC_CALL = re.compile(
    r'\b(malloc|calloc|realloc|ZALLOC|MZ_ALLOC|zmalloc|zalloc|'
    r'ALLOC|mz_stream_alloc|HeapAlloc|VirtualAlloc|new\b)\s*[(<]',
    re.MULTILINE,
)

# goto 语句
_RE_GOTO = re.compile(r'\bgoto\s+([a-zA-Z_]\w*)\s*;', re.MULTILINE)

# errno 赋值
_RE_ERRNO = re.compile(r'\berrno\s*=\s*([A-Z_]\w*)\s*;', re.MULTILINE)

# 错误码符号识别（用于判断 return 值是否为错误码）
_RE_ERROR_CODE = re.compile(
    r'\b(?:'
    r'Z_(?:STREAM|MEM|BUF|VERSION|DATA|ERRNO)_ERROR|'
    r'MZ_(?:STREAM|MEM|OPEN|CLOSE|WRITE|READ|HASH|SUPPORT|PARAM|SIGN|CRC|'
    r'EXIST|PASSWORD|INTERNAL)_ERROR|'
    r'MZ_OK|Z_OK|'
    r'EOF|EINVAL|ENOMEM|ENOENT|EACCES|EPERM|EBADF|EIO|'
    r'-1|NULL|nullptr|false|FALSE'
    r')\b',
)

# 已知可能失败但返回值常被忽略的函数（用于检测 unchecked call）
_RISKY_UNCHECKED = frozenset({
    'fwrite', 'fread', 'write', 'read', 'fflush', 'fclose',
    'mz_stream_write', 'mz_stream_read', 'mz_stream_flush',
    'send', 'recv', 'sendto', 'recvfrom',
})


# ==================================================================
# §2  工具函数
# ==================================================================

def _read_func_source(
    repo_path: str,
    rel_path: str,
    start_line: int,
    end_line: int,
) -> Optional[str]:
    """
    按行范围读取函数源码。

    Returns
    -------
    str | None  失败（文件不存在、编码问题、超大文件）时返回 None
    """
    abs_path = os.path.join(repo_path, rel_path)
    if not os.path.isfile(abs_path):
        return None
    try:
        if os.path.getsize(abs_path) > _MAX_FUNC_BYTES * 10:
            return None
    except OSError:
        return None

    for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'gbk'):
        try:
            with open(abs_path, 'r', encoding=enc, errors='strict') as f:
                lines = f.readlines()
            s = max(0, start_line - 1)
            e = min(len(lines), end_line)
            return ''.join(lines[s:e])
        except (UnicodeDecodeError, ValueError):
            continue
        except OSError:
            return None
    return None


def _format_params(params) -> str:
    """将 io.params 列表格式化为可读字符串。"""
    if not params or not isinstance(params, list):
        return '（无参数）'
    parts = []
    for p in params:
        t = str(p.get('type', '') or '').strip()
        n = str(p.get('name', '') or '').strip()
        if t and n:
            parts.append(f'{t} {n}')
        elif t:
            parts.append(t)
        elif n:
            parts.append(n)
    return ', '.join(parts) if parts else '（无参数）'


def _parse_llm_list(raw) -> list[str]:
    """
    从 LLM 返回的 dict/list 中提取字符串列表。
    容错：支持 {"items": [...]} / 直接 list / {"conditions": [...]} 等。
    """
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x and str(x).strip()]

    if isinstance(raw, dict):
        for key in ('items', 'conditions', 'postconditions',
                    'preconditions', 'exceptions', 'results', 'list'):
            val = raw.get(key)
            if isinstance(val, list):
                return [str(x).strip() for x in val if x and str(x).strip()]
        # 回退：取第一个 list 类型的 value
        for val in raw.values():
            if isinstance(val, list):
                return [str(x).strip() for x in val if x and str(x).strip()]

    return []


# ==================================================================
# §3  tree-sitter 工具（C/C++ 专用）
# ==================================================================

def _ts_text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _find_all_ts_nodes(root, wanted: set) -> list:
    """DFS 收集所有指定类型的 tree-sitter 节点。"""
    result, stack = [], [root]
    while stack:
        node = stack.pop()
        if node.type in wanted:
            result.append(node)
        for child in reversed(node.children):
            stack.append(child)
    return result


def _ts_get_func_body(source: str, func_name: str, language: str):
    """
    用 tree-sitter 找到目标函数体节点。
    返回 (body_node, src_bytes) 或 (None, None)。
    """
    if not _TREE_SITTER_OK:
        return None, None

    ts_name   = 'cpp' if language in ('C++', 'Objective-C') else 'c'
    src_bytes = source.encode('utf-8', errors='replace')
    try:
        parser = _ts_get_parser(ts_name)
        tree   = parser.parse(src_bytes)
    except Exception:
        return None, None

    for fn_node in _find_all_ts_nodes(tree.root_node, {'function_definition'}):
        body = fn_node.child_by_field_name('body')
        if body is None:
            continue
        decl = fn_node.child_by_field_name('declarator')
        if decl is None:
            continue
        # 从 declarator 文本中提取函数名（取 '(' 之前最后一个标识符）
        decl_text   = _ts_text(decl, src_bytes)
        before_paren = decl_text.split('(')[0]
        words = re.findall(r'[a-zA-Z_]\w*', before_paren)
        if words and words[-1] == func_name:
            return body, src_bytes

    return None, None


def _ts_is_early_exit(node, src: bytes) -> bool:
    """判断一个语句节点是否构成早退（包含 return / goto）。"""
    text = _ts_text(node, src)
    return bool(re.search(r'\b(?:return|goto)\b', text))


# ==================================================================
# §4  C/C++ tree-sitter SA
# ==================================================================

def _sa_c_precondition(source: str, func_name: str, language: str) -> dict:
    """
    C/C++ 前置条件 SA（tree-sitter 优先，正则补充）。

    策略：
      - 扫描函数体前 40% 的直接子语句（最少 6 条）
      - 收集有早退语义的 if_statement（guard）
      - 收集 assert / MZ_ASSERT 等断言调用
      - 按条件类型分类（null check / range / state / other）
    """
    body, src_bytes = _ts_get_func_body(source, func_name, language)

    guard_conditions: list[str] = []
    asserts:          list[str] = []
    state_checks:     list[str] = []
    raw_guards:       list[str] = []

    if body is not None:
        children = [c for c in body.children
                    if c.type not in ('{', '}', 'comment')]
        scan_n = max(6, int(len(children) * 0.40))

        for stmt in children[:scan_n]:
            stmt_text = _ts_text(stmt, src_bytes).strip()

            # ── if_statement 守卫 ─────────────────────────────────
            if stmt.type == 'if_statement':
                cond_node = stmt.child_by_field_name('condition')
                if cond_node is None:
                    continue
                cond = _ts_text(cond_node, src_bytes).strip()

                if _ts_is_early_exit(stmt, src_bytes):
                    # 分类
                    if re.search(
                        r'==\s*(?:NULL|Z_NULL|nullptr|0)\b'
                        r'|!=\s*(?:NULL|Z_NULL|nullptr)\b'
                        r'|!\s*[a-zA-Z_]',
                        cond
                    ):
                        guard_conditions.append(f'null/zero check: {cond[:120]}')
                    elif re.search(r'[<>]=?\s*\d', cond):
                        guard_conditions.append(f'range check: {cond[:120]}')
                    elif re.search(
                        r'\b(?:status|state|mode|type|initialized|ready|level|'
                        r'avail_in|avail_out|next_in|next_out)\b',
                        cond, re.I
                    ):
                        state_checks.append(f'state check: {cond[:120]}')
                    else:
                        guard_conditions.append(f'guard: {cond[:120]}')

                    raw_guards.append(stmt_text[:240])

            # ── assert / 断言宏 ───────────────────────────────────
            elif stmt.type == 'expression_statement':
                expr_text = stmt_text.rstrip(';')
                m = re.match(
                    r'\b((?:assert|MZ_ASSERT|ASSERT|VERIFY|MINIZIP_ASSERT)'
                    r'\s*\((.+)\))\s*$',
                    expr_text, re.DOTALL
                )
                if m:
                    asserts.append(m.group(2).strip()[:120])

    # 正则补充（捕捉 tree-sitter 可能遗漏的多行条件）
    else:
        for m in _RE_C_NULL_GUARD.finditer(source):
            cond = m.group(1).strip()[:120]
            entry = f'null check: {cond}'
            if entry not in guard_conditions:
                guard_conditions.append(entry)
        for m in _RE_C_RANGE_GUARD.finditer(source):
            cond = m.group(1).strip()[:120]
            entry = f'range check: {cond}'
            if entry not in guard_conditions:
                guard_conditions.append(entry)
        for m in _RE_ASSERT.finditer(source):
            entry = m.group(1).strip()[:100]
            if entry not in asserts:
                asserts.append(entry)

    result: dict = {}
    if guard_conditions:
        result['guard_conditions'] = list(dict.fromkeys(guard_conditions))[:10]
    if asserts:
        result['asserts'] = list(dict.fromkeys(asserts))[:6]
    if state_checks:
        result['state_checks'] = list(dict.fromkeys(state_checks))[:6]
    if raw_guards:
        result['raw_guards'] = raw_guards[:6]
    return result


def _sa_c_postcondition(source: str, func_name: str, language: str) -> dict:
    """
    C/C++ 后置条件 SA（tree-sitter 优先）。

    提取：return 值集合、输出参数写回、内存分配、状态字段变更。
    """
    body, src_bytes = _ts_get_func_body(source, func_name, language)

    return_values:    list[str] = []
    output_writes:    list[str] = []
    alloc_calls:      list[str] = []
    state_mutations:  list[str] = []

    if body is not None:
        # return 值
        for ret in _find_all_ts_nodes(body, {'return_statement'}):
            ret_text = _ts_text(ret, src_bytes).strip()
            m = re.match(r'return\s+(.+?)\s*;', ret_text, re.DOTALL)
            if m:
                val = re.sub(r'\s+', ' ', m.group(1).strip())[:100]
                if val and val not in return_values:
                    return_values.append(val)

        # 赋值表达式
        for assign in _find_all_ts_nodes(body, {'assignment_expression'}):
            assign_text = _ts_text(assign, src_bytes).strip()

            # 解引用赋值 (*param = ...)
            if re.match(r'\*\s*[a-zA-Z_]', assign_text):
                short = assign_text[:100]
                if short not in output_writes:
                    output_writes.append(short)

            # 结构体字段赋值 (ptr->field = ...)
            elif re.match(r'[a-zA-Z_]\w*\s*->\s*[a-zA-Z_]', assign_text):
                short = assign_text[:100]
                if short not in state_mutations and len(state_mutations) < 8:
                    state_mutations.append(short)

        # 内存分配调用
        for call in _find_all_ts_nodes(body, {'call_expression'}):
            call_text = _ts_text(call, src_bytes).strip()
            if re.match(
                r'(?:malloc|calloc|realloc|ZALLOC|zmalloc|zalloc|'
                r'strdup|mz_stream_alloc)\s*\(',
                call_text
            ):
                short = call_text[:80]
                if short not in alloc_calls:
                    alloc_calls.append(short)

    else:
        # 正则兜底
        for m in _RE_RETURN.finditer(source):
            val = m.group(1).strip()[:100]
            if val not in return_values:
                return_values.append(val)
        for m in _RE_DEREF_ASSIGN.finditer(source):
            entry = f'*{m.group(1)} = {m.group(2).strip()}'[:100]
            if entry not in output_writes:
                output_writes.append(entry)
        for m in _RE_ALLOC_CALL.finditer(source):
            name = m.group(1).strip()
            if name not in alloc_calls:
                alloc_calls.append(name)

    result: dict = {}
    if return_values:
        result['return_values'] = list(dict.fromkeys(return_values))[:10]
    if output_writes:
        result['output_writes'] = output_writes[:6]
    if alloc_calls:
        result['allocation_calls'] = alloc_calls[:4]
    if state_mutations:
        result['state_mutations'] = state_mutations[:6]
    return result


def _sa_c_exception(source: str, func_name: str, language: str) -> dict:
    """
    C/C++ 异常/错误处理 SA（tree-sitter 优先）。

    提取：错误返回值、goto 清理、已检查调用、未检查调用、errno 使用。
    """
    body, src_bytes = _ts_get_func_body(source, func_name, language)

    error_returns:     list[str] = []
    goto_labels:       list[str] = []
    error_checks:      list[str] = []
    unchecked_calls:   list[str] = []
    errno_assignments: list[str] = []

    if body is not None:
        # 错误返回
        for ret in _find_all_ts_nodes(body, {'return_statement'}):
            ret_text = _ts_text(ret, src_bytes).strip()
            if _RE_ERROR_CODE.search(ret_text):
                short = ret_text[:120]
                if short not in error_returns:
                    error_returns.append(short)

        # goto 语句（通常是错误清理跳转）
        for goto in _find_all_ts_nodes(body, {'goto_statement'}):
            label = _ts_text(goto, src_bytes).strip()[:80]
            if label not in goto_labels:
                goto_labels.append(label)

        # if 语句中的错误检查模式
        for if_node in _find_all_ts_nodes(body, {'if_statement'}):
            cond_node = if_node.child_by_field_name('condition')
            if cond_node is None:
                continue
            cond      = _ts_text(cond_node, src_bytes).strip()
            conseq    = if_node.child_by_field_name('consequence')
            if conseq and _ts_is_early_exit(if_node, src_bytes):
                # 条件中引用常见错误变量
                if re.search(
                    r'\b(?:ret|err|status|rc|result|rv|retval|'
                    r'err_code|error|res)\b.*[!=<>]',
                    cond
                ):
                    entry = f'if ({cond[:80]}) → error exit'
                    if entry not in error_checks:
                        error_checks.append(entry)

        # 未检查的高风险调用（expression_statement 且调用名在黑名单中）
        for expr_stmt in [c for c in body.children
                          if c.type == 'expression_statement']:
            expr = _ts_text(expr_stmt, src_bytes).strip().rstrip(';')
            m = re.match(r'([a-zA-Z_]\w*)\s*\(', expr)
            if m and m.group(1) in _RISKY_UNCHECKED:
                short = expr[:100]
                if short not in unchecked_calls:
                    unchecked_calls.append(short)

        # errno 赋值
        for assign in _find_all_ts_nodes(body, {'assignment_expression'}):
            assign_text = _ts_text(assign, src_bytes).strip()
            if re.match(r'\berrno\s*=', assign_text):
                short = assign_text[:80]
                if short not in errno_assignments:
                    errno_assignments.append(short)

    else:
        # 正则兜底
        for m in _RE_RETURN.finditer(source):
            val = m.group(1).strip()
            if _RE_ERROR_CODE.search(val):
                entry = f'return {val}'[:100]
                if entry not in error_returns:
                    error_returns.append(entry)
        for m in _RE_GOTO.finditer(source):
            label = f'goto {m.group(1)}'
            if label not in goto_labels:
                goto_labels.append(label)
        for m in _RE_ERRNO.finditer(source):
            entry = f'errno = {m.group(1)}'
            if entry not in errno_assignments:
                errno_assignments.append(entry)

    result: dict = {}
    if error_returns:
        result['error_returns'] = list(dict.fromkeys(error_returns))[:8]
    if goto_labels:
        result['goto_cleanup'] = list(dict.fromkeys(goto_labels))[:5]
    if error_checks:
        result['error_checks'] = error_checks[:6]
    if unchecked_calls:
        result['unchecked_calls'] = unchecked_calls[:4]
    if errno_assignments:
        result['errno_usage'] = list(dict.fromkeys(errno_assignments))[:4]
    return result


# ==================================================================
# §5  Python AST SA
# ==================================================================

def _py_find_target(source: str, func_name: str):
    """用 ast 找到目标函数节点，失败返回 None。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == func_name):
            return node
    return None


def _sa_python_precondition(source: str, func_name: str) -> dict:
    fn = _py_find_target(source, func_name)
    if fn is None:
        return {}

    guard_conditions: list[str] = []
    asserts:          list[str] = []
    scan_n = max(4, int(len(fn.body) * 0.35))

    for stmt in fn.body[:scan_n]:
        if isinstance(stmt, ast.If):
            is_early = any(isinstance(s, (ast.Return, ast.Raise))
                           for s in stmt.body)
            if is_early:
                try:
                    cond = ast.unparse(stmt.test)
                    guard_conditions.append(f'guard: {cond[:120]}')
                except Exception:
                    pass
        elif isinstance(stmt, ast.Assert):
            try:
                cond = ast.unparse(stmt.test)
                asserts.append(cond[:120])
            except Exception:
                pass

    result: dict = {}
    if guard_conditions:
        result['guard_conditions'] = guard_conditions
    if asserts:
        result['asserts'] = asserts
    return result


def _sa_python_postcondition(source: str, func_name: str) -> dict:
    fn = _py_find_target(source, func_name)
    if fn is None:
        return {}

    return_values: list[str] = []
    yield_values:  list[str] = []

    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and node.value is not None:
            try:
                val = ast.unparse(node.value)[:100]
                if val not in return_values:
                    return_values.append(val)
            except Exception:
                pass
        elif isinstance(node, ast.Yield) and node.value is not None:
            try:
                val = ast.unparse(node.value)[:100]
                if val not in yield_values:
                    yield_values.append(val)
            except Exception:
                pass

    result: dict = {}
    if return_values:
        result['return_values'] = list(dict.fromkeys(return_values))[:10]
    if yield_values:
        result['yield_values'] = yield_values[:4]
    return result


def _sa_python_exception(source: str, func_name: str) -> dict:
    fn = _py_find_target(source, func_name)
    if fn is None:
        return {}

    raises:    list[str] = []
    handlers:  list[str] = []
    err_rets:  list[str] = []

    for node in ast.walk(fn):
        if isinstance(node, ast.Raise):
            try:
                exc = ast.unparse(node.exc) if node.exc else 're-raise'
                if exc not in raises:
                    raises.append(exc[:100])
            except Exception:
                pass
        elif isinstance(node, ast.ExceptHandler):
            try:
                exc_type = ast.unparse(node.type) if node.type else 'Exception'
                entry    = f'catches {exc_type}'
                if entry not in handlers:
                    handlers.append(entry)
            except Exception:
                pass
        elif isinstance(node, ast.Return) and node.value is not None:
            try:
                val = ast.unparse(node.value)
                if re.search(r'\b(?:None|False|-1|error|err|_error)\b', val, re.I):
                    short = val[:100]
                    if short not in err_rets:
                        err_rets.append(short)
            except Exception:
                pass

    result: dict = {}
    if raises:
        result['raises'] = raises[:6]
    if handlers:
        result['exception_handlers'] = list(dict.fromkeys(handlers))[:6]
    if err_rets:
        result['error_returns'] = err_rets[:6]
    return result


# ==================================================================
# §6  通用正则 SA（兜底，语言无关）
# ==================================================================

def _sa_regex_precondition(source: str) -> dict:
    guards: list[str] = []
    asserts: list[str] = []
    for m in _RE_C_NULL_GUARD.finditer(source):
        e = f'null check: {m.group(1).strip()[:120]}'
        if e not in guards:
            guards.append(e)
    for m in _RE_C_RANGE_GUARD.finditer(source):
        e = f'range check: {m.group(1).strip()[:120]}'
        if e not in guards:
            guards.append(e)
    for m in _RE_ASSERT.finditer(source):
        e = m.group(1).strip()[:100]
        if e not in asserts:
            asserts.append(e)
    result: dict = {}
    if guards:
        result['guard_conditions'] = guards[:8]
    if asserts:
        result['asserts'] = asserts[:6]
    return result


def _sa_regex_postcondition(source: str) -> dict:
    rets: list[str] = []
    outs: list[str] = []
    allocs: list[str] = []
    for m in _RE_RETURN.finditer(source):
        v = m.group(1).strip()[:100]
        if v and v not in rets:
            rets.append(v)
    for m in _RE_DEREF_ASSIGN.finditer(source):
        e = f'*{m.group(1)} = {m.group(2).strip()}'[:100]
        if e not in outs:
            outs.append(e)
    for m in _RE_ALLOC_CALL.finditer(source):
        n = m.group(1).strip()
        if n not in allocs:
            allocs.append(n)
    result: dict = {}
    if rets:
        result['return_values'] = list(dict.fromkeys(rets))[:10]
    if outs:
        result['output_writes'] = outs[:6]
    if allocs:
        result['allocation_calls'] = allocs[:4]
    return result


def _sa_regex_exception(source: str) -> dict:
    err_rets: list[str] = []
    gotos: list[str] = []
    errnos: list[str] = []
    for m in _RE_RETURN.finditer(source):
        val = m.group(1).strip()
        if _RE_ERROR_CODE.search(val):
            e = f'return {val}'[:100]
            if e not in err_rets:
                err_rets.append(e)
    for m in _RE_GOTO.finditer(source):
        e = f'goto {m.group(1)}'
        if e not in gotos:
            gotos.append(e)
    for m in _RE_ERRNO.finditer(source):
        e = f'errno = {m.group(1)}'
        if e not in errnos:
            errnos.append(e)
    result: dict = {}
    if err_rets:
        result['error_returns'] = list(dict.fromkeys(err_rets))[:8]
    if gotos:
        result['goto_cleanup'] = gotos[:5]
    if errnos:
        result['errno_usage'] = errnos[:4]
    return result


# ==================================================================
# §7  SA 分发器
# ==================================================================

def _run_sa(
    kind: str,       # 'precondition' | 'postcondition' | 'exception'
    source: str,
    func_name: str,
    language: str,
) -> dict:
    """
    根据语言选择最优 SA 策略，返回结构化特征字典。
    C/C++ 优先 tree-sitter，Python 优先 ast，其他语言用正则。
    """
    is_c_like = language in ('C', 'C++', 'Objective-C')
    is_python  = language == 'Python'

    if kind == 'precondition':
        if is_c_like and _TREE_SITTER_OK:
            ts  = _sa_c_precondition(source, func_name, language)
            rg  = _sa_regex_precondition(source)
            return {**rg, **ts}           # ts 优先覆盖
        if is_python:
            py = _sa_python_precondition(source, func_name)
            rg = _sa_regex_precondition(source)
            return {**rg, **py}
        return _sa_regex_precondition(source)

    if kind == 'postcondition':
        if is_c_like and _TREE_SITTER_OK:
            ts  = _sa_c_postcondition(source, func_name, language)
            rg  = _sa_regex_postcondition(source)
            return {**rg, **ts}
        if is_python:
            py = _sa_python_postcondition(source, func_name)
            rg = _sa_regex_postcondition(source)
            return {**rg, **py}
        return _sa_regex_postcondition(source)

    if kind == 'exception':
        if is_c_like and _TREE_SITTER_OK:
            ts  = _sa_c_exception(source, func_name, language)
            rg  = _sa_regex_exception(source)
            return {**rg, **ts}
        if is_python:
            py = _sa_python_exception(source, func_name)
            rg = _sa_regex_exception(source)
            return {**rg, **py}
        return _sa_regex_exception(source)

    return {}


# ==================================================================
# §8  analyze_func_summary —— 单次 LLM 调用生成所有函数摘要字段
# ==================================================================

def analyze_func_summary(
    repo_id: int,
    db_path: Optional[str] = None,
    func_ids: Optional[list[int]] = None,
    skip_if_exists: bool = True,
    languages: Optional[list[str]] = None,
) -> dict[int, dict]:
    """
    SA + LLM 一次调用，同时生成函数的 precondition / postcondition /
    exception / description，合并写入对应 func 表字段。

    Parameters
    ----------
    repo_id         : 目标仓库 id
    db_path         : SQLite 路径；不传则用 config.DB_PATH
    func_ids        : 指定函数 id 列表；None 则处理全部函数
    skip_if_exists  : True = 跳过四个字段均已存在的函数（增量处理）
    languages       : 语言白名单；None 则不过滤

    Returns
    -------
    dict[int, dict]
        {func_id → {"precondition": [...], "postcondition": [...],
                     "exception": [...], "description": "..."}}

    Raises
    ------
    ValueError  repo_id 不存在
    """
    from llm.client  import chat_completion_json
    from llm.prompts import ANALYZE_FUNC_SUMMARY_SYSTEM, ANALYZE_FUNC_SUMMARY_USER
    import config as _cfg

    _db   = db_path or DB_PATH
    label = '[analyze_func_summary]'

    # ── 取仓库信息 ──────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f'{label} repo_id={repo_id} 在数据库中不存在。')

    repo_path = repo['path']
    repo_name = repo['name']
    print(f'{label} 目标仓库：{repo_name}（{repo_path}）')

    # ── 构建文件语言映射 ─────────────────────────────────────────
    all_files = FileDB.list_by_repo(repo_id, db_path=_db)
    file_map  = {f['id']: f for f in all_files}

    # ── 取函数列表并过滤 ─────────────────────────────────────────
    all_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)

    if func_ids is not None:
        id_set    = set(func_ids)
        all_funcs = [f for f in all_funcs if f['id'] in id_set]

    if languages:
        lang_set  = set(languages)
        all_funcs = [
            f for f in all_funcs
            if (file_map.get(f['file_id']) or {}).get('language', 'Unknown')
               in lang_set
        ]

    if skip_if_exists:
        before    = len(all_funcs)
        all_funcs = [
            f for f in all_funcs
            if not (
                f.get('precondition') and
                f.get('postcondition') and
                f.get('exception') and
                f.get('description')
            )
        ]
        skipped_cnt = before - len(all_funcs)
        if skipped_cnt:
            print(f'{label} 跳过已有完整摘要的函数：{skipped_cnt} 个')

    total   = len(all_funcs)
    print(
        f'{label} 待处理函数：{total} 个'
        f'（模型：{_cfg.LLM_MODEL}，tree-sitter={"可用" if _TREE_SITTER_OK else "不可用"}）'
    )

    result:  dict[int, dict] = {}
    success = error = skipped = 0

    for idx, fn_rec in enumerate(all_funcs, start=1):
        func_id   = fn_rec['id']
        func_name = fn_rec['name']
        file_id   = fn_rec.get('file_id')

        file_rec  = file_map.get(file_id) if file_id else None
        language  = (file_rec or {}).get('language', 'Unknown')

        # 解析 place
        place = fn_rec.get('place') or {}
        if isinstance(place, str):
            try:
                place = _json.loads(place)
            except Exception:
                place = {}

        rel_path   = place.get('file_path', '')
        start_line = int(place.get('start_line', 0))
        end_line   = int(place.get('end_line', 0))

        if not rel_path or start_line <= 0:
            skipped += 1
            result[func_id] = {}
            continue

        # 读取函数源码
        source = _read_func_source(repo_path, rel_path, start_line, end_line)
        if source is None:
            print(f'{label}   ⚠ 无法读取源码：{rel_path}:{start_line}，跳过')
            skipped += 1
            result[func_id] = {}
            continue

        # 运行三个维度的 SA，合并提供给 LLM
        try:
            sa_pre  = _run_sa('precondition',  source, func_name, language)
            sa_post = _run_sa('postcondition', source, func_name, language)
            sa_exc  = _run_sa('exception',     source, func_name, language)
            sa_combined: dict = {}
            if sa_pre:  sa_combined['precondition_hints']  = sa_pre
            if sa_post: sa_combined['postcondition_hints'] = sa_post
            if sa_exc:  sa_combined['exception_hints']     = sa_exc
        except Exception as exc:
            print(f'{label}   ⚠ SA 失败（{func_name}）：{exc}，以空 SA 继续')
            sa_combined = {}

        # 准备 prompt 参数
        interface = fn_rec.get('interface') or {}
        if isinstance(interface, str):
            try:
                interface = _json.loads(interface)
            except Exception:
                interface = {}

        params_text  = _format_params(interface.get('params', []))
        return_type  = (interface.get('returns') or {}).get('type', '') or ''
        source_trunc = source[:_MAX_SOURCE_IN_PROMPT]
        if len(source) > _MAX_SOURCE_IN_PROMPT:
            source_trunc += f'\n... (源码截断，原长 {len(source)} 字符)'

        user_content = ANALYZE_FUNC_SUMMARY_USER.format(
            func_name   = func_name,
            language    = language,
            signature   = str(fn_rec.get('signature', '') or '')[:300],
            params      = params_text,
            return_type = return_type,
            sa_results  = _json.dumps(sa_combined, ensure_ascii=False, indent=2),
            source_code = source_trunc,
        )

        messages = [
            {'role': 'system', 'content': ANALYZE_FUNC_SUMMARY_SYSTEM},
            {'role': 'user',   'content': user_content},
        ]

        # ── LLM 调用（含重试）──────────────────────────────────
        last_exc = None
        call_ok  = False

        for attempt in range(1, _LLM_MAX_RETRIES + 1):
            try:
                raw = chat_completion_json(messages=messages, temperature=0.1)

                def _to_list(val) -> list[str]:
                    if isinstance(val, list):
                        return [str(x).strip() for x in val if x and str(x).strip()]
                    return [str(val).strip()] if val and str(val).strip() else []

                if isinstance(raw, dict):
                    precondition  = _to_list(raw.get('precondition'))
                    postcondition = _to_list(raw.get('postcondition'))
                    exception     = _to_list(raw.get('exception'))
                    description   = str(raw.get('description', '') or '').strip()
                else:
                    precondition = postcondition = exception = []
                    description  = ''

                FuncDB.update(
                    func_id,
                    db_path       = _db,
                    precondition  = precondition,
                    postcondition = postcondition,
                    exception     = exception,
                    description   = description,
                )

                result[func_id] = {
                    'precondition':  precondition,
                    'postcondition': postcondition,
                    'exception':     exception,
                    'description':   description,
                }
                success += 1
                call_ok  = True
                break

            except Exception as exc:
                last_exc = exc
                if attempt < _LLM_MAX_RETRIES:
                    wait = _LLM_RETRY_DELAYS[attempt - 1]
                    print(
                        f'{label}   ↻ LLM 失败 第{attempt}/{_LLM_MAX_RETRIES}次'
                        f'（func_id={func_id} {func_name}）：{exc}'
                        f'，{wait}s 后重试…'
                    )
                    time.sleep(wait)
                else:
                    print(
                        f'{label}   ✗ LLM 已放弃'
                        f'（func_id={func_id} {func_name}）：{last_exc}'
                    )

        if not call_ok:
            error += 1
            result[func_id] = {}
            try:
                FuncDB.update(
                    func_id, db_path=_db,
                    precondition=[], postcondition=[], exception=[], description='',
                )
            except Exception as we:
                print(f'{label}   ⚠ 写库失败（func_id={func_id}）：{we}')

        # 进度日志
        if idx % 10 == 0 or idx == total:
            print(
                f'{label}   进度 {idx}/{total}  '
                f'✓={success}  ✗={error}  skip={skipped}'
            )

    print(
        f'{label} ✓ 完成：\n'
        f'  总处理  : {total}\n'
        f'  写库成功 : {success}\n'
        f'  LLM失败  : {error}\n'
        f'  跳过     : {skipped}'
    )
    return result