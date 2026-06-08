"""
analyzer/area_analyzer.py
CodeMAP Area 层分析器

实现：
  - analyze_area_file : 扫描每个 area 路径下的文件结构，
                        写入 file 表并更新 area.filelist，
                        中间产物保存至 data/analyze_area_file/<repo_name>.json
"""

import json as _json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, AreaDB, FileDB
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


def _scan_area_files(
    area_abs_path: str,
    repo_path: str,
    other_area_abs_paths: set[str],
) -> list[dict]:
    """
    递归扫描 area 目录，返回所有有效文件的 name + path 列表。

    关键设计：**不递归进入属于其他 area 的子目录**，从根源上避免
    同一文件被重复归属到多个 area（当 area 路径存在包含关系时尤其重要，
    例如 area='.' 与 area='src/' 同时存在）。

    Parameters
    ----------
    area_abs_path : str
        当前 area 目录的绝对路径
    repo_path : str
        仓库根目录的绝对路径（用于计算 file 的相对路径）
    other_area_abs_paths : set[str]
        其他所有 area 的绝对路径集合；遇到匹配的子目录时跳过

    Returns
    -------
    list[dict]
        每项 {"name": str, "path": str}
        path 相对于仓库根，统一使用 '/' 分隔符
    """
    collected: list[dict] = []

    for root, dirs, filenames in os.walk(area_abs_path, topdown=True):
        # ---------- 过滤子目录 ----------
        dirs_keep: list[str] = []
        for d in sorted(dirs):
            # 忽略列表 & 隐藏目录
            if d in _IGNORE_DIRS or d.startswith('.'):
                continue
            # 属于另一个独立 area 的目录 → 不递归，由该 area 自行扫描
            child_abs = os.path.normpath(os.path.join(root, d))
            if child_abs in other_area_abs_paths:
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
#  analyze_area_file
# ==================================================================

