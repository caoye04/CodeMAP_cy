"""
test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_five_real_repo.py

针对 repo_4_codemap 下五个真实仓库的 init_repo + analyze_repo_language 集成观测测试。
本测试不做正确性断言，仅通过日志记录每个仓库对应数据库的 repo 层级信息。

仓库路径（相对 test/ 目录）  : ../../../repo_4_codemap/<name>/
仓库路径（相对 codemap/ 目录）: ../../repo_4_codemap/<name>/

仓库列表：libuv / linenoise / minizip-ng / sqlite / tmux

运行：
    python -m pytest "test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_five_real_repo.py" -v -s

日志输出：
    test/log/five_real_repo_<YYYYMMDD_HHMMSS>.log

注意：
    文件名含连字符，pytest 通过路径收集，勿以 import 方式引用本模块。
"""

import os
import sys
import json
import logging
import sqlite3
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB
from analyzer.repo_analyzer import init_repo, analyze_repo_language


# ======================================================================
#  常量
# ======================================================================

_BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../../repo_4_codemap')
)

_REPO_NAMES = ['libuv', 'linenoise', 'minizip-ng', 'sqlite', 'tmux']

_REPO_PATHS: dict[str, str] = {
    name: os.path.join(_BASE_DIR, name)
    for name in _REPO_NAMES
}


# ======================================================================
#  日志
# ======================================================================

def _setup_logger() -> logging.Logger:
    """
    在 test/log/ 创建 five_real_repo_<时间戳>.log。
    同时向控制台输出，方便 pytest -s 模式下实时观察。
    """
    log_dir = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'five_real_repo_{ts}.log')

    logger = logging.getLogger('five_real_repo_test')
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fmt = logging.Formatter(
            '%(asctime)s  %(levelname)-7s  %(message)s',
            datefmt='%H:%M:%S',
        )
        # 文件 Handler
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # 控制台 Handler（pytest -s 可见）
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    # 启动头部
    logger.info('=' * 70)
    logger.info('五库集成观测测试  开始')
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


# ======================================================================
#  repo 层级信息展示（核心日志工具）
# ======================================================================

def _log_repo_info(db_path: str, label: str) -> None:
    """
    直接查询 SQLite repo 表，将以下字段写入日志：
      id / name / path / language.main / language.stats（全量按字节降序）
    language 为 NULL 时注明"尚未分析"。
    """
    _logger.info('')
    _logger.info(f'  ┌── Repo 层级快照  [{label}]')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM repo ORDER BY id').fetchall()
        conn.close()
    except Exception as exc:
        _logger.error(f'  │  ⚠ 读取数据库失败：{exc}')
        _logger.info('  └' + '─' * 52)
        return

    if not rows:
        _logger.info('  │  repo 表为空（0 条记录）')
        _logger.info('  └' + '─' * 52)
        return

    for row in rows:
        d = dict(row)

        # 反序列化 language 字段（可能是 str / dict / None）
        raw = d.get('language')
        lang_obj = None
        if isinstance(raw, str):
            try:
                lang_obj = json.loads(raw)
            except Exception:
                pass
        elif isinstance(raw, dict):
            lang_obj = raw

        _logger.info(f'  │  id         : {d["id"]}')
        _logger.info(f'  │  name       : {d["name"]}')
        _logger.info(f'  │  path       : {d["path"]}')

        if lang_obj is None:
            _logger.info('  │  language   : 尚未分析 (NULL)')
        else:
            stats: list[dict] = lang_obj.get('stats') or []
            total_bytes = sum(s.get('bytes', 0) for s in stats)
            _logger.info(f'  │  主语言     : {lang_obj.get("main")}')
            _logger.info(f'  │  总字节数   : {total_bytes:>14,} bytes（已识别扩展名）')
            _logger.info(f'  │  语言分布   : 共 {len(stats)} 种，按字节数降序')
            for s in stats:
                pct = s.get('pct', 0.0)
                bar = '█' * max(1, int(pct / 2))
                _logger.info(
                    f'  │    {s["lang"]:22s}  {pct:6.2f}%  '
                    f'{s["bytes"]:>14,} bytes  {bar}'
                )

    _logger.info('  └' + '─' * 52)


# ======================================================================
#  模块级汇总（收集所有结果，测试完成后统一打印）
# ======================================================================

_summary: list[dict] = []   # 每条 {"name", "main", "langs", "total_bytes", "skipped"}


