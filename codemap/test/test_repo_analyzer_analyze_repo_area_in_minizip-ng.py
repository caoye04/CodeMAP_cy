"""
test/test_repo_analyzer_analyze_repo_area_in_minizip-ng.py
针对真实 minizip-ng 仓库的 analyze_repo_area 集成测试

前置依赖（fixture 链自动保证执行顺序）：
  init_repo → analyze_repo_language → analyze_repo_area

仓库路径（相对 test/ 目录）  : ../../../repo_4_codemap/minizip-ng/
仓库路径（相对 codemap/ 目录）: ../../repo_4_codemap/minizip-ng/

运行：
    python -m pytest "test/test_repo_analyzer_analyze_repo_area_in_minizip-ng.py" -v

日志输出：
    test/log/minizip_ng_area_<YYYYMMDD_HHMMSS>.log

注意：
    文件名含连字符，pytest 通过路径收集，勿以 import 方式引用本模块。
    analyze_repo_area 依赖 LLM 调用，需保证网络与 API 可用。
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
from config import DATA_DIR


# ==================================================================
#  常量：minizip-ng 仓库绝对路径
# ==================================================================

_REPO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../../repo_4_codemap/minizip-ng')
)

pytestmark = pytest.mark.skipif(
    not os.path.isdir(_REPO_PATH),
    reason=f'minizip-ng 仓库未找到，跳过：{_REPO_PATH}',
)


# ==================================================================
#  日志
# ==================================================================

def _setup_logger() -> logging.Logger:
    """
    在 test/log/ 创建 minizip_ng_area_<时间戳>.log。
    Logger 名 'minizip_ng_area_test'，幂等注册 Handler。
    """
    log_dir = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'minizip_ng_area_{ts}.log')

    logger = logging.getLogger('minizip_ng_area_test')
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
    logger.info('minizip-ng  analyze_repo_area 集成测试开始')
    logger.info(f'仓库路径  : {_REPO_PATH}')
    logger.info(f'日志文件  : {log_file}')
    logger.info('=' * 68)
    return logger


_logger = _setup_logger()


# ==================================================================
#  Area 层级信息打印（核心日志工具）
# ==================================================================

def _log_area_info(db_path: str, repo_id: int, label: str) -> None:
    """
    直接读取 SQLite，将 area 表记录及 repo.arealist 写入日志。
    包含：repo.arealist 简要索引 + area 全量记录（id/name/path/rationale）。
    """
    _logger.info('')
    _logger.info(f'┌── Area 层级信息 [{label}]')

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
        _logger.warning(f'│  读取数据库失败：{exc}')
        _logger.info('└' + '─' * 50)
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
        _logger.info(f'│  repo.arealist（{len(arealist_obj)} 项）：')
        for a in arealist_obj:
            brief = a.get('brief', '')
            if len(brief) > 40:
                brief = brief[:37] + '...'
            _logger.info(
                f'│    [{a.get("area_id", "?"):>3}]  '
                f'{a.get("name", ""):28s}  {brief}'
            )
    else:
        _logger.info('│  repo.arealist : 尚未更新 (NULL)')

    _logger.info('│')
    _logger.info(f'│  area 表记录（共 {len(area_rows)} 条）：')
    for row in area_rows:
        d = dict(row)
        rationale = d.get('rationale') or '（无）'
        if len(rationale) > 80:
            rationale = rationale[:77] + '...'
        _logger.info('│  ─────────────────────────────────────────────')
        _logger.info(f'│  id        : {d["id"]}')
        _logger.info(f'│  name      : {d["name"]}')
        _logger.info(f'│  path      : {d["path"]}')
        _logger.info(f'│  rationale : {rationale}')

    if not area_rows:
        _logger.info('│  （area 表无记录）')
    _logger.info('└' + '─' * 50)


# ==================================================================
#  Fixtures
# ==================================================================

@pytest.fixture(scope='module')
def db(tmp_path_factory):
    """模块级临时数据库，整个测试文件共享，保证用例间状态连续。"""
    db_file = str(tmp_path_factory.mktemp('minizip_ng_area') / 'codemap.db')
    _logger.info(f'[db] 创建临时数据库 → {db_file}')
    init_db(db_file)
    _logger.info('[db] 表结构初始化完成')
    return db_file


@pytest.fixture(scope='module')
def repo_id(db):
    """模块级：调用 init_repo()，返回 repo_id 供后续 fixture 和用例复用。"""
    _logger.info('')
    _logger.info('── 前置步骤 [1/2]：init_repo ──────────────────────────')
    rid = init_repo(_REPO_PATH, db_path=db)
    _logger.info(f'init_repo 完成，repo_id = {rid}')
    return rid


@pytest.fixture(scope='module')
def language_ready(repo_id, db):
    """
    模块级：调用 analyze_repo_language()，确保 repo.language 已填充。
    analyze_repo_area 读取主语言信息，故须先行执行。
    """
    _logger.info('')
    _logger.info('── 前置步骤 [2/2]：analyze_repo_language ──────────────')
    result = analyze_repo_language(repo_id, db_path=db)
    _logger.info(f'analyze_repo_language 完成，主语言：{result.get("main")}')
    return result


@pytest.fixture(scope='module')
def area_result(language_ready, repo_id, db):
    """
    模块级：调用 analyze_repo_area()，写入 area 表并更新 repo.arealist，
    返回 validated area 列表供全部测试用例复用。
    """
    _logger.info('')
    _logger.info('── analyze_repo_area ────────────────────────────────────')
    _logger.info(f'调用 analyze_repo_area(repo_id={repo_id})')
    result = analyze_repo_area(repo_id, db_path=db)
    _logger.info(f'analyze_repo_area 返回，共 {len(result)} 个 area')
    _log_area_info(db, repo_id, label='analyze_repo_area 初次调用完成后')
    return result


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

class TestAnalyzeRepoArea:

    def test_return_type_and_nonempty(self, area_result):
        """
        analyze_repo_area 应：
          - 返回值类型为 list
          - 列表非空（minizip-ng 必然可划分出至少一个 area）
        """
        assert isinstance(area_result, list), \
            f'返回值应为 list，实际类型：{type(area_result).__name__}'
        assert len(area_result) > 0, \
            'minizip-ng 至少应划分出一个 area，返回列表不应为空'
        _logger.info(f'断言通过：返回非空 list，共 {len(area_result)} 个 area ✓')

    def test_area_count_in_reasonable_range(self, area_result):
        """
        area 数量应在合理范围内。
        设计文档建议 3-12 个，测试放宽至 2-15 以兼容模型差异。
        """
        count = len(area_result)
        assert 2 <= count <= 15, \
            f'area 数量应在 [2, 15] 之间（设计文档建议 3-12），实际：{count}'
        _logger.info(f'断言通过：area 数量 {count} 在合理范围 [2, 15] 内 ✓')

    def test_each_area_has_required_fields(self, area_result):
        """
        每个 area 条目应包含 area_id / name / path / rationale / brief，
        且所有字段值非 None、非空字符串。
        """
        required_fields = {'area_id', 'name', 'path', 'rationale', 'brief'}
        for idx, area in enumerate(area_result):
            missing = required_fields - set(area.keys())
            assert not missing, \
                f'area[{idx}] 缺少字段：{missing}，完整条目：{area}'
            for field in required_fields:
                val = area[field]
                assert val is not None, \
                    f'area[{idx}].{field} 不应为 None'
                assert str(val).strip() != '', \
                    f'area[{idx}].{field} 不应为空字符串，实际：{val!r}'
            _logger.info(
                f'  area[{idx}]  id={area["area_id"]}  '
                f'name={area["name"]!r}  path={area["path"]!r}  ✓'
            )
        _logger.info(f'断言通过：所有 {len(area_result)} 个 area 字段完整且非空 ✓')

    def test_area_id_is_positive_int(self, area_result):
        """
        每个 area 的 area_id 应为正整数（由 AreaDB.create 写库后返回）。
        """
        for idx, area in enumerate(area_result):
            aid = area.get('area_id')
            assert isinstance(aid, int) and aid > 0, \
                f'area[{idx}].area_id 应为正整数，实际：{aid!r}'
        _logger.info(f'断言通过：所有 area_id 均为正整数 ✓')

    def test_no_duplicate_ids_or_paths(self, area_result):
        """
        area_id 和 path 在返回列表中均不重复。
        """
        ids   = [a['area_id'] for a in area_result]
        paths = [a['path']    for a in area_result]
        assert len(ids)   == len(set(ids)),   f'area_id 存在重复：{ids}'
        assert len(paths) == len(set(paths)), f'area path 存在重复：{paths}'
        _logger.info('断言通过：area_id 和 path 均无重复 ✓')

    def test_all_paths_exist_on_disk(self, area_result):
        """
        每个 area 的 path 对应磁盘路径应真实存在。
        path='.' 对应仓库根目录，其余为相对仓库根的子路径。
        """
        for area in area_result:
            path  = area['path']
            abs_p = _REPO_PATH if path == '.' else os.path.join(_REPO_PATH, path)
            assert os.path.exists(abs_p), \
                f'area path 在磁盘上不存在：{path!r}（绝对路径：{abs_p}）'
            _logger.info(f'  ✓ 磁盘路径存在：{path}')
        _logger.info(f'断言通过：所有 {len(area_result)} 个 path 在磁盘上存在 ✓')

    def test_db_area_records_match_return(self, area_result, repo_id, db):
        """
        数据库 area 表中属于 repo_id 的记录应与返回列表完全对应：
          - 记录总数相等
          - 每个 area_id 可单独查到，且 name / path 与返回值一致
        """
        db_areas = AreaDB.list_by_repo(repo_id, db_path=db)
        assert len(db_areas) == len(area_result), \
            (f'DB area 记录数（{len(db_areas)}）'
             f'与返回列表（{len(area_result)}）不一致')

        for area in area_result:
            record = AreaDB.get_by_id(area['area_id'], db_path=db)
            assert record is not None, \
                f'area_id={area["area_id"]} 在 DB 中找不到记录'
            assert record['name'] == area['name'], \
                (f'area_id={area["area_id"]} name 不一致：'
                 f'DB={record["name"]!r} / 返回={area["name"]!r}')
            assert record['path'] == area['path'], \
                (f'area_id={area["area_id"]} path 不一致：'
                 f'DB={record["path"]!r} / 返回={area["path"]!r}')

        _logger.info(
            f'断言通过：DB area 表 {len(db_areas)} 条记录与返回列表完全匹配 ✓'
        )

    def test_db_area_has_rationale(self, area_result, db):
        """
        area 表中的 rationale 字段应已写入非空字符串（LLM 给出的分层依据）。
        """
        for area in area_result:
            record = AreaDB.get_by_id(area['area_id'], db_path=db)
            rationale = record.get('rationale') or ''
            assert rationale.strip() != '', \
                f'area_id={area["area_id"]} 的 rationale 不应为空'
        _logger.info(f'断言通过：所有 area 的 rationale 已写入数据库 ✓')

    def test_db_repo_arealist_updated(self, area_result, repo_id, db):
        """
        repo.arealist 应被更新为非空列表，
        长度与 area_result 一致，且每项含 area_id / name / brief。
        """
        repo     = RepoDB.get_by_id(repo_id, db_path=db)
        arealist = repo.get('arealist')

        assert isinstance(arealist, list), \
            f'repo.arealist 应反序列化为 list，实际类型：{type(arealist).__name__}'
        assert len(arealist) > 0, \
            'repo.arealist 不应为空列表'
        assert len(arealist) == len(area_result), \
            (f'repo.arealist 长度（{len(arealist)}）'
             f'与 area_result（{len(area_result)}）不一致')

        for idx, item in enumerate(arealist):
            for key in ('area_id', 'name', 'brief'):
                assert key in item, \
                    f'repo.arealist[{idx}] 缺少字段 {key!r}，实际：{item}'
                assert item[key] is not None, \
                    f'repo.arealist[{idx}].{key} 不应为 None'

        _logger.info(
            f'断言通过：repo.arealist 已更新，共 {len(arealist)} 项，结构完整 ✓'
        )

    def test_intermediate_json_saved(self, area_result):
        """
        中间产物 JSON 应写入 data/analyze_repo_area/minizip-ng.json，
        文件包含 areas / repo_id / repo_name / llm_raw 字段，
        且 areas 条目数与返回列表一致。
        """
        json_path = os.path.join(DATA_DIR, 'analyze_repo_area', 'minizip-ng.json')
        assert os.path.isfile(json_path), \
            f'中间产物 JSON 文件不存在：{json_path}'

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for key in ('areas', 'repo_id', 'repo_name', 'llm_raw'):
            assert key in data, \
                f'JSON 缺少字段 {key!r}，实际 keys：{list(data.keys())}'

        assert isinstance(data['areas'], list), \
            f'JSON.areas 应为 list，实际类型：{type(data["areas"]).__name__}'
        assert len(data['areas']) == len(area_result), \
            (f'JSON areas 数量（{len(data["areas"])}）'
             f'与返回列表（{len(area_result)}）不一致')

        _logger.info(f'断言通过：中间产物 JSON 结构完整，areas={len(data["areas"])} ✓')
        _logger.info(f'  文件路径：{json_path}')

    def test_force_false_raises_on_duplicate(self, area_result, repo_id, db):
        """
        area 记录已存在时，force=False（默认值）再次调用应抛出 ValueError，
        且错误信息提示已有 area 记录。
        """
        with pytest.raises(ValueError, match=r'已有.*area.*记录'):
            analyze_repo_area(repo_id, db_path=db, force=False)
        _logger.info('断言通过：force=False 时重复调用抛出 ValueError ✓')

    def test_force_true_allows_reanalysis(self, area_result, repo_id, db):
        """
        force=True 时应允许重新分析（此用例最后执行，会修改 DB 状态）：
          - 清除全部旧 area 记录
          - 返回新的非空 area 列表
          - 旧 area_id 在 DB 中应不再存在（级联删除）
          - repo.arealist 以新数据覆盖更新
        """
        old_ids = {a['area_id'] for a in area_result}
        _logger.info(f'旧 area_id 集合：{sorted(old_ids)}')

        new_result = analyze_repo_area(repo_id, db_path=db, force=True)

        # 返回值非空
        assert isinstance(new_result, list) and len(new_result) > 0, \
            'force=True 重新分析后返回列表不应为空'

        # 旧 area_id 应已被删除
        for old_id in old_ids:
            record = AreaDB.get_by_id(old_id, db_path=db)
            assert record is None, \
                (f'旧 area_id={old_id} 在 force=True 后仍存在于 DB'
                 f'（应已级联删除）')

        # repo.arealist 已用新数据覆盖
        repo     = RepoDB.get_by_id(repo_id, db_path=db)
        arealist = repo.get('arealist')
        assert isinstance(arealist, list) and len(arealist) == len(new_result), \
            f'force=True 后 repo.arealist 应与新 area 数量（{len(new_result)}）一致'

        _log_area_info(db, repo_id, label='force=True 重新分析后')
        _logger.info(
            f'断言通过：force=True 重新分析成功，'
            f'新 area 共 {len(new_result)} 个，旧记录已全部清除 ✓'
        )