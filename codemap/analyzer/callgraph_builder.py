"""
Builds a static function call graph.
Features:
- Build repository call graph.
- Save/load call graph as JSON.
- Update function callgraph in the database.
Analysis priority:
Python AST -> Tree-sitter -> Regex fallback.

"""
import ast
import json as _json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, FileDB, FuncDB
from config import DB_PATH, DATA_DIR


# ==================================================================
# 0. check tree-sitter
# ==================================================================

try:
    from tree_sitter_languages import get_parser as _ts_get_parser
    _ts_get_parser('c')
    _TREE_SITTER_OK = True
except Exception:
    _TREE_SITTER_OK = False


# ==================================================================
# 1. constant
# ==================================================================

_C_KEYWORDS: frozenset[str] = frozenset({
    'if', 'else', 'while', 'for', 'do', 'switch', 'case',
    'break', 'continue', 'return', 'goto', 'default',
    'sizeof', 'alignof', 'typeof', '_Alignof', '_Generic',
    '__typeof__', '__typeof', '__sizeof__',
    '__builtin_expect', '__builtin_unreachable',
    '__builtin_offsetof', '__builtin_constant_p',
    '__builtin_va_start', '__builtin_va_end', '__builtin_va_arg',
    'NULL', 'TRUE', 'FALSE', 'true', 'false', 'nullptr',
    'offsetof', 'container_of', 'likely', 'unlikely',
    'static_assert', '_Static_assert',
    'new', 'delete', 'throw', 'catch', 'try',
    'typeid', 'decltype', 'noexcept', 'constexpr',
    '__declspec', '__cdecl', '__stdcall', '__fastcall',
    'int', 'char', 'short', 'long', 'float', 'double',
    'void', 'unsigned', 'signed', 'bool', 'auto',
    'const', 'volatile', 'register', 'static', 'extern', 'inline',
    'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
    'int8_t', 'int16_t', 'int32_t', 'int64_t',
    'size_t', 'ssize_t', 'off_t', 'ptrdiff_t', 'uintptr_t', 'intptr_t',
    'BOOL', 'BYTE', 'WORD', 'DWORD', 'QWORD', 'HANDLE',
})

_C_CALL_RE = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')

