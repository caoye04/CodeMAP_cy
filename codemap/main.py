"""
main.py
CodeMAP 主流程入口 —— build_codemap

────────────────────────────────────────────────────────────────────
  Step  1 : init_repo
  Step  2 : analyze_repo_language
  Step  3 : analyze_repo_area                        [LLM]
  Step  4 : analyze_area_file
  Step  5 : analyze_file_language
  Step  6 : analyze_file_func
  Step  7 : build_callgraph
  Step  8 : analyze_func_callgraph
  Step  9 : analyze_func_precondition                [SA+LLM]
  Step 10 : analyze_func_postcondition               [SA+LLM]
  Step 11 : analyze_func_exception                   [SA+LLM]
  Step 12 : analyze_func_description                 [LLM]
  Step 13 : analyze_file_funclist_brief              [LLM batch]
  Step 14 : analyze_file_description                 [LLM]
  Step 15 : analyze_area_filelist_brief              [LLM batch]
  Step 16 : analyze_area_description                 [LLM]
  Step 17 : analyze_repo_arealist_brief              [LLM batch]
  Step 18 : analyze_repo_description                 [LLM]
  Step 19 : build_codemap

命令行用法
──────────────────────────────────────────────────────────────────────
  # 首次全量分析（使用默认数据库路径）
  python main.py /path/to/repo

  # 强制重建（清空同名仓库旧数据后重建）
  python main.py /path/to/repo --force

  # 指定仓库名和数据库路径
  python main.py /path/to/repo --repo-name my_project --db-path ./my.db
"""

import argparse
import logging
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

# ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from config import DB_PATH, DATA_DIR
from db.dao import init_db, RepoDB, FuncDB, FileDB

from analyzer.repo_analyzer import (
    init_repo,
    analyze_repo_language,
    analyze_repo_area,
    analyze_repo_arealist_brief,
    analyze_repo_description,
)
from analyzer.area_analyzer import (
    analyze_area_file,
    analyze_area_filelist_brief,
    analyze_area_description,
)
from analyzer.file_analyzer import (
    analyze_file_language,
    analyze_file_func,
    analyze_file_funclist_brief,
    analyze_file_description,
)
from analyzer.callgraph_builder import build_callgraph, analyze_func_callgraph
from analyzer.func_analyzer import analyze_func_summary


# ==================================================================
# 日志配置
# ==================================================================

def _make_logger(
    log_dir: Optional[str] = None,
) -> tuple[logging.Logger, str]:
    """
    创建构建日志器，同时输出到控制台（INFO）和日志文件（DEBUG）。

    Returns
    -------
    (logger, log_file_path)
    """
    _log_dir = log_dir or os.path.join(_HERE, 'logs')
    os.makedirs(_log_dir, exist_ok=True)

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(_log_dir, f'codemap_{ts}.log')

    # 使用时间戳命名避免多次调用时 handler 重叠
    logger = logging.getLogger(f'codemap_{ts}')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s  %(levelname)-7s  %(message)s',
        datefmt='%H:%M:%S',
    ))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        '%(asctime)s  %(message)s',
        datefmt='%H:%M:%S',
    ))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger, log_file


# ==================================================================
# 工具函数
# ==================================================================

def _enable_wal(db_path: str, logger: logging.Logger) -> None:
    """
    开启 SQLite WAL（Write-Ahead Logging）模式。

    并发写入同一数据库时，
    WAL 模式下 SQLite 内部串行化写操作，防止 SQLITE_BUSY 冲突。
    """
    try:
        with sqlite3.connect(db_path) as conn:
            mode = conn.execute('PRAGMA journal_mode=WAL').fetchone()[0]
            conn.execute('PRAGMA synchronous=NORMAL')
        logger.debug(f'[WAL] journal_mode = {mode}')
    except Exception as e:
        logger.warning(f'[WAL] 开启失败（不影响功能）：{e}')


