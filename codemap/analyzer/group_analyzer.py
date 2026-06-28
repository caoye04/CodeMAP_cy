"""
analyzer/group_analyzer.py
CodeMAP Group 层分析器

实现：
  - analyze_group_file : 扫描每个 group 路径下的文件结构，
                        写入 file 表并更新 group.filelist，
                        中间产物保存至 data/analyze_group_file/<repo_name>.json
"""

import json as _json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, GroupDB, FileDB
from config import DB_PATH, DATA_DIR


# ------------------------------------------------------------------
#  ① 过滤黑名单：需要跳过的文件扩展名
#     原则：二进制、编译产物、媒体、打包归档、临时文件 —— 无代码分析价值
# ------------------------------------------------------------------
_SKIP_EXTENSIONS: frozenset[str] = frozenset({
    # 编译 / 链接产物
    '.o', '.obj', '.a', '.lib', '.so', '.dll', '.dylib',
    '.exe', '.out', '.elf', '.ko', '.lo', '.la',
    # Python 字节码
    '.pyc', '.pyo', '.pyd',
    # Java 字节码 / 打包
    '.class', '.jar', '.war', '.ear',
    # Node 构建产物
    '.map',
    # 图片
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico',
    '.svg', '.webp', '.tiff', '.tif', '.raw', '.heic',
    # 音视频
    '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.wav', '.flac', '.ogg', '.webm',
    # 压缩包 / 归档
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.zst', '.lz4', '.lzma',
    # 字体
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    # Office / PDF
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods',
    # 数据库文件
    '.db', '.sqlite', '.sqlite3',
    # 其他二进制数据
    '.bin', '.dat', '.iso', '.img',
    # 调试符号
    '.pdb',
    # 覆盖率 / 性能分析产物
    '.gcda', '.gcno', '.profraw', '.profdata',
    # 临时 / 备份
    '.bak', '.swp', '.swo', '.orig', '.tmp', '.temp',
    # 锁文件（带扩展名的）
    '.lock',
    # 证书 / 密钥
    '.pem', '.key', '.crt', '.cer', '.p12', '.pfx', '.der',
    # 版本控制补丁（不属于源码）
    '.patch', '.diff',
})

# ------------------------------------------------------------------
#  ② 过滤黑名单：需要跳过的具体文件名（小写比较）
# ------------------------------------------------------------------
_SKIP_FILENAMES: frozenset[str] = frozenset({
    # 系统残留
    '.ds_store', 'thumbs.db', 'desktop.ini',
    # 包管理锁文件
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'poetry.lock', 'pipfile.lock', 'cargo.lock',
    'composer.lock', 'gemfile.lock', 'mix.lock', 'packages.lock.json',
    # VCS 配置（隐藏文件过滤已覆盖大部分，这里补充非隐藏的）
    '.gitignore', '.gitattributes', '.gitmodules', '.gitkeep',
    # 编辑器 / 格式化配置
    '.editorconfig', '.clang-format', '.clang-tidy',
    '.prettierrc', '.eslintrc', '.babelrc', '.stylelintrc',
    # Docker / CI 元信息
    '.npmignore', '.dockerignore', '.mailmap',
    # compile_commands.json：clang 工具链产物，非源码
    'compile_commands.json',
})

# ------------------------------------------------------------------
#  ③ 遍历时跳过的目录（与 repo_analyzer.py 完全保持一致）
# ------------------------------------------------------------------
_IGNORE_DIRS: frozenset[str] = frozenset({
    '.git', '.svn', '.hg',
    '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache',
    'node_modules',
    '.venv', 'venv', 'env', '.env',
    'build', 'dist', '.build', 'out', 'target', 'cmake-build-debug',
    '.idea', '.vscode',
    'vendor',
})


# ==================================================================
#  内部辅助函数
# ==================================================================

def _is_useful_file(filename: str) -> bool:
    """
    判断文件名是否值得纳入 CodeMAP 分析。

    过滤逻辑（按顺序）：
      1. 以 '.' 开头的隐藏文件 → 跳过
      2. 扩展名在 _SKIP_EXTENSIONS 黑名单 → 跳过
      3. 文件名（小写）在 _SKIP_FILENAMES 黑名单 → 跳过
      4. 其余文件 → 保留（宁可多扫，后续步骤可按语言再做筛选）

    Parameters
    ----------
    filename : str
        仅文件名，不含路径

    Returns
    -------
    bool
    """
    if filename.startswith('.'):
        return False

    _, ext = os.path.splitext(filename)
    if ext.lower() in _SKIP_EXTENSIONS:
        return False

    if filename.lower() in _SKIP_FILENAMES:
        return False

    return True


