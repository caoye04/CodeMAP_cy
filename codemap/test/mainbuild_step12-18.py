"""
test/mainbuild_step12-18.py

在已有 Step 0-7 数据库基础上，为 minizip-ng 补充完成 后续 的全量描述生成。

──────────────────────────────────────────────────────────────────────
执行顺序（均支持断点续建，skip_if_exists=True）
──────────────────────────────────────────────────────────────────────
  Step 12 : analyze_func_description        [Agent × parallel 10，重试5次]
  Step 13 : analyze_file_funclist_brief     [LLM batch per file，重试5次]
  Step 14 : analyze_file_description        [LLM per file，重试5次]
  Step 15 : analyze_area_filelist_brief     [LLM batch per area，重试5次]
  Step 16 : analyze_area_description        [LLM per area，重试5次]
  Step 17 : analyze_repo_arealist_brief     [LLM batch，重试5次]
  Step 18 : analyze_repo_description        [LLM，重试5次]

──────────────────────────────────────────────────────────────────────
前置条件
──────────────────────────────────────────────────────────────────────
  已完成 Step 0-7，数据库存在于：
    data/test_db/db_minizip-ng_main.db

──────────────────────────────────────────────────────────────────────
断点续建
──────────────────────────────────────────────────────────────────────
  默认 skip_if_exists=True：DB 中已有描述的实体自动跳过。
  --force  重新生成所有描述（不删除 DB，仅覆盖写入）。
  --step N 只执行从第 N 步开始（如 --step 14 跳过前3步）。

──────────────────────────────────────────────────────────────────────
输出
──────────────────────────────────────────────────────────────────────
  复用数据库 : data/test_db/db_minizip-ng_main.db
  日志       : test/log/mainbuild_step12-18_<YYYYMMDD_HHMMSS>.log

──────────────────────────────────────────────────────────────────────
运行
──────────────────────────────────────────────────────────────────────
  python test/mainbuild_step12-18.py
  python test/mainbuild_step12-18.py --force
  python test/mainbuild_step12-18.py --step 14
  python test/mainbuild_step12-18.py --force --step 16
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime

# ── 路径 ─────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..'))

from db.dao  import RepoDB, FuncDB, FileDB
from config  import DATA_DIR

from analyzer.func_analyzer  import analyze_func_description
from analyzer.file_analyzer  import (
    analyze_file_funclist_brief,
    analyze_file_description,
)
from analyzer.area_analyzer  import (
    analyze_area_filelist_brief,
    analyze_area_description,
)
from analyzer.repo_analyzer  import (
    analyze_repo_arealist_brief,
    analyze_repo_description,
)

# ── 配置 ─────────────────────────────────────────────────────────────────────

_DB_PATH = os.path.join(DATA_DIR, 'test_db', 'db_minizip-ng_main.db')

# Step 12 并发度（Agent per func）
FUNC_DESC_WORKERS = 10


# ── 日志 ─────────────────────────────────────────────────────────────────────

def _setup_logger() -> logging.Logger:
    log_dir  = os.path.join(_HERE, 'log')
    os.makedirs(log_dir, exist_ok=True)
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'mainbuild_step12-18_{ts}.log')

    logger = logging.getLogger('mainbuild_step12-18')
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
    logger.info('minizip-ng  Step 8 描述生成  (基于已有 Step 0-7 数据库)')
    logger.info(f'DB   : {_DB_PATH}')
    logger.info(f'日志 : {log_file}')
    logger.info('=' * 70)
    return logger


_log = _setup_logger()


# ── 计时上下文 ────────────────────────────────────────────────────────────────

class _Timer:
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


# ── 统计工具 ──────────────────────────────────────────────────────────────────

def _count_nonempty(d: dict) -> tuple[int, int]:
    """返回 (有数据数量, 总数量)"""
    total    = len(d)
    nonempty = sum(1 for v in d.values() if v)
    return nonempty, total


def _print_summary(
    repo_id: int,
    step_results: dict[int, dict],
    total_elapsed: float,
) -> None:
    """打印 Step 8 汇总报告。"""
    mins, secs = divmod(int(total_elapsed), 60)
    _log.info('')
    _log.info('=' * 70)
    _log.info('Step 8 构建完成  汇总报告')
    _log.info(f'  DB      : {_DB_PATH}')
    _log.info(f'  总耗时  : {mins}m {secs}s  ({total_elapsed:.0f}s)')
    _log.info('  ─── 各步骤结果 ───────────────────────────────────────────')

    labels = {
        12: 'Step 12  func.description',
        13: 'Step 13  file funclist brief',
        14: 'Step 14  file.description',
        15: 'Step 15  area filelist brief',
        16: 'Step 16  area.description',
        17: 'Step 17  repo arealist brief',
        18: 'Step 18  repo.description',
    }
    for step, label in labels.items():
        res = step_results.get(step)
        if res is None:
            _log.info(f'  {label:<40s} [跳过]')
        elif isinstance(res, dict):
            ne, tot = _count_nonempty(res)
            pct = ne / tot * 100 if tot else 0
            _log.info(f'  {label:<40s} {ne}/{tot} ({pct:.0f}%)')
        elif isinstance(res, (list, str)):
            n = len(res) if isinstance(res, list) else (1 if res else 0)
            _log.info(f'  {label:<40s} ok ({n})')

    # 额外：从 DB 直接统计 func.description 覆盖率
    all_funcs    = FuncDB.list_by_repo(repo_id, db_path=_DB_PATH)
    with_desc    = sum(1 for f in all_funcs if f.get('description'))
    _log.info(
        f'\n  func.description DB 实际覆盖：{with_desc}/{len(all_funcs)}'
        f'  ({with_desc/len(all_funcs)*100:.1f}%)' if all_funcs else ''
    )
    _log.info('=' * 70)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='minizip-ng Step 8 全量描述生成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python test/mainbuild_step12-18.py                 # 增量续建
  python test/mainbuild_step12-18.py --force         # 覆盖重建所有描述
  python test/mainbuild_step12-18.py --step 14       # 从 Step 14 开始
  python test/mainbuild_step12-18.py --force --step 16  # 强制重建 Step 16+
        """.strip(),
    )
    parser.add_argument(
        '--force', action='store_true',
        help='覆盖已有描述重新生成（默认：增量，已有数据跳过）',
    )
    parser.add_argument(
        '--step', type=int, default=12, choices=range(12, 19),
        metavar='N',
        help='从第 N 步开始执行（12-18，默认12）',
    )
    args = parser.parse_args()

    skip = not args.force
    start_step = args.step

    # ── 前置检查 ──────────────────────────────────────────────────────────────
    if not os.path.isfile(_DB_PATH):
        _log.error(
            f'数据库文件不存在：{_DB_PATH}\n'
            '请先运行 python test/mainbuild_step0-7.py 完成 Step 0-7 构建。'
        )
        sys.exit(1)

    # 取 repo_id
    repo = RepoDB.get_by_name('minizip-ng', db_path=_DB_PATH)
    if repo is None:
        _log.error(
            "数据库中未找到 'minizip-ng' 仓库记录。"
            "请确认 Step 0-7 已成功完成。"
        )
        sys.exit(1)

    repo_id = repo['id']
    _log.info(f'repo_id = {repo_id}  (minizip-ng)')
    _log.info(f'skip_if_exists = {skip}  start_step = {start_step}')

    total_t0      = time.time()
    step_results: dict[int, object] = {}

    # ── Step 12: analyze_func_description ────────────────────────────────────
    if start_step <= 12:
        with _Timer(f'Step 12  analyze_func_description  [Agent × {FUNC_DESC_WORKERS} 并行]'):
            res = analyze_func_description(
                repo_id        = repo_id,
                db_path        = _DB_PATH,
                skip_if_exists = skip,
                languages      = ['C', 'C++'],
                max_workers    = FUNC_DESC_WORKERS,
            )
        ne, tot = _count_nonempty(res)
        _log.info(f'  描述生成：{ne}/{tot} 个函数')
        step_results[12] = res
    else:
        _log.info(f'Step 12 跳过（--step={start_step}）')
        step_results[12] = None

    # ── Step 13: analyze_file_funclist_brief ──────────────────────────────────
    if start_step <= 13:
        with _Timer('Step 13  analyze_file_funclist_brief'):
            res = analyze_file_funclist_brief(
                repo_id        = repo_id,
                db_path        = _DB_PATH,
                skip_if_exists = skip,
            )
        _log.info(f'  处理文件：{len(res)} 个')
        step_results[13] = res
    else:
        _log.info(f'Step 13 跳过（--step={start_step}）')
        step_results[13] = None

    # ── Step 14: analyze_file_description ────────────────────────────────────
    if start_step <= 14:
        with _Timer('Step 14  analyze_file_description'):
            res = analyze_file_description(
                repo_id        = repo_id,
                db_path        = _DB_PATH,
                skip_if_exists = skip,
            )
        ne, tot = _count_nonempty(res)
        _log.info(f'  描述生成：{ne}/{tot} 个文件')
        step_results[14] = res
    else:
        _log.info(f'Step 14 跳过（--step={start_step}）')
        step_results[14] = None

    # ── Step 15: analyze_area_filelist_brief ──────────────────────────────────
    if start_step <= 15:
        with _Timer('Step 15  analyze_area_filelist_brief'):
            res = analyze_area_filelist_brief(
                repo_id        = repo_id,
                db_path        = _DB_PATH,
                skip_if_exists = skip,
            )
        _log.info(f'  处理 area：{len(res)} 个')
        step_results[15] = res
    else:
        _log.info(f'Step 15 跳过（--step={start_step}）')
        step_results[15] = None

    # ── Step 16: analyze_area_description ────────────────────────────────────
    if start_step <= 16:
        with _Timer('Step 16  analyze_area_description'):
            res = analyze_area_description(
                repo_id        = repo_id,
                db_path        = _DB_PATH,
                skip_if_exists = skip,
            )
        ne, tot = _count_nonempty(res)
        _log.info(f'  描述生成：{ne}/{tot} 个 area')
        step_results[16] = res
    else:
        _log.info(f'Step 16 跳过（--step={start_step}）')
        step_results[16] = None

    # ── Step 17: analyze_repo_arealist_brief ──────────────────────────────────
    if start_step <= 17:
        with _Timer('Step 17  analyze_repo_arealist_brief'):
            res = analyze_repo_arealist_brief(
                repo_id        = repo_id,
                db_path        = _DB_PATH,
                skip_if_exists = skip,
            )
        _log.info(f'  arealist brief 条目：{len(res)} 个')
        step_results[17] = res
    else:
        _log.info(f'Step 17 跳过（--step={start_step}）')
        step_results[17] = None

    # ── Step 18: analyze_repo_description ────────────────────────────────────
    if start_step <= 18:
        with _Timer('Step 18  analyze_repo_description'):
            desc = analyze_repo_description(
                repo_id        = repo_id,
                db_path        = _DB_PATH,
                skip_if_exists = skip,
            )
        _log.info(f'  仓库描述：{len(desc)} 字符')
        step_results[18] = desc
    else:
        _log.info(f'Step 18 跳过（--step={start_step}）')
        step_results[18] = None

    # ── 汇总 ─────────────────────────────────────────────────────────────────
    _print_summary(repo_id, step_results, time.time() - total_t0)


if __name__ == '__main__':
    main()