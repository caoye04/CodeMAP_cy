"""
test/test_area_analyzer_analyze_area_file_in_minizip-ng.py
针对真实 minizip-ng 仓库的 analyze_area_file 集成测试

前置依赖（fixture 链自动保证执行顺序）：
  init_repo → analyze_repo_language → analyze_repo_area → analyze_area_file

仓库路径（相对 test/ 目录）  : ../../../repo_4_codemap/minizip-ng/
仓库路径（相对 codemap/ 目录）: ../../repo_4_codemap/minizip-ng/

运行：
    python -m pytest "test/test_area_analyzer_analyze_area_file_in_minizip-ng.py" -v

日志输出：
    test/log/minizip_ng_file_<YYYYMMDD_HHMMSS>.log

注意：
    文件名含连字符，pytest 通过路径收集，勿以 import 方式引用本模块。
    analyze_area_file 不依赖 LLM，纯本地磁盘扫描，速度较快。
    analyze_repo_area 依赖 LLM，需保证网络与 API 可用。
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB, AreaDB, FileDB
from analyzer.repo_analyzer import init_repo, analyze_repo_language, analyze_repo_area
from analyzer.area_analyzer import analyze_area_file
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
    在 test/log/ 创建 minizip_ng_file_<时间戳>.log。
    Logger 名 'minizip_ng_file_test'，幂等注册 Handler。
    """
    log_dir = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'minizip_ng_file_{ts}.log')

    logger = logging.getLogger('minizip_ng_file_test')
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
    logger.info('minizip-ng  analyze_area_file 集成测试开始')
    logger.info(f'仓库路径  : {_REPO_PATH}')
    logger.info(f'日志文件  : {log_file}')
    logger.info('=' * 68)
    return logger


_logger = _setup_logger()


# ==================================================================
#  核心日志工具 1：数据库层级结构 repo → area → file
# ==================================================================

def _log_db_structure(db_path: str, repo_id: int, label: str) -> None:
    """
    直接读取 SQLite，以树状结构将「repo → area → file」层级信息写入日志。

    展示内容：
      - repo  基本信息（name / path / 主语言 / area 数）
      - area  id / name / path / 文件数 / filelist 是否已更新
      - file  id / name / language / 相对路径（每个 area 缩进展示）
    """
    _logger.info('')
    _logger.info(f'┌── 数据库结构快照 [{label}]')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # ── repo ──────────────────────────────────────────────────
        repo_row = conn.execute(
            'SELECT * FROM repo WHERE id = ?', (repo_id,)
        ).fetchone()

        if repo_row is None:
            _logger.warning('│  repo 记录未找到')
            _logger.info('└' + '─' * 60)
            conn.close()
            return

        repo_d    = dict(repo_row)
        main_lang = '?'
        lang_raw  = repo_d.get('language')
        if isinstance(lang_raw, str):
            try:
                main_lang = json.loads(lang_raw).get('main', '?')
            except Exception:
                pass

        area_count = conn.execute(
            'SELECT COUNT(*) FROM area WHERE repo_id = ?', (repo_id,)
        ).fetchone()[0]
        file_count_total = conn.execute(
            'SELECT COUNT(*) FROM file WHERE repo_id = ?', (repo_id,)
        ).fetchone()[0]

        _logger.info(
            f'│  repo : id={repo_d["id"]}  name={repo_d["name"]!r}  '
            f'主语言={main_lang}  area数={area_count}  file总数={file_count_total}'
        )
        _logger.info(f'│         path={repo_d["path"]}')

        # ── area + file ───────────────────────────────────────────
        area_rows = conn.execute(
            'SELECT * FROM area WHERE repo_id = ? ORDER BY path',
            (repo_id,)
        ).fetchall()

        _logger.info('│')
        for ai, area_row in enumerate(area_rows):
            area_d   = dict(area_row)
            area_id  = area_d['id']
            is_last_area = (ai == len(area_rows) - 1)
            area_connector = '└─' if is_last_area else '├─'
            area_prefix    = '   ' if is_last_area else '│  '

            file_rows = conn.execute(
                'SELECT * FROM file WHERE area_id = ? ORDER BY path',
                (area_id,)
            ).fetchall()
            file_count = len(file_rows)

            # area.filelist 状态
            filelist_raw = area_d.get('filelist')
            filelist_status = '未更新(NULL)'
            if isinstance(filelist_raw, str):
                try:
                    fl = json.loads(filelist_raw)
                    filelist_status = f'已更新（{len(fl)} 项）'
                except Exception:
                    filelist_status = '解析失败'

            _logger.info(
                f'│  {area_connector} area [{area_id:>3}] {area_d["name"]!r:<26s} '
                f'path={area_d["path"]!r:<20s} '
                f'文件数={file_count}  filelist={filelist_status}'
            )

            # file 列表
            for fi, file_row in enumerate(file_rows):
                fd              = dict(file_row)
                is_last_file    = (fi == len(file_rows) - 1)
                file_connector  = '└── ' if is_last_file else '├── '
                lang_str        = fd.get('language') or '—'
                # 截断超长路径
                path_str = fd['path']
                if len(path_str) > 55:
                    path_str = '...' + path_str[-52:]

                _logger.info(
                    f'│  {area_prefix}  {file_connector}'
                    f'[{fd["id"]:>4}] {fd["name"]:<36s}'
                    f'lang={lang_str:<6s}  {path_str}'
                )

            if not file_rows:
                _logger.info(f'│  {area_prefix}      （该 area 暂无 file 记录）')

        conn.close()

    except Exception as exc:
        _logger.warning(f'│  读取数据库失败：{exc}')

    _logger.info('└' + '─' * 60)


