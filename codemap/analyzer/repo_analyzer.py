# init_repo / analyze_repo_*
"""
analyzer/repo_analyzer.py
CodeMAP 仓库层分析器

实现：
  - init_repo              : 初始化仓库记录，建库建表，写入 repo:name / repo:path
  - analyze_repo_language  : 扫描仓库文件，统计语言字节数和占比，写入 repo:language
  - analyze_repo_area      : LLM 分析仓库模块划分，写入 area 表 / repo:arealist
"""

import json as _json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB, AreaDB
from config import DB_PATH, DATA_DIR

# ------------------------------------------------------------------
#  常量：扩展名 → 编程语言
# ------------------------------------------------------------------
_EXT_TO_LANG: dict[str, str] = {
    # C / C++
    '.c':     'C',
    '.h':     'C',        # C 头文件（.hpp/.hxx 单独归 C++）
    '.cpp':   'C++',
    '.cxx':   'C++',
    '.cc':    'C++',
    '.hpp':   'C++',
    '.hxx':   'C++',
    # Python
    '.py':    'Python',
    # Java
    '.java':  'Java',
    # JavaScript / TypeScript
    '.js':    'JavaScript',
    '.jsx':   'JavaScript',
    '.ts':    'TypeScript',
    '.tsx':   'TypeScript',
    # Go
    '.go':    'Go',
    # Rust
    '.rs':    'Rust',
    # Shell
    '.sh':    'Shell',
    '.bash':  'Shell',
    '.zsh':   'Shell',
    # CMake（文件名匹配见下方特判）
    '.cmake': 'CMake',
    # Ruby
    '.rb':    'Ruby',
    # Swift
    '.swift': 'Swift',
    # Kotlin
    '.kt':    'Kotlin',
    '.kts':   'Kotlin',
    # Scala
    '.scala': 'Scala',
    # Haskell
    '.hs':    'Haskell',
    # Assembly
    '.asm':   'Assembly',
    '.s':     'Assembly',
    # Lua
    '.lua':   'Lua',
    # Perl
    '.pl':    'Perl',
    '.pm':    'Perl',
    # Fortran
    '.f':     'Fortran',
    '.f90':   'Fortran',
    '.f95':   'Fortran',
    # R
    '.r':     'R',
    # MATLAB / Objective-C（.m 有歧义，优先 MATLAB；Obj-C 通常搭配 .mm）
    '.m':     'MATLAB',
    '.mm':    'Objective-C',
    # ---- 配置 / 文档类（统计但不作为主语言候选）----
    '.md':    'Markdown',
    '.rst':   'reStructuredText',
    '.yaml':  'YAML',
    '.yml':   'YAML',
    '.json':  'JSON',
    '.xml':   'XML',
    '.html':  'HTML',
    '.htm':   'HTML',
    '.css':   'CSS',
    '.sql':   'SQL',
    '.toml':  'TOML',
    '.ini':   'INI',
    '.cfg':   'INI',
}

# 遍历时跳过的目录（版本控制、构建产物、虚拟环境等）
_IGNORE_DIRS: set[str] = {
    '.git', '.svn', '.hg',
    '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache',
    'node_modules',
    '.venv', 'venv', 'env', '.env',
    'build', 'dist', '.build', 'out', 'target', 'cmake-build-debug',
    '.idea', '.vscode',
    'vendor',
}

# 不作为主语言候选的"非代码"语言集合
_NON_CODE_LANGS: set[str] = {
    'Markdown', 'reStructuredText',
    'YAML', 'JSON', 'XML', 'HTML', 'CSS',
    'SQL', 'TOML', 'INI',
}


# ==================================================================
#  init_repo
# ==================================================================

