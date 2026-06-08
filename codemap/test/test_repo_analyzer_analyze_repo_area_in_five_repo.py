"""
test/test_repo_analyzer_analyze_repo_area_in_five_repo.py

针对 repo_4_codemap 下五个真实仓库的 analyze_repo_area 集成观测测试。
本测试不做正确性断言，仅通过日志记录每个仓库 area 层级的划分情况。

每个用例内部依次执行：
  [1/3] init_repo
  [2/3] analyze_repo_language
  [3/3] analyze_repo_area

仓库列表：libuv / linenoise / minizip-ng / sqlite / tmux

运行：
    python -m pytest "test/test_repo_analyzer_analyze_repo_area_in_five_repo.py" -v -s

日志输出：
    test/log/five_real_repo_area_<YYYYMMDD_HHMMSS>.log

注意：
    文件名含连字符，pytest 通过路径收集，勿以 import 方式引用本模块。
    analyze_repo_area 依赖 LLM 调用，整体耗时较长，建议预留充足时间。
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB, AreaDB
from analyzer.repo_analyzer import init_repo, analyze_repo_language, analyze_repo_area


# ==================================================================
#  常量
# ==================================================================

_BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../../repo_4_codemap')
)

_REPO_NAMES = ['libuv', 'linenoise', 'minizip-ng', 'sqlite', 'tmux']

_REPO_PATHS: dict[str, str] = {
    name: os.path.join(_BASE_DIR, name)
    for name in _REPO_NAMES
}


# ==================================================================
#  日志
# ==================================================================

def _setup_logger() -> logging.Logger:
    """
    在 test/log/ 创建 five_real_repo_area_<时间戳>.log。
    同时向控制台输出，方便 pytest -s 模式下实时观察。
    """
    log_dir = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'five_real_repo_area_{ts}.log')

    logger = logging.getLogger('five_real_repo_area_test')
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fmt = logging.Formatter(
            '%(asctime)s  %(levelname)-7s  %(message)s',
            datefmt='%H:%M:%S',
        )
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    logger.info('=' * 70)
    logger.info('五库 analyze_repo_area 集成观测测试  开始')
    logger.info(f'基础路径  : {_BASE_DIR}')
    logger.info(f'日志文件  : {log_file}')
    logger.info(f'仓库列表  : {" / ".join(_REPO_NAMES)}')
    logger.info('')
    logger.info('各仓库目录状态：')
    for name, path in _REPO_PATHS.items():
        tag = '✓ 存在' if os.path.isdir(path) else '✗ 不存在'
        logger.info(f'  {name:15s}  [{tag}]  {path}')
    logger.info('=' * 70)
    return logger


_logger = _setup_logger()


# ==================================================================
#  Area 层级信息展示（核心日志工具）
# ==================================================================

def _log_area_info(db_path: str, repo_id: int, label: str) -> None:
    """
    直接查询 SQLite area 表及 repo.arealist，写入日志。
    展示：repo.arealist 简要索引 + area 全量记录（id/name/path/rationale）。
    """
    _logger.info('')
    _logger.info(f'  ┌── Area 层级快照  [{label}]')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        repo_row = conn.execute(
            'SELECT arealist FROM repo WHERE id = ?', (repo_id,)
        ).fetchone()
        area_rows = conn.execute(
            'SELECT * FROM area WHERE repo_id = ? ORDER BY path', (repo_id,)
        ).fetchall()
        conn.close()
    except Exception as exc:
        _logger.error(f'  │  ⚠ 读取数据库失败：{exc}')
        _logger.info('  └' + '─' * 52)
        return

    # repo.arealist
    arealist_raw = dict(repo_row).get('arealist') if repo_row else None
    arealist_obj = None
    if isinstance(arealist_raw, str):
        try:
            arealist_obj = json.loads(arealist_raw)
        except Exception:
            pass
    elif isinstance(arealist_raw, list):
        arealist_obj = arealist_raw

    if arealist_obj is not None:
        _logger.info(f'  │  repo.arealist（{len(arealist_obj)} 项）：')
        for a in arealist_obj:
            brief = a.get('brief', '')
            if len(brief) > 40:
                brief = brief[:37] + '...'
            _logger.info(
                f'  │    [{a.get("area_id", "?"):>3}]  '
                f'{a.get("name", ""):28s}  {brief}'
            )
    else:
        _logger.info('  │  repo.arealist : 尚未更新 (NULL)')

    _logger.info(f'  │')
    _logger.info(f'  │  area 表记录（共 {len(area_rows)} 条）：')
    for row in area_rows:
        d = dict(row)
        rationale = d.get('rationale') or '（无）'
        if len(rationale) > 100:
            rationale = rationale[:97] + '...'
        _logger.info('  │  ───────────────────────────────────────────────')
        _logger.info(f'  │  id        : {d["id"]}')
        _logger.info(f'  │  name      : {d["name"]}')
        _logger.info(f'  │  path      : {d["path"]}')
        _logger.info(f'  │  rationale : {rationale}')

    if not area_rows:
        _logger.info('  │  （area 表无记录）')
    _logger.info('  └' + '─' * 52)


# ==================================================================
#  汇总（收集各仓库结果，测试结束后统一打印）
# ==================================================================

_summary: list[dict] = []


def _append_summary(
    name: str,
    skipped: bool = False,
    failed: bool = False,
    main_lang: str = '-',
    area_count: int = 0,
    area_names: list | None = None,
) -> None:
    _summary.append(dict(
        name=name,
        skipped=skipped,
        failed=failed,
        main_lang=main_lang,
        area_count=area_count,
        area_names=area_names or [],
    ))


def _print_summary() -> None:
    """测试全部结束后打印五库对比汇总表。"""
    _logger.info('')
    _logger.info('╔' + '═' * 80 + '╗')
    _logger.info('║  五库 analyze_repo_area  汇总对比' + ' ' * 47 + '║')
    _logger.info('╠' + '═' * 80 + '╣')
    _logger.info(
        f'║  {"仓库名":<14}  {"主语言":<8}  {"area数":>5}  '
        f'{"状态":<8}  {"area 名称列表（前5项）"}'
        + ' ' * 5 + '║'
    )
    _logger.info('╠' + '─' * 80 + '╣')
    for s in _summary:
        if s['skipped']:
            status = '⏭ 已跳过'
            row = f'║  {s["name"]:<14}  {"":8}  {"--":>5}  {status:<10}  {"":32}║'
        elif s['failed']:
            status = '✗ 调用失败'
            row = (
                f'║  {s["name"]:<14}  {s["main_lang"]:<8}  {"ERR":>5}  '
                f'{status:<10}  {"（见日志）":32}║'
            )
        else:
            status = '✓ 完成'
            names_str = ', '.join(s['area_names'][:5])
            if len(s['area_names']) > 5:
                names_str += f'  (+{len(s["area_names"]) - 5})'
            if len(names_str) > 32:
                names_str = names_str[:29] + '...'
            row = (
                f'║  {s["name"]:<14}  {s["main_lang"]:<8}  {s["area_count"]:>5}  '
                f'{status:<10}  {names_str:<32}║'
            )
        _logger.info(row)
    _logger.info('╚' + '═' * 80 + '╝')


# ==================================================================
#  Fixtures
# ==================================================================

@pytest.fixture(scope='module', autouse=True)
def _module_summary():
    """模块级 autouse：测试全部结束后打印汇总表。"""
    yield
    _print_summary()
    _logger.info('')
    _logger.info('五库 analyze_repo_area 集成观测测试  结束')
    _logger.info('=' * 70)


@pytest.fixture(autouse=True)
def _log_boundary(request):
    """每条用例前后打印分隔线，方便定位日志段落。"""
    repo_name = (
        request.node.callspec.params.get('repo_name', '?')
        if hasattr(request.node, 'callspec')
        else '?'
    )
    _logger.info('')
    _logger.info('━' * 70)
    _logger.info(f'▶ 用例开始  [{repo_name}]')
    _logger.info('━' * 70)
    yield
    _logger.info(f'◀ 用例结束  [{repo_name}]')


# ==================================================================
#  测试（无断言，纯观测）
# ==================================================================

@pytest.mark.parametrize('repo_name', _REPO_NAMES)
def test_observe_analyze_repo_area(repo_name: str, tmp_path):
    """
    对 repo_4_codemap 下的每个真实仓库，依次执行：
      [1/3] init_repo            → 记录 repo 基本信息
      [2/3] analyze_repo_language → 记录语言分布摘要
      [3/3] analyze_repo_area    → 记录 area 层级快照（全量）

    本用例不做任何正确性断言，仅作集成观测用途。
    仓库目录不存在时自动跳过；analyze_repo_area 调用失败时记录错误并继续。
    """
    repo_path = _REPO_PATHS[repo_name]
    db_path   = str(tmp_path / f'{repo_name}.db')

    _logger.info('')
    _logger.info(f'  仓库名称  : {repo_name}')
    _logger.info(f'  仓库路径  : {repo_path}')
    _logger.info(f'  数据库    : {db_path}')

    # 目录不存在 → 跳过
    if not os.path.isdir(repo_path):
        _logger.warning(f'  ⚠ 仓库目录不存在，跳过：{repo_path}')
        _append_summary(repo_name, skipped=True)
        pytest.skip(f'仓库目录不存在：{repo_path}')

    # ── [1/3] init_repo ────────────────────────────────────────
    _logger.info('')
    _logger.info(f'  [1/3] init_repo("{repo_name}")')
    init_db(db_path)
    repo_id = init_repo(repo_path, db_path=db_path)
    _logger.info(f'        → 返回 repo_id = {repo_id}')

    # ── [2/3] analyze_repo_language ────────────────────────────
    _logger.info('')
    _logger.info(f'  [2/3] analyze_repo_language(repo_id={repo_id})')
    lang_result = analyze_repo_language(repo_id, db_path=db_path)
    main_lang   = lang_result.get('main', '-')
    lang_stats  = lang_result.get('stats', [])
    _logger.info(
        f'        → 主语言 = {main_lang}，'
        f'语言种数 = {len(lang_stats)}，'
        f'总字节数 = {sum(s.get("bytes", 0) for s in lang_stats):,}'
    )

    # ── [3/3] analyze_repo_area ────────────────────────────────
    _logger.info('')
    _logger.info(f'  [3/3] analyze_repo_area(repo_id={repo_id})')
    try:
        area_result = analyze_repo_area(repo_id, db_path=db_path)
        area_names  = [a.get('name', '') for a in area_result]
        _logger.info(
            f'        → 共 {len(area_result)} 个 area：'
            f'{", ".join(area_names)}'
        )
        _log_area_info(
            db_path, repo_id,
            label=f'{repo_name}  /  analyze_repo_area 完成后',
        )
        _append_summary(
            repo_name,
            main_lang=main_lang,
            area_count=len(area_result),
            area_names=area_names,
        )
    except Exception as exc:
        _logger.error(f'        ⚠ analyze_repo_area 调用失败：{exc}')
        _append_summary(repo_name, failed=True, main_lang=main_lang)
        # 观测测试不向上抛出，确保其余仓库继续执行
        # 如需让 pytest 将此标记为 FAILED，可改为 raise