# ==================================================================
#  核心日志工具 2：analyze_area_file 返回值摘要
# ==================================================================

def _log_file_summary(result: dict, label: str) -> None:
    """
    将 analyze_area_file 的返回值（dict[area_id → list[file_dict]]）
    按 area 分组打印，给出每个 area 的文件数及文件列表基本信息。
    """
    _logger.info('')
    _logger.info(f'┌── analyze_area_file 返回值摘要 [{label}]')

    total = 0
    for area_id, files in sorted(result.items()):
        _logger.info(f'│  area_id={area_id:>3}  文件数={len(files)}')
        for f in files:
            path_str = f['path']
            if len(path_str) > 55:
                path_str = '...' + path_str[-52:]
            _logger.info(
                f'│    [{f["file_id"]:>4}] {f["name"]:<36s}  {path_str}'
            )
        total += len(files)

    _logger.info('│')
    _logger.info(f'│  合计：{len(result)} 个 area，{total} 个文件')
    _logger.info('└' + '─' * 60)


# ==================================================================
#  Fixtures
# ==================================================================

@pytest.fixture(scope='module')
def db(tmp_path_factory):
    """模块级临时数据库，整个测试文件共享，保证用例间状态连续。"""
    db_file = str(tmp_path_factory.mktemp('minizip_ng_file') / 'codemap.db')
    _logger.info(f'[db] 创建临时数据库 → {db_file}')
    init_db(db_file)
    _logger.info('[db] 表结构初始化完成')
    return db_file


@pytest.fixture(scope='module')
def repo_id(db):
    """模块级：调用 init_repo()，返回 repo_id 供后续 fixture 和用例复用。"""
    _logger.info('')
    _logger.info('── 前置步骤 [1/3]：init_repo ──────────────────────────')
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
    _logger.info('── 前置步骤 [2/3]：analyze_repo_language ──────────────')
    result = analyze_repo_language(repo_id, db_path=db)
    _logger.info(f'analyze_repo_language 完成，主语言：{result.get("main")}')
    top5 = result.get('stats', [])[:5]
    for entry in top5:
        _logger.info(
            f'  {entry["lang"]:<18s} {entry["pct"]:6.2f}%  '
            f'{entry["bytes"]:>12,} bytes'
        )
    return result


@pytest.fixture(scope='module')
def area_ready(language_ready, repo_id, db):
    """
    模块级：调用 analyze_repo_area()，确保 area 表已建立。
    analyze_area_file 依赖 area 记录，故须先行执行。
    """
    _logger.info('')
    _logger.info('── 前置步骤 [3/3]：analyze_repo_area ──────────────────')
    result = analyze_repo_area(repo_id, db_path=db)
    _logger.info(f'analyze_repo_area 完成，共 {len(result)} 个 area')
    for a in result:
        _logger.info(
            f'  area_id={a["area_id"]:>3}  '
            f'name={a["name"]!r:<28s}  '
            f'path={a["path"]!r}'
        )
    return result