def init_repo(
    repo_path: str,
    repo_name: str | None = None,
    db_path: str | None = None,
    force: bool = False,
) -> int:
    """
    初始化仓库：建库建表，并在 repo 表中写入仓库基本信息。

    Parameters
    ----------
    repo_path : str
        仓库本地路径（绝对或相对均可，内部统一转为绝对路径）。
    repo_name : str | None
        仓库名称；若不传则取路径末尾目录名。
    db_path : str | None
        SQLite 数据库文件路径；不传则使用 config.DB_PATH。
    force : bool
        若同名 repo 已存在，True = 先删除再重建，False = 抛出 ValueError。

    Returns
    -------
    int
        新建 repo 记录的 id。

    Raises
    ------
    FileNotFoundError
        repo_path 不存在或不是目录。
    ValueError
        同名 repo 已存在且 force=False。
    """
    # ① 路径规范化
    abs_path = os.path.abspath(repo_path)
    if not os.path.isdir(abs_path):
        raise FileNotFoundError(
            f"[init_repo] 仓库路径不存在或不是目录：{abs_path}"
        )

    # ② 仓库名：优先用传入参数，否则取目录名
    name = repo_name or os.path.basename(abs_path.rstrip(os.sep))

    # ③ 建库建表（幂等：schema 里全部用 CREATE TABLE IF NOT EXISTS）
    _db = db_path or DB_PATH
    init_db(_db)

    # ④ 检查同名记录
    existing = RepoDB.get_by_name(name, db_path=_db)
    if existing is not None:
        if force:
            RepoDB.delete(existing['id'], db_path=_db)
            print(f"[init_repo] 已删除旧记录 id={existing['id']}，准备重建。")
        else:
            raise ValueError(
                f"[init_repo] 仓库 '{name}' 已存在（id={existing['id']}）。"
                "如需重建，请传入 force=True 或手动删除旧记录。"
            )

    # ⑤ 写入新记录
    repo_id = RepoDB.create(name, abs_path, db_path=_db)
    print(
        f"[init_repo] ✓ 仓库 '{name}' 已初始化\n"
        f"            repo_id = {repo_id}\n"
        f"            path    = {abs_path}\n"
        f"            db      = {_db}"
    )
    return repo_id


# ==================================================================
#  analyze_repo_language  —— 内部辅助
# ==================================================================

def _scan_language_bytes(repo_path: str) -> dict[str, int]:
    """
    递归遍历仓库目录，对每个可识别文件累加字节数，返回 {语言: 字节数}。

    忽略规则：
      - _IGNORE_DIRS 中的目录
      - 无法识别扩展名且无特殊文件名的文件
      - 读取文件大小失败的文件（SymLink 断链等）
    """
    lang_bytes: dict[str, int] = {}

    for root, dirs, files in os.walk(repo_path, topdown=True):
        # 原地过滤：让 os.walk 不再递归进入忽略目录
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith('.')]

        for filename in files:
            # --- 语言判定 ---
            _, ext = os.path.splitext(filename)
            lang = _EXT_TO_LANG.get(ext.lower())

            # 无扩展名的特殊文件名匹配
            if lang is None:
                lower_name = filename.lower()
                if lower_name in ('makefile', 'gnumakefile'):
                    lang = 'Makefile'
                elif filename == 'CMakeLists.txt':
                    lang = 'CMake'

            if lang is None:
                continue  # 无法识别，跳过

            # --- 字节数统计 ---
            file_path = os.path.join(root, filename)
            try:
                size = os.path.getsize(file_path)
            except OSError:
                continue

            lang_bytes[lang] = lang_bytes.get(lang, 0) + size

    return lang_bytes


# ==================================================================
#  analyze_repo_language
# ==================================================================