_STDLIB_HEADER: dict[str, str] = {
    # ── stdio.h ──
    'printf': 'stdio.h', 'fprintf': 'stdio.h', 'sprintf': 'stdio.h',
    'snprintf': 'stdio.h', 'vprintf': 'stdio.h', 'vfprintf': 'stdio.h',
    'vsprintf': 'stdio.h', 'vsnprintf': 'stdio.h',
    'scanf': 'stdio.h', 'fscanf': 'stdio.h', 'sscanf': 'stdio.h',
    'vfscanf': 'stdio.h', 'vsscanf': 'stdio.h', 'vscanf': 'stdio.h',
    'fopen': 'stdio.h', 'fclose': 'stdio.h',
    'fread': 'stdio.h', 'fwrite': 'stdio.h',
    'fseek': 'stdio.h', 'fseeko': 'stdio.h', 'fseeko64': 'stdio.h',
    'ftell': 'stdio.h', 'ftello': 'stdio.h', 'ftello64': 'stdio.h',
    'fflush': 'stdio.h', 'rewind': 'stdio.h',
    'feof': 'stdio.h', 'ferror': 'stdio.h', 'clearerr': 'stdio.h',
    'perror': 'stdio.h',
    'fgetc': 'stdio.h', 'fputc': 'stdio.h', 'ungetc': 'stdio.h',
    'fgets': 'stdio.h', 'fputs': 'stdio.h',
    'puts': 'stdio.h', 'putchar': 'stdio.h', 'getchar': 'stdio.h',
    'remove': 'stdio.h', 'rename': 'stdio.h',
    'tmpfile': 'stdio.h', 'tmpnam': 'stdio.h',
    'fileno': 'stdio.h', 'fdopen': 'stdio.h',
    'popen': 'stdio.h', 'pclose': 'stdio.h',
    'setvbuf': 'stdio.h', 'setbuf': 'stdio.h',
    'malloc': 'stdlib.h', 'free': 'stdlib.h',
    'calloc': 'stdlib.h', 'realloc': 'stdlib.h',
    'aligned_alloc': 'stdlib.h', 'posix_memalign': 'stdlib.h',
    'exit': 'stdlib.h', 'abort': 'stdlib.h',
    '_exit': 'unistd.h', 'atexit': 'stdlib.h',
    'at_quick_exit': 'stdlib.h', 'quick_exit': 'stdlib.h',
    'atoi': 'stdlib.h', 'atol': 'stdlib.h', 'atoll': 'stdlib.h',
    'atof': 'stdlib.h',
    'strtol': 'stdlib.h', 'strtoul': 'stdlib.h',
    'strtoll': 'stdlib.h', 'strtoull': 'stdlib.h',
    'strtof': 'stdlib.h', 'strtod': 'stdlib.h', 'strtold': 'stdlib.h',
    'rand': 'stdlib.h', 'srand': 'stdlib.h', 'rand_r': 'stdlib.h',
    'qsort': 'stdlib.h', 'qsort_r': 'stdlib.h', 'bsearch': 'stdlib.h',
    'abs': 'stdlib.h', 'labs': 'stdlib.h', 'llabs': 'stdlib.h',
    'div': 'stdlib.h', 'ldiv': 'stdlib.h', 'lldiv': 'stdlib.h',
    'getenv': 'stdlib.h', 'setenv': 'stdlib.h', 'unsetenv': 'stdlib.h',
    'putenv': 'stdlib.h', 'system': 'stdlib.h', 'realpath': 'stdlib.h',
    'mbstowcs': 'stdlib.h', 'wcstombs': 'stdlib.h',
    'memset': 'string.h', 'memcpy': 'string.h', 'memmove': 'string.h',
    'memcmp': 'string.h', 'memchr': 'string.h', 'memrchr': 'string.h',
    'strlen': 'string.h', 'strnlen': 'string.h',
    'strcpy': 'string.h', 'strncpy': 'string.h',
    'stpcpy': 'string.h', 'stpncpy': 'string.h',
    'strcat': 'string.h', 'strncat': 'string.h',
    'strcmp': 'string.h', 'strncmp': 'string.h',
    'strcasecmp': 'string.h', 'strncasecmp': 'string.h',
    'strcoll': 'string.h', 'strxfrm': 'string.h',
    'strchr': 'string.h', 'strrchr': 'string.h',
    'strstr': 'string.h', 'strcasestr': 'string.h',
    'strtok': 'string.h', 'strtok_r': 'string.h',
    'strdup': 'string.h', 'strndup': 'string.h',
    'strerror': 'string.h', 'strerror_r': 'string.h',
    'strspn': 'string.h', 'strcspn': 'string.h',
    'strpbrk': 'string.h', 'strsep': 'string.h',
    'sqrt': 'math.h', 'sqrtf': 'math.h', 'sqrtl': 'math.h',
    'cbrt': 'math.h', 'cbrtf': 'math.h',
    'pow': 'math.h', 'powf': 'math.h',
    'log': 'math.h', 'logf': 'math.h',
    'log2': 'math.h', 'log2f': 'math.h',
    'log10': 'math.h', 'log10f': 'math.h',
    'exp': 'math.h', 'expf': 'math.h',
    'exp2': 'math.h', 'exp2f': 'math.h',
    'ceil': 'math.h', 'ceilf': 'math.h',
    'floor': 'math.h', 'floorf': 'math.h',
    'round': 'math.h', 'roundf': 'math.h',
    'trunc': 'math.h', 'truncf': 'math.h',
    'fabs': 'math.h', 'fabsf': 'math.h',
    'fmod': 'math.h', 'fmodf': 'math.h',
    'fmin': 'math.h', 'fminf': 'math.h',
    'fmax': 'math.h', 'fmaxf': 'math.h',
    'sin': 'math.h', 'sinf': 'math.h',
    'cos': 'math.h', 'cosf': 'math.h',
    'tan': 'math.h', 'tanf': 'math.h',
    'asin': 'math.h', 'acos': 'math.h',
    'atan': 'math.h', 'atan2': 'math.h', 'atan2f': 'math.h',
    'sinh': 'math.h', 'cosh': 'math.h', 'tanh': 'math.h',
    'hypot': 'math.h', 'hypotf': 'math.h',
    'isnan': 'math.h', 'isinf': 'math.h', 'isfinite': 'math.h',
    'modf': 'math.h', 'frexp': 'math.h', 'ldexp': 'math.h',
    'assert': 'assert.h',
    'isalpha': 'ctype.h', 'isdigit': 'ctype.h', 'isalnum': 'ctype.h',
    'isspace': 'ctype.h', 'isupper': 'ctype.h', 'islower': 'ctype.h',
    'isprint': 'ctype.h', 'ispunct': 'ctype.h', 'isxdigit': 'ctype.h',
    'iscntrl': 'ctype.h', 'isgraph': 'ctype.h', 'isblank': 'ctype.h',
    'toupper': 'ctype.h', 'tolower': 'ctype.h',
    'time': 'time.h', 'clock': 'time.h', 'difftime': 'time.h',
    'mktime': 'time.h', 'gmtime': 'time.h', 'gmtime_r': 'time.h',
    'localtime': 'time.h', 'localtime_r': 'time.h',
    'strftime': 'time.h', 'strptime': 'time.h',
    'ctime': 'time.h', 'asctime': 'time.h',
    'nanosleep': 'time.h',
    'clock_gettime': 'time.h', 'clock_settime': 'time.h',
    'clock_getres': 'time.h',
    'read': 'unistd.h', 'write': 'unistd.h', 'close': 'unistd.h',
    'lseek': 'unistd.h', 'lseek64': 'unistd.h',
    'unlink': 'unistd.h', 'rmdir': 'unistd.h',
    'link': 'unistd.h', 'symlink': 'unistd.h', 'readlink': 'unistd.h',
    'getpid': 'unistd.h', 'getppid': 'unistd.h',
    'getuid': 'unistd.h', 'getgid': 'unistd.h',
    'geteuid': 'unistd.h', 'getegid': 'unistd.h',
    'fork': 'unistd.h', 'execv': 'unistd.h', 'execvp': 'unistd.h',
    'execve': 'unistd.h', 'execl': 'unistd.h', 'execlp': 'unistd.h',
    'sleep': 'unistd.h', 'usleep': 'unistd.h',
    'getcwd': 'unistd.h', 'chdir': 'unistd.h',
    'dup': 'unistd.h', 'dup2': 'unistd.h',
    'pipe': 'unistd.h', 'isatty': 'unistd.h',
    'access': 'unistd.h', 'truncate': 'unistd.h', 'ftruncate': 'unistd.h',
    'fsync': 'unistd.h', 'fdatasync': 'unistd.h',
    'gethostname': 'unistd.h',
    'open': 'fcntl.h', 'open64': 'fcntl.h', 'openat': 'fcntl.h',
    'creat': 'fcntl.h', 'fcntl': 'fcntl.h',
    'stat': 'sys/stat.h', 'stat64': 'sys/stat.h',
    'lstat': 'sys/stat.h', 'fstat': 'sys/stat.h', 'fstat64': 'sys/stat.h',
    'mkdir': 'sys/stat.h', 'mkdirat': 'sys/stat.h',
    'chmod': 'sys/stat.h', 'fchmod': 'sys/stat.h', 'umask': 'sys/stat.h',
    'opendir': 'dirent.h', 'closedir': 'dirent.h',
    'readdir': 'dirent.h', 'readdir_r': 'dirent.h',
    'scandir': 'dirent.h', 'rewinddir': 'dirent.h',
    'pthread_create': 'pthread.h', 'pthread_join': 'pthread.h',
    'pthread_detach': 'pthread.h', 'pthread_exit': 'pthread.h',
    'pthread_self': 'pthread.h', 'pthread_equal': 'pthread.h',
    'pthread_cancel': 'pthread.h',
    'pthread_mutex_init': 'pthread.h', 'pthread_mutex_lock': 'pthread.h',
    'pthread_mutex_trylock': 'pthread.h', 'pthread_mutex_unlock': 'pthread.h',
    'pthread_mutex_destroy': 'pthread.h',
    'pthread_cond_init': 'pthread.h', 'pthread_cond_wait': 'pthread.h',
    'pthread_cond_timedwait': 'pthread.h',
    'pthread_cond_signal': 'pthread.h', 'pthread_cond_broadcast': 'pthread.h',
    'pthread_cond_destroy': 'pthread.h',
    'pthread_rwlock_init': 'pthread.h', 'pthread_rwlock_rdlock': 'pthread.h',
    'pthread_rwlock_wrlock': 'pthread.h', 'pthread_rwlock_unlock': 'pthread.h',
    'pthread_rwlock_destroy': 'pthread.h',
    'pthread_key_create': 'pthread.h', 'pthread_key_delete': 'pthread.h',
    'pthread_setspecific': 'pthread.h', 'pthread_getspecific': 'pthread.h',
    'setjmp': 'setjmp.h', 'longjmp': 'setjmp.h',
    '_setjmp': 'setjmp.h', '_longjmp': 'setjmp.h',
    'sigsetjmp': 'setjmp.h', 'siglongjmp': 'setjmp.h',
    'signal': 'signal.h', 'raise': 'signal.h',
    'kill': 'signal.h', 'sigaction': 'signal.h',
    'sigemptyset': 'signal.h', 'sigfillset': 'signal.h',
    'sigaddset': 'signal.h', 'sigdelset': 'signal.h',
    'sigismember': 'signal.h', 'sigprocmask': 'signal.h',
    'deflateInit': 'zlib.h', 'deflateInit2': 'zlib.h', 'deflateInit2_': 'zlib.h',
    'deflate': 'zlib.h', 'deflateEnd': 'zlib.h', 'deflateReset': 'zlib.h',
    'deflateSetDictionary': 'zlib.h', 'deflateCopy': 'zlib.h',
    'deflateParams': 'zlib.h', 'deflateTune': 'zlib.h',
    'deflateBound': 'zlib.h', 'deflatePrime': 'zlib.h',
    'inflateInit': 'zlib.h', 'inflateInit2': 'zlib.h', 'inflateInit2_': 'zlib.h',
    'inflate': 'zlib.h', 'inflateEnd': 'zlib.h', 'inflateReset': 'zlib.h',
    'inflateReset2': 'zlib.h', 'inflatePrime': 'zlib.h',
    'inflateSetDictionary': 'zlib.h', 'inflateGetDictionary': 'zlib.h',
    'inflateSync': 'zlib.h', 'inflateCopy': 'zlib.h',
    'compress': 'zlib.h', 'compress2': 'zlib.h', 'compressBound': 'zlib.h',
    'uncompress': 'zlib.h', 'uncompress2': 'zlib.h',
    'adler32': 'zlib.h', 'adler32_z': 'zlib.h', 'adler32_combine': 'zlib.h',
    'crc32': 'zlib.h', 'crc32_z': 'zlib.h', 'crc32_combine': 'zlib.h',
    'zlibVersion': 'zlib.h', 'zlibCompileFlags': 'zlib.h', 'zError': 'zlib.h',
    'GetLastError': 'windows.h', 'SetLastError': 'windows.h',
    'CreateFileA': 'windows.h', 'CreateFileW': 'windows.h',
    'CloseHandle': 'windows.h', 'ReadFile': 'windows.h', 'WriteFile': 'windows.h',
    'VirtualAlloc': 'windows.h', 'VirtualFree': 'windows.h',
    'HeapAlloc': 'windows.h', 'HeapFree': 'windows.h',
    'GetProcessHeap': 'windows.h',
    'LoadLibraryA': 'windows.h', 'LoadLibraryW': 'windows.h',
    'FreeLibrary': 'windows.h', 'GetProcAddress': 'windows.h',
    'MultiByteToWideChar': 'windows.h', 'WideCharToMultiByte': 'windows.h',
}