def _scan_group_files(
    group_abs_path: str,
    repo_path: str,
    other_group_abs_paths: set[str],
) -> list[dict]:
    """
    递归扫描 group 目录，返回所有有效文件的 name + path 列表。

    关键设计：**不递归进入属于其他 group 的子目录**，从根源上避免
    同一文件被重复归属到多个 group（当 group 路径存在包含关系时尤其重要，
    例如 group='.' 与 group='src/' 同时存在）。

    Parameters
    ----------
    group_abs_path : str
        当前 group 目录的绝对路径
    repo_path : str
        仓库根目录的绝对路径（用于计算 file 的相对路径）
    other_group_abs_paths : set[str]
        其他所有 group 的绝对路径集合；遇到匹配的子目录时跳过

    Returns
    -------
    list[dict]
        每项 {"name": str, "path": str}
        path 相对于仓库根，统一使用 '/' 分隔符
    """
    collected: list[dict] = []

    for root, dirs, filenames in os.walk(group_abs_path, topdown=True):
        # ---------- 过滤子目录 ----------
        dirs_keep: list[str] = []
        for d in sorted(dirs):
            # 忽略列表 & 隐藏目录
            if d in _IGNORE_DIRS or d.startswith('.'):
                continue
            # 属于另一个独立 group 的目录 → 不递归，由该 group 自行扫描
            child_abs = os.path.normpath(os.path.join(root, d))
            if child_abs in other_group_abs_paths:
                continue
            dirs_keep.append(d)
        dirs[:] = dirs_keep

        # ---------- 收集文件 ----------
        for filename in sorted(filenames):
            if not _is_useful_file(filename):
                continue

            file_abs = os.path.join(root, filename)
            try:
                rel_path = os.path.relpath(file_abs, repo_path)
                # 统一使用 '/' 分隔符（Windows 兼容）
                rel_path = rel_path.replace(os.sep, '/')
            except ValueError:
                # Windows 跨盘符时 relpath 可能抛 ValueError
                continue

            collected.append({
                'name': filename,
                'path': rel_path,
            })

    return collected


# ==================================================================
#  analyze_group_file
# ==================================================================

