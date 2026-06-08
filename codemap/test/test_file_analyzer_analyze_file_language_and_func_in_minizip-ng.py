"""
test/test_file_analyzer_analyze_file_language_and_func_in_minizip-ng.py
针对真实 minizip-ng 仓库的 analyze_file_language 和 analyze_file_func 集成测试

前置依赖（fixture 链自动保证执行顺序）：
  init_repo → analyze_repo_language → analyze_repo_area
  → analyze_area_file → analyze_file_language → analyze_file_func

仓库路径（相对 test/ 目录）  : ../../../repo_4_codemap/minizip-ng/
仓库路径（相对 codemap/ 目录）: ../../repo_4_codemap/minizip-ng/

运行：
    python -m pytest "test/test_file_analyzer_analyze_file_language_and_func_in_minizip-ng.py" -v -s

日志输出：
    test/log/minizip_ng_file_func_<YYYYMMDD_HHMMSS>.log

注意：
    文件名含连字符，pytest 通过路径收集，勿以 import 方式引用本模块。
    analyze_file_language 不依赖 LLM，基于扩展名推断，极快。
    analyze_file_func 依赖 ctags（若安装）或 LLM 兜底，
      处理大型 C 仓库可能耗时较长，请确保相关工具或网络可用。
    analyze_repo_area 依赖 LLM，需保证网络与 API 可用。
    force=False 为全部测试的唯一模式（断点续跑语义）。
"""