# ==================================================================
# 2. tree-sitter tool-func
# ==================================================================

def _ts_text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode('utf-8', errors='replace')

# DFS
def _find_all_nodes(root, wanted: set) -> list:
    result, stack = [], [root]
    while stack:
        node = stack.pop()
        if node.type in wanted:
            result.append(node)
        for child in reversed(node.children):
            stack.append(child)
    return result


# ==================================================================
# 3. Extracting C/C++ function definition names
# ==================================================================

def _find_c_func_declarator(node) -> Optional[object]:
    if node is None:
        return None
    if node.type == 'function_declarator':
        return node
    wrapping = {
        'pointer_declarator', 'reference_declarator',
        'parenthesized_declarator', 'abstract_declarator',
        'abstract_pointer_declarator',
    }
    if node.type in wrapping:
        inner = node.child_by_field_name('declarator')
        if inner:
            r = _find_c_func_declarator(inner)
            if r:
                return r
        for child in node.children:
            r = _find_c_func_declarator(child)
            if r:
                return r
    return None


def _extract_c_decl_name(node, src: bytes) -> str:
    if node is None:
        return ''
    t = node.type
    if t in ('identifier', 'field_identifier'):
        return _ts_text(node, src)
    if t in ('qualified_identifier', 'destructor_name',
             'operator_name', 'template_function', 'template_method'):
        return _ts_text(node, src)
    if t in ('pointer_declarator', 'reference_declarator'):
        inner = node.child_by_field_name('declarator')
        if inner:
            return _extract_c_decl_name(inner, src)
    if t == 'parenthesized_declarator':
        for child in node.children:
            r = _extract_c_decl_name(child, src)
            if r:
                return r
    for child in node.children:
        r = _extract_c_decl_name(child, src)
        if r:
            return r
    return _ts_text(node, src)


