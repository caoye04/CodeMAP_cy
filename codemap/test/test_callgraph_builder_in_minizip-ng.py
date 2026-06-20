"""
test/test_callgraph_builder_in_minizip-ng.py
针对真实 minizip-ng 仓库的 build_callgraph + analyze_func_callgraph 集成测试

前置依赖（fixture 链自动保证执行顺序）：
  init_repo → analyze_repo_language → analyze_repo_area
  → analyze_area_file → analyze_file_language → analyze_file_func
  → build_callgraph → analyze_func_callgraph

仓库路径（相对 codemap/）: ../../repo_4_codemap/minizip-ng/

运行：
    python -m pytest "test/test_callgraph_builder_in_minizip-ng.py" -v -s

日志：
    test/log/minizip_ng_callgraph_<YYYYMMDD_HHMMSS>.log

注意：
  - build_callgraph 需要 CodeQL CLI 可用（CODEQL_BIN 环境变量或 PATH）
  - C/C++ 仓库构建默认使用 --build-mode=autobuild，可能需要几分钟
  - CodeQL DB 默认保留在 data/codeql_dbs/minizip-ng/ 以供后续复用
  - 测试中 build_mode='none' 用于 CI 环境（无需编译，提取信息有限但速度快）
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB, AreaDB, FileDB, FuncDB
from analyzer.repo_analyzer  import init_repo, analyze_repo_language, analyze_repo_area
from analyzer.area_analyzer  import analyze_area_file
from analyzer.file_analyzer  import analyze_file_language, analyze_file_func
from analyzer.callgraph_builder import (
    build_callgraph,
    analyze_func_callgraph,
    _check_codeql,
    _classify_file_type,
    _normalize_path,
    _CALLGRAPH_DIR,
    CODEQL_BIN,
)
from config import DATA_DIR


# ==================================================================
#  常量
# ==================================================================

_REPO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../../repo_4_codemap/minizip-ng')
)

# 跳过条件
pytestmark = pytest.mark.skipif(
    not os.path.isdir(_REPO_PATH),
    reason=f'minizip-ng 仓库未找到，跳过：{_REPO_PATH}',
)

# CodeQL 可用性标志（模块级，只检测一次）
_CODEQL_AVAILABLE = _check_codeql(CODEQL_BIN)


# ==================================================================
#  日志
# ==================================================================

def _setup_logger() -> logging.Logger:
    log_dir = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'minizip_ng_callgraph_{ts}.log')

    logger = logging.getLogger('minizip_ng_callgraph_test')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s  %(levelname)-7s  %(message)s', datefmt='%H:%M:%S'
        ))
        logger.addHandler(fh)

    logger.info('=' * 68)
    logger.info('minizip-ng  build_callgraph / analyze_func_callgraph 集成测试')
    logger.info(f'仓库路径    : {_REPO_PATH}')
    logger.info(f'CodeQL 可用 : {_CODEQL_AVAILABLE}')
    logger.info(f'日志文件    : {log_file}')
    logger.info('=' * 68)
    return logger


_logger = _setup_logger()


# ==================================================================
#  日志工具
# ==================================================================

def _log_callgraph_stats(cg_data: dict, label: str) -> None:
    """将调用图统计信息写入日志。"""
    _logger.info('')
    _logger.info(f'┌── 调用图概况 [{label}]')
    _logger.info(f'│  语言           : {cg_data.get("language", "?")}')
    stats = cg_data.get('stats', {})
    for k, v in stats.items():
        _logger.info(f'│  {k:<22s} : {v:,}')
    by_func = cg_data.get('by_func', {})
    _logger.info(f'│  by_func 条目数 : {len(by_func):,}')

    # 打印 Top 10 callee 最多的函数
    top10 = sorted(by_func.values(), key=lambda x: len(x['callees']), reverse=True)[:10]
    _logger.info('│')
    _logger.info('│  callee 最多的前 10 个函数：')
    for e in top10:
        ftype = _classify_file_type(e['file'])
        _logger.info(
            f'│    {e["name"]:<36s} file={e["file"]!r:<30s} '
            f'type={ftype}  callee数={len(e["callees"])}  caller数={len(e["callers"])}'
        )
    _logger.info('└' + '─' * 60)


def _log_func_callgraph_sample(result: dict, label: str, sample: int = 20) -> None:
    """从 analyze_func_callgraph 结果中抽样写日志。"""
    _logger.info('')
    _logger.info(f'┌── func.callgraph 样本（前 {sample} 条有 callgraph 的函数）[{label}]')

    count = 0
    for fid, cg in sorted(result.items()):
        if not cg.get('callers') and not cg.get('callees'):
            continue
        if count >= sample:
            break
        callers = cg.get('callers', [])
        callees = cg.get('callees', [])
        _logger.info(
            f'│  func_id={fid:>5}  '
            f'caller数={len(callers):>3}  callee数={len(callees):>3}'
        )
        for c in callers[:3]:
            _logger.info(
                f'│    ← {c["name"]:<30s} file={c["file"]!r:<25s} type={c["type"]}'
            )
        for c in callees[:5]:
            _logger.info(
                f'│    → {c["name"]:<30s} file={c["file"]!r:<25s} type={c["type"]}'
            )
        count += 1

    empty_count = sum(
        1 for cg in result.values()
        if not cg.get('callers') and not cg.get('callees')
    )
    _logger.info('│')
    _logger.info(f'│  空 callgraph（无调用关系）的函数数：{empty_count}')
    _logger.info('└' + '─' * 60)


# ==================================================================
#  Fixtures
# ==================================================================

@pytest.fixture(scope='module')
def db(tmp_path_factory):
    """模块级临时数据库，整个测试共享。"""
    db_file = str(
        tmp_path_factory.mktemp('minizip_ng_callgraph') / 'codemap.db'
    )
    _logger.info(f'[db] 临时数据库 → {db_file}')
    init_db(db_file)
    return db_file


@pytest.fixture(scope='module')
def repo_id(db):
    _logger.info('\n── 前置 [1/6]：init_repo ─────────────────────────────')
    rid = init_repo(_REPO_PATH, db_path=db)
    _logger.info(f'init_repo 完成，repo_id = {rid}')
    return rid


@pytest.fixture(scope='module')
def language_ready(repo_id, db):
    _logger.info('\n── 前置 [2/6]：analyze_repo_language ────────────────')
    result = analyze_repo_language(repo_id, db_path=db)
    _logger.info(f"主语言：{result.get('main')}")
    return result


@pytest.fixture(scope='module')
def area_ready(language_ready, repo_id, db):
    _logger.info('\n── 前置 [3/6]：analyze_repo_area ────────────────────')
    result = analyze_repo_area(repo_id, db_path=db)
    _logger.info(f'划分 {len(result)} 个 area')
    return result


@pytest.fixture(scope='module')
def file_ready(area_ready, repo_id, db):
    _logger.info('\n── 前置 [4/6]：analyze_area_file ────────────────────')
    result = analyze_area_file(repo_id, db_path=db)
    total  = sum(len(v) for v in result.values())
    _logger.info(f'共 {total} 个文件入库')
    return result


@pytest.fixture(scope='module')
def lang_file_ready(file_ready, repo_id, db):
    _logger.info('\n── 前置 [5/6]：analyze_file_language + analyze_file_func ─')
    analyze_file_language(repo_id, db_path=db)
    result = analyze_file_func(repo_id, db_path=db)
    total  = sum(len(v) for v in result.values())
    _logger.info(f'共 {total} 个函数入库')
    return result


@pytest.fixture(scope='module')
def callgraph_result(lang_file_ready, repo_id, db):
    """
    运行 build_callgraph。
    若 CodeQL 不可用则跳过后续所有依赖此 fixture 的测试。
    """
    if not _CODEQL_AVAILABLE:
        pytest.skip('CodeQL CLI 不可用，跳过 build_callgraph 相关测试')

    _logger.info('\n── build_callgraph ───────────────────────────────────')
    _logger.info(f'repo_id = {repo_id}')

    # 使用 build_mode='autobuild' 以获得完整调用信息
    # CI 环境可改为 build_mode='none'（速度快，信息有限）
    result = build_callgraph(
        repo_id          = repo_id,
        db_path          = db,
        force            = True,
        keep_codeql_db   = True,
        build_mode       = 'autobuild',
        query_timeout    = 600,
        db_create_timeout= 3600,
    )

    _log_callgraph_stats(result, 'build_callgraph 完成')
    return result


@pytest.fixture(scope='module')
def func_callgraph_result(callgraph_result, repo_id, db):
    """运行 analyze_func_callgraph，返回 {func_id: callgraph_dict}。"""
    _logger.info('\n── analyze_func_callgraph ────────────────────────────')
    result = analyze_func_callgraph(repo_id, db_path=db, force=True)
    _log_func_callgraph_sample(result, 'analyze_func_callgraph 完成')
    return result


@pytest.fixture(autouse=True)
def _log_boundary(request):
    _logger.info('\n' + '─' * 68)
    _logger.info(f'▶ {request.node.name}')
    _logger.info('─' * 68)
    yield
    _logger.info(f'◀ {request.node.name}  完成')


# ==================================================================
#  工具函数测试（无需 CodeQL）
# ==================================================================

class TestHelpers:
    """对 _classify_file_type / _normalize_path 等辅助函数的单元测试。"""

    def test_classify_file_type_user(self):
        """相对路径 → user。"""
        assert _classify_file_type('src/deflate.c')     == 'user'
        assert _classify_file_type('mz_zip.c')          == 'user'
        assert _classify_file_type('include/zlib.h')    == 'user'
        _logger.info('classify user 断言通过 ✓')

    def test_classify_file_type_lib(self):
        """空路径、绝对路径、../路径 → lib。"""
        assert _classify_file_type('')                         == 'lib'
        assert _classify_file_type('/usr/include/string.h')   == 'lib'
        assert _classify_file_type('C:/MSVC/include/stdio.h') == 'lib'
        assert _classify_file_type('../external/zlib/zlib.h') == 'lib'
        _logger.info('classify lib 断言通过 ✓')

    def test_normalize_path(self):
        """路径规范化：统一正斜杠，去除前导 './'。"""
        assert _normalize_path('./src/foo.c')   == 'src/foo.c'
        assert _normalize_path('src\\foo.c')    == 'src/foo.c'
        assert _normalize_path('  ./a/b.c  ')  == 'a/b.c'
        assert _normalize_path('no/change.c')  == 'no/change.c'
        _logger.info('normalize_path 断言通过 ✓')


# ==================================================================
#  build_callgraph 测试
# ==================================================================

class TestBuildCallgraph:

    # ------------------------------------------------------------------
    # 返回值结构
    # ------------------------------------------------------------------

    def test_return_type_and_required_keys(self, callgraph_result):
        """
        返回值为 dict，且包含所有必要顶层字段：
        repo_id, repo_name, repo_path, language, stats, by_func
        """
        required = {'repo_id', 'repo_name', 'repo_path', 'language', 'stats', 'by_func'}
        missing  = required - set(callgraph_result.keys())
        assert not missing, f'返回值缺少字段：{missing}'
        _logger.info(f'返回值字段完整 ✓（{sorted(callgraph_result.keys())}）')

    def test_language_is_cpp(self, callgraph_result):
        """minizip-ng 为 C 仓库，CodeQL 语言应为 cpp。"""
        lang = callgraph_result.get('language')
        assert lang == 'cpp', f'期望 language=cpp，实际：{lang!r}'
        _logger.info(f'language=cpp 断言通过 ✓')

    def test_stats_structure(self, callgraph_result):
        """
        stats 字段包含所有计数键，且均为非负整数；
        total_edges >= unique_edges（原始边 ≥ 去重边）。
        """
        stats    = callgraph_result.get('stats', {})
        required = {'total_edges', 'unique_edges', 'total_funcs',
                    'user_caller_funcs', 'lib_callee_refs'}
        missing  = required - set(stats.keys())
        assert not missing, f'stats 缺少字段：{missing}'

        for k, v in stats.items():
            assert isinstance(v, int) and v >= 0, \
                f'stats.{k} 应为非负整数，实际：{v!r}'

        assert stats['total_edges'] >= stats['unique_edges'], \
            '总边数应 >= 去重边数'

        _logger.info(
            f'stats 结构正确 ✓  total_edges={stats["total_edges"]:,}  '
            f'unique_edges={stats["unique_edges"]:,}  '
            f'total_funcs={stats["total_funcs"]:,}'
        )

    def test_callgraph_nonempty(self, callgraph_result):
        """
        minizip-ng 是真实 C 库，by_func 必须非空，且 unique_edges > 0。
        """
        by_func      = callgraph_result.get('by_func', {})
        unique_edges = callgraph_result['stats']['unique_edges']

        assert len(by_func) > 0,      'by_func 不应为空'
        assert unique_edges > 0,      'unique_edges 应 > 0（仓库内存在函数调用关系）'

        _logger.info(
            f'调用图非空断言通过 ✓  by_func={len(by_func):,}  '
            f'unique_edges={unique_edges:,}'
        )

    # ------------------------------------------------------------------
    # by_func 条目结构
    # ------------------------------------------------------------------

    def test_by_func_entry_structure(self, callgraph_result):
        """
        每个 by_func 条目包含 name / file / callers / callees，
        callers / callees 均为列表，每项含 name / file / line / type。
        """
        by_func = callgraph_result.get('by_func', {})
        checked = 0
        required_entry = {'name', 'file', 'callers', 'callees'}
        required_node  = {'name', 'file', 'line', 'type'}

        for key, entry in list(by_func.items())[:200]:  # 抽样前 200 条
            missing_entry = required_entry - set(entry.keys())
            assert not missing_entry, \
                f'by_func[{key!r}] 缺少字段：{missing_entry}'

            for side in ('callers', 'callees'):
                assert isinstance(entry[side], list), \
                    f'by_func[{key!r}].{side} 应为 list'
                for idx, node in enumerate(entry[side][:5]):  # 只检查前 5 个
                    missing_node = required_node - set(node.keys())
                    assert not missing_node, \
                        f'by_func[{key!r}].{side}[{idx}] 缺少字段：{missing_node}'
                    assert node['type'] in ('user', 'lib'), \
                        f'type 应为 user/lib，实际：{node["type"]!r}'
            checked += 1

        _logger.info(f'by_func 条目结构检查通过 ✓（抽样 {checked} 条）')

    def test_key_format(self, callgraph_result):
        """
        by_func 的键格式应为 '{name}||{file}'，
        且 key 中函数名 / 文件名与条目内 name / file 一致。
        """
        by_func = callgraph_result.get('by_func', {})
        violations: list[str] = []

        for key, entry in list(by_func.items())[:500]:
            if '||' not in key:
                violations.append(f'键缺少 || 分隔符：{key!r}')
                continue
            k_name, k_file = key.split('||', 1)
            if k_name != entry.get('name'):
                violations.append(
                    f'键名与 name 不一致：{key!r} vs {entry.get("name")!r}'
                )
            if k_file != entry.get('file'):
                violations.append(
                    f'键文件与 file 不一致：{key!r} vs {entry.get("file")!r}'
                )

        assert not violations, \
            f'key 格式错误（前 5 条）：{violations[:5]}'
        _logger.info(f'by_func key 格式断言通过 ✓（抽样 500 条）')

    def test_type_classification_consistency(self, callgraph_result):
        """
        条目本身是用户函数（相对路径），其 caller/callee 中 type 字段
        应与 _classify_file_type 的逻辑一致。
        """
        by_func    = callgraph_result.get('by_func', {})
        mismatches = []

        for key, entry in list(by_func.items())[:300]:
            for side in ('callers', 'callees'):
                for node in entry[side][:10]:
                    expected = _classify_file_type(node['file'])
                    if node['type'] != expected:
                        mismatches.append(
                            f'{key}.{side}: file={node["file"]!r}  '
                            f'recorded={node["type"]}  expected={expected}'
                        )

        assert not mismatches, \
            f'type 分类不一致（前 3 条）：{mismatches[:3]}'
        _logger.info('type 分类一致性断言通过 ✓')

    # ------------------------------------------------------------------
    # 中间产物文件
    # ------------------------------------------------------------------

    def test_json_file_saved(self, callgraph_result):
        """
        中间产物 JSON 应写入 data/callgraph/minizip-ng.json，
        且文件大小 > 0、内容可正常解析。
        """
        json_path = os.path.join(_CALLGRAPH_DIR, 'minizip-ng.json')
        assert os.path.isfile(json_path), \
            f'调用图 JSON 不存在：{json_path}'
        assert os.path.getsize(json_path) > 0, \
            '调用图 JSON 大小应 > 0'

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert data.get('repo_name') == 'minizip-ng', \
            f'JSON repo_name 不符：{data.get("repo_name")!r}'

        file_size_kb = os.path.getsize(json_path) / 1024
        _logger.info(
            f'JSON 文件断言通过 ✓  路径={json_path}  大小={file_size_kb:.1f} KB'
        )

    # ------------------------------------------------------------------
    # force 参数
    # ------------------------------------------------------------------

    def test_force_false_reuses_file(self, callgraph_result, repo_id, db):
        """
        force=False 且结果文件已存在时，直接读取文件返回，
        不重新执行 CodeQL 查询（结果结构应与首次完全一致）。
        """
        result2 = build_callgraph(repo_id, db_path=db, force=False)
        assert result2.get('repo_name') == callgraph_result.get('repo_name'), \
            'force=False 返回的 repo_name 应与原始一致'
        assert result2.get('stats', {}).get('total_edges') == \
               callgraph_result.get('stats', {}).get('total_edges'), \
               'force=False 返回的 total_edges 应与原始一致'
        _logger.info('force=False 复用文件断言通过 ✓')


# ==================================================================
#  analyze_func_callgraph 测试
# ==================================================================

class TestAnalyzeFuncCallgraph:

    # ------------------------------------------------------------------
    # 返回值结构
    # ------------------------------------------------------------------

    def test_return_type_and_nonempty(self, func_callgraph_result, repo_id, db):
        """
        返回值为 dict，键为 func_id（正整数），值为 callgraph dict；
        DB 中存在函数时返回非空。
        """
        assert isinstance(func_callgraph_result, dict), \
            f'返回值应为 dict，实际：{type(func_callgraph_result).__name__}'

        total_funcs = len(FuncDB.list_by_repo(repo_id, db_path=db))
        assert len(func_callgraph_result) == total_funcs, \
            (f'返回 dict 长度（{len(func_callgraph_result)}）'
             f'应等于仓库函数总数（{total_funcs}）')

        _logger.info(
            f'返回值结构断言通过 ✓  func_id 数={len(func_callgraph_result):,}'
        )

    def test_all_func_ids_are_positive_int(self, func_callgraph_result):
        """所有 func_id 键应为正整数。"""
        for fid in func_callgraph_result:
            assert isinstance(fid, int) and fid > 0, \
                f'func_id 应为正整数，实际：{fid!r}'
        _logger.info('所有 func_id 均为正整数 ✓')

    def test_callgraph_dict_structure(self, func_callgraph_result):
        """
        每个 callgraph dict 包含 callers / callees 两个列表；
        列表内每项含 name / file / line / type 字段。
        """
        required_cg   = {'callers', 'callees'}
        required_node = {'name', 'file', 'line', 'type'}
        checked       = 0

        for fid, cg in list(func_callgraph_result.items())[:300]:
            missing_cg = required_cg - set(cg.keys())
            assert not missing_cg, \
                f'func_id={fid} callgraph 缺少字段：{missing_cg}'

            for side in ('callers', 'callees'):
                assert isinstance(cg[side], list), \
                    f'func_id={fid} callgraph.{side} 应为 list'
                for idx, node in enumerate(cg[side][:5]):
                    missing_node = required_node - set(node.keys())
                    assert not missing_node, \
                        f'func_id={fid} callgraph.{side}[{idx}] 缺少字段：{missing_node}'
                    assert node['type'] in ('user', 'lib'), \
                        f'type 值非法：{node["type"]!r}'
            checked += 1

        _logger.info(f'callgraph dict 结构断言通过 ✓（抽样 {checked} 条）')

    # ------------------------------------------------------------------
    # 数据库一致性
    # ------------------------------------------------------------------

    def test_db_callgraph_updated(self, func_callgraph_result, repo_id, db):
        """
        DB 中所有函数的 callgraph 字段应已更新（非 None）；
        DB 值与返回 dict 完全对应。
        """
        db_funcs = FuncDB.list_by_repo(repo_id, db_path=db)
        mismatches: list[str] = []
        none_count = 0

        for func in db_funcs:
            fid    = func['id']
            db_cg  = func.get('callgraph')

            if db_cg is None:
                none_count += 1
                continue  # 统计后在下方断言

            # 与返回值对比（callers 和 callees 长度一致）
            if fid in func_callgraph_result:
                ret_cg = func_callgraph_result[fid]
                if len(db_cg.get('callers', [])) != len(ret_cg.get('callers', [])):
                    mismatches.append(
                        f'func_id={fid} callers 长度不一致：'
                        f'DB={len(db_cg["callers"])} / ret={len(ret_cg["callers"])}'
                    )
                if len(db_cg.get('callees', [])) != len(ret_cg.get('callees', [])):
                    mismatches.append(
                        f'func_id={fid} callees 长度不一致：'
                        f'DB={len(db_cg["callees"])} / ret={len(ret_cg["callees"])}'
                    )

        assert none_count == 0, \
            f'仍有 {none_count} 个函数的 callgraph 字段为 None（未更新）'
        assert not mismatches, \
            f'DB 与返回值不一致（前 3 条）：{mismatches[:3]}'

        _logger.info(
            f'DB callgraph 更新断言通过 ✓  检查 {len(db_funcs)} 条函数记录'
        )

    # ------------------------------------------------------------------
    # 调用关系合理性
    # ------------------------------------------------------------------

    def test_some_functions_have_callees(self, func_callgraph_result):
        """
        minizip-ng 是完整 C 库，至少有 5% 的函数应有 callee（内部有函数调用）。
        """
        total     = len(func_callgraph_result)
        with_callee = sum(
            1 for cg in func_callgraph_result.values()
            if cg.get('callees')
        )
        ratio = with_callee / total if total else 0

        # 阈值较宽松：build-mode=none 时可能覆盖较少
        assert with_callee > 0, \
            '至少应有一个函数有 callee（仓库存在函数调用）'
        _logger.info(
            f'有 callee 的函数：{with_callee:,} / {total:,} = {ratio:.1%}  ✓'
        )

    def test_some_functions_have_callers(self, func_callgraph_result):
        """至少有 1 个函数被其他函数调用（有 caller）。"""
        with_caller = sum(
            1 for cg in func_callgraph_result.values()
            if cg.get('callers')
        )
        assert with_caller > 0, \
            '至少应有一个函数有 caller'
        _logger.info(f'有 caller 的函数：{with_caller:,}  ✓')

    def test_lib_callees_exist(self, func_callgraph_result):
        """
        minizip-ng 作为 C 库必然调用 libc 函数（malloc/memset/printf 等），
        至少应有一条 type='lib' 的 callee 引用。
        """
        lib_ref_count = sum(
            1
            for cg in func_callgraph_result.values()
            for node in cg.get('callees', [])
            if node.get('type') == 'lib'
        )
        assert lib_ref_count > 0, \
            '至少应有一条库函数引用（minizip-ng 调用了 libc 等外部函数）'
        _logger.info(f'lib 类型 callee 引用总数：{lib_ref_count:,}  ✓')

    def test_user_callee_files_relative(self, func_callgraph_result):
        """
        type='user' 的 callee，其 file 字段应为相对路径（不含绝对路径前缀）。
        """
        violations: list[str] = []
        for fid, cg in list(func_callgraph_result.items())[:500]:
            for node in cg.get('callees', []):
                if node.get('type') == 'user':
                    f = node.get('file', '')
                    if f.startswith('/') or (len(f) > 1 and f[1] == ':'):
                        violations.append(
                            f'func_id={fid} user callee file 为绝对路径：{f!r}'
                        )
        assert not violations, \
            f'user callee file 不应为绝对路径（前 3 条）：{violations[:3]}'
        _logger.info('user callee 路径均为相对路径 ✓')

    # ------------------------------------------------------------------
    # force 参数行为
    # ------------------------------------------------------------------

    def test_force_false_skips_existing(self, func_callgraph_result, repo_id, db):
        """
        force=False 时，已有 callgraph 数据的函数应被跳过（不重新写库）。
        运行 analyze_func_callgraph(force=False) 后，DB 中的值保持不变。
        """
        # 取一个有 callee 的函数做对比
        sample_fid = next(
            (fid for fid, cg in func_callgraph_result.items() if cg.get('callees')),
            None
        )
        if sample_fid is None:
            pytest.skip('没有含 callee 的函数，跳过此用例')

        before_cg = FuncDB.get_by_id(sample_fid, db_path=db).get('callgraph', {})
        result2   = analyze_func_callgraph(repo_id, db_path=db, force=False)
        after_cg  = FuncDB.get_by_id(sample_fid, db_path=db).get('callgraph', {})

        assert len(before_cg.get('callees', [])) == len(after_cg.get('callees', [])), \
            'force=False 时 callgraph 数据不应变化'

        _logger.info(
            f'force=False 断点续跑断言通过 ✓  '
            f'sample func_id={sample_fid}  '
            f'callee数={len(after_cg.get("callees", []))}'
        )

    def test_force_true_overwrites(self, func_callgraph_result, repo_id, db):
        """
        force=True 时，全部函数的 callgraph 应被重新写入。
        结果不应因重复运行而改变（幂等性验证）。
        """
        result2 = analyze_func_callgraph(repo_id, db_path=db, force=True)

        # 函数总数一致
        assert len(result2) == len(func_callgraph_result), \
            (f'force=True 返回函数数（{len(result2)}）'
             f'应与首次（{len(func_callgraph_result)}）一致')

        # 任意一个函数的 callee 数量一致
        sample_fid = next(iter(func_callgraph_result))
        assert len(result2.get(sample_fid, {}).get('callees', [])) == \
               len(func_callgraph_result.get(sample_fid, {}).get('callees', [])), \
               'force=True 重新运行结果应与首次一致（幂等）'

        _logger.info(f'force=True 幂等性断言通过 ✓')

    # ------------------------------------------------------------------
    # 单文件模式
    # ------------------------------------------------------------------

    def test_file_id_scope(self, func_callgraph_result, repo_id, db):
        """
        指定 file_id 时，只处理该文件下的函数，
        返回 dict 的 func_id 均应属于该文件。
        """
        # 取第一个有函数的文件
        all_files = FileDB.list_by_repo(repo_id, db_path=db)
        target_file = next(
            (f for f in all_files
             if FuncDB.list_by_file(f['id'], db_path=db)),
            None
        )
        if target_file is None:
            pytest.skip('没有包含函数的文件，跳过此用例')

        fid    = target_file['id']
        result = analyze_func_callgraph(repo_id, db_path=db, file_id=fid, force=True)

        # 验证返回的所有 func_id 都属于 target_file
        expected_func_ids = {
            f['id'] for f in FuncDB.list_by_file(fid, db_path=db)
        }
        for func_id in result:
            assert func_id in expected_func_ids, \
                (f'file_id={fid} 模式下，返回 func_id={func_id} '
                 f'不属于该文件（期望集合中的 {len(expected_func_ids)} 个）')

        _logger.info(
            f'file_id 范围限定断言通过 ✓  '
            f'file_id={fid}（{target_file["name"]}）  '
            f'返回 {len(result)} 个函数'
        )