def analyze_repo_language(
    repo_id: int,
    db_path: str | None = None,
) -> dict:
    """
    扫描仓库目录，统计各语言字节数和占比，确定主要编程语言，并写入数据库。

    主语言判定规则（按优先级）：
      1. 若字节数最多的语言属于代码型语言（非 _NON_CODE_LANGS），直接选取；
      2. 否则在 stats 列表中顺延，取第一个代码型语言；
      3. 若所有语言均为非代码型，则以字节数最多者兜底（罕见情形）。

    Parameters
    ----------
    repo_id : int
        目标仓库的 id（由 init_repo 返回）。
    db_path : str | None
        SQLite 数据库路径；不传则使用 config.DB_PATH。

    Returns
    -------
    dict
        写入 repo.language 字段的内容，格式：
        {
            "main": "C",
            "stats": [
                {"lang": "C",     "pct": 82.30, "bytes": 500000},
                {"lang": "CMake", "pct": 10.10, "bytes":  61000},
                ...               # 按 bytes 降序排列
            ]
        }

    Raises
    ------
    ValueError
        repo_id 在数据库中不存在。
    """
    _db = db_path or DB_PATH

    # ① 取仓库信息
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_repo_language] repo_id={repo_id} 不存在于数据库。")

    repo_path = repo['path']
    print(f"[analyze_repo_language] 开始扫描：{repo_path}")

    # ② 扫描并统计字节数
    lang_bytes = _scan_language_bytes(repo_path)

    # ③ 处理空仓库边界情形
    if not lang_bytes:
        print("[analyze_repo_language] ⚠ 未识别到任何代码文件。")
        language_data: dict = {"main": "Unknown", "stats": []}
        RepoDB.update(repo_id, db_path=_db, language=language_data)
        return language_data

    # ④ 计算总字节数 & 构造 stats 列表（按字节数降序）
    total_bytes = sum(lang_bytes.values())
    stats: list[dict] = sorted(
        [
            {
                "lang":  lang,
                "pct":   round(b / total_bytes * 100, 2),
                "bytes": b,
            }
            for lang, b in lang_bytes.items()
        ],
        key=lambda x: x["bytes"],
        reverse=True,
    )

    # ⑤ 确定主要语言
    main_lang: str = stats[0]["lang"]          # 默认：字节数最多
    for entry in stats:
        if entry["lang"] not in _NON_CODE_LANGS:
            main_lang = entry["lang"]
            break
    # 若所有语言均为非代码型，则 main_lang 保持 stats[0]["lang"]（已赋默认值）

    # ⑥ 组装 language 数据并写库
    language_data = {"main": main_lang, "stats": stats}
    RepoDB.update(repo_id, db_path=_db, language=language_data)

    # ⑦ 控制台摘要
    print(f"[analyze_repo_language] ✓ 主语言：{main_lang}")
    top_n = min(5, len(stats))
    print(f"[analyze_repo_language]   语言分布（Top {top_n}）：")
    for entry in stats[:top_n]:
        bar = "█" * int(entry["pct"] / 2)
        print(
            f"    {entry['lang']:18s} {entry['pct']:6.2f}%  "
            f"{entry['bytes']:>12,} bytes  {bar}"
        )

    return language_data

# ==================================================================
#  analyze_repo_area —— 辅助：目录树 & README
# ==================================================================