def analyze_group_file(
    repo_id: int,
    db_path: str | None = None,
    force: bool = False,
) -> dict[int, list[dict]]:
    """
    扫描仓库每个 group 路径下的文件，写入 file 表并更新 group.filelist。

    流程
    ----
    1. 读取仓库信息和所有 group 记录
    2. 预计算各 group 的绝对路径，构造互斥集合（防重叠扫描）
    3. 对每个 group 递归扫描文件，_is_useful_file() 过滤无效文件
    4. 将文件写入 file 表（name / path），防御性地检测路径重复
    5. 更新 group.filelist（file_id + name，brief 留空待后续步骤填充）
    6. 汇总写出中间产物 JSON → data/analyze_group_file/<repo_name>.json

    数据库写入字段
    --------------
    - file.name   : 文件名（basename）
    - file.path   : 相对仓库根的路径，'/' 分隔
    - group.filelist: [{"file_id": int, "name": str, "brief": ""}]

    Parameters
    ----------
    repo_id : int
        目标仓库 id（由 init_repo 返回）
    db_path : str | None
        SQLite 数据库路径；不传则使用 config.DB_PATH
    force : bool
        若已存在 file 记录：
          True  = 先清除所有旧 file 记录再重建
          False = 抛出 ValueError

    Returns
    -------
    dict[int, list[dict]]
        键为 group_id，值为该 group 下已入库的文件列表，每项：
        {
            "file_id": int,
            "name":    str,
            "path":    str,  # 相对仓库根，'/' 分隔
        }

    Raises
    ------
    ValueError
        · repo_id 在数据库中不存在
        · 该仓库尚无 group 记录（需先执行 analyze_repo_group）
        · force=False 且已有 file 记录
    """
    _db = db_path or DB_PATH

    # ── ① 取仓库信息 ────────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_group_file] repo_id={repo_id} 在数据库中不存在。"
        )

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[analyze_group_file] 目标仓库：{repo_name}（{repo_path}）")

    # ── ② 取 group 列表 ──────────────────────────────────────────────
    groups = GroupDB.list_by_repo(repo_id, db_path=_db)
    if not groups:
        raise ValueError(
            f"[analyze_group_file] repo_id={repo_id} 无 group 记录，"
            "请先执行 analyze_repo_group。"
        )
    print(f"[analyze_group_file] 共 {len(groups)} 个 group，开始扫描文件…")

    # ── ③ 处理已有 file 记录 ────────────────────────────────────────
    existing_files = FileDB.list_by_repo(repo_id, db_path=_db)
    if existing_files:
        if force:
            for f in existing_files:
                FileDB.delete(f['id'], db_path=_db)
            print(f"[analyze_group_file] 已清除 {len(existing_files)} 条旧 file 记录。")
        else:
            raise ValueError(
                f"[analyze_group_file] repo_id={repo_id} 已有 {len(existing_files)} 个 file 记录。"
                " 如需重新扫描，请传入 force=True。"
            )

    # ── ④ 预计算各 group 绝对路径 ────────────────────────────────────
    # normpath 确保路径字符串可直接用集合匹配，Windows 下统一反斜杠
    group_abs_map: dict[int, str] = {}
    for group in groups:
        rel = group['path']
        abs_p = (
            repo_path
            if rel == '.'
            else os.path.normpath(os.path.join(repo_path, rel))
        )
        group_abs_map[group['id']] = abs_p

    # ── ⑤ 逐 group 扫描文件 ──────────────────────────────────────────
    result: dict[int, list[dict]]   = {}
    all_group_records: list[dict]    = []   # 用于中间产物 JSON

    for group in groups:
        group_id       = group['id']
        group_name     = group['name']
        group_path_rel = group['path']
        group_abs      = group_abs_map[group_id]

        # 路径不存在时发出警告并跳过（LLM 给出的路径可能已被删除/重命名）
        if not os.path.exists(group_abs):
            print(
                f"[analyze_group_file] ⚠ group '{group_name}' 路径不存在，"
                f"已跳过：{group_abs}"
            )
            result[group_id] = []
            continue

        # 当前 group 以外的所有 group 绝对路径（扫描时不递归进入）
        other_abs: set[str] = {
            p for aid, p in group_abs_map.items() if aid != group_id
        }

        print(
            f"[analyze_group_file]   扫描 group [{group_id:3d}] "
            f"'{group_name}'（{group_path_rel}）…"
        )

        raw_files = _scan_group_files(group_abs, repo_path, other_abs)
        print(f"[analyze_group_file]     → 发现 {len(raw_files)} 个有效文件")

        # ── ⑥ 写入 file 表 ──────────────────────────────────────────
        group_filelist:      list[dict] = []   # 写回 group.filelist
        group_file_records:  list[dict] = []   # 供调用方和中间产物使用

        for file_info in raw_files:
            file_name = file_info['name']
            file_path = file_info['path']   # 相对仓库根

            # 防御：若同一路径已存在（group 路径部分重叠时），不重复创建
            existing_file = FileDB.get_by_path(repo_id, file_path, db_path=_db)
            if existing_file is not None:
                file_id = existing_file['id']
                print(
                    f"[analyze_group_file]     ⚠ 路径已存在（group 路径重叠？）："
                    f"{file_path} → 复用 file_id={file_id}"
                )
            else:
                file_id = FileDB.create(
                    repo_id = repo_id,
                    group_id = group_id,
                    name    = file_name,
                    path    = file_path,
                    db_path = _db,
                )

            group_filelist.append({
                'file_id': file_id,
                'name':    file_name,
                'brief':   '',      # 留给 analyze_group_filelist_description（step16）填充
            })
            group_file_records.append({
                'file_id': file_id,
                'name':    file_name,
                'path':    file_path,
            })

        # ── ⑦ 更新 group.filelist ────────────────────────────────────
        GroupDB.update(group_id, db_path=_db, filelist=group_filelist)

        result[group_id] = group_file_records
        all_group_records.append({
            'group_id':    group_id,
            'group_name':  group_name,
            'group_path':  group_path_rel,
            'file_count': len(group_file_records),
            'files':      group_file_records,
        })

        print(
            f"[analyze_group_file]     ✓ '{group_name}'："
            f"{len(group_file_records)} 个文件已入库"
        )

    # ── ⑧ 保存中间产物 JSON ─────────────────────────────────────────
    output_dir  = os.path.join(DATA_DIR, 'analyze_group_file')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{repo_name}.json")

    total_files = sum(len(v) for v in result.values())
    intermediate = {
        'repo_id':   repo_id,
        'repo_name': repo_name,
        'repo_path': repo_path,
        'summary': {
            'total_groups': len(groups),
            'total_files': total_files,
        },
        'groups': all_group_records,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        _json.dump(intermediate, f, ensure_ascii=False, indent=2)
    print(f"[analyze_group_file] ✓ 中间产物 → {output_path}")

    print(
        f"[analyze_group_file] ✓ 完成：{len(groups)} 个 group，"
        f"共 {total_files} 个文件已入库。"
    )
    return result

# ─────────────────────────────────────────────────
# Step 15: analyze_group_filelist_brief
# Step 16: analyze_group_description

import time as _time_a
from typing import Optional

_AREA_MAX_DESC_CHARS = 500
_AREA_MAX_RETRIES    = 5
_AREA_RETRY_DELAYS   = (2, 5, 10, 20, 40)


def _group_retry(fn, label: str = "", max_retries: int = _AREA_MAX_RETRIES):
    last_exc = None
    for i in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if i < max_retries - 1:
                wait = _AREA_RETRY_DELAYS[min(i, len(_AREA_RETRY_DELAYS)-1)]
                print(f"  ↻ 重试{i+1}/{max_retries} ({label})：{exc}，{wait}s 后…")
                _time_a.sleep(wait)
    raise RuntimeError(f"重试 {max_retries} 次失败 ({label})：{last_exc}")


def analyze_group_filelist_brief(
    repo_id: int,
    db_path: Optional[str] = None,
    skip_if_exists: bool = True,
) -> dict[int, list]:
    """
    为仓库内每个 group 的 filelist 生成 brief，
    批量写入 group.filelist 的 brief 字段。

    依赖：file.description 已完成（Step 14）。

    Returns
    -------
    dict[int, list]  {group_id → 更新后的 filelist}
    """
    from llm.client  import chat_completion_json
    from llm.prompts import (
        ANALYZE_AREA_FILELIST_BRIEF_SYSTEM,
        ANALYZE_AREA_FILELIST_BRIEF_USER,
    )
    import json as _j

    _db   = db_path or DB_PATH
    repo  = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_group_filelist_brief] repo_id={repo_id} 不存在。")

    groups = GroupDB.list_by_repo(repo_id, db_path=_db)
    print(
        f"[analyze_group_filelist_brief] 目标仓库：{repo['name']}，"
        f"共 {len(groups)} 个 group"
    )

    result: dict[int, list] = {}
    processed = skipped = error = 0

    for group_rec in groups:
        group_id   = group_rec["id"]
        group_name = group_rec["name"]
        filelist  = group_rec.get("filelist") or []
        if isinstance(filelist, str):
            try:
                filelist = _j.loads(filelist)
            except Exception:
                filelist = []

        if not filelist:
            result[group_id] = []
            skipped += 1
            continue

        if skip_if_exists and all(e.get("brief") for e in filelist):
            result[group_id] = filelist
            skipped += 1
            continue

        # 收集文件描述
        file_lines: list[str] = []
        for entry in filelist:
            fid   = entry.get("file_id")
            fname = entry.get("name", "")
            if fid:
                file_rec = FileDB.get_by_id(fid, db_path=_db)
                raw_desc = (file_rec or {}).get("description", "") or ""
                desc     = raw_desc[:_AREA_MAX_DESC_CHARS]
            else:
                desc = ""
            if not desc:
                desc = f"[文件名] {fname}"
            file_lines.append(f"file_id={fid}  name={fname}\n描述：{desc}\n")

        file_list_text = "\n---\n".join(file_lines)
        user_content   = ANALYZE_AREA_FILELIST_BRIEF_USER.format(
            group_name      = group_name,
            file_count     = len(filelist),
            file_list_text = file_list_text,
        )
        messages = [
            {"role": "system", "content": ANALYZE_AREA_FILELIST_BRIEF_SYSTEM},
            {"role": "user",   "content": user_content},
        ]

        try:
            def _call():
                return chat_completion_json(messages=messages, temperature=0.1)

            raw = _group_retry(_call, label=f"group_id={group_id} {group_name}")
        except Exception as exc:
            print(f"[analyze_group_filelist_brief]   ✗ {group_name}：{exc}")
            result[group_id] = filelist
            error += 1
            continue

        briefs_list = raw.get("briefs", []) if isinstance(raw, dict) else []
        brief_map   = {int(b["file_id"]): b["brief"]
                       for b in briefs_list
                       if isinstance(b, dict) and b.get("file_id") is not None}

        new_filelist = []
        for entry in filelist:
            new_entry = dict(entry)
            fid = entry.get("file_id")
            if fid and fid in brief_map:
                new_entry["brief"] = brief_map[fid]
            new_filelist.append(new_entry)

        GroupDB.update(group_id, db_path=_db, filelist=new_filelist)
        result[group_id] = new_filelist
        processed += 1
        print(
            f"[analyze_group_filelist_brief]   ✓ {group_name}"
            f"  files={len(new_filelist)}  briefs_updated={len(brief_map)}"
        )

    print(
        f"[analyze_group_filelist_brief] ✓ 完成："
        f"处理={processed}  跳过={skipped}  失败={error}"
    )
    return result