@pytest.fixture(scope='module')
def file_result(area_ready, repo_id, db):
    """
    模块级：调用 analyze_area_file()，写入 file 表并更新 area.filelist，
    返回 dict[area_id, list[file_dict]] 供全部测试用例复用。
    """
    _logger.info('')
    _logger.info('── analyze_area_file ─────────────────────────────────────')
    _logger.info(f'调用 analyze_area_file(repo_id={repo_id})')

    result = analyze_area_file(repo_id, db_path=db)
    total  = sum(len(v) for v in result.values())

    _logger.info(
        f'analyze_area_file 返回，共 {len(result)} 个 area，{total} 个文件'
    )

    # ── 两种视角的日志输出 ──────────────────────────────────────────
    _log_file_summary(result, label='analyze_area_file 初次调用完成后')
    _log_db_structure(db, repo_id, label='analyze_area_file 初次调用完成后')

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

class TestAnalyzeAreaFile:

    # ------------------------------------------------------------------
    # 返回值结构
    # ------------------------------------------------------------------

    def test_return_type_and_nonempty(self, file_result):
        """
        analyze_area_file 应：
          - 返回值类型为 dict
          - 字典非空（至少有一个 area）
          - 全局文件总数 > 0（minizip-ng 有源码文件）
        """
        assert isinstance(file_result, dict), \
            f'返回值应为 dict，实际类型：{type(file_result).__name__}'
        assert len(file_result) > 0, \
            '返回 dict 不应为空（至少有一个 area）'

        total = sum(len(v) for v in file_result.values())
        assert total > 0, \
            'minizip-ng 应包含可识别文件，文件总数不应为 0'

        _logger.info(
            f'断言通过：返回非空 dict，{len(file_result)} 个 area，'
            f'{total} 个文件 ✓'
        )

    def test_each_file_has_required_fields(self, file_result):
        """
        每个 file 条目应包含 file_id / name / path，
        且所有字段值非 None、非空字符串。
        """
        required = {'file_id', 'name', 'path'}
        checked  = 0
        for area_id, files in file_result.items():
            for idx, finfo in enumerate(files):
                missing = required - set(finfo.keys())
                assert not missing, \
                    f'area_id={area_id} file[{idx}] 缺少字段：{missing}'
                for field in required:
                    val = finfo[field]
                    assert val is not None, \
                        f'area_id={area_id} file[{idx}].{field} 不应为 None'
                    assert str(val).strip() != '', \
                        f'area_id={area_id} file[{idx}].{field} 不应为空字符串'
                checked += 1

        _logger.info(f'断言通过：共检查 {checked} 个 file 条目，字段均完整且非空 ✓')

    def test_file_id_is_positive_int(self, file_result):
        """每个 file_id 应为正整数（由 FileDB.create 写库后返回）。"""
        for area_id, files in file_result.items():
            for finfo in files:
                fid = finfo.get('file_id')
                assert isinstance(fid, int) and fid > 0, \
                    f'area_id={area_id} file_id 应为正整数，实际：{fid!r}'

        _logger.info('断言通过：所有 file_id 均为正整数 ✓')

    # ------------------------------------------------------------------
    # 去重 / 路径规范
    # ------------------------------------------------------------------

    def test_no_duplicate_file_ids_or_paths(self, file_result):
        """
        全局范围内 file_id 和 path 均不重复，
        确保同一文件未被多个 area 重复收录。
        """
        all_ids   = [f['file_id'] for files in file_result.values() for f in files]
        all_paths = [f['path']    for files in file_result.values() for f in files]

        dup_ids   = [x for x in set(all_ids)   if all_ids.count(x)   > 1]
        dup_paths = [x for x in set(all_paths) if all_paths.count(x) > 1]

        assert not dup_ids, \
            f'存在重复 file_id：{dup_ids}'
        assert not dup_paths, \
            f'存在重复 file path（共 {len(dup_paths)} 条）：{dup_paths[:5]}...'

        _logger.info(
            f'断言通过：{len(all_ids)} 个文件中，file_id 和 path 均无重复 ✓'
        )

    def test_path_uses_forward_slash(self, file_result):
        """所有 file.path 应使用 '/' 分隔符（跨平台规范）。"""
        violations = []
        for area_id, files in file_result.items():
            for finfo in files:
                if '\\' in finfo['path']:
                    violations.append((area_id, finfo['path']))

        assert not violations, \
            f'以下 file.path 含反斜杠（应使用 /）：{violations[:5]}'

        _logger.info('断言通过：所有 file.path 使用正斜杠分隔符 ✓')

    # ------------------------------------------------------------------
    # 磁盘验证
    # ------------------------------------------------------------------

    def test_all_file_paths_exist_on_disk(self, file_result):
        """
        每个 file.path（相对仓库根）对应的实际磁盘文件应存在。
        """
        checked = 0
        for area_id, files in file_result.items():
            for finfo in files:
                abs_p = os.path.join(_REPO_PATH, finfo['path'])
                assert os.path.isfile(abs_p), \
                    f'file 路径在磁盘上不存在或不是文件：{finfo["path"]!r}'
                checked += 1

        _logger.info(f'断言通过：{checked} 个 file 路径在磁盘上均存在 ✓')

    def test_file_count_per_area_reasonable(self, file_result):
        """
        每个 area 下的文件数不超过 500（异常上限），
        且全局至少有一个 area 包含文件（仓库非空）。
        """
        for area_id, files in file_result.items():
            assert len(files) <= 500, \
                (f'area_id={area_id} 文件数 {len(files)} '
                 f'超出预期上限 500，可能存在扫描逻辑异常')
            _logger.info(f'  area_id={area_id:>3}  文件数={len(files)}  ✓')

        non_empty = sum(1 for v in file_result.values() if v)
        assert non_empty > 0, '至少应有一个 area 包含文件'

        _logger.info(
            f'断言通过：{non_empty} 个 area 包含文件，'
            f'无 area 超出上限 500 ✓'
        )

    # ------------------------------------------------------------------
    # 数据库一致性
    # ------------------------------------------------------------------

    def test_db_file_records_match_return(self, file_result, repo_id, db):
        """
        DB file 表中属于 repo_id 的记录总数应与返回值文件总数一致，
        且每个 file_id 可按 id 查到，name / path 与返回值完全吻合。
        """
        db_files     = FileDB.list_by_repo(repo_id, db_path=db)
        return_total = sum(len(v) for v in file_result.values())

        assert len(db_files) == return_total, \
            (f'DB file 记录数（{len(db_files)}）'
             f'与返回文件总数（{return_total}）不一致')

        for area_id, files in file_result.items():
            for finfo in files:
                record = FileDB.get_by_id(finfo['file_id'], db_path=db)
                assert record is not None, \
                    f'file_id={finfo["file_id"]} 在 DB 中找不到记录'
                assert record['name'] == finfo['name'], \
                    (f'file_id={finfo["file_id"]} name 不一致：'
                     f'DB={record["name"]!r} / 返回={finfo["name"]!r}')
                assert record['path'] == finfo['path'], \
                    (f'file_id={finfo["file_id"]} path 不一致：'
                     f'DB={record["path"]!r} / 返回={finfo["path"]!r}')

        _logger.info(
            f'断言通过：DB file 表 {len(db_files)} 条记录与返回列表完全匹配 ✓'
        )

    def test_db_file_fk_correct(self, file_result, repo_id, db):
        """
        DB 中每条 file 记录的外键应正确：
          file.repo_id == repo_id  且  file.area_id 与 file_result 的 key 一致。
        """
        for area_id, files in file_result.items():
            for finfo in files:
                record = FileDB.get_by_id(finfo['file_id'], db_path=db)
                assert record['repo_id'] == repo_id, \
                    (f'file_id={finfo["file_id"]} repo_id 错误：'
                     f'DB={record["repo_id"]} / 期望={repo_id}')
                assert record['area_id'] == area_id, \
                    (f'file_id={finfo["file_id"]} area_id 错误：'
                     f'DB={record["area_id"]} / 期望={area_id}')

        _logger.info('断言通过：所有 file 记录的 repo_id / area_id 外键正确 ✓')

    def test_area_filelist_updated(self, file_result, repo_id, db):
        """
        每个 area 的 filelist 字段应被正确更新：
          - 反序列化后为 list
          - 长度与 file_result 对应 area 的文件数一致
          - 每项包含 file_id / name / brief 字段
        """
        for area_id, files in file_result.items():
            area_record = AreaDB.get_by_id(area_id, db_path=db)
            filelist    = area_record.get('filelist')

            assert isinstance(filelist, list), \
                (f'area_id={area_id} filelist 应反序列化为 list，'
                 f'实际类型：{type(filelist).__name__}')
            assert len(filelist) == len(files), \
                (f'area_id={area_id} filelist 长度（{len(filelist)}）'
                 f'与返回文件数（{len(files)}）不一致')

            for idx, item in enumerate(filelist):
                for key in ('file_id', 'name', 'brief'):
                    assert key in item, \
                        (f'area_id={area_id} filelist[{idx}] '
                         f'缺少字段 {key!r}，实际：{item}')

            _logger.info(
                f'  area_id={area_id:>3}  filelist 长度={len(filelist):>4}  ✓'
            )

        _logger.info('断言通过：所有 area.filelist 已正确更新 ✓')

    # ------------------------------------------------------------------
    # 中间产物
    # ------------------------------------------------------------------

    def test_intermediate_json_saved(self, file_result):
        """
        中间产物 JSON 应写入 data/analyze_area_file/minizip-ng.json，
        包含 areas / repo_id / repo_name / summary 字段，
        且 summary.total_files 与返回值文件总数一致。
        """
        json_path = os.path.join(DATA_DIR, 'analyze_area_file', 'minizip-ng.json')
        assert os.path.isfile(json_path), \
            f'中间产物 JSON 文件不存在：{json_path}'

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for key in ('areas', 'repo_id', 'repo_name', 'summary'):
            assert key in data, \
                f'JSON 缺少字段 {key!r}，实际 keys：{list(data.keys())}'

        return_total = sum(len(v) for v in file_result.values())
        json_total   = data['summary'].get('total_files', -1)
        assert json_total == return_total, \
            (f'JSON summary.total_files（{json_total}）'
             f'与返回值文件总数（{return_total}）不一致')

        # 详细打印 JSON 摘要到日志
        _logger.info(f'中间产物 JSON 路径：{json_path}')
        _logger.info(f'  summary.total_areas = {data["summary"].get("total_areas")}')
        _logger.info(f'  summary.total_files = {json_total}')
        for area_rec in data.get('areas', []):
            _logger.info(
                f'    area_id={area_rec.get("area_id"):>3}  '
                f'name={area_rec.get("area_name")!r:<28s}  '
                f'file_count={area_rec.get("file_count"):>4}  '
                f'area_path={area_rec.get("area_path")!r}'
            )

        _logger.info(
            f'断言通过：中间产物 JSON 结构完整，total_files={json_total} ✓'
        )

    # ------------------------------------------------------------------
    # force 参数行为
    # ------------------------------------------------------------------

    def test_force_false_raises_on_duplicate(self, file_result, repo_id, db):
        """
        file 记录已存在时，force=False（默认值）再次调用应抛出 ValueError，
        且错误信息提示已有 file 记录。
        """
        with pytest.raises(ValueError, match=r'已有.*file.*记录'):
            analyze_area_file(repo_id, db_path=db, force=False)

        _logger.info('断言通过：force=False 时重复调用抛出 ValueError ✓')

    def test_force_true_allows_reanalysis(self, file_result, repo_id, db):
        """
        force=True 时应允许重新扫描（此用例最后执行，会修改 DB 状态）：
          - 清除全部旧 file 记录并重建
          - 返回新的非空 dict，文件总数合理
          - 旧 file_id 在 DB 中应不再存在
          - 每个 area.filelist 以新数据覆盖更新
        """
        old_ids = {
            f['file_id']
            for files in file_result.values()
            for f in files
        }
        _logger.info(f'旧 file_id 集合大小：{len(old_ids)}')

        new_result = analyze_area_file(repo_id, db_path=db, force=True)
        new_total  = sum(len(v) for v in new_result.values())

        # 返回值非空
        assert isinstance(new_result, dict) and new_total > 0, \
            'force=True 重新扫描后返回 dict 不应为空'

        # 旧 file_id 应已被删除
        for old_id in old_ids:
            record = FileDB.get_by_id(old_id, db_path=db)
            assert record is None, \
                (f'旧 file_id={old_id} 在 force=True 后仍存在于 DB'
                 f'（应已被删除）')

        # 每个 area.filelist 以新数据覆盖
        for area_id, files in new_result.items():
            area_record = AreaDB.get_by_id(area_id, db_path=db)
            filelist    = area_record.get('filelist')
            assert isinstance(filelist, list) and len(filelist) == len(files), \
                (f'force=True 后 area_id={area_id} filelist 长度'
                 f'（{len(filelist) if isinstance(filelist, list) else "N/A"}）'
                 f'应与新文件数（{len(files)}）一致')

        _log_db_structure(db, repo_id, label='force=True 重新扫描后')
        _logger.info(
            f'断言通过：force=True 重新扫描成功，'
            f'新文件共 {new_total} 个，旧 {len(old_ids)} 条记录已全部清除 ✓'
        )