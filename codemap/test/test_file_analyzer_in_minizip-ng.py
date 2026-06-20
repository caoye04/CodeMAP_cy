"""
test/test_file_analyzer_in_minizip-ng.py
针对真实 minizip-ng 仓库的 analyze_file_language + analyze_file_func 集成测试

前置 fixture 链（模块级，自动保证顺序）：
  init_repo
    → analyze_repo_language
      → analyze_repo_area
        → analyze_area_file
          → analyze_file_language   ← Step 5a
            → analyze_file_func     ← Step 5b

仓库路径（相对 codemap/）：../../repo_4_codemap/minizip-ng/

运行：
    python -m pytest "test/test_file_analyzer_in_minizip-ng.py" -v -s

日志：
    test/log/minizip_ng_func_<YYYYMMDD_HHMMSS>.log

数据库：
    data/test_db/db_minizip-ng_<YYYYMMDD>_<HHMM>.db
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
from config import DATA_DIR


# ==================================================================
# 常量
# ==================================================================

_REPO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../../repo_4_codemap/minizip-ng')
)

pytestmark = pytest.mark.skipif(
    not os.path.isdir(_REPO_PATH),
    reason=f'minizip-ng 仓库未找到，跳过：{_REPO_PATH}',
)


# ==================================================================
# 日志工具
# ==================================================================

def _setup_logger() -> logging.Logger:
    log_dir  = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'minizip_ng_func_{ts}.log')

    logger = logging.getLogger('minizip_ng_func_test')
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s  %(levelname)-7s  %(message)s',
            datefmt='%H:%M:%S',
        ))
        logger.addHandler(fh)

    logger.info('=' * 70)
    logger.info('minizip-ng  analyze_file_language + analyze_file_func 集成测试')
    logger.info(f'仓库路径  : {_REPO_PATH}')
    logger.info(f'日志文件  : {log_file}')
    logger.info('=' * 70)
    return logger


_logger = _setup_logger()


# ==================================================================
# 日志辅助：打印函数统计树
# ==================================================================

def _log_func_summary(
    result: dict, label: str,
    max_files: int = 30,
    max_funcs_per_file: int = 10,
) -> None:
    """打印 analyze_file_func 返回值的分层摘要。"""
    _logger.info('')
    _logger.info(f'┌── analyze_file_func 返回值摘要 [{label}]')

    non_empty = {fid: fns for fid, fns in result.items() if fns}
    total     = sum(len(v) for v in result.values())
    _logger.info(f'│  总文件数={len(result)}  含函数文件={len(non_empty)}  总函数数={total}')
    _logger.info('│')

    shown = 0
    for file_id, funcs in sorted(non_empty.items()):
        if shown >= max_files:
            _logger.info(f'│  ... （还有 {len(non_empty) - shown} 个文件未展示）')
            break
        _logger.info(f'│  file_id={file_id:>4}  funcs={len(funcs)}')
        for fn in funcs[:max_funcs_per_file]:
            _logger.info(
                f'│    [{fn["func_id"]:>5}] '
                f'{fn["name"]:<40s} '
                f'L{fn["start_line"]}-{fn["end_line"]}'
            )
        if len(funcs) > max_funcs_per_file:
            _logger.info(f'│    ... 还有 {len(funcs) - max_funcs_per_file} 个函数')
        shown += 1

    _logger.info('└' + '─' * 62)


def _log_db_func_stats(db_path: str, repo_id: int, label: str) -> None:
    """直接查询数据库，打印 func 表基础统计信息。"""
    _logger.info('')
    _logger.info(f'┌── DB func 表统计 [{label}]')
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        total = conn.execute(
            'SELECT COUNT(*) FROM func WHERE repo_id=?', (repo_id,)
        ).fetchone()[0]
        _logger.info(f'│  func 总记录数 = {total}')

        # 按 place.file_path 统计每文件函数数（Top 15）
        rows = conn.execute(
            'SELECT place FROM func WHERE repo_id=?', (repo_id,)
        ).fetchall()

        from collections import Counter
        path_cnt: Counter = Counter()
        for row in rows:
            place_raw = row['place']
            if isinstance(place_raw, str):
                try:
                    p = json.loads(place_raw)
                    path_cnt[p.get('file_path', '?')] += 1
                except Exception:
                    path_cnt['?'] += 1

        _logger.info(f'│  涉及文件数 = {len(path_cnt)}  Top 15 函数密集文件：')
        for path, cnt in path_cnt.most_common(15):
            _logger.info(f'│    {cnt:>4}  {path}')

        conn.close()
    except Exception as exc:
        _logger.warning(f'│  读取 DB 失败：{exc}')
    _logger.info('└' + '─' * 62)


# ==================================================================
# Fixtures（模块级，保证串行执行）
# ==================================================================

@pytest.fixture(scope='module')
def db():
    """
    在 data/test_db/ 下创建持久化数据库，命名规则：
        db_<仓库名>_<YYYYMMDD>_<HHMM>.db
    测试结束后不删除，便于离线查阅。
    """
    repo_name   = os.path.basename(_REPO_PATH)          # 'minizip-ng'
    ts          = datetime.now().strftime('%Y%m%d_%H%M') # '20240101_1430'
    db_filename = f'db_{repo_name}_{ts}.db'

    test_db_dir = os.path.join(DATA_DIR, 'test_db')
    os.makedirs(test_db_dir, exist_ok=True)

    db_file = os.path.join(test_db_dir, db_filename)
    init_db(db_file)
    _logger.info(f'[db] 创建测试数据库：{db_file}')
    return db_file


@pytest.fixture(scope='module')
def repo_id(db):
    _logger.info('── 前置 [1/4]：init_repo')
    rid = init_repo(_REPO_PATH, db_path=db)
    _logger.info(f'repo_id = {rid}')
    return rid


@pytest.fixture(scope='module')
def language_ready(repo_id, db):
    _logger.info('── 前置 [2/4]：analyze_repo_language')
    res = analyze_repo_language(repo_id, db_path=db)
    _logger.info(f'主语言：{res.get("main")}')
    return res


@pytest.fixture(scope='module')
def area_ready(language_ready, repo_id, db):
    _logger.info('── 前置 [3/4]：analyze_repo_area（需 LLM）')
    res = analyze_repo_area(repo_id, db_path=db)
    _logger.info(f'共 {len(res)} 个 area')
    return res


@pytest.fixture(scope='module')
def file_ready(area_ready, repo_id, db):
    _logger.info('── 前置 [4/4]：analyze_area_file')
    res = analyze_area_file(repo_id, db_path=db)
    total = sum(len(v) for v in res.values())
    _logger.info(f'共 {total} 个文件')
    return res


@pytest.fixture(scope='module')
def lang_result(file_ready, repo_id, db):
    """Step 5a：analyze_file_language"""
    _logger.info('── Step 5a：analyze_file_language')
    res = analyze_file_language(repo_id, db_path=db)
    _logger.info(f'语言检测完成，共 {len(res)} 个文件')
    return res


@pytest.fixture(scope='module')
def func_result(lang_result, repo_id, db):
    """Step 5b：analyze_file_func"""
    _logger.info('── Step 5b：analyze_file_func')
    res = analyze_file_func(repo_id, db_path=db)
    total = sum(len(v) for v in res.values())
    _logger.info(f'函数提取完成，共 {total} 个函数')
    _log_func_summary(res, 'analyze_file_func 初次完成')
    _log_db_func_stats(db, repo_id, 'analyze_file_func 初次完成')
    return res


@pytest.fixture(autouse=True)
def _log_case(request):
    _logger.info('')
    _logger.info('─' * 70)
    _logger.info(f'▶ {request.node.name}')
    _logger.info('─' * 70)
    yield
    _logger.info(f'◀ {request.node.name}  完成')


# ==================================================================
# 测试：analyze_file_language（Step 5a）
# ==================================================================

class TestAnalyzeFileLanguage:

    def test_returns_nonempty_dict(self, lang_result):
        """应返回非空字典，key 为 file_id（正整数）。"""
        assert isinstance(lang_result, dict), \
            f'返回类型应为 dict，实为 {type(lang_result)}'
        assert len(lang_result) > 0, '结果不应为空（仓库有文件）'

        for fid in lang_result:
            assert isinstance(fid, int) and fid > 0, \
                f'key 应为正整数 file_id，实为 {fid!r}'

        _logger.info(f'断言通过：{len(lang_result)} 个文件 ✓')

    def test_all_values_are_nonempty_strings(self, lang_result):
        """每个语言值为非空字符串。"""
        for fid, lang in lang_result.items():
            assert isinstance(lang, str) and lang.strip(), \
                f'file_id={fid} language 应为非空字符串，实为 {lang!r}'

        _logger.info('断言通过：所有 language 为非空字符串 ✓')

    def test_c_files_detected_as_c(self, lang_result, repo_id, db):
        """
        minizip-ng 是 C 项目，.c 文件应被检测为 'C'，
        .h 文件也应被检测为 'C'（而非 Unknown）。
        """
        all_files = FileDB.list_by_repo(repo_id, db_path=db)
        c_source  = [f for f in all_files if f['name'].endswith('.c')]
        h_header  = [f for f in all_files if f['name'].endswith('.h')]

        assert c_source, 'minizip-ng 应有 .c 源文件'
        for f in c_source:
            lang = lang_result.get(f['id'])
            assert lang == 'C', \
                f'{f["name"]} 应检测为 C，实为 {lang!r}'

        for f in h_header:
            lang = lang_result.get(f['id'])
            assert lang == 'C', \
                f'{f["name"]} 应检测为 C（头文件），实为 {lang!r}'

        _logger.info(
            f'断言通过：{len(c_source)} 个 .c + {len(h_header)} 个 .h '
            f'均检测为 C ✓'
        )

    def test_db_language_field_updated(self, lang_result, repo_id, db):
        """DB 中 file.language 与返回值一致（检查前 50 条）。"""
        checked = 0
        for fid, expected_lang in list(lang_result.items())[:50]:
            rec = FileDB.get_by_id(fid, db_path=db)
            assert rec is not None, f'file_id={fid} 在 DB 中找不到'
            assert rec.get('language') == expected_lang, (
                f'file_id={fid} DB.language={rec.get("language")!r} '
                f'≠ 返回值={expected_lang!r}'
            )
            checked += 1

        _logger.info(f'断言通过：检查前 {checked} 条，DB language 与返回值一致 ✓')

    def test_no_unknown_on_c_ext(self, lang_result, repo_id, db):
        """没有 .c/.h/.py 文件被标记为 Unknown。"""
        all_files   = FileDB.list_by_repo(repo_id, db_path=db)
        code_ext    = {'.c', '.h', '.cpp', '.hpp', '.py'}
        violations  = []
        for f in all_files:
            _, ext = os.path.splitext(f['name'])
            if ext.lower() in code_ext:
                lang = lang_result.get(f['id'])
                if lang == 'Unknown':
                    violations.append(f['path'])

        assert not violations, \
            f'以下代码文件被标记为 Unknown：{violations[:10]}'
        _logger.info(f'断言通过：所有已知扩展名代码文件均非 Unknown ✓')


# ==================================================================
# 测试：analyze_file_func（Step 5b）
# ==================================================================

class TestAnalyzeFileFunc:

    # ------------------------------------------------------------------
    # 返回值结构
    # ------------------------------------------------------------------

    def test_return_type_and_nonempty(self, func_result):
        """返回值应为非空 dict，全局函数总数 > 0。"""
        assert isinstance(func_result, dict)
        assert len(func_result) > 0

        total = sum(len(v) for v in func_result.values())
        assert total > 0, 'minizip-ng 应有可提取的函数'

        _logger.info(f'断言通过：{total} 个函数，{len(func_result)} 个文件键 ✓')

    def test_c_files_have_functions(self, func_result, repo_id, db):
        """
        主要的 .c 源文件应提取到函数（tree-sitter 或 ctags 都要能工作）。
        至少一半 .c 文件包含函数。
        """
        all_files = FileDB.list_by_repo(repo_id, db_path=db)
        c_files   = [f for f in all_files if f['name'].endswith('.c')]

        c_with_funcs = sum(
            1 for f in c_files
            if func_result.get(f['id'])
        )
        ratio = c_with_funcs / len(c_files) if c_files else 0

        assert ratio >= 0.5, (
            f'仅 {c_with_funcs}/{len(c_files)} 个 .c 文件有函数，'
            f'比例 {ratio:.0%} 低于期望 50%'
        )
        _logger.info(
            f'断言通过：{c_with_funcs}/{len(c_files)} 个 .c 文件含函数 '
            f'（{ratio:.0%}）✓'
        )

    def test_each_func_has_required_fields(self, func_result):
        """每个函数条目必须含 func_id / name / start_line / end_line。"""
        required = {'func_id', 'name', 'start_line', 'end_line'}
        checked  = 0
        for file_id, funcs in func_result.items():
            for fn in funcs:
                missing = required - set(fn.keys())
                assert not missing, \
                    f'file_id={file_id} 函数 {fn.get("name")!r} 缺少字段：{missing}'
                assert fn['func_id'] > 0
                assert fn['name'].strip()
                assert fn['start_line'] > 0
                assert fn['end_line'] >= fn['start_line']
                checked += 1

        _logger.info(f'断言通过：{checked} 个函数条目字段完整 ✓')

    def test_no_duplicate_func_ids(self, func_result):
        """全局范围内 func_id 唯一，无重复写库。"""
        all_ids = [
            fn['func_id']
            for fns in func_result.values()
            for fn in fns
        ]
        dup = [x for x in set(all_ids) if all_ids.count(x) > 1]
        assert not dup, f'存在重复 func_id：{dup[:10]}'
        _logger.info(f'断言通过：{len(all_ids)} 个 func_id 均唯一 ✓')

    # ------------------------------------------------------------------
    # 数据库一致性
    # ------------------------------------------------------------------

    def test_db_func_records_match_return(self, func_result, repo_id, db):
        """DB func 表记录总数与返回值函数总数一致。"""
        db_total     = len(FuncDB.list_by_repo(repo_id, db_path=db))
        return_total = sum(len(v) for v in func_result.values())
        assert db_total == return_total, (
            f'DB func 记录数（{db_total}）≠ 返回函数总数（{return_total}）'
        )
        _logger.info(f'断言通过：DB func 记录数 {db_total} 与返回值一致 ✓')

    def test_func_place_and_io_fields_in_db(self, func_result, repo_id, db):
        """
        DB 中 func.place 和 func.io 应正确反序列化为 dict，
        place 包含 file_path / start_line / end_line，
        io 包含 params / returns。
        检查前 100 条。
        """
        all_funcs = FuncDB.list_by_repo(repo_id, db_path=db)
        checked   = 0
        for fn_rec in all_funcs[:100]:
            fid = fn_rec['id']

            place = fn_rec.get('place')
            assert isinstance(place, dict), \
                f'func_id={fid} place 应为 dict，实为 {type(place)}'
            for key in ('file_path', 'start_line', 'end_line'):
                assert key in place, \
                    f'func_id={fid} place 缺少字段 {key!r}'

            io = fn_rec.get('io')
            assert isinstance(io, dict), \
                f'func_id={fid} io 应为 dict，实为 {type(io)}'
            for key in ('params', 'returns'):
                assert key in io, \
                    f'func_id={fid} io 缺少字段 {key!r}'

            checked += 1

        _logger.info(f'断言通过：{checked} 条 func 记录的 place / io 字段均合法 ✓')

    def test_func_fk_correct(self, func_result, repo_id, db):
        """func.repo_id 与 file_id 外键正确（检查前 50 条）。"""
        all_funcs = FuncDB.list_by_repo(repo_id, db_path=db)
        for fn_rec in all_funcs[:50]:
            fid = fn_rec['id']
            assert fn_rec['repo_id'] == repo_id, \
                f'func_id={fid} repo_id={fn_rec["repo_id"]} ≠ {repo_id}'

            file_rec = FileDB.get_by_id(fn_rec['file_id'], db_path=db)
            assert file_rec is not None, \
                f'func_id={fid} 关联 file_id={fn_rec["file_id"]} 在 DB 中不存在'
            assert file_rec['repo_id'] == repo_id

        _logger.info('断言通过：外键 repo_id / file_id 均正确 ✓')

    # ------------------------------------------------------------------
    # file.funclist 一致性
    # ------------------------------------------------------------------

    def test_file_funclist_updated(self, func_result, repo_id, db):
        """
        每个含函数的文件，file.funclist 应已更新为 list，
        且长度与 func_result 对应列表一致；每项含 func_id / name / brief。
        """
        checked = 0
        for file_id, funcs in func_result.items():
            file_rec = FileDB.get_by_id(file_id, db_path=db)
            funclist = file_rec.get('funclist')

            assert isinstance(funclist, list), \
                f'file_id={file_id} funclist 应为 list，实为 {type(funclist)}'
            assert len(funclist) == len(funcs), (
                f'file_id={file_id} funclist 长度 {len(funclist)} '
                f'≠ 返回函数数 {len(funcs)}'
            )

            for idx, item in enumerate(funclist):
                for key in ('func_id', 'name', 'brief'):
                    assert key in item, \
                        f'file_id={file_id} funclist[{idx}] 缺少字段 {key!r}'

            checked += 1

        _logger.info(f'断言通过：{checked} 个文件的 funclist 均已正确更新 ✓')

    # ------------------------------------------------------------------
    # C 函数 io 字段质量（tree-sitter 专项）
    # ------------------------------------------------------------------

    def test_c_funcs_have_param_info(self, func_result, repo_id, db):
        """
        C 文件中，若函数签名含括号（非无参），params 列表不应全为空——
        至少 50% 的多参数函数有解析到参数信息。
        """
        all_files = FileDB.list_by_repo(repo_id, db_path=db)
        c_file_ids = {
            f['id'] for f in all_files
            if f.get('language') == 'C' and f['name'].endswith('.c')
        }

        multi_param_funcs = 0   # 应有参数
        with_params       = 0   # 实际有解析到参数

        for fid in c_file_ids:
            for fn in func_result.get(fid, []):
                fn_rec = FuncDB.get_by_id(fn['func_id'], db_path=db)
                if fn_rec is None:
                    continue
                io = fn_rec.get('io', {})
                if not isinstance(io, dict):
                    continue

                sig = fn_rec.get('signature', '')
                # 只统计签名里含参数的函数（排除 foo(void) 和 foo()）
                params_in_sig = sig.count(',') >= 1
                if not params_in_sig:
                    continue

                multi_param_funcs += 1
                if io.get('params'):
                    with_params += 1

        if multi_param_funcs > 0:
            ratio = with_params / multi_param_funcs
            assert ratio >= 0.5, (
                f'多参数 C 函数中仅 {with_params}/{multi_param_funcs} '
                f'解析到参数信息（{ratio:.0%}），期望 ≥ 50%'
            )
            _logger.info(
                f'断言通过：{with_params}/{multi_param_funcs} 个多参数 C 函数 '
                f'解析到 params（{ratio:.0%}）✓'
            )
        else:
            _logger.info('跳过：未找到多参数 C 函数（可能 tree-sitter 未安装）')

    # ------------------------------------------------------------------
    # force 参数行为
    # ------------------------------------------------------------------

    def test_force_false_raises(self, func_result, repo_id, db):
        """force=False（默认）时重复调用应抛出 ValueError。"""
        with pytest.raises(ValueError, match=r'已有.*func.*记录'):
            analyze_file_func(repo_id, db_path=db, force=False)

        _logger.info('断言通过：force=False 重复调用抛出 ValueError ✓')

    def test_force_true_reanalysis(self, func_result, repo_id, db):
        """
        force=True 时应允许重新提取：
          - 旧 func_id 被删除
          - 新结果非空
          - file.funclist 以新数据覆盖
        """
        old_ids = {
            fn['func_id']
            for fns in func_result.values()
            for fn in fns
        }
        _logger.info(f'旧 func_id 数量：{len(old_ids)}')

        new_result = analyze_file_func(repo_id, db_path=db, force=True)
        new_total  = sum(len(v) for v in new_result.values())

        assert isinstance(new_result, dict) and new_total > 0

        # 旧 func_id 应已不存在
        for old_id in list(old_ids)[:20]:   # 抽检前 20 条
            assert FuncDB.get_by_id(old_id, db_path=db) is None, \
                f'旧 func_id={old_id} 在 force=True 后仍存在'

        # file.funclist 以新数据覆盖
        for file_id, new_funcs in new_result.items():
            rec      = FileDB.get_by_id(file_id, db_path=db)
            funclist = rec.get('funclist')
            assert isinstance(funclist, list) and len(funclist) == len(new_funcs)

        _log_db_func_stats(db, repo_id, 'force=True 重新提取后')
        _logger.info(
            f'断言通过：force=True 重新提取 {new_total} 个函数，'
            f'旧 {len(old_ids)} 条已清除 ✓'
        )

    # ------------------------------------------------------------------
    # languages 过滤参数
    # ------------------------------------------------------------------

    def test_languages_filter(self, func_result, repo_id, db):
        """
        languages=['C'] 时只处理 C 文件，返回的 file_id 均属于 C 文件。
        """
        all_files = FileDB.list_by_repo(repo_id, db_path=db)
        c_file_ids = {f['id'] for f in all_files if f.get('language') == 'C'}

        # force=True 避免与前一用例冲突
        result_c = analyze_file_func(
            repo_id, db_path=db,
            force=True,
            languages=['C'],
        )

        non_c_ids = set(result_c.keys()) - c_file_ids
        assert not non_c_ids, \
            f'语言过滤后结果中存在非 C 文件 id：{non_c_ids}'

        total = sum(len(v) for v in result_c.values())
        _logger.info(
            f'断言通过：languages=["C"] 过滤后，'
            f'仅包含 C 文件（{len(result_c)} 个，共 {total} 个函数）✓'
        )