class _Timer:
    """计时上下文管理器：打印步骤标签、开始/结束及耗时。"""

    def __init__(self, label: str, logger: logging.Logger):
        self._label  = label
        self._t0     = 0.0
        self._logger = logger

    def __enter__(self):
        self._t0 = time.time()
        self._logger.info(f'▶ {self._label}')
        return self

    def __exit__(self, exc_type, *_):
        elapsed    = time.time() - self._t0
        mins, secs = divmod(int(elapsed), 60)
        duration   = f'{mins}m {secs}s' if mins else f'{secs}s'
        icon       = '✓' if exc_type is None else '✗'
        self._logger.info(f'◀ {icon} {self._label}  耗时 {duration}')


def _find_repo_id(
    repo_name: str,
    repo_path: str,
    db_path: str,
) -> Optional[int]:
    """
    断点续建时，从数据库中定位已有仓库记录 ID。
    先按名称精确匹配，再按绝对路径兜底。
    """
    rec = RepoDB.get_by_name(repo_name, db_path=db_path)
    if rec:
        return rec['id']

    abs_path  = os.path.abspath(repo_path)
    all_repos = RepoDB.list_all(db_path=db_path)
    for r in all_repos:
        if os.path.abspath(r.get('path', '')) == abs_path:
            return r['id']

    return None

# ==================================================================
# build_codemap
# ==================================================================