def _get_c_func_name(func_def_node, src: bytes) -> Optional[str]:
    declarator = func_def_node.child_by_field_name('declarator')
    if declarator is None:
        return None
    func_decl = _find_c_func_declarator(declarator)
    if func_decl is None:
        return None
    inner = func_decl.child_by_field_name('declarator')
    if inner is None:
        return None
    name = _extract_c_decl_name(inner, src).strip()
    return name or None


# ==================================================================
# 4. callee name extraction
# ==================================================================

def _get_callee_name_c(func_field, src: bytes) -> Optional[str]:
    t = func_field.type

    if t == 'identifier':
        name = _ts_text(func_field, src).strip()
        return name if name not in _C_KEYWORDS else None

    if t == 'field_expression':
        field = func_field.child_by_field_name('field')
        if field:
            return _ts_text(field, src).strip() or None
        return None

    if t == 'qualified_identifier':
        text = _ts_text(func_field, src).strip()
        return text or None

    if t == 'template_function':
        name_node = func_field.child_by_field_name('name')
        if name_node:
            return _ts_text(name_node, src).strip() or None
        for child in func_field.children:
            if child.type == 'qualified_identifier':
                return _get_callee_name_c(child, src)
        return None

    if t in (
        'parenthesized_expression', 'pointer_expression',
        'subscript_expression', 'conditional_expression',
        'binary_expression', 'cast_expression',
        'unary_expression', 'comma_expression',
    ):
        return None

    for child in func_field.children:
        if child.type == 'identifier':
            name = _ts_text(child, src).strip()
            if name and name not in _C_KEYWORDS:
                return name

    return None


