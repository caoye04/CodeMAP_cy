"""
test/mainbuild_step0-7.py

对 minizip-ng 完整执行 Step 0-7 构建流程，不限制处理函数数量。

──────────────────────────────────────────────────────────────────────
执行顺序
──────────────────────────────────────────────────────────────────────
  Step 0 : init_repo
  Step 1 : analyze_repo_language
  Step 2 : analyze_repo_area                        （LLM）
  Step 3 : analyze_area_file
  Step 4 : analyze_file_language + analyze_file_func
  Step 5 : build_callgraph
  Step 6 : analyze_func_callgraph
  Step 7 : analyze_func_precondition  ─┐
           analyze_func_postcondition  ├─ ThreadPoolExecutor 三路并行
           analyze_func_exception     ─┘

──────────────────────────────────────────────────────────────────────
并行策略（Step 7）
──────────────────────────────────────────────────────────────────────
  · 三种分析写入 DB 的列不同（precondition / postcondition / exception），
    无行级写-写冲突，可安全并发。
  · LLM 调用为网络 I/O，Python GIL 在 socket.recv 阻塞时主动释放，
    线程真正并发，无需 multiprocessing。
  · DB 启用 WAL 模式：读不阻塞写，写操作由 SQLite 内部串行化，
    不会出现 SQLITE_BUSY 或数据损坏。
  · 理论加速比 ≈ ×3（取决于 LLM 端的并发上限）。
  · 若遇 API 限速错误，将 MAX_STEP7_WORKERS 调低为 2 或 1。

──────────────────────────────────────────────────────────────────────
断点续建
──────────────────────────────────────────────────────────────────────
  默认使用 skip_if_exists=True：DB 中已有数据的函数自动跳过，
  中断后重新执行脚本不会重复调用 LLM。
  使用 --force 可清空 DB 重新全量构建。

──────────────────────────────────────────────────────────────────────
输出
──────────────────────────────────────────────────────────────────────
  数据库 : data/test_db/db_minizip-ng_main.db
  日志   : test/log/mainbuild_<YYYYMMDD_HHMMSS>.log

──────────────────────────────────────────────────────────────────────
运行
──────────────────────────────────────────────────────────────────────
  python test/mainbuild_step0-7.py
  python test/mainbuild_step0-7.py --force   # 清空旧 DB 后重建
"""

import argparse
import logging
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ── 路径 ─────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..'))

from db.dao import init_db, FuncDB, FileDB
from analyzer.repo_analyzer     import init_repo, analyze_repo_language, analyze_repo_area
from analyzer.area_analyzer     import analyze_area_file
from analyzer.file_analyzer     import analyze_file_language, analyze_file_func
from analyzer.callgraph_builder import build_callgraph, analyze_func_callgraph
from analyzer.func_analyzer     import (
    analyze_func_precondition,
    analyze_func_postcondition,
    analyze_func_exception,
)
from config import DATA_DIR

# ── 配置 ─────────────────────────────────────────────────────────────────────

_REPO_PATH = os.path.abspath(
    os.path.join(_HERE, '../../../repo_4_codemap/minizip-ng')
)
_DB_DIR  = os.path.join(DATA_DIR, 'test_db')
_DB_PATH = os.path.join(_DB_DIR, 'db_minizip-ng_main.db')

# Step 7 并行工作线程数
#   3 → 三路同时调用 LLM，约 ×3 加速（推荐）
#   2 → 遇 API 限速时降级
#   1 → 完全串行，用于排查问题
MAX_STEP7_WORKERS = 3


# ── 日志 ─────────────────────────────────────────────────────────────────────

def _setup_logger() -> logging.Logger:
    log_dir = os.path.join(_HERE, 'log')
    os.makedirs(log_dir, exist_ok=True)
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'mainbuild_{ts}.log')

    logger = logging.getLogger('mainbuild')
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s  %(levelname)-7s  %(message)s', datefmt='%H:%M:%S'
        ))

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            '%(asctime)s  %(message)s', datefmt='%H:%M:%S'
        ))

        logger.addHandler(fh)
        logger.addHandler(ch)

    logger.info('=' * 70)
    logger.info('minizip-ng  全量构建  Step 0-7')
    logger.info(f'仓库  : {_REPO_PATH}')
    logger.info(f'DB    : {_DB_PATH}')
    logger.info(f'日志  : {log_file}')
    logger.info(f'Step7 并行度 : MAX_STEP7_WORKERS = {MAX_STEP7_WORKERS}')
    logger.info('=' * 70)
    return logger


_log = _setup_logger()


# ── SQLite WAL 模式 ───────────────────────────────────────────────────────────