import json
import logging
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB, AreaDB, FileDB, FuncDB
from analyzer.repo_analyzer import init_repo, analyze_repo_language, analyze_repo_area
from analyzer.area_analyzer import analyze_area_file
from analyzer.file_analyzer import analyze_file_language, analyze_file_func
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
    在 test/log/ 创建 minizip_ng_file_func_<时间戳>.log。
    Logger 名 'minizip_ng_file_func_test'，幂等注册 Handler。
    """
    log_dir = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'minizip_ng_file_func_{ts}.log')

    logger = logging.getLogger('minizip_ng_file_func_test')
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
    logger.info('minizip-ng  analyze_file_language + analyze_file_func 集成测试开始')
    logger.info(f'仓库路径  : {_REPO_PATH}')
    logger.info(f'日志文件  : {log_file}')
    logger.info('=' * 68)
    return logger


_logger = _setup_logger()


# ==================================================================
#  核心日志工具 1：语言分布摘要
# ==================================================================

def _log_language_summary(lang_result: dict, label: str) -> None:
    """
    将 analyze_file_language 返回值（dict[file_id → lang]）
    按语言聚合统计，写入日志。
    """
    _logger.info('')
    _logger.info(f'┌── analyze_file_language 摘要 [{label}]')

    counter = Counter(lang_result.values())
    total   = len(lang_result)
    _logger.info(f'│  处理文件总数：{total}')
    _logger.info('│  语言分布（降序）：')
    for lang, cnt in counter.most_common():
        bar = '█' * min(cnt, 35)
        pct = cnt / total * 100 if total else 0
        _logger.info(f'│    {lang:<22s}: {cnt:4d}  ({pct:5.1f}%)  {bar}')

    _logger.info('└' + '─' * 60)


# ==================================================================
#  核心日志工具 2：func 提取结果摘要
# ==================================================================

def _log_func_summary(func_result: dict, label: str, top_n: int = 15) -> None:
    """
    将 analyze_file_func 返回值（dict[file_id → list[func_dict]]）
    按函数数量降序展示前 top_n 个含函数文件，及每个文件的前 4 个函数。
    """
    _logger.info('')
    _logger.info(f'┌── analyze_file_func 摘要 [{label}]')

    total_files = len(func_result)
    total_funcs = sum(len(v) for v in func_result.values())
    nonempty    = sum(1 for v in func_result.values() if v)

    _logger.info(
        f'│  文件总数：{total_files}  含函数文件：{nonempty}  函数总数：{total_funcs}'
    )
    _logger.info(f'│')
    _logger.info(f'│  函数最多的 Top {top_n} 个文件：')

    sorted_items = sorted(func_result.items(), key=lambda kv: -len(kv[1]))
    for fid, funcs in sorted_items[:top_n]:
        if not funcs:
            break
        _logger.info(f'│  file_id={fid:<4d}  函数数={len(funcs):>4d}')
        for f in funcs[:4]:
            _logger.info(
                f'│    [{f["func_id"]:>5}] {f["name"]:<38s}'
                f'行 {f["start_line"]:>4}-{f["end_line"]:<4}'
            )
        if len(funcs) > 4:
            _logger.info(f'│    ... (另有 {len(funcs) - 4} 个函数)')

    _logger.info('│')
    _logger.info(f'│  合计：{total_files} 个文件，{total_funcs} 个函数')
    _logger.info('└' + '─' * 60)


# ==================================================================
#  核心日志工具 3：area → file → func 三层 DB 结构快照
# ==================================================================

def _log_db_full_structure(db_path: str, repo_id: int, label: str,
                            max_areas: int = 6) -> None:
    """
    从 SQLite 直接读取 area → file → func 三层结构写入日志，
    展示前 max_areas 个 area，每 area 前 5 个文件，每文件前 3 个函数。
    """
    _logger.info('')
    _logger.info(f'┌── 数据库结构快照 [{label}]')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        total_areas = conn.execute(
            'SELECT COUNT(*) FROM area WHERE repo_id = ?', (repo_id,)
        ).fetchone()[0]
        total_files = conn.execute(
            'SELECT COUNT(*) FROM file WHERE repo_id = ?', (repo_id,)
        ).fetchone()[0]
        total_funcs = conn.execute(
            'SELECT COUNT(*) FROM func WHERE repo_id = ?', (repo_id,)
        ).fetchone()[0]

        _logger.info(
            f'│  repo_id={repo_id}  area数={total_areas}  '
            f'file总数={total_files}  func总数={total_funcs}'
        )
        _logger.info('│')

        area_rows = conn.execute(
            'SELECT * FROM area WHERE repo_id = ? ORDER BY path LIMIT ?',
            (repo_id, max_areas),
        ).fetchall()

        for ai, area_row in enumerate(area_rows):
            ad      = dict(area_row)
            area_id = ad['id']
            is_last = (ai == len(area_rows) - 1 and total_areas <= max_areas)
            a_conn  = '└─' if is_last else '├─'
            a_pfx   = '   ' if is_last else '│  '

            file_total   = conn.execute(
                'SELECT COUNT(*) FROM file WHERE area_id = ?', (area_id,)
            ).fetchone()[0]
            func_in_area = conn.execute(
                'SELECT COUNT(*) FROM func WHERE area_id = ?', (area_id,)
            ).fetchone()[0]

            _logger.info(
                f'│  {a_conn} area [{area_id:>3}] {ad["name"]!r:<26s}'
                f'path={ad["path"]!r:<20s}  '
                f'文件={file_total}  函数={func_in_area}'
            )

            file_rows = conn.execute(
                'SELECT * FROM file WHERE area_id = ? ORDER BY name LIMIT 5',
                (area_id,),
            ).fetchall()

            for fi, file_row in enumerate(file_rows):
                fd      = dict(file_row)
                fid_val = fd['id']
                is_last_f = (fi == len(file_rows) - 1 and file_total <= 5)
                f_conn  = '└── ' if is_last_f else '├── '
                f_pfx   = '    ' if is_last_f else '│   '
                lang    = fd.get('language') or '—'
                func_cnt = conn.execute(
                    'SELECT COUNT(*) FROM func WHERE file_id = ?', (fid_val,)
                ).fetchone()[0]

                _logger.info(
                    f'│  {a_pfx}  {f_conn}'
                    f'[{fid_val:>4}] {fd["name"]:<34s}'
                    f'lang={lang:<10s}  func={func_cnt}'
                )

                func_rows = conn.execute(
                    'SELECT id, name, place FROM func '
                    'WHERE file_id = ? ORDER BY name LIMIT 3',
                    (fid_val,),
                ).fetchall()
                for fr in func_rows:
                    frd       = dict(fr)
                    place_str = ''
                    if frd.get('place'):
                        try:
                            pl = json.loads(frd['place'])
                            place_str = (
                                f" @行{pl.get('start_line','?')}"
                                f"-{pl.get('end_line','?')}"
                            )
                        except Exception:
                            pass
                    _logger.info(
                        f'│  {a_pfx}  {f_pfx}   '
                        f'func [{frd["id"]:>5}] {frd["name"]}{place_str}'
                    )
                if func_cnt > 3:
                    _logger.info(
                        f'│  {a_pfx}  {f_pfx}   '
                        f'... (另有 {func_cnt - 3} 个函数)'
                    )

            if file_total > 5:
                _logger.info(
                    f'│  {a_pfx}  ... (该 area 另有 {file_total - 5} 个文件)'
                )

        if total_areas > max_areas:
            _logger.info(
                f'│  ... (共 {total_areas} 个 area，仅展示前 {max_areas} 个)'
            )

        conn.close()

    except Exception as exc:
        _logger.warning(f'│  读取数据库失败：{exc}')

    _logger.info('└' + '─' * 60)


# ==================================================================
#  Fixtures
# ==================================================================

@pytest.fixture(scope='module')
def db(tmp_path_factory):
    """模块级临时数据库，整个测试文件共享，保证用例间状态连续。"""
    db_file = str(tmp_path_factory.mktemp('minizip_ng_func') / 'codemap.db')
    _logger.info(f'[db] 创建临时数据库 → {db_file}')
    init_db(db_file)
    _logger.info('[db] 表结构初始化完成')
    return db_file


@pytest.fixture(scope='module')
def repo_id(db):
    """模块级：调用 init_repo()，返回 repo_id。"""
    _logger.info('')
    _logger.info('── 前置步骤 [1/4]：init_repo ──────────────────────────')
    rid = init_repo(_REPO_PATH, db_path=db)
    _logger.info(f'init_repo 完成，repo_id = {rid}')
    return rid


@pytest.fixture(scope='module')
def language_ready(repo_id, db):
    """模块级：analyze_repo_language，填充 repo.language（analyze_repo_area 需用主语言）。"""
    _logger.info('')
    _logger.info('── 前置步骤 [2/4]：analyze_repo_language ──────────────')
    result = analyze_repo_language(repo_id, db_path=db)
    _logger.info(
        f'analyze_repo_language 完成 | '
        f'主语言：{result.get("main")} | '
        f'语言数：{len(result.get("stats", []))}'
    )
    return result


@pytest.fixture(scope='module')
def area_ready(language_ready, repo_id, db):
    """模块级：analyze_repo_area（LLM 调用），建立 area 层级。"""
    _logger.info('')
    _logger.info('── 前置步骤 [3/4]：analyze_repo_area ──────────────────')
    result = analyze_repo_area(repo_id, db_path=db)
    _logger.info(f'analyze_repo_area 完成，共 {len(result)} 个 area')
    for a in result:
        _logger.info(
            f'  [{a["area_id"]:>3}] {a["name"]!r:<30s}  path={a["path"]!r}'
        )
    return result


@pytest.fixture(scope='module')
def file_ready(area_ready, repo_id, db):
    """模块级：analyze_area_file，扫描并建立 file 层级（纯磁盘操作）。"""
    _logger.info('')
    _logger.info('── 前置步骤 [4/4]：analyze_area_file ──────────────────')
    result = analyze_area_file(repo_id, db_path=db)
    total  = sum(len(v) for v in result.values())
    _logger.info(
        f'analyze_area_file 完成 | '
        f'{len(result)} 个 area | {total} 个文件'
    )
    return result


@pytest.fixture(scope='module')
def lang_result(file_ready, repo_id, db):
    """
    模块级：调用 analyze_file_language()，写入 file.language。
    返回 dict[file_id → language]，供 TestAnalyzeFileLanguage 全部用例复用。
    """
    _logger.info('')
    _logger.info('── analyze_file_language ─────────────────────────────────')
    _logger.info(f'调用 analyze_file_language(repo_id={repo_id})')

    result = analyze_file_language(repo_id, db_path=db)

    _logger.info(f'analyze_file_language 完成，共处理 {len(result)} 个文件')
    _log_language_summary(result, label='analyze_file_language 完成后')
    return result


@pytest.fixture(scope='module')
def func_result(lang_result, repo_id, db):
    """
    模块级：调用 analyze_file_func()，写入 func 表并更新 file.funclist。
    返回 dict[file_id → list[func_dict]]，供 TestAnalyzeFileFunc 全部用例复用。

    注意：此步骤可能耗时较长（取决于 ctags/LLM 可用性与文件数量）。
    minizip-ng 以 C 为主，ctags 可用时较快；否则走 LLM 逐文件分析。
    """
    _logger.info('')
    _logger.info('── analyze_file_func ─────────────────────────────────────')
    _logger.info(f'调用 analyze_file_func(repo_id={repo_id}, force=False)')

    result = analyze_file_func(repo_id, db_path=db, force=False)

    total_funcs = sum(len(v) for v in result.values())
    _logger.info(
        f'analyze_file_func 完成 | '
        f'{len(result)} 个文件 | {total_funcs} 个函数'
    )

    _log_func_summary(result, label='analyze_file_func 完成后')
    _log_db_full_structure(db, repo_id, label='analyze_file_func 完成后')
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
#  TestAnalyzeFileLanguage
# ==================================================================

class TestAnalyzeFileLanguage:
    """
    针对 analyze_file_language 的功能测试。
    该函数基于文件扩展名推断语言，不依赖 LLM，速度极快。
    """

    def test_return_type_and_size_matches_files(self, lang_result, file_ready):
        """
        返回值为 dict，且键数（file_id 数量）与 analyze_area_file
        扫描到的文件总数严格相等。
        """
        total_files = sum(len(v) for v in file_ready.values())
        assert isinstance(lang_result, dict), \
            f'返回值应为 dict，实际类型：{type(lang_result).__name__}'
        assert len(lang_result) == total_files, \
            (f'lang_result 键数（{len(lang_result)}）'
             f'应与文件总数（{total_files}）一致')
        _logger.info(
            f'断言通过：返回 dict，{len(lang_result)} 个 file_id == '
            f'文件总数 {total_files} ✓'
        )

    def test_all_values_are_nonempty_strings(self, lang_result):
        """
        所有 language 值为非空字符串（如 "C" / "CMake" / "Unknown"），
        确保未出现 None 或空串写入 DB。
        """
        bad = [
            (fid, lang)
            for fid, lang in lang_result.items()
            if not (isinstance(lang, str) and lang.strip())
        ]
        assert not bad, \
            f'以下 file_id 的 language 值不合法：{bad[:10]}'
        _logger.info(
            f'断言通过：{len(lang_result)} 个文件的 language 值均为非空字符串 ✓'
        )

    def test_c_source_files_identified_as_c(self, lang_result, repo_id, db):
        """
        .c 扩展名文件应被识别为 "C"。
        minizip-ng 为 C 仓库，此项是核心正确性验证。
        """
        files   = FileDB.list_by_repo(repo_id, db_path=db)
        c_files = [f for f in files if f['name'].lower().endswith('.c')]
        assert c_files, 'minizip-ng 应包含 .c 文件，但未找到'

        wrong = [
            (f['id'], f['name'], lang_result.get(f['id']))
            for f in c_files
            if lang_result.get(f['id']) != 'C'
        ]
        assert not wrong, \
            (f'.c 文件被误判（共 {len(wrong)} 个）：'
             f'{[(n, l) for _, n, l in wrong[:5]]}')

        _logger.info(f'断言通过：{len(c_files)} 个 .c 文件均识别为 "C" ✓')

    def test_h_header_files_identified_as_c(self, lang_result, repo_id, db):
        """
        .h 扩展名文件（C 头文件）应被识别为 "C"。
        """
        files   = FileDB.list_by_repo(repo_id, db_path=db)
        h_files = [f for f in files if f['name'].lower().endswith('.h')]
        if not h_files:
            _logger.info('仓库中无 .h 文件，跳过此检查')
            return

        wrong = [
            (f['id'], f['name'], lang_result.get(f['id']))
            for f in h_files
            if lang_result.get(f['id']) != 'C'
        ]
        assert not wrong, \
            (f'.h 文件被误判（共 {len(wrong)} 个）：'
             f'{[(n, l) for _, n, l in wrong[:5]]}')

        _logger.info(f'断言通过：{len(h_files)} 个 .h 文件均识别为 "C" ✓')

    def test_db_file_language_field_updated(self, lang_result, repo_id, db):
        """
        DB file 表的 language 字段应被正确写入，
        且与 analyze_file_language 的返回值一一对应，不存在遗漏或错误。
        """
        files   = FileDB.list_by_repo(repo_id, db_path=db)
        checked = 0
        for f in files:
            fid      = f['id']
            db_lang  = f.get('language')
            ret_lang = lang_result.get(fid)

            assert db_lang is not None and db_lang.strip(), \
                f'file_id={fid}（{f["name"]}）DB language 字段未更新（为 None 或空）'
            assert db_lang == ret_lang, \
                (f'file_id={fid} DB language（{db_lang!r}）'
                 f'与返回值（{ret_lang!r}）不一致')
            checked += 1

        _logger.info(f'断言通过：DB 中 {checked} 个 file.language 字段均正确更新 ✓')

    def test_c_dominates_language_distribution(self, lang_result):
        """
        minizip-ng 以 C 为主，C 类文件占比应超过 30%，
        用于整体验证语言检测结果符合仓库特征。
        """
        counter = Counter(lang_result.values())
        total   = len(lang_result)
        c_cnt   = counter.get('C', 0)
        c_ratio = c_cnt / total if total else 0.0

        assert c_ratio > 0.3, \
            (f'minizip-ng 的 C 文件占比（{c_ratio:.1%}）应 > 30%，'
             f'实际 C 文件数 {c_cnt}/{total}')

        _logger.info(
            f'断言通过：C 文件 {c_cnt}/{total} = {c_ratio:.1%}（> 30%） ✓'
        )
        _logger.info('  完整语言分布：')
        for lang, cnt in counter.most_common():
            _logger.info(f'    {lang:<22s}: {cnt}')


# ==================================================================
#  TestAnalyzeFileFunc
# ==================================================================

class TestAnalyzeFileFunc:
    """
    针对 analyze_file_func 的功能测试。
    函数提取按优先级：Python ast → ctags → LLM 兜底。
    """

    # ------------------------------------------------------------------
    # 返回值结构
    # ------------------------------------------------------------------

    def test_return_type_and_total_funcs_nonzero(self, func_result, file_ready):
        """
        返回值为 dict，键数与文件总数一致，
        全局函数总数 > 0（minizip-ng 为 C 仓库，含大量函数定义）。
        """
        total_files = sum(len(v) for v in file_ready.values())
        assert isinstance(func_result, dict), \
            f'返回值应为 dict，实际：{type(func_result).__name__}'
        assert len(func_result) == total_files, \
            (f'返回 dict 键数（{len(func_result)}）'
             f'与文件总数（{total_files}）不一致')

        total_funcs = sum(len(v) for v in func_result.values())
        assert total_funcs > 0, \
            'minizip-ng 应提取到函数定义，但函数总数为 0（检查 ctags/LLM 是否正常）'

        _logger.info(
            f'断言通过：{len(func_result)} 个文件，{total_funcs} 个函数 ✓'
        )

    def test_each_func_entry_has_required_fields(self, func_result):
        """
        每个 func 条目应包含 func_id / name / start_line / end_line，
        且 func_id 为正整数，name 为非空字符串。
        """
        required = {'func_id', 'name', 'start_line', 'end_line'}
        checked  = 0

        for fid, funcs in func_result.items():
            for idx, func in enumerate(funcs):
                missing = required - set(func.keys())
                assert not missing, \
                    f'file_id={fid} func[{idx}] 缺少字段：{missing}'
                assert isinstance(func['func_id'], int) and func['func_id'] > 0, \
                    (f'file_id={fid} func[{idx}].func_id 应为正整数，'
                     f'实际：{func["func_id"]!r}')
                assert str(func.get('name', '')).strip(), \
                    f'file_id={fid} func[{idx}].name 不应为空字符串'
                checked += 1

        _logger.info(f'断言通过：{checked} 个 func 条目字段均完整、合法 ✓')

    def test_no_duplicate_func_ids_globally(self, func_result):
        """
        全局范围内 func_id 不重复，确保每条 func 记录唯一入库。
        """
        all_ids = [
            func['func_id']
            for funcs in func_result.values()
            for func in funcs
        ]
        dup_ids = [x for x in set(all_ids) if all_ids.count(x) > 1]
        assert not dup_ids, \
            f'存在重复 func_id（共 {len(dup_ids)} 个）：{dup_ids[:10]}'

        _logger.info(f'断言通过：{len(all_ids)} 个 func_id 全局无重复 ✓')

    def test_line_numbers_valid(self, func_result):
        """
        每个函数行号应满足：start_line ≥ 1，end_line ≥ start_line，
        且不超过 100,000（合理上限，排除解析错误导致的异常大值）。
        """
        bad: list[str] = []
        for fid, funcs in func_result.items():
            for func in funcs:
                s    = func.get('start_line', -1)
                e    = func.get('end_line',   -1)
                name = func.get('name', '?')
                if s < 1:
                    bad.append(
                        f'file_id={fid} func={name!r} start_line={s} < 1'
                    )
                elif e < s:
                    bad.append(
                        f'file_id={fid} func={name!r} end({e}) < start({s})'
                    )
                elif e > 100_000:
                    bad.append(
                        f'file_id={fid} func={name!r} end_line={e} 超出上限'
                    )

        assert not bad, \
            f'行号异常（共 {len(bad)} 处）：\n' + '\n'.join(bad[:10])

        total = sum(len(v) for v in func_result.values())
        _logger.info(f'断言通过：{total} 个函数行号均合法 ✓')

    def test_c_source_files_contain_functions(self, func_result, repo_id, db):
        """
        .c 源文件中至少 60% 应提取到函数，
        确保函数提取策略对 minizip-ng 的核心 C 代码生效。
        """
        files   = FileDB.list_by_repo(repo_id, db_path=db)
        c_files = [f for f in files if f['name'].lower().endswith('.c')]
        if not c_files:
            _logger.info('无 .c 文件，跳过')
            return

        with_funcs = [f for f in c_files if func_result.get(f['id'])]
        ratio      = len(with_funcs) / len(c_files)

        assert ratio >= 0.6, \
            (f'至少 60% 的 .c 文件应有函数，'
             f'实际：{len(with_funcs)}/{len(c_files)} = {ratio:.1%}')

        _logger.info(
            f'断言通过：{len(with_funcs)}/{len(c_files)} 个 .c 文件含函数'
            f'（{ratio:.1%} ≥ 60%） ✓'
        )

    # ------------------------------------------------------------------
    # 数据库一致性
    # ------------------------------------------------------------------

    def test_db_func_count_matches_return(self, func_result, repo_id, db):
        """
        DB func 表属于 repo_id 的记录总数应与返回值函数总数完全一致。
        """
        db_funcs     = FuncDB.list_by_repo(repo_id, db_path=db)
        return_total = sum(len(v) for v in func_result.values())

        assert len(db_funcs) == return_total, \
            (f'DB func 记录数（{len(db_funcs)}）'
             f'与返回函数总数（{return_total}）不一致')

        _logger.info(
            f'断言通过：DB func 表 {len(db_funcs)} 条记录 == 返回总数 ✓'
        )

    def test_db_func_name_matches_return(self, func_result, repo_id, db):
        """
        每个返回的 func_id 在 DB 中存在，且 name 字段与返回值完全吻合。
        """
        for fid, funcs in func_result.items():
            for func in funcs:
                record = FuncDB.get_by_id(func['func_id'], db_path=db)
                assert record is not None, \
                    f'func_id={func["func_id"]} 在 DB 中找不到记录'
                assert record['name'] == func['name'], \
                    (f'func_id={func["func_id"]} name 不一致：'
                     f'DB={record["name"]!r} / 返回={func["name"]!r}')

        total = sum(len(v) for v in func_result.values())
        _logger.info(f'断言通过：{total} 个 func 的 name 与 DB 记录完全吻合 ✓')

    def test_db_func_foreign_keys_correct(self, func_result, repo_id, db):
        """
        DB 每条 func 记录的 repo_id / file_id 外键应与返回值中的 key 对应一致。
        """
        for fid, funcs in func_result.items():
            for func in funcs:
                record = FuncDB.get_by_id(func['func_id'], db_path=db)
                assert record['repo_id'] == repo_id, \
                    (f'func_id={func["func_id"]} repo_id 错误：'
                     f'DB={record["repo_id"]} / 期望={repo_id}')
                assert record['file_id'] == fid, \
                    (f'func_id={func["func_id"]} file_id 错误：'
                     f'DB={record["file_id"]} / 期望={fid}')

        _logger.info('断言通过：所有 func 记录的 repo_id / file_id 外键正确 ✓')

    def test_db_func_place_field_structure(self, func_result, repo_id, db):
        """
        DB 每条 func 记录的 place 字段（经 dao 反序列化后）应为包含
        file_path / start_line / end_line 的 dict，且行号类型为 int。
        place=None 的条目发出警告但不导致失败（兜底场景）。
        """
        checked  = 0
        none_cnt = 0

        for fid, funcs in func_result.items():
            for func in funcs:
                record = FuncDB.get_by_id(func['func_id'], db_path=db)
                place  = record.get('place')
                if place is None:
                    none_cnt += 1
                    continue

                assert isinstance(place, dict), \
                    (f'func_id={func["func_id"]} place 应为 dict，'
                     f'实际：{type(place).__name__}')
                for key in ('file_path', 'start_line', 'end_line'):
                    assert key in place, \
                        (f'func_id={func["func_id"]} place 缺少字段 {key!r}，'
                         f'实际键：{list(place.keys())}')
                assert isinstance(place['start_line'], int), \
                    f'func_id={func["func_id"]} place.start_line 应为 int'
                checked += 1

        if none_cnt:
            _logger.warning(f'  {none_cnt} 个 func 的 place 字段为 None（已跳过检查）')
        _logger.info(f'断言通过：{checked} 个 func 的 place 字段结构正确 ✓')

    def test_db_func_io_field_structure(self, func_result, repo_id, db):
        """
        DB 每条 func 记录的 io 字段（若非 None）应包含：
          params（list）和 returns（含 type 键的 dict）两个子字段，
        确保 io 数据结构对齐 schema 设计。
        """
        checked  = 0
        none_cnt = 0

        for fid, funcs in func_result.items():
            for func in funcs:
                record = FuncDB.get_by_id(func['func_id'], db_path=db)
                io     = record.get('io')
                if io is None:
                    none_cnt += 1
                    continue

                assert isinstance(io, dict), \
                    (f'func_id={func["func_id"]} io 应为 dict，'
                     f'实际：{type(io).__name__}')
                assert 'params' in io, \
                    f'func_id={func["func_id"]} io 缺少 params 字段'
                assert 'returns' in io, \
                    f'func_id={func["func_id"]} io 缺少 returns 字段'
                assert isinstance(io['params'], list), \
                    f'func_id={func["func_id"]} io.params 应为 list'
                assert isinstance(io['returns'], dict), \
                    f'func_id={func["func_id"]} io.returns 应为 dict'
                assert 'type' in io['returns'], \
                    (f'func_id={func["func_id"]} io.returns 缺少 type 字段，'
                     f'实际：{io["returns"]}')
                checked += 1

        if none_cnt:
            _logger.warning(f'  {none_cnt} 个 func 的 io 字段为 None（已跳过检查）')
        _logger.info(f'断言通过：{checked} 个 func 的 io 字段结构正确 ✓')

    def test_file_funclist_field_updated(self, func_result, repo_id, db):
        """
        每个 file 的 funclist 字段应被正确更新：
          - 反序列化为 list
          - 长度与 func_result 对应文件的函数数一致
          - 每项含 func_id / name / brief 三个字段
        """
        checked = 0
        for fid, funcs in func_result.items():
            file_rec = FileDB.get_by_id(fid, db_path=db)
            funclist = file_rec.get('funclist')

            assert isinstance(funclist, list), \
                (f'file_id={fid} funclist 应反序列化为 list，'
                 f'实际类型：'
                 f'{type(funclist).__name__ if funclist is not None else "None"}')
            assert len(funclist) == len(funcs), \
                (f'file_id={fid} funclist 长度（{len(funclist)}）'
                 f'与返回函数数（{len(funcs)}）不一致')

            for idx, item in enumerate(funclist):
                for key in ('func_id', 'name', 'brief'):
                    assert key in item, \
                        (f'file_id={fid} funclist[{idx}] 缺少字段 {key!r}，'
                         f'实际：{item}')
            checked += 1

        _logger.info(f'断言通过：{checked} 个 file 的 funclist 均已正确更新 ✓')

    # ------------------------------------------------------------------
    # force=False 行为验证（断点续跑）
    # ------------------------------------------------------------------

    def test_force_false_skips_existing_records_consistently(
        self, func_result, repo_id, db
    ):
        """
        func 记录已存在时，force=False（默认值）再次调用应：
          ① 不抛出任何异常（断点续跑，跳过已有记录）
          ② 返回函数总数与首次调用一致
          ③ DB 中 func 总数保持不变（不重复写入）

        此用例验证断点续跑语义，确保幂等性。
        """
        _logger.info('── force=False 重复调用验证（断点续跑）──────────────')

        first_total     = sum(len(v) for v in func_result.values())
        db_cnt_before   = len(FuncDB.list_by_repo(repo_id, db_path=db))

        # 第二次调用，force=False（默认），不应抛异常
        second_result  = analyze_file_func(repo_id, db_path=db, force=False)
        second_total   = sum(len(v) for v in second_result.values())
        db_cnt_after   = len(FuncDB.list_by_repo(repo_id, db_path=db))

        assert isinstance(second_result, dict), \
            f'第二次调用返回值应为 dict，实际：{type(second_result).__name__}'
        assert second_total == first_total, \
            (f'force=False 重复调用后函数总数（{second_total}）'
             f'应与首次（{first_total}）一致')
        assert db_cnt_after == db_cnt_before, \
            (f'force=False 后 DB func 总数从 {db_cnt_before} → {db_cnt_after}，'
             f'应保持不变（断点续跑不重复写入）')

        _logger.info(
            f'断言通过：force=False 重复调用不抛异常，'
            f'函数总数保持 {first_total}，'
            f'DB 记录数保持 {db_cnt_before} ✓'
        )