def _get_callee_name_generic(call_node, src: bytes, ts_lang: str) -> Optional[str]:
    func_field = call_node.child_by_field_name('function')
    if func_field:
        t = func_field.type
        if t in ('identifier', 'simple_identifier'):
            return _ts_text(func_field, src).strip() or None
        if t in ('field_expression', 'member_expression',
                 'selector_expression', 'dot_expression'):
            for fn in ('field', 'name', 'selector', 'attribute'):
                n = func_field.child_by_field_name(fn)
                if n:
                    return _ts_text(n, src).strip() or None
        if t in ('qualified_identifier', 'scoped_identifier',
                 'scope_resolution', 'type_qualified'):
            text = _ts_text(func_field, src).strip()
            parts = re.split(r'[:./]+', text)
            return parts[-1].strip() if parts else None
        def _dfs(n, d=0):
            if d > 3:
                return None
            if n.type in ('identifier', 'simple_identifier', 'type_identifier'):
                return _ts_text(n, src).strip() or None
            for ch in n.children:
                r = _dfs(ch, d + 1)
                if r:
                    return r
            return None
        r = _dfs(func_field)
        if r:
            return r

    name_field = call_node.child_by_field_name('name')
    if name_field:
        return _ts_text(name_field, src).strip() or None

    macro_field = call_node.child_by_field_name('macro')
    if macro_field:
        return _ts_text(macro_field, src).strip() or None

    return None


# ==================================================================
# 5. File-level call relationship extraction 
# ==================================================================

def _read_source_for_callgraph(abs_path: str) -> Optional[str]:
    try:
        if os.path.getsize(abs_path) > 5 * 1024 * 1024:
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


def _build_name_line_index(db_funcs: list[dict]) -> tuple[
    dict[tuple[str, int], int],
    dict[str, list[int]],
]:
    name_line_to_id: dict[tuple[str, int], int] = {}
    name_to_ids: dict[str, list[int]] = defaultdict(list)
    for fn in db_funcs:
        place = fn.get('place', {})
        if not isinstance(place, dict):
            continue
        sl   = place.get('start_line', 0)
        name = fn['name']
        fid  = fn['id']
        name_line_to_id[(name, sl)] = fid
        name_to_ids[name].append(fid)
    return name_line_to_id, name_to_ids


def _resolve_caller_id(
    func_name: str,
    start_line: int,
    name_line_to_id: dict,
    name_to_ids: dict,
) -> Optional[int]:
    fid = name_line_to_id.get((func_name, start_line))
    if fid is not None:
        return fid
    for delta in (-1, 1, -2, 2):
        fid = name_line_to_id.get((func_name, start_line + delta))
        if fid is not None:
            return fid
    ids = name_to_ids.get(func_name, [])
    if len(ids) == 1:
        return ids[0]
    return None

def _extract_c_file_calls(
    source: str,
    db_funcs: list[dict],
    language: str,
) -> list[tuple[int, str]]:
    if not _TREE_SITTER_OK:
        return []

    ts_name = 'cpp' if language in ('C++', 'Objective-C') else 'c'
    src_bytes = source.encode('utf-8', errors='replace')
    try:
        parser = _ts_get_parser(ts_name)
        tree   = parser.parse(src_bytes)
    except Exception as e:
        print(f"  [callgraph/_extract_c] tree-sitter Parsing failed（{ts_name}）: {e}")
        return []

    name_line_to_id, name_to_ids = _build_name_line_index(db_funcs)
    results: list[tuple[int, str]] = []

    for func_node in _find_all_nodes(tree.root_node, {'function_definition'}):
        body = func_node.child_by_field_name('body')
        if body is None:
            continue

        start_line = func_node.start_point[0] + 1
        func_name  = _get_c_func_name(func_node, src_bytes)
        if not func_name:
            continue

        caller_id = _resolve_caller_id(func_name, start_line, name_line_to_id, name_to_ids)
        if caller_id is None:
            continue

        seen: set[str] = set()
        for call_node in _find_all_nodes(body, {'call_expression'}):
            func_field = call_node.child_by_field_name('function')
            if func_field is None:
                continue
            callee = _get_callee_name_c(func_field, src_bytes)
            if callee and callee not in seen:
                seen.add(callee)
                results.append((caller_id, callee))

    return results