def build_codemap(
    repo_path: str,
    repo_name: Optional[str] = None,
    db_path: Optional[str] = None,
    force: bool = False,
    start_step: int = 1,
    languages: Optional[list[str]] = None,
    skip_if_exists: bool = True,
    max_step9_11_workers: int = 3,
    max_step12_workers: int = 10,
    no_desc: bool = False,
    log_dir: Optional[str] = None,
) -> dict:
    """
    Parameters
    ----------
    repo_path : str
        仓库本地路径（绝对或相对均可，内部统一转为绝对路径）
    repo_name : str | None
        仓库名称；不传则取路径末尾目录名
    db_path : str | None
        SQLite 数据库路径；不传则使用 config.DB_PATH。
    force : bool
        True  = 对结构性步骤强制清空旧数据后重建
        False = 增量模式，各步骤已有数据自动跳过
    start_step : int
        从第几步开始执行，用于断点续建
    languages : list[str] | None
        函数分析的语言白名单；None 表示处理全部语言。
    skip_if_exists : bool
        True  = 已有数据的函数/文件自动跳过；False = 强制重新分析所有实体
    no_desc : bool
    log_dir : str | None
        日志输出目录；不传则使用 <project_root>/logs/。

    Returns
    -------
    dict
        构建结果摘要，字段包括：
        {
            'repo_id':       int,
            'repo_name':     str,
            'db_path':       str,
            'log_file':      str,
            'total_elapsed': float,    # 总耗时（秒）
            'step1':  {...},           # 各步骤简要统计
            'step2':  {...},
            ...
            'step18': {...},
        }

    Raises
    ------
    FileNotFoundError
        repo_path 不存在或不是目录
    """
    # ─────────────────────────────────────────────────
    abs_repo_path = os.path.abspath(repo_path)
    if not os.path.isdir(abs_repo_path):
        raise FileNotFoundError(
            f'[build_codemap] 仓库路径不存在或不是目录：{abs_repo_path}'
        )
    if not (1 <= start_step <= 18):
        raise ValueError(
            f'[build_codemap] start_step={start_step} 超出有效范围 [1, 18]。'
        )

    _db    = db_path or DB_PATH
    _name  = repo_name or os.path.basename(abs_repo_path.rstrip(os.sep))
    summary: dict = {}

    # ── 日志初始化 ───────────────────────────────────────────────────────────
    _log, log_file = _make_logger(log_dir)

    _log.info('=' * 70)
    _log.info('CodeMAP 构建开始')
    _log.info(f'  仓库路径            : {abs_repo_path}')
    _log.info(f'  仓库名称            : {_name}')
    _log.info(f'  数据库              : {_db}')
    _log.info(f'  日志文件            : {log_file}')
    _log.info(f'  force               : {force}')
    _log.info(f'  start_step          : {start_step}')
    _log.info(f'  languages           : {languages or "（全部语言）"}')
    _log.info(f'  skip_if_exists      : {skip_if_exists}')
    _log.info(f'  no_desc             : {no_desc}')
    _log.info(f'  max_step9-11_workers: {max_step9_11_workers}')
    _log.info(f'  max_step12_workers  : {max_step12_workers}')
    _log.info('=' * 70)

    total_t0 = time.time()

    # ── 数据库初始化 ──────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(_db)), exist_ok=True)
    init_db(_db)
    _enable_wal(_db, _log)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1 : init_repo
    # ─────────────────────────────────────────────────────────────────────────
    repo_id: Optional[int] = None

    if start_step <= 1:
        with _Timer('Step 1   init_repo', _log):
            repo_id = init_repo(
                repo_path = abs_repo_path,
                repo_name = _name,
                db_path   = _db,
                force     = force,
            )
        _log.info(f'  repo_id = {repo_id}')
        summary['step1'] = {'repo_id': repo_id}

    else:
        # 断点续建：从数据库中找已有记录
        repo_id = _find_repo_id(_name, abs_repo_path, _db)
        if repo_id is None:
            raise ValueError(
                f'[build_codemap] 指定 start_step={start_step}（跳过 Step 1）'
                f"，但数据库中找不到仓库 '{_name}'。\n"
                "请先完整执行 Step 1（去掉 --step 参数或指定 --step 1）。"
            )
        _log.info(
            f'Step 1 跳过（start_step={start_step}），'
            f"已有 repo_id={repo_id}（'{_name}'）"
        )
        summary['step1'] = {'repo_id': repo_id, 'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2 : analyze_repo_language
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 2:
        with _Timer('Step 2   analyze_repo_language', _log):
            lang_r = analyze_repo_language(repo_id, db_path=_db)
        main_lang = lang_r.get('main', 'Unknown')
        _log.info(f'  主语言 : {main_lang}')
        summary['step2'] = {'main_language': main_lang}
    else:
        _log.info(f'Step 2 跳过（start_step={start_step}）')
        summary['step2'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3 : analyze_repo_area  [LLM]
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 3:
        with _Timer('Step 3   analyze_repo_area  [LLM]', _log):
            area_r = analyze_repo_area(
                repo_id,
                db_path = _db,
                force   = force,
            )
        _log.info(f'  area 数 : {len(area_r)}')
        summary['step3'] = {'area_count': len(area_r)}
    else:
        _log.info(f'Step 3 跳过（start_step={start_step}）')
        summary['step3'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4 : analyze_area_file
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 4:
        with _Timer('Step 4   analyze_area_file', _log):
            file_r = analyze_area_file(
                repo_id,
                db_path = _db,
                force   = force,
            )
        total_files = sum(len(v) for v in file_r.values())
        _log.info(f'  文件总数 : {total_files}')
        summary['step4'] = {'file_count': total_files}
    else:
        _log.info(f'Step 4 跳过（start_step={start_step}）')
        summary['step4'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5 : analyze_file_language
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 5:
        with _Timer('Step 5   analyze_file_language', _log):
            lang_map = analyze_file_language(repo_id, db_path=_db)
        _log.info(f'  检测文件数 : {len(lang_map)}')
        summary['step5'] = {'detected_files': len(lang_map)}
    else:
        _log.info(f'Step 5 跳过（start_step={start_step}）')
        summary['step5'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6 : analyze_file_func
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 6:
        with _Timer('Step 6   analyze_file_func', _log):
            func_r = analyze_file_func(
                repo_id,
                db_path   = _db,
                force     = force,
                languages = languages,
            )
        total_funcs = sum(len(v) for v in func_r.values())
        _log.info(f'  函数总数 : {total_funcs}')
        summary['step6'] = {'func_count': total_funcs}
    else:
        _log.info(f'Step 6 跳过（start_step={start_step}）')
        summary['step6'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7 : build_callgraph
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 7:
        with _Timer('Step 7   build_callgraph', _log):
            cg_path = build_callgraph(
                repo_id,
                db_path = _db,
                force   = force,
            )
        _log.info(f'  调用图文件 : {cg_path}')
        summary['step7'] = {'callgraph_path': cg_path}
    else:
        # 自动定位已有调用图（analyze_func_callgraph 支持 callgraph_path=None 自动查找）
        repo_rec = RepoDB.get_by_id(repo_id, db_path=_db)
        cg_path  = os.path.join(
            DATA_DIR, 'callgraph',
            f"{repo_rec['name']}_callgraph.json" if repo_rec else '',
        )
        _log.info(
            f'Step 7 跳过（start_step={start_step}），'
            f'缓存文件：{cg_path}'
        )
        summary['step7'] = {'skipped': True, 'callgraph_path': cg_path}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8 : analyze_func_callgraph
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 8:
        with _Timer('Step 8   analyze_func_callgraph', _log):
            cg_r = analyze_func_callgraph(
                repo_id,
                db_path        = _db,
                # cg_path 存在时传入精确路径；否则传 None 让函数自动定位
                callgraph_path = cg_path if os.path.isfile(cg_path) else None,
            )
        _log.info(f'  callgraph 写库 : {len(cg_r)} 个函数')
        summary['step8'] = {'func_count': len(cg_r)}
    else:
        _log.info(f'Step 8 跳过（start_step={start_step}）')
        summary['step8'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Steps 9-12 : analyze_func_summary  [SA + LLM，单次调用生成全部摘要字段]
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 9:
        with _Timer('Steps 9-12  analyze_func_summary  [SA+LLM]', _log):
            summary_r = analyze_func_summary(
                repo_id        = repo_id,
                db_path        = _db,
                skip_if_exists = skip_if_exists,
                languages      = languages,
            )
        ne = sum(1 for v in summary_r.values() if v)
        _log.info(
            f'  函数摘要生成 : {ne}/{len(summary_r)} 个函数有完整数据\n'
            f'  （precondition / postcondition / exception / description 合并写入）'
        )
        for s in range(9, 13):
            summary[f'step{s}'] = {'total': len(summary_r), 'nonempty': ne}
    else:
        _log.info(f'Steps 9-12 跳过（start_step={start_step}）')
        for s in range(9, 13):
            summary[f'step{s}'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Steps 13-18 : 描述生成阶段（可用 --no-desc 整体跳过）
    # ─────────────────────────────────────────────────────────────────────────
    if no_desc:
        _log.info('')
        _log.info('--no-desc 标志已设置，跳过 Step 13-18 的文件/Area/Repo 描述生成。')
        _log.info('（函数摘要 description 已在 Steps 9-12 中一并生成）')
        for s in range(13, 19):
            summary[f'step{s}'] = {'skipped': True, 'reason': 'no_desc'}

    else:
        # ── Step 13 : analyze_file_funclist_brief  [LLM batch] ───────────────
        if start_step <= 13:
            with _Timer('Step 13  analyze_file_funclist_brief', _log):
                fl_brief = analyze_file_funclist_brief(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            _log.info(f'  处理文件数 : {len(fl_brief)}')
            summary['step13'] = {'file_count': len(fl_brief)}
        else:
            _log.info(f'Step 13 跳过（start_step={start_step}）')
            summary['step13'] = {'skipped': True}

        # ── Step 14 : analyze_file_description  [LLM] ────────────────────────
        if start_step <= 14:
            with _Timer('Step 14  analyze_file_description', _log):
                file_desc = analyze_file_description(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            ne = sum(1 for v in file_desc.values() if v)
            _log.info(f'  文件描述生成 : {ne}/{len(file_desc)}')
            summary['step14'] = {'total': len(file_desc), 'nonempty': ne}
        else:
            _log.info(f'Step 14 跳过（start_step={start_step}）')
            summary['step14'] = {'skipped': True}

        # ── Step 15 : analyze_area_filelist_brief  [LLM batch] ───────────────
        if start_step <= 15:
            with _Timer('Step 15  analyze_area_filelist_brief', _log):
                al_brief = analyze_area_filelist_brief(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            _log.info(f'  处理 area 数 : {len(al_brief)}')
            summary['step15'] = {'area_count': len(al_brief)}
        else:
            _log.info(f'Step 15 跳过（start_step={start_step}）')
            summary['step15'] = {'skipped': True}

        # ── Step 16 : analyze_area_description  [LLM] ────────────────────────
        if start_step <= 16:
            with _Timer('Step 16  analyze_area_description', _log):
                area_desc = analyze_area_description(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            ne = sum(1 for v in area_desc.values() if v)
            _log.info(f'  area 描述生成 : {ne}/{len(area_desc)}')
            summary['step16'] = {'total': len(area_desc), 'nonempty': ne}
        else:
            _log.info(f'Step 16 跳过（start_step={start_step}）')
            summary['step16'] = {'skipped': True}

        # ── Step 17 : analyze_repo_arealist_brief  [LLM batch] ───────────────
        if start_step <= 17:
            with _Timer('Step 17  analyze_repo_arealist_brief', _log):
                arealist = analyze_repo_arealist_brief(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            _log.info(f'  arealist 条目 : {len(arealist)} 个')
            summary['step17'] = {'area_count': len(arealist)}
        else:
            _log.info(f'Step 17 跳过（start_step={start_step}）')
            summary['step17'] = {'skipped': True}

        # ── Step 18 : analyze_repo_description  [LLM] ────────────────────────
        if start_step <= 18:
            with _Timer('Step 18  analyze_repo_description', _log):
                repo_desc = analyze_repo_description(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            _log.info(f'  仓库描述 : {len(repo_desc)} 字符')
            summary['step18'] = {'desc_chars': len(repo_desc)}
        else:
            _log.info(f'Step 18 跳过（start_step={start_step}）')
            summary['step18'] = {'skipped': True}

    # ── 汇总报告 ─────────────────────────────────────────────────────────────
    total_elapsed = time.time() - total_t0
    mins, secs    = divmod(int(total_elapsed), 60)

    _STEP_LABELS = {
        1:  'init_repo',
        2:  'analyze_repo_language',
        3:  'analyze_repo_area',
        4:  'analyze_area_file',
        5:  'analyze_file_language',
        6:  'analyze_file_func',
        7:  'build_callgraph',
        8:  'analyze_func_callgraph',
        9:  'analyze_func_precondition',
        10: 'analyze_func_postcondition',
        11: 'analyze_func_exception',
        12: 'analyze_func_description',
        13: 'analyze_file_funclist_brief',
        14: 'analyze_file_description',
        15: 'analyze_area_filelist_brief',
        16: 'analyze_area_description',
        17: 'analyze_repo_arealist_brief',
        18: 'analyze_repo_description',
    }

    _log.info('')
    _log.info('=' * 70)
    _log.info('CodeMAP 构建完成  ✓')
    _log.info(f'  仓库    : {_name}  (repo_id={repo_id})')
    _log.info(f'  数据库  : {_db}')
    _log.info(f'  日志    : {log_file}')
    _log.info(f'  总耗时  : {mins}m {secs}s  ({total_elapsed:.0f}s)')
    _log.info('  ─── 各步骤结果摘要 ─────────────────────────────────────')

    for num, label in _STEP_LABELS.items():
        info = summary.get(f'step{num}', {})
        if info.get('skipped'):
            reason = info.get('reason', '')
            status = f'[跳过{" - " + reason if reason else ""}]'
        else:
            # 过滤掉路径等冗长字段，只展示数值统计
            parts = [
                f'{k}={v}'
                for k, v in info.items()
                if k not in ('skipped', 'reason', 'callgraph_path')
                and v is not None
            ]
            status = '  '.join(parts) if parts else '✓'
        _log.info(f'  Step {num:2d}  {label:<35s}  {status}')

    _log.info('=' * 70)

    # 将元信息写回 summary 供调用方使用
    summary.update({
        'repo_id':       repo_id,
        'repo_name':     _name,
        'db_path':       _db,
        'log_file':      log_file,
        'total_elapsed': total_elapsed,
    })

    return summary


# ==================================================================
# 命令行入口
# ==================================================================

def main() -> None:
    """命令行入口：解析参数后调用 build_codemap。"""

    parser = argparse.ArgumentParser(
        prog            = 'codemap',
        description     = 'CodeMAP —— 代码仓库结构化知识库构建工具（Step 1-18 全流程）',
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog          = """
使用示例：
  # 首次全量分析（使用默认数据库）
  python main.py /path/to/repo

  # 强制重建：清空同名仓库旧数据后重新分析
  python main.py /path/to/repo --force

  # 断点续建：从 Step 12 继续（已完成 Step 1-11）
  python main.py /path/to/repo --step 12

  # 指定仓库名称和数据库路径
  python main.py /path/to/repo --repo-name my_project --db-path ./my.db

  # 只分析 C/C++ 函数，跳过其他语言（大幅缩短 LLM 分析时间）
  python main.py /path/to/repo --languages C C++

  # 只做结构化分析+函数，跳过 Step 13-18 的描述生成
  python main.py /path/to/repo --no-desc


  # 强制重新分析所有实体（覆盖已有数据）
  python main.py /path/to/repo --step 9 --no-skip --languages C
        """.strip(),
    )

    parser.add_argument(
        'repo_path',
        help = '要分析的代码仓库本地路径（绝对或相对路径均可）',
    )
    parser.add_argument(
        '--repo-name', '-n',
        dest    = 'repo_name',
        default = None,
        metavar = 'NAME',
        help    = '仓库名称（默认：取路径末尾目录名）',
    )
    parser.add_argument(
        '--db-path', '-d',
        dest    = 'db_path',
        default = None,
        metavar = 'PATH',
        help    = f'SQLite 数据库路径（默认：{DB_PATH}）',
    )
    parser.add_argument(
        '--force', '-f',
        action  = 'store_true',
        default = False,
        help    = (
            '强制重建：删除同名仓库旧数据后重新分析'
            '（数据库文件本身保留，只清除该仓库的记录）'
        ),
    )
    parser.add_argument(
        '--step', '-s',
        type    = int,
        default = 1,
        choices = range(1, 19),
        metavar = 'N',
        help    = '从第 N 步开始执行（1-18，默认 1），用于断点续建',
    )
    parser.add_argument(
        '--languages', '-l',
        nargs   = '+',
        default = None,
        metavar = 'LANG',
        help    = (
            'Step 6/9-12 函数分析的语言白名单（如 C C++）；'
            '不传则处理全部语言'
        ),
    )
    parser.add_argument(
        '--no-desc',
        action  = 'store_true',
        default = False,
        help    = '跳过 Step 12-18 的所有描述生成步骤，只完成结构化分析（Step 1-11）',
    )
    parser.add_argument(
        '--no-skip',
        action  = 'store_true',
        default = False,
        help    = '禁用增量跳过：对所有实体重新分析（即使 DB 中已有数据）',
    )
    parser.add_argument(
        '--workers-step9-11',
        type    = int,
        default = 3,
        metavar = 'N',
        help    = (
            'Steps 9-11 并行度（最大 3，默认 3）；'
            'API 限速时可降为 2 或 1'
        ),
    )
    parser.add_argument(
        '--workers-step12',
        type    = int,
        default = 10,
        metavar = 'N',
        help    = 'Step 12 并发函数描述生成数（默认 10）',
    )
    parser.add_argument(
        '--log-dir',
        dest    = 'log_dir',
        default = None,
        metavar = 'DIR',
        help    = f'日志输出目录（默认：<project_root>/logs/）',
    )

    args = parser.parse_args()

    try:
        build_codemap(
            repo_path            = args.repo_path,
            repo_name            = args.repo_name,
            db_path              = args.db_path,
            force                = args.force,
            start_step           = args.step,
            languages            = args.languages,
            skip_if_exists       = not args.no_skip,
            max_step9_11_workers = args.workers_step9_11,
            max_step12_workers   = args.workers_step12,
            no_desc              = args.no_desc,
            log_dir              = args.log_dir,
        )
        sys.exit(0)

    except FileNotFoundError as e:
        print(f'[错误] {e}', file=sys.stderr)
        sys.exit(1)

    except ValueError as e:
        print(f'[错误] {e}', file=sys.stderr)
        sys.exit(2)

    except KeyboardInterrupt:
        print(
            '\n[中断] 用户中断构建。'
            '已完成的数据已持久化到数据库，'
            '下次可使用 --step N 从断点续建。',
            file=sys.stderr,
        )
        sys.exit(130)

    except Exception as e:
        print(f'[未知错误] {e}', file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)


if __name__ == '__main__':
    main()