def _build_dir_tree(repo_path: str, max_depth: int = 3, max_chars: int = 8000) -> str:
    """
    生成仓库目录树字符串（类 Unix `tree` 命令格式）。

    Parameters
    ----------
    repo_path : str
        仓库根目录绝对路径
    max_depth : int
        最大递归深度（从根算起，根的直接子项为第 1 层）
    max_chars : int
        输出字符上限，超出后追加截断提示

    Returns
    -------
    str
        多行字符串，可直接放入 prompt
    """
    lines: list[str] = []
    root_name = os.path.basename(repo_path.rstrip(os.sep))
    lines.append(f"{root_name}/")

    def _walk(path: str, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return

        try:
            raw = list(os.scandir(path))
        except PermissionError:
            return

        # 过滤忽略目录和隐藏目录
        entries = [
            e for e in raw
            if not (e.is_dir() and (e.name in _IGNORE_DIRS or e.name.startswith('.')))
        ]
        # 排序：目录在前，同类按名称字母序（忽略大小写）
        entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

        for i, entry in enumerate(entries):
            is_last   = (i == len(entries) - 1)
            connector = '└── ' if is_last else '├── '
            suffix    = '/' if entry.is_dir() else ''
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")

            if entry.is_dir() and depth < max_depth:
                child_prefix = prefix + ('    ' if is_last else '│   ')
                _walk(entry.path, child_prefix, depth + 1)

    _walk(repo_path, '', 1)

    result = '\n'.join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + '\n...(目录树已截断，超过字符上限)'
    return result


def _read_readme(repo_path: str, max_chars: int = 3000) -> str:
    """
    读取仓库根目录的 README 文件内容（截取前 max_chars 字符）。

    Returns
    -------
    str
        README 内容，或 "（未找到 README 文件）"
    """
    candidates = [
        'README.md', 'README.rst', 'README.txt', 'README',
        'readme.md', 'readme.rst', 'readme.txt', 'readme',
        'Readme.md', 'Readme.rst',
    ]
    for name in candidates:
        full_path = os.path.join(repo_path, name)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(max_chars)
            file_size = os.path.getsize(full_path)
            suffix = '\n\n...(README 已截断，仅展示前部分)' if file_size > max_chars else ''
            print(f"[analyze_repo_area] 读取 README：{name}（{len(content)} 字符）")
            return content + suffix
        except OSError:
            continue
    return '（未找到 README 文件）'


# ==================================================================
#  analyze_repo_area
# ==================================================================

def analyze_repo_area(
    repo_id: int,
    db_path: str | None = None,
    force: bool = False,
) -> list[dict]:
    """
    使用 LLM 对仓库进行模块划分（area 分层），并将结果持久化到数据库和中间文件。

    流程
    ----
    1. 构建仓库目录树（最多 3 层）
    2. 读取 README（作为 LLM 背景输入）
    3. 调用 LLM 生成 area 划分方案（name / path / rationale / brief）
    4. 校验 LLM 给出的 path 在磁盘上确实存在，去掉无效项
    5. 中间产物 JSON → data/analyze_repo_area/<repo_name>.json
    6. 写数据库：
       - area 表：为每个 area 创建记录（name / path / rationale）
       - repo 表：更新 arealist 字段（存简要索引）

    Parameters
    ----------
    repo_id : int
        目标仓库的 id（由 init_repo 返回）
    db_path : str | None
        SQLite 数据库路径；不传则使用 config.DB_PATH
    force : bool
        若已存在 area 记录，True = 先删除再重建，False = 抛出 ValueError

    Returns
    -------
    list[dict]
        已入库的 area 信息列表，每项：
        {
            "area_id":   int,
            "name":      str,
            "path":      str,   # 相对仓库根
            "rationale": str,
            "brief":     str,
        }

    Raises
    ------
    ValueError
        repo_id 不存在 / force=False 且已有 area 记录 / LLM 无有效输出
    RuntimeError
        LLM API 调用失败
    """
    _db = db_path or DB_PATH

    # ── ① 取仓库信息 ────────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_repo_area] repo_id={repo_id} 在数据库中不存在。"
        )

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[analyze_repo_area] 目标仓库：{repo_name}（{repo_path}）")

    # ── ② 处理已有 area 记录 ────────────────────────────────────────
    existing = AreaDB.list_by_repo(repo_id, db_path=_db)
    if existing:
        if force:
            for a in existing:
                AreaDB.delete(a['id'], db_path=_db)
            print(f"[analyze_repo_area] 已清除 {len(existing)} 条旧 area 记录。")
        else:
            raise ValueError(
                f"[analyze_repo_area] repo_id={repo_id} 已有 {len(existing)} 个 area 记录。"
                " 如需重新分析，请传入 force=True。"
            )

    # ── ③ 收集上下文信息 ────────────────────────────────────────────
    language_info = repo.get('language') or {}
    main_language = (
        language_info.get('main', 'Unknown')
        if isinstance(language_info, dict)
        else 'Unknown'
    )

    dir_tree       = _build_dir_tree(repo_path, max_depth=3)
    readme_content = _read_readme(repo_path)

    print(
        f"[analyze_repo_area] 上下文准备完毕 | "
        f"主语言：{main_language} | "
        f"目录树：{len(dir_tree)} 字符 | "
        f"README：{len(readme_content)} 字符"
    )

    # ── ④ 调用 LLM ──────────────────────────────────────────────────
    # 延迟导入：仅在需要时加载 LLM 模块，避免无关步骤引入额外依赖
    from llm.client  import chat_completion_json
    from llm.prompts import ANALYZE_REPO_AREA_SYSTEM, ANALYZE_REPO_AREA_USER
    import config as _cfg

    user_content = ANALYZE_REPO_AREA_USER.format(
        repo_name      = repo_name,
        main_language  = main_language,
        dir_tree       = dir_tree,
        readme_content = readme_content,
    )

    messages = [
        {"role": "system", "content": ANALYZE_REPO_AREA_SYSTEM},
        {"role": "user",   "content": user_content},
    ]

    print(f"[analyze_repo_area] 调用 LLM（模型：{_cfg.LLM_MODEL}）…")
    llm_raw = chat_completion_json(messages=messages, temperature=0.3)
    print(f"[analyze_repo_area] LLM 响应已接收，开始解析…")

    # ── ⑤ 解析 LLM 输出结构 ────────────────────────────────────────
    if isinstance(llm_raw, dict) and 'areas' in llm_raw:
        areas_raw: list[dict] = llm_raw['areas']
    elif isinstance(llm_raw, list):
        areas_raw = llm_raw
    else:
        raise ValueError(
            f"[analyze_repo_area] LLM 输出结构不符合预期（类型：{type(llm_raw)}）：\n"
            f"{_json.dumps(llm_raw, ensure_ascii=False, indent=2)[:600]}"
        )

    # ── ⑥ 字段提取 + 路径校验 + 去重 ───────────────────────────────
    seen_paths: set[str] = set()
    validated:  list[dict] = []

    for item in areas_raw:
        name      = str(item.get('name',      '')).strip()
        path      = str(item.get('path',      '')).strip()
        rationale = str(item.get('rationale', '')).strip()
        brief     = str(item.get('brief',     '')).strip()

        # 必填字段检查
        if not name or not path:
            print(f"[analyze_repo_area] ⚠ 跳过缺少 name/path 的条目：{item}")
            continue

        # 路径去重
        if path in seen_paths:
            print(f"[analyze_repo_area] ⚠ 跳过重复 path：{path}")
            continue
        seen_paths.add(path)

        # 磁盘存在性校验
        abs_path = repo_path if path == '.' else os.path.join(repo_path, path)
        if not os.path.exists(abs_path):
            print(f"[analyze_repo_area] ⚠ path 在磁盘上不存在，已跳过：{path}")
            continue

        validated.append({
            'name':      name,
            'path':      path,
            'rationale': rationale,
            'brief':     brief,
        })

    if not validated:
        raise ValueError(
            "[analyze_repo_area] 所有 LLM 输出的 area 均未通过校验，请查看上方日志。"
        )

    # ── ⑦ 保存中间产物 JSON ─────────────────────────────────────────
    output_dir = os.path.join(DATA_DIR, 'analyze_repo_area')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{repo_name}.json")

    intermediate = {
        'repo_id':       repo_id,
        'repo_name':     repo_name,
        'repo_path':     repo_path,
        'main_language': main_language,
        'llm_raw':       llm_raw,
        'areas':         validated,
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        _json.dump(intermediate, f, ensure_ascii=False, indent=2)
    print(f"[analyze_repo_area] ✓ 中间产物 → {output_path}")

    # ── ⑧ 写入数据库 ────────────────────────────────────────────────
    arealist: list[dict] = []

    for area_data in validated:
        area_id = AreaDB.create(
            repo_id   = repo_id,
            name      = area_data['name'],
            path      = area_data['path'],
            rationale = area_data['rationale'],
            db_path   = _db,
        )
        area_data['area_id'] = area_id  # 回写 id，供调用方使用

        arealist.append({
            'area_id': area_id,
            'name':    area_data['name'],
            'brief':   area_data['brief'],
        })

        print(
            f"[analyze_repo_area]   + [{area_id:3d}] "
            f"{area_data['name']:30s}  path={area_data['path']}"
        )

    # 更新 repo.arealist（简要索引）
    RepoDB.update(repo_id, db_path=_db, arealist=arealist)

    print(
        f"[analyze_repo_area] ✓ 完成：{len(validated)} 个 area 已入库，"
        f"repo.arealist 已更新。"
    )
    return validated

# ─────────────────────────────────────────────
# Step 17: analyze_repo_arealist_brief
# Step 18: analyze_repo_description

import time as _time_r
from typing import Optional

_REPO_MAX_AREA_DESC  = 600
_REPO_MAX_RETRIES    = 5
_REPO_RETRY_DELAYS   = (2, 5, 10, 20, 40)


def _repo_retry(fn, label: str = "", max_retries: int = _REPO_MAX_RETRIES):
    last_exc = None
    for i in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if i < max_retries - 1:
                wait = _REPO_RETRY_DELAYS[min(i, len(_REPO_RETRY_DELAYS)-1)]
                print(f"  ↻ 重试{i+1}/{max_retries} ({label})：{exc}，{wait}s 后…")
                _time_r.sleep(wait)
    raise RuntimeError(f"重试 {max_retries} 次失败 ({label})：{last_exc}")


def analyze_repo_arealist_brief(
    repo_id: int,
    db_path: str | None = None,
    skip_if_exists: bool = True,
) -> list[dict]:
    """
    为 repo.arealist 中每个 area 生成 brief，写回 repo.arealist。

    依赖：area.description 已完成（Step 16）。

    Returns
    -------
    list[dict]  更新后的 arealist
    """
    from llm.client  import chat_completion_json
    from llm.prompts import (
        ANALYZE_REPO_AREALIST_BRIEF_SYSTEM,
        ANALYZE_REPO_AREALIST_BRIEF_USER,
    )
    import json as _j

    _db  = db_path or DB_PATH
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_repo_arealist_brief] repo_id={repo_id} 不存在。")

    arealist = repo.get("arealist") or []
    if isinstance(arealist, str):
        try:
            arealist = _j.loads(arealist)
        except Exception:
            arealist = []

    if not arealist:
        print("[analyze_repo_arealist_brief] arealist 为空，跳过。")
        return []

    if skip_if_exists and all(e.get("brief") for e in arealist):
        print("[analyze_repo_arealist_brief] 所有 area 已有 brief，跳过。")
        return arealist

    # 收集各 area 描述
    area_lines: list[str] = []
    for entry in arealist:
        aid   = entry.get("area_id")
        aname = entry.get("name", "")
        if aid:
            area_rec = AreaDB.get_by_id(aid, db_path=_db)
            desc     = (area_rec or {}).get("description", "") or ""
            desc     = desc[:_REPO_MAX_AREA_DESC]
        else:
            desc = ""
        if not desc:
            desc = f"[area 名称] {aname}"
        area_lines.append(f"area_id={aid}  name={aname}\n描述：{desc}\n")

    area_list_text = "\n---\n".join(area_lines)
    user_content   = ANALYZE_REPO_AREALIST_BRIEF_USER.format(
        repo_name      = repo["name"],
        area_count     = len(arealist),
        area_list_text = area_list_text,
    )
    messages = [
        {"role": "system", "content": ANALYZE_REPO_AREALIST_BRIEF_SYSTEM},
        {"role": "user",   "content": user_content},
    ]

    try:
        def _call():
            return chat_completion_json(messages=messages, temperature=0.1)

        raw = _repo_retry(_call, label=f"repo={repo['name']} arealist_brief")
    except Exception as exc:
        print(f"[analyze_repo_arealist_brief] ✗ LLM 调用失败：{exc}")
        return arealist

    briefs_list = raw.get("briefs", []) if isinstance(raw, dict) else []
    brief_map   = {int(b["area_id"]): b["brief"]
                   for b in briefs_list
                   if isinstance(b, dict) and b.get("area_id") is not None}

    new_arealist = []
    for entry in arealist:
        new_entry = dict(entry)
        aid = entry.get("area_id")
        if aid and aid in brief_map:
            new_entry["brief"] = brief_map[aid]
        new_arealist.append(new_entry)

    RepoDB.update(repo_id, db_path=_db, arealist=new_arealist)
    print(
        f"[analyze_repo_arealist_brief] ✓ 完成："
        f"areas={len(new_arealist)}  briefs_updated={len(brief_map)}"
    )
    return new_arealist


