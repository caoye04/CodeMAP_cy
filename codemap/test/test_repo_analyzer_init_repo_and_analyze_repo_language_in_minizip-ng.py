"""
test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_minizip-ng.py
针对真实 minizip-ng 仓库的 init_repo + analyze_repo_language 集成测试

仓库路径（相对 test/ 目录）：../../../repo_4_codemap/minizip-ng/ 
仓库路径（相对 codemap/ 目录）：../../repo_4_codemap/minizip-ng/ 

运行：
    python -m pytest "test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_minizip-ng.py" -v

日志输出：
    test/log/minizip_ng_<YYYYMMDD_HHMMSS>.log

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


# ==================================================================
#  常量：minizip-ng 仓库绝对路径
# ==================================================================

_REPO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../../repo_4_codemap/minizip-ng')
)

# 仓库不存在时跳过整个模块，而不是报错
pytestmark = pytest.mark.skipif(
    not os.path.isdir(_REPO_PATH),
    reason=f'minizip-ng 仓库未找到，跳过：{_REPO_PATH}',
)


# ==================================================================
#  日志：简单单文件，只记录 repo 层级信息
# ==================================================================

def _setup_logger() -> logging.Logger:
    """
    在 test/log/ 创建 minizip_ng_<时间戳>.log。
    Logger 名 'minizip_ng_test'，幂等注册 Handler。
    """
    log_dir = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'minizip_ng_{ts}.log')

    logger = logging.getLogger('minizip_ng_test')
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s  %(levelname)-7s  %(message)s',
            datefmt='%H:%M:%S',
        ))
        logger.addHandler(fh)

    logger.info('=' * 68)
    logger.info(f'minizip-ng 集成测试开始')
    logger.info(f'仓库路径  : {_REPO_PATH}')
    logger.info(f'日志文件  : {log_file}')
    logger.info('=' * 68)
    return logger


_logger = _setup_logger()


# ==================================================================
#  repo 层级信息打印（核心日志工具）
# ==================================================================

def _log_repo_info(db_path: str, label: str) -> None:
    """
    直接读取 SQLite，将 repo 表的 repo 层级信息写入日志。
    包含：id / name / path / language.main / language.stats（全量）。
    """
    _logger.info('')
    _logger.info(f'┌── Repo 层级信息 [{label}]')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM repo ORDER BY id').fetchall()
        conn.close()
    except Exception as exc:
        _logger.warning(f'│  读取数据库失败：{exc}')
        _logger.info('└' + '─' * 50)
        return

    if not rows:
        _logger.info('│  repo 表为空（0 条记录）')
        _logger.info('└' + '─' * 50)
        return

    for row in rows:
        d = dict(row)

        # 反序列化 language 字段
        raw = d.get('language')
        lang_obj = None
        if isinstance(raw, str):
            try:
                lang_obj = json.loads(raw)
            except Exception:
                pass
        elif isinstance(raw, dict):
            lang_obj = raw

        _logger.info(f'│  id       : {d["id"]}')
        _logger.info(f'│  name     : {d["name"]}')
        _logger.info(f'│  path     : {d["path"]}')

        if lang_obj is None:
            _logger.info('│  language : 尚未分析')
        else:
            stats: list[dict] = lang_obj.get('stats') or []
            total_bytes = sum(s['bytes'] for s in stats)
            _logger.info(f'│  主语言   : {lang_obj.get("main")}')
            _logger.info(f'│  文件总量 : {total_bytes:>12,} bytes（已识别扩展名，不含忽略目录）')
            _logger.info(f'│  语言分布 : （共 {len(stats)} 种，按字节数降序）')
            for s in stats:
                bar = '█' * int(s['pct'] / 2)
                _logger.info(
                    f'│    {s["lang"]:20s}  {s["pct"]:6.2f}%  '
                    f'{s["bytes"]:>12,} bytes  {bar}'
                )

    _logger.info('└' + '─' * 50)


# ==================================================================
#  Fixtures
# ==================================================================

@pytest.fixture(scope='module')
def db(tmp_path_factory):
    """模块级临时数据库，整个测试文件共享，保证用例间状态连续。"""
    db_file = str(tmp_path_factory.mktemp('minizip_ng') / 'codemap.db')
    _logger.info(f'[db] 创建临时数据库 → {db_file}')
    init_db(db_file)
    _logger.info('[db] 表结构初始化完成')
    return db_file


@pytest.fixture(scope='module')
def repo_id(db):
    """
    模块级：调用 init_repo() 写入 minizip-ng 基本信息，
    返回 repo_id 供后续测试复用。
    """
    _logger.info('')
    _logger.info('── init_repo ──────────────────────────────────────────')
    _logger.info(f'调用 init_repo("{_REPO_PATH}")')
    rid = init_repo(_REPO_PATH, db_path=db)
    _logger.info(f'返回 repo_id = {rid}')
    _log_repo_info(db, label='init_repo 完成后')
    return rid


@pytest.fixture(autouse=True)
def _log_boundary(request):
    """自动在每条用例前后打印分隔线。"""
    _logger.info('')
    _logger.info('─' * 68)
    _logger.info(f'▶ {request.node.name}')
    _logger.info('─' * 68)
    yield
    _logger.info(f'◀ {request.node.name}  完成')


# ==================================================================
#  测试
# ==================================================================

class TestMinizipNgRepo:

    def test_init_repo_basic(self, repo_id, db):
        """
        init_repo 应：
          - 返回正整数 repo_id
          - 在 DB 中写入 name='minizip-ng' 和绝对路径
          - language 字段此时为 NULL（尚未分析）
        """
        assert isinstance(repo_id, int) and repo_id > 0, \
            f'repo_id 应为正整数，实际：{repo_id}'

        repo = RepoDB.get_by_id(repo_id, db_path=db)
        assert repo is not None, f'DB 中找不到 repo_id={repo_id}'
        assert repo['name'] == 'minizip-ng', \
            f'name 应为 "minizip-ng"，实际：{repo["name"]!r}'
        assert os.path.isabs(repo['path']), \
            f'path 应为绝对路径，实际：{repo["path"]!r}'
        assert repo['language'] is None, \
            'init_repo 完成后 language 应为 NULL'

        _logger.info('断言通过：repo_id 正整数 / name 正确 / path 绝对 / language=NULL ✓')

    def test_analyze_repo_language(self, repo_id, db):
        """
        analyze_repo_language 应：
          - 返回包含 main 和 stats 的 dict
          - minizip-ng 为 C 项目，main 应为 'C'
          - stats 按字节数降序，占比之和约 100%
          - 结果同步写入 DB，可反序列化为 dict
        """
        _logger.info(f'调用 analyze_repo_language(repo_id={repo_id})')
        result = analyze_repo_language(repo_id, db_path=db)
        _log_repo_info(db, label='analyze_repo_language 完成后')

        # 结构检查
        assert 'main' in result and 'stats' in result, \
            f'返回值缺少必要键，实际 keys：{list(result.keys())}'
        assert isinstance(result['stats'], list) and len(result['stats']) > 0, \
            'stats 应为非空列表'

        # 主语言
        assert result['main'] == 'C', \
            f'minizip-ng 主语言应为 "C"，实际：{result["main"]!r}'

        # 排序
        byte_seq = [s['bytes'] for s in result['stats']]
        assert byte_seq == sorted(byte_seq, reverse=True), \
            'stats 应按字节数降序排列'

        # 占比之和
        total_pct = sum(s['pct'] for s in result['stats'])
        assert abs(total_pct - 100.0) < 0.1, \
            f'占比之和应约为 100.0，实际：{total_pct:.4f}'

        # DB 持久化
        repo = RepoDB.get_by_id(repo_id, db_path=db)
        assert isinstance(repo['language'], dict), \
            f'DB 中 language 应反序列化为 dict，实际类型：{type(repo["language"]).__name__}'
        assert repo['language']['main'] == 'C', \
            f'DB 中 language.main 应为 "C"，实际：{repo["language"]["main"]!r}'

        _logger.info('断言通过：结构 / 主语言(C) / 排序 / 占比 / DB持久化 ✓')