def _extract_python_file_calls(
    source: str,
    rel_path: str,
    db_funcs: list[dict],
) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError:
        return []

    name_line_to_id, name_to_ids = _build_name_line_index(db_funcs)
    results: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        caller_id = _resolve_caller_id(
            node.name, node.lineno, name_line_to_id, name_to_ids
        )
        if caller_id is None:
            continue

        seen: set[str] = set()
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if isinstance(child.func, ast.Name):
                callee = child.func.id
            elif isinstance(child.func, ast.Attribute):
                callee = child.func.attr
            else:
                continue
            if callee and callee not in seen:
                seen.add(callee)
                results.append((caller_id, callee))

    return results

_LANG_TS_TYPES: dict[str, tuple[set, set]] = {
    'java':       (
        {'method_declaration', 'constructor_declaration'},
        {'method_invocation', 'object_creation_expression'},
    ),
    'javascript': (
        {'function_declaration', 'method_definition', 'function_expression',
         'arrow_function', 'generator_function_declaration'},
        {'call_expression', 'new_expression'},
    ),
    'typescript': (
        {'function_declaration', 'method_definition', 'function_expression',
         'arrow_function', 'generator_function_declaration'},
        {'call_expression', 'new_expression'},
    ),
    'go':         (
        {'function_declaration', 'method_declaration'},
        {'call_expression'},
    ),
    'rust':       (
        {'function_item'},
        {'call_expression', 'macro_invocation'},
    ),
    'ruby':       (
        {'method', 'singleton_method'},
        {'call', 'method_call'},
    ),
    'kotlin':     (
        {'function_declaration'},
        {'call_expression', 'constructor_invocation'},
    ),
    'swift':      (
        {'function_declaration'},
        {'call_expression', 'explicit_member_expression'},
    ),
}

_LANG_TO_TS_NAME: dict[str, str] = {
    'Java': 'java', 'JavaScript': 'javascript', 'TypeScript': 'typescript',
    'Go': 'go', 'Rust': 'rust', 'Ruby': 'ruby',
    'Kotlin': 'kotlin', 'Swift': 'swift',
}


def _extract_generic_ts_file_calls(
    source: str,
    db_funcs: list[dict],
    ts_lang: str,
) -> list[tuple[int, str]]:
    if not _TREE_SITTER_OK:
        return []

    func_types, call_types = _LANG_TS_TYPES.get(ts_lang, (set(), set()))
    if not func_types or not call_types:
        return []

    src_bytes = source.encode('utf-8', errors='replace')
    try:
        parser = _ts_get_parser(ts_lang)
        tree   = parser.parse(src_bytes)
    except Exception:
        return []

    name_line_to_id, name_to_ids = _build_name_line_index(db_funcs)
    results: list[tuple[int, str]] = []

    for func_node in _find_all_nodes(tree.root_node, func_types):
        start_line = func_node.start_point[0] + 1

        name_node = func_node.child_by_field_name('name')
        func_name = _ts_text(name_node, src_bytes).strip() if name_node else ''
        if not func_name:
            continue

        caller_id = _resolve_caller_id(func_name, start_line, name_line_to_id, name_to_ids)
        if caller_id is None:
            continue

        seen: set[str] = set()
        for call_node in _find_all_nodes(func_node, call_types):
            callee = _get_callee_name_generic(call_node, src_bytes, ts_lang)
            if callee and callee not in seen:
                seen.add(callee)
                results.append((caller_id, callee))

    return results

def _strip_comments_strings(text: str) -> str:

    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.DOTALL)
    text = re.sub(r'//[^\n]*', ' ', text)
    text = re.sub(r'"[^"\n]{0,500}"', '""', text)
    text = re.sub(r"'[^'\n]{0,4}'", "''", text)
    return text


def _extract_regex_file_calls(
    source: str,
    db_funcs: list[dict],
) -> list[tuple[int, str]]:
    lines  = source.split('\n')
    result: list[tuple[int, str]] = []

    for fn in db_funcs:
        place = fn.get('place', {})
        if not isinstance(place, dict):
            continue
        start = place.get('start_line', 0)
        end   = place.get('end_line', start)
        fid   = fn['id']
        if start <= 0:
            continue

        func_src = '\n'.join(lines[start - 1:end])
        func_src = _strip_comments_strings(func_src)

        seen: set[str] = set()
        for m in _C_CALL_RE.finditer(func_src):
            name = m.group(1)
            if name not in _C_KEYWORDS and name not in seen:
                seen.add(name)
                result.append((fid, name))

    return result