def _enable_wal(db_path: str) -> None:
    """
    开启 WAL（Write-Ahead Logging）日志模式。

    Step 7 三路线程并发写入同一 DB 时，默认 DELETE 模式会频繁触发
    SQLITE_BUSY。WAL 模式下写操作在 SQLite 内部串行化，各线程无需
    额外加锁即可安全并发。synchronous=NORMAL 在安全性与性能间取平衡。
    """
    with sqlite3.connect(db_path) as conn:
        mode = conn.execute('PRAGMA journal_mode=WAL').fetchone()[0]
        conn.execute('PRAGMA synchronous=NORMAL')
    _log.debug(f'[WAL] journal_mode = {mode}')


# ── 计时上下文管理器 ─────────────────────────────────────────────────────────

class _Timer:
    """with _Timer('Step N  xxx'): ..."""

    def __init__(self, label: str):
        self._label = label
        self._t0    = 0.0

    def __enter__(self):
        self._t0 = time.time()
        _log.info(f'▶ {self._label}')
        return self

    def __exit__(self, *_):
        elapsed     = time.time() - self._t0
        mins, secs  = divmod(int(elapsed), 60)
        duration    = f'{mins}m {secs}s' if mins else f'{secs}s'
        _log.info(f'◀ {self._label}  耗时 {duration}')


# ── 获取全量 C 函数 ID ────────────────────────────────────────────────────────

def _get_all_c_func_ids(repo_id: int) -> list[int]:
    """
    返回仓库内所有 C 语言函数的 func_id 列表，不设数量上限。
    排列顺序：有 callee（有实际调用）的函数优先，其余追加其后。
    """
    all_files  = FileDB.list_by_repo(repo_id, db_path=_DB_PATH)
    c_file_ids = {f['id'] for f in all_files if f.get('language') == 'C'}

    all_funcs  = FuncDB.list_by_repo(repo_id, db_path=_DB_PATH)

    with_callee = [
        f for f in all_funcs
        if f.get('file_id') in c_file_ids
        and isinstance(f.get('callgraph'), dict)
        and f['callgraph'].get('callees')
    ]
    wc_ids = {f['id'] for f in with_callee}
    without_callee = [
        f for f in all_funcs
        if f.get('file_id') in c_file_ids and f['id'] not in wc_ids
    ]

    ids = [f['id'] for f in with_callee + without_callee]
    _log.info(
        f'[func_ids]  C 函数共 {len(ids)} 个'
        f'（有 callee={len(with_callee)}，无 callee={len(without_callee)}）'
    )
    return ids


# ── Step 7 并行分析 ───────────────────────────────────────────────────────────

def _run_step7_parallel(
    repo_id: int,
    func_ids: list[int],
) -> tuple[dict, dict, dict]:
    """
    用 ThreadPoolExecutor 并行执行三路 Step 7 分析。

    skip_if_exists=True：DB 中已有数据的函数自动跳过，
    支持中断后重新执行脚本续建，不会重复调用 LLM。
    """
    task_defs = [
        ('precondition',  analyze_func_precondition),
        ('postcondition', analyze_func_postcondition),
        ('exception',     analyze_func_exception),
    ]
    results: dict[str, dict] = {}
    t0 = time.time()

    _log.info(
        f'  三路并行启动'
        f'（workers={MAX_STEP7_WORKERS}，目标函数={len(func_ids)} 个）'
    )

    with ThreadPoolExecutor(
        max_workers=MAX_STEP7_WORKERS,
        thread_name_prefix='step7',
    ) as pool:
        future_to_name = {
            pool.submit(
                fn,
                repo_id,
                db_path=_DB_PATH,
                func_ids=func_ids,
                skip_if_exists=True,
            ): name
            for name, fn in task_defs
        }

        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                r        = future.result()
                nonempty = sum(1 for v in r.values() if v)
                results[name] = r
                _log.info(
                    f'  ✓ {name:<15s}  写库={len(r)} 个'
                    f'  有数据={nonempty}/{len(r)}'
                    f'  已耗时={time.time() - t0:.0f}s'
                )
            except Exception as exc:
                _log.error(f'  ✗ {name} 发生异常：{exc}', exc_info=True)
                results[name] = {}

    _log.info(f'  三路分析全部完成，总耗时 {time.time() - t0:.1f}s')
    return (
        results.get('precondition',  {}),
        results.get('postcondition', {}),
        results.get('exception',     {}),
    )


# ── 汇总报告 ─────────────────────────────────────────────────────────────────