def analyze_area_file(
    repo_id: int,
    db_path: str | None = None,
    force: bool = False,
) -> dict[int, list[dict]]:
    """
    扫描仓库每个 area 路径下的文件，写入 file 表并更新 area.filelist。

    流程
    ----
    1. 读取仓库信息和所有 area 记录
    2. 预计算各 area 的绝对路径，构造互斥集合（防重叠扫描）
    3. 对每个 area 递归扫描文件，_is_useful_file() 过滤无效文件
    4. 将文件写入 file 表（name / path），防御性地检测路径重复
    5. 更新 area.filelist（file_id + name，brief 留空待后续步骤填充）
    6. 汇总写出中间产物 JSON → data/analyze_area_file/<repo_name>.json

    数据库写入字段
    --------------
    - file.name   : 文件名（basename）
    - file.path   : 相对仓库根的路径，'/' 分隔
    - area.filelist: [{"file_id": int, "name": str, "brief": ""}]

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
        键为 area_id，值为该 area 下已入库的文件列表，每项：
        {
            "file_id": int,
            "name":    str,
            "path":    str,  # 相对仓库根，'/' 分隔
        }

    Raises
    ------
    ValueError
        · repo_id 在数据库中不存在
        · 该仓库尚无 area 记录（需先执行 analyze_repo_area）
        · force=False 且已有 file 记录
    """
    _db = db_path or DB_PATH

    # ── ① 取仓库信息 ────────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_area_file] repo_id={repo_id} 在数据库中不存在。"
        )

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[analyze_area_file] 目标仓库：{repo_name}（{repo_path}）")

    # ── ② 取 area 列表 ──────────────────────────────────────────────
    areas = AreaDB.list_by_repo(repo_id, db_path=_db)
    if not areas:
        raise ValueError(
            f"[analyze_area_file] repo_id={repo_id} 无 area 记录，"
            "请先执行 analyze_repo_area。"
        )
    print(f"[analyze_area_file] 共 {len(areas)} 个 area，开始扫描文件…")

    # ── ③ 处理已有 file 记录 ────────────────────────────────────────
    existing_files = FileDB.list_by_repo(repo_id, db_path=_db)
    if existing_files:
        if force:
            for f in existing_files:
                FileDB.delete(f['id'], db_path=_db)
            print(f"[analyze_area_file] 已清除 {len(existing_files)} 条旧 file 记录。")
        else:
            raise ValueError(
                f"[analyze_area_file] repo_id={repo_id} 已有 {len(existing_files)} 个 file 记录。"
                " 如需重新扫描，请传入 force=True。"
            )

    # ── ④ 预计算各 area 绝对路径 ────────────────────────────────────
    # normpath 确保路径字符串可直接用集合匹配，Windows 下统一反斜杠
    area_abs_map: dict[int, str] = {}
    for area in areas:
        rel = area['path']
        abs_p = (
            repo_path
            if rel == '.'
            else os.path.normpath(os.path.join(repo_path, rel))
        )
        area_abs_map[area['id']] = abs_p

    # ── ⑤ 逐 area 扫描文件 ──────────────────────────────────────────
    result: dict[int, list[dict]]   = {}
    all_area_records: list[dict]    = []   # 用于中间产物 JSON

    for area in areas:
        area_id       = area['id']
        area_name     = area['name']
        area_path_rel = area['path']
        area_abs      = area_abs_map[area_id]

        # 路径不存在时发出警告并跳过（LLM 给出的路径可能已被删除/重命名）
        if not os.path.exists(area_abs):
            print(
                f"[analyze_area_file] ⚠ area '{area_name}' 路径不存在，"
                f"已跳过：{area_abs}"
            )
            result[area_id] = []
            continue

        # 当前 area 以外的所有 area 绝对路径（扫描时不递归进入）
        other_abs: set[str] = {
            p for aid, p in area_abs_map.items() if aid != area_id
        }

        print(
            f"[analyze_area_file]   扫描 area [{area_id:3d}] "
            f"'{area_name}'（{area_path_rel}）…"
        )

        raw_files = _scan_area_files(area_abs, repo_path, other_abs)
        print(f"[analyze_area_file]     → 发现 {len(raw_files)} 个有效文件")

        # ── ⑥ 写入 file 表 ──────────────────────────────────────────
        area_filelist:      list[dict] = []   # 写回 area.filelist
        area_file_records:  list[dict] = []   # 供调用方和中间产物使用

        for file_info in raw_files:
            file_name = file_info['name']
            file_path = file_info['path']   # 相对仓库根

            # 防御：若同一路径已存在（area 路径部分重叠时），不重复创建
            existing_file = FileDB.get_by_path(repo_id, file_path, db_path=_db)
            if existing_file is not None:
                file_id = existing_file['id']
                print(
                    f"[analyze_area_file]     ⚠ 路径已存在（area 路径重叠？）："
                    f"{file_path} → 复用 file_id={file_id}"
                )
            else:
                file_id = FileDB.create(
                    repo_id = repo_id,
                    area_id = area_id,
                    name    = file_name,
                    path    = file_path,
                    db_path = _db,
                )

            area_filelist.append({
                'file_id': file_id,
                'name':    file_name,
                'brief':   '',      # 留给 analyze_area_filelist_description（step16）填充
            })
            area_file_records.append({
                'file_id': file_id,
                'name':    file_name,
                'path':    file_path,
            })

        # ── ⑦ 更新 area.filelist ────────────────────────────────────
        AreaDB.update(area_id, db_path=_db, filelist=area_filelist)

        result[area_id] = area_file_records
        all_area_records.append({
            'area_id':    area_id,
            'area_name':  area_name,
            'area_path':  area_path_rel,
            'file_count': len(area_file_records),
            'files':      area_file_records,
        })

        print(
            f"[analyze_area_file]     ✓ '{area_name}'："
            f"{len(area_file_records)} 个文件已入库"
        )

    # ── ⑧ 保存中间产物 JSON ─────────────────────────────────────────
    output_dir  = os.path.join(DATA_DIR, 'analyze_area_file')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{repo_name}.json")

    total_files = sum(len(v) for v in result.values())
    intermediate = {
        'repo_id':   repo_id,
        'repo_name': repo_name,
        'repo_path': repo_path,
        'summary': {
            'total_areas': len(areas),
            'total_files': total_files,
        },
        'areas': all_area_records,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        _json.dump(intermediate, f, ensure_ascii=False, indent=2)
    print(f"[analyze_area_file] ✓ 中间产物 → {output_path}")

    print(
        f"[analyze_area_file] ✓ 完成：{len(areas)} 个 area，"
        f"共 {total_files} 个文件已入库。"
    )
    return result