def _extract_file_calls(
    abs_path: str,
    rel_path: str,
    language: str,
    db_funcs: list[dict],
) -> list[tuple[int, str]]:
    if not db_funcs:
        return []

    source = _read_source_for_callgraph(abs_path)
    if source is None:
        return []

    if language == 'Python':
        return _extract_python_file_calls(source, rel_path, db_funcs)

    if language in ('C', 'C++', 'Objective-C'):
        if _TREE_SITTER_OK:
            result = _extract_c_file_calls(source, db_funcs, language)
            if result:
                return result
        return _extract_regex_file_calls(source, db_funcs)

    ts_name = _LANG_TO_TS_NAME.get(language)
    if ts_name and _TREE_SITTER_OK:
        try:
            result = _extract_generic_ts_file_calls(source, db_funcs, ts_name)
            if result:
                return result
        except Exception:
            pass

    return _extract_regex_file_calls(source, db_funcs)


# ==================================================================
# 6. callee Classification
# ==================================================================

def _classify_callee(
    callee_name: str,
    user_func_index: dict[str, list[dict]],
) -> tuple[str, Optional[str], Optional[int]]:
    short_name = callee_name.rsplit('::', 1)[-1].strip()
    matches = user_func_index.get(callee_name) or user_func_index.get(short_name)
    if matches:
        m = matches[0]
        return ('user', m['file'], m['func_id'])

    header = _STDLIB_HEADER.get(short_name)
    if header:
        return ('lib', f'<{header}>', None)

    return ('lib', None, None)


# ==================================================================
# 7. build_callgraph
# ==================================================================