def analyze_group_description(
    repo_id: int,
    db_path: Optional[str] = None,
    skip_if_exists: bool = True,
) -> dict[int, str]:
    """
    为仓库内每个 group 生成自然语言描述，写入 group.description。

    依赖：file.description 已完成（Step 14）。

    Returns
    -------
    dict[int, str]  {group_id → description_text}
    """
    from llm.client  import chat_completion
    from llm.prompts import (
        ANALYZE_AREA_DESCRIPTION_SYSTEM,
        ANALYZE_AREA_DESCRIPTION_USER,
    )
    import json as _j

    _db   = db_path or DB_PATH
    repo  = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_group_description] repo_id={repo_id} 不存在。")

    groups = GroupDB.list_by_repo(repo_id, db_path=_db)
    print(
        f"[analyze_group_description] 目标仓库：{repo['name']}，"
        f"共 {len(groups)} 个 group"
    )

    result:   dict[int, str] = {}
    processed = skipped = error = 0

    for group_rec in groups:
        group_id   = group_rec["id"]
        group_name = group_rec["name"]
        group_path = group_rec.get("path", "")
        rationale = group_rec.get("rationale", "")

        if skip_if_exists and group_rec.get("description"):
            result[group_id] = group_rec["description"]
            skipped += 1
            continue

        # 文件结构列表
        filelist = group_rec.get("filelist") or []
        if isinstance(filelist, str):
            try:
                filelist = _j.loads(filelist)
            except Exception:
                filelist = []

        file_structure = "\n".join(
            f"  {e.get('name','')}  {e.get('brief','')}"
            for e in filelist
        ) or "（无文件记录）"

        # 各文件描述
        file_desc_parts: list[str] = []
        for entry in filelist[:30]:
            fid   = entry.get("file_id")
            fname = entry.get("name", "")
            brief = entry.get("brief", "")
            if fid:
                file_rec = FileDB.get_by_id(fid, db_path=_db)
                desc     = (file_rec or {}).get("description", "") or ""
                desc     = desc[:500]
            else:
                desc = brief
            file_desc_parts.append(f"### {fname}\n{desc or brief or '（暂无描述）'}")
        file_descriptions = "\n\n".join(file_desc_parts) or "（无文件描述）"

        user_content = ANALYZE_AREA_DESCRIPTION_USER.format(
            group_name         = group_name,
            group_path         = group_path,
            rationale         = rationale or "（未提供）",
            file_structure    = file_structure,
            file_descriptions = file_descriptions,
        )
        messages = [
            {"role": "system", "content": ANALYZE_AREA_DESCRIPTION_SYSTEM},
            {"role": "user",   "content": user_content},
        ]

        try:
            def _call():
                return chat_completion(messages=messages, temperature=0.2)

            desc = _group_retry(_call, label=f"group_id={group_id} {group_name}")
            desc = desc.strip()
        except Exception as exc:
            print(f"[analyze_group_description]   ✗ {group_name}：{exc}")
            result[group_id] = ""
            error += 1
            continue

        GroupDB.update(group_id, db_path=_db, description=desc)
        result[group_id] = desc
        processed += 1
        print(f"[analyze_group_description]   ✓ {group_name}  ({len(desc)} 字符)")

    print(
        f"[analyze_group_description] ✓ 完成："
        f"处理={processed}  跳过={skipped}  失败={error}"
    )
    return result