def _print_summary(
    pre: dict, post: dict, exc: dict, total_elapsed: float
) -> None:
    def _stats(d: dict) -> tuple[int, int, float]:
        total    = len(d)
        nonempty = sum(1 for v in d.values() if v)
        avg_len  = (
            sum(len(v) for v in d.values() if v) / nonempty
            if nonempty else 0.0
        )
        return nonempty, total, avg_len

    mins, secs = divmod(int(total_elapsed), 60)

    _log.info('')
    _log.info('=' * 70)
    _log.info('构建完成  汇总报告')
    _log.info(f'  DB       : {_DB_PATH}')
    _log.info(f'  总耗时   : {mins}m {secs}s  ({total_elapsed:.0f}s)')
    _log.info('  ─── Step 7 覆盖率 ───────────────────────────────────────')
    for label, d in [
        ('precondition',  pre),
        ('postcondition', post),
        ('exception',     exc),
    ]:
        ne, tot, avg = _stats(d)
        pct = ne / tot * 100 if tot else 0.0
        _log.info(
            f'  {label:<15s}: 有数据={ne}/{tot} ({pct:.0f}%)'
            f'  平均条数={avg:.1f}'
        )
    _log.info('=' * 70)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='minizip-ng 全量构建 Step 0-7（无函数数量限制）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python test/mainbuild_step0-7.py           # 增量续建（已有数据跳过）
  python test/mainbuild_step0-7.py --force   # 删除旧 DB 后重建
        """.strip(),
    )
    parser.add_argument(
        '--force', action='store_true',
        help='删除旧 DB 后重建（默认：增量续建，已有数据自动跳过）',
    )
    args = parser.parse_args()

    # ── 前置检查 ──────────────────────────────────────────────────────────────
    if not os.path.isdir(_REPO_PATH):
        _log.error(f'仓库路径不存在，请确认：{_REPO_PATH}')
        sys.exit(1)

    # ── 准备 DB ───────────────────────────────────────────────────────────────
    os.makedirs(_DB_DIR, exist_ok=True)
    if args.force and os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)
        _log.info('[--force] 已删除旧数据库，将全量重建')

    init_db(_DB_PATH)
    _enable_wal(_DB_PATH)

    total_t0 = time.time()

    # ── Step 0：初始化仓库 ────────────────────────────────────────────────────
    with _Timer('Step 0  init_repo'):
        repo_id = init_repo(_REPO_PATH, db_path=_DB_PATH)
    _log.info(f'  repo_id = {repo_id}')

    # ── Step 1：仓库语言统计 ──────────────────────────────────────────────────
    with _Timer('Step 1  analyze_repo_language'):
        lang_r = analyze_repo_language(repo_id, db_path=_DB_PATH)
    _log.info(f'  主语言 : {lang_r.get("main")}')

    # ── Step 2：模块/区域划分（LLM）──────────────────────────────────────────
    with _Timer('Step 2  analyze_repo_area  [LLM]'):
        area_r = analyze_repo_area(repo_id, db_path=_DB_PATH)
    _log.info(f'  area 数 : {len(area_r)}')

    # ── Step 3：文件归属 ──────────────────────────────────────────────────────
    with _Timer('Step 3  analyze_area_file'):
        file_r = analyze_area_file(repo_id, db_path=_DB_PATH)
    _log.info(f'  file 数 : {sum(len(v) for v in file_r.values())}')

    # ── Step 4：文件语言识别 + 函数提取 ──────────────────────────────────────
    with _Timer('Step 4  analyze_file_language + analyze_file_func'):
        analyze_file_language(repo_id, db_path=_DB_PATH)
        func_r = analyze_file_func(repo_id, db_path=_DB_PATH)
    _log.info(f'  func 数 : {sum(len(v) for v in func_r.values())}')

    # ── Step 5：构建调用图 ────────────────────────────────────────────────────
    with _Timer('Step 5  build_callgraph'):
        cg_path = build_callgraph(repo_id, db_path=_DB_PATH)
    _log.info(f'  callgraph : {cg_path}')

    # ── Step 6：写入调用关系 ──────────────────────────────────────────────────
    with _Timer('Step 6  analyze_func_callgraph'):
        cg_r = analyze_func_callgraph(
            repo_id, db_path=_DB_PATH, callgraph_path=cg_path
        )
    _log.info(f'  callgraph 写库 : {len(cg_r)} 个函数')

    # ── Step 7：前置/后置/异常分析（三路并行）────────────────────────────────
    func_ids = _get_all_c_func_ids(repo_id)
    with _Timer('Step 7  precondition / postcondition / exception  [LLM × 3 并行]'):
        pre, post, exc = _run_step7_parallel(repo_id, func_ids)

    # ── 汇总 ──────────────────────────────────────────────────────────────────
    _print_summary(pre, post, exc, time.time() - total_t0)


if __name__ == '__main__':
    main()