def build_callgraph(
    repo_id: int,
    db_path: Optional[str] = None,
    force: bool = False,
) -> str:

    _db = db_path or DB_PATH

    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[build_callgraph] repo_id={repo_id} does not exist in the database.")

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[build_callgraph] target warehouse:{repo_name}（{repo_path}）")

    output_dir  = os.path.join(DATA_DIR, 'callgraph')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'{repo_name}_callgraph.json')

    if os.path.exists(output_path) and not force:
        print(
            f"[build_callgraph] Callgraph already exists (using cache): {output_path}\n"
            f"[build_callgraph] To regenerate, please pass in the following information: force=True。"
        )
        return output_path

    all_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)
    if not all_funcs:
        raise ValueError(
            f"[build_callgraph] repo_id={repo_id} no func record"
        )
    print(f"[build_callgraph] {len(all_funcs)} function records have been loaded.")

    user_func_index: dict[str, list[dict]] = defaultdict(list)
    for fn in all_funcs:
        place = fn.get('place', {})
        if not isinstance(place, dict):
            continue
        user_func_index[fn['name']].append({
            'func_id':    fn['id'],
            'file':       place.get('file_path', ''),
            'start_line': place.get('start_line', 0),
        })

    all_files    = FileDB.list_by_repo(repo_id, db_path=_db)
    file_map:     dict[int, dict] = {f['id']: f for f in all_files}
    func_id_map:  dict[int, dict] = {fn['id']: fn for fn in all_funcs}

    funcs_by_file: dict[int, list[dict]] = defaultdict(list)
    for fn in all_funcs:
        funcs_by_file[fn['file_id']].append(fn)

    raw_edges: list[tuple[int, str]] = []
    total_files = len(funcs_by_file)
    processed = skipped = err_count = 0

    for file_id, file_funcs in funcs_by_file.items():
        file_rec = file_map.get(file_id)
        if file_rec is None:
            skipped += 1
            continue

        rel_path = file_rec.get('path', '')
        language = file_rec.get('language') or 'Unknown'
        abs_path = os.path.join(repo_path, rel_path)

        if not os.path.isfile(abs_path):
            skipped += 1
            continue

        try:
            edges = _extract_file_calls(abs_path, rel_path, language, file_funcs)
        except Exception as exc:
            print(f"[build_callgraph]  ⚠ error ({rel_path}): {exc}")
            err_count += 1
            continue

        raw_edges.extend(edges)
        processed += 1

        if processed % 50 == 0:
            print(
                f"[build_callgraph] progress {processed}/{total_files},"
                f"{len(raw_edges)} raw edges collected"
            )

    print(
        f"[build_callgraph] Extraction complete:"
        f"Processed={processed} Skipped={skipped} Error={err_count}"
        f"Raw call edges={len(raw_edges)}"
    )

    raw_edges_dedup = list(dict.fromkeys(raw_edges))
    print(
        f"[build_callgraph] Deduplicated edge call: {len(raw_edges_dedup)} edges"
        f"(Removes duplicates from {len(raw_edges) - len(raw_edges_dedup)} edges)"
    )

    call_edges: list[dict] = []
    cnt_user = cnt_lib_known = cnt_lib_unknown = 0

    for caller_id, callee_name in raw_edges_dedup:
        caller_fn = func_id_map.get(caller_id)
        if caller_fn is None:
            continue
        caller_place = caller_fn.get('place', {})
        if not isinstance(caller_place, dict):
            continue
        caller_file = caller_place.get('file_path', '')

        callee_type, callee_file, callee_id = _classify_callee(
            callee_name, user_func_index
        )

        call_edges.append({
            'caller_id':   caller_id,
            'caller_name': caller_fn['name'],
            'caller_file': caller_file,
            'callee_name': callee_name,
            'callee_id':   callee_id,
            'callee_file': callee_file,
            'callee_type': callee_type,
        })

        if callee_type == 'user':
            cnt_user += 1
        elif callee_file:
            cnt_lib_known += 1
        else:
            cnt_lib_unknown += 1

    output_data = {
        'repo_id':         repo_id,
        'repo_name':       repo_name,
        'generated_at':    datetime.now().isoformat(timespec='seconds'),
        'stats': {
            'total_functions':   len(all_funcs),
            'total_edges':       len(call_edges),
            'user_edges':        cnt_user,
            'lib_edges_known':   cnt_lib_known,
            'lib_edges_unknown': cnt_lib_unknown,
        },
        'user_func_index': dict(user_func_index),
        'call_edges':      call_edges,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        _json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(
        f"[build_callgraph] ✓ callgraph saved：{output_path}\n"
        f"  call_edges      : {len(call_edges)}\n"
        f"  user edges      : {cnt_user}\n"
        f"  cnt_lib_known   : {cnt_lib_known}\n"
        f"  cnt_lib_unknown : {cnt_lib_unknown}"
    )
    return output_path


# ==================================================================
# 8. analyze_func_callgraph
# ==================================================================

def analyze_func_callgraph(
    repo_id: int,
    db_path: Optional[str] = None,
    callgraph_path: Optional[str] = None,
) -> dict[int, dict]:

    _db = db_path or DB_PATH
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_func_callgraph] repo_id={repo_id} does not exist in the database."
        )
    repo_name = repo['name']
    print(f"[analyze_func_callgraph] target_repo：{repo_name}")

    if callgraph_path:
        cg_path = callgraph_path
    else:
        cg_path = os.path.join(DATA_DIR, 'callgraph', f'{repo_name}_callgraph.json')

    if not os.path.isfile(cg_path):
        raise ValueError(
            f"[analyze_func_callgraph] callgraph file does not exist:{cg_path}"
        )

    print(f"[analyze_func_callgraph] callgraph {cg_path}")
    try:
        with open(cg_path, 'r', encoding='utf-8') as f:
            cg_data = _json.load(f)
    except (_json.JSONDecodeError, OSError) as e:
        raise RuntimeError(
            f"[analyze_func_callgraph] file error：{e}"
        ) from e

    call_edges: list[dict] = cg_data.get('call_edges', [])
    print(f"[analyze_func_callgraph] call_edges:{len(call_edges)}")


    callees_map: dict[int, dict[tuple, dict]] = defaultdict(dict)
    callers_map: dict[int, dict[tuple, dict]] = defaultdict(dict)

    for edge in call_edges:
        caller_id   = edge.get('caller_id')
        caller_name = edge.get('caller_name', '')
        caller_file = edge.get('caller_file') or ''
        callee_name = edge.get('callee_name', '')
        callee_id   = edge.get('callee_id')
        callee_file = edge.get('callee_file')
        callee_type = edge.get('callee_type', 'lib')

        if not caller_id or not callee_name:
            continue

        # caller → callees
        c_key = (callee_name, callee_file or '')
        callees_map[caller_id][c_key] = {
            'name': callee_name,
            'file': callee_file,
            'type': callee_type,
        }

        # callee (user only) → callers
        if callee_id is not None:
            r_key = (caller_name, caller_file)
            callers_map[callee_id][r_key] = {
                'name': caller_name,
                'file': caller_file if caller_file else None,
                'type': 'user',
            }

    all_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)
    if not all_funcs:
        print("[analyze_func_callgraph] ⚠ No func record, skip writing to the library.")
        return {}

    result: dict[int, dict] = {}
    updated = has_callees = has_callers = 0

    for fn_rec in all_funcs:
        fid = fn_rec['id']

        callees_raw = callees_map.get(fid, {})
        callers_raw = callers_map.get(fid, {})

        sorted_callees = sorted(
            callees_raw.values(),
            key=lambda x: (0 if x['type'] == 'user' else 1,
                           x['name'],
                           x.get('file', '') or ''),
        )
        sorted_callers = sorted(
            callers_raw.values(),
            key=lambda x: (x['name'], x.get('file', '') or ''),
        )

        cg = {
            'callers': sorted_callers,
            'callees': sorted_callees,
        }

        FuncDB.update(fid, db_path=_db, callgraph=cg)
        result[fid] = cg
        updated += 1

        if sorted_callees:
            has_callees += 1
        if sorted_callers:
            has_callers += 1

    print(
        f"[analyze_func_callgraph] ✓ Done:\n"
        f" Updated function count: {updated}\n"
        f" Has callee functions: {has_callees}\n"
        f" Has caller functions: {has_callers}"
    )

    return result