def _append_summary(
    name: str,
    skipped: bool = False,
    main: str = '-',
    langs: int = 0,
    total_bytes: int = 0,
) -> None:
    _summary.append(dict(
        name=name, skipped=skipped,
        main=main, langs=langs, total_bytes=total_bytes,
    ))


def _print_summary() -> None:
    """测试结束后打印所有仓库的对比摘要。"""
    _logger.info('')
    _logger.info('╔' + '═' * 68 + '╗')
    _logger.info('║  五库汇总对比' + ' ' * 55 + '║')
    _logger.info('╠' + '═' * 68 + '╣')
    _logger.info(
        f'║  {"仓库名":<14}  {"主语言":<10}  {"语言种数":>6}  '
        f'{"总字节数":>16}  {"状态":<8}║'
    )
    _logger.info('╠' + '─' * 68 + '╣')
    for s in _summary:
        if s['skipped']:
            status = '⏭ 已跳过'
            row = f'║  {s["name"]:<14}  {"-":<10}  {"--":>6}  {"--":>16}  {status:<10}║'
        else:
            status = '✓ 完成'
            row = (
                f'║  {s["name"]:<14}  {s["main"]:<10}  {s["langs"]:>6}  '
                f'{s["total_bytes"]:>16,}  {status:<10}║'
            )
        _logger.info(row)
    _logger.info('╚' + '═' * 68 + '╝')


# ======================================================================
#  Fixture
# ======================================================================

@pytest.fixture(scope='module', autouse=True)
def _module_summary():
    """模块级 autouse：测试全部结束后打印汇总表。"""
    yield
    _print_summary()
    _logger.info('')
    _logger.info('五库集成观测测试  结束')
    _logger.info('=' * 70)


@pytest.fixture(autouse=True)
def _log_boundary(request):
    """每条用例前后打印分隔线，方便定位日志段落。"""
    repo_name = request.node.callspec.params.get('repo_name', '?') \
        if hasattr(request.node, 'callspec') else '?'
    _logger.info('')
    _logger.info('━' * 70)
    _logger.info(f'▶ 用例开始  [{repo_name}]')
    _logger.info('━' * 70)
    yield
    _logger.info(f'◀ 用例结束  [{repo_name}]')


# ======================================================================
#  测试（无断言，纯观测）
# ======================================================================

@pytest.mark.parametrize('repo_name', _REPO_NAMES)
def test_observe_init_and_language(repo_name: str, tmp_path):
    """
    对 repo_4_codemap 下的每个真实仓库，依次执行：
      [1/2] init_repo            → 记录 repo 表快照
      [2/2] analyze_repo_language → 记录 repo 表快照（含语言分布）

    本用例不做任何正确性断言，仅作集成观测用途。
    仓库目录不存在时自动跳过。
    """
    repo_path = _REPO_PATHS[repo_name]
    db_path = str(tmp_path / f'{repo_name}.db')

    _logger.info('')
    _logger.info(f'  仓库名称  : {repo_name}')
    _logger.info(f'  仓库路径  : {repo_path}')
    _logger.info(f'  数据库    : {db_path}')

    # 目录不存在 → 跳过
    if not os.path.isdir(repo_path):
        _logger.warning(f'  ⚠ 仓库目录不存在，跳过：{repo_path}')
        _append_summary(repo_name, skipped=True)
        pytest.skip(f'仓库目录不存在：{repo_path}')

    # ── [1/2] init_repo ───────────────────────────────────────────
    _logger.info('')
    _logger.info(f'  [1/2] init_repo("{repo_name}")')
    init_db(db_path)
    repo_id = init_repo(repo_path, db_path=db_path)
    _logger.info(f'        → 返回 repo_id = {repo_id}')
    _log_repo_info(db_path, label=f'{repo_name}  /  init_repo 完成后')

    # ── [2/2] analyze_repo_language ───────────────────────────────
    _logger.info('')
    _logger.info(f'  [2/2] analyze_repo_language(repo_id={repo_id})')
    result = analyze_repo_language(repo_id, db_path=db_path)
    main_lang = result.get('main', '-')
    stats = result.get('stats') or []
    total_bytes = sum(s.get('bytes', 0) for s in stats)
    _logger.info(f'        → 主语言 = {main_lang}，语言种数 = {len(stats)}，'
                 f'总字节数 = {total_bytes:,}')
    _log_repo_info(db_path, label=f'{repo_name}  /  analyze_repo_language 完成后')

    # 记录到汇总
    _append_summary(repo_name, main=main_lang, langs=len(stats), total_bytes=total_bytes)