def analyze_repo_description(
    repo_id: int,
    db_path: str | None = None,
    skip_if_exists: bool = True,
) -> str:
    """
    为仓库生成自然语言描述，写入 repo.description。

    依赖：area.description 已完成（Step 16）。

    Returns
    -------
    str  仓库描述文本
    """
    from llm.client  import chat_completion
    from llm.prompts import (
        ANALYZE_REPO_DESCRIPTION_SYSTEM,
        ANALYZE_REPO_DESCRIPTION_USER,
    )
    import json as _j

    _db  = db_path or DB_PATH
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_repo_description] repo_id={repo_id} 不存在。")

    if skip_if_exists and repo.get("description"):
        print(
            f"[analyze_repo_description] '{repo['name']}' 已有描述，跳过。"
        )
        return repo["description"]

    repo_path = repo["path"]
    repo_name = repo["name"]

    # 语言信息
    language_info = repo.get("language") or {}
    if isinstance(language_info, str):
        try:
            language_info = _j.loads(language_info)
        except Exception:
            language_info = {}
    main_language  = language_info.get("main", "Unknown")
    lang_stats_raw = language_info.get("stats", [])
    language_stats = "，".join(
        f"{s['lang']} {s['pct']}%" for s in lang_stats_raw[:6]
    )

    # 目录树
    dir_tree = _build_dir_tree(repo_path, max_depth=3)

    # README
    readme_content = _read_readme(repo_path)

    # area 结构 + 描述
    areas      = AreaDB.list_by_repo(repo_id, db_path=_db)
    arealist   = repo.get("arealist") or []
    if isinstance(arealist, str):
        try:
            arealist = _j.loads(arealist)
        except Exception:
            arealist = []

    brief_map  = {e.get("area_id"): e.get("brief", "") for e in arealist}

    area_structure_lines: list[str] = []
    area_desc_parts:      list[str] = []

    for area in areas:
        aid   = area["id"]
        aname = area["name"]
        apath = area["path"]
        brief = brief_map.get(aid, "")
        area_structure_lines.append(f"  [{aname}]  path={apath}  {brief}")

        desc = area.get("description", "") or ""
        area_desc_parts.append(
            f"### {aname}（{apath}）\n{desc[:_REPO_MAX_AREA_DESC] or '（暂无描述）'}"
        )

    area_structure  = "\n".join(area_structure_lines) or "（无 area 记录）"
    area_descriptions = "\n\n".join(area_desc_parts) or "（无 area 描述）"

    user_content = ANALYZE_REPO_DESCRIPTION_USER.format(
        repo_name         = repo_name,
        main_language     = main_language,
        language_stats    = language_stats or "（未知）",
        dir_tree          = dir_tree,
        area_structure    = area_structure,
        readme_content    = readme_content,
        area_descriptions = area_descriptions,
    )
    messages = [
        {"role": "system", "content": ANALYZE_REPO_DESCRIPTION_SYSTEM},
        {"role": "user",   "content": user_content},
    ]

    try:
        def _call():
            return chat_completion(messages=messages, temperature=0.2)

        desc = _repo_retry(_call, label=f"repo={repo_name} description")
        desc = desc.strip()
    except Exception as exc:
        print(f"[analyze_repo_description] ✗ LLM 调用失败：{exc}")
        return ""

    RepoDB.update(repo_id, db_path=_db, description=desc)
    print(f"[analyze_repo_description] ✓ 完成：{len(desc)} 字符")
    return desc