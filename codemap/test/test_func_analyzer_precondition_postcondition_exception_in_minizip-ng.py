"""
test/test_func_analyzer_precondition_postcondition_exception_in_minizip-ng.py
针对 minizip-ng 的 analyze_func_precondition/postcondition/exception 集成测试

前置 fixture 链（模块级串行）：
  init_repo → analyze_repo_language → analyze_repo_area
    → analyze_area_file → analyze_file_language → analyze_file_func
      → build_callgraph → analyze_func_callgraph
        → [precondition / postcondition / exception]  ← Step 7

为加快测试速度，Step 7 只处理 C 语言文件中的前 N_SAMPLE 个函数，
其余函数的 step-7 字段保持 NULL，不影响后续步骤的增量补全。

运行：
    python -m pytest "test/test_func_analyzer_precondition_postcondition_exception_in_minizip-ng.py" -v -s

日志：
    test/log/minizip_ng_step7_<YYYYMMDD_HHMMSS>.log
数据库：
    data/test_db/db_minizip-ng_step7_<YYYYMMDD_HHMM>.db
"""

import json
import logging
import os
import sys
import re
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, FuncDB, FileDB
from analyzer.repo_analyzer     import init_repo, analyze_repo_language, analyze_repo_area
from analyzer.area_analyzer     import analyze_area_file
from analyzer.file_analyzer     import analyze_file_language, analyze_file_func
from analyzer.callgraph_builder import build_callgraph, analyze_func_callgraph
from analyzer.func_analyzer     import (
    analyze_func_precondition,
    analyze_func_postcondition,
    analyze_func_exception,
)
from config import DATA_DIR

# ==================================================================
# 常量
# ==================================================================

_REPO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../../repo_4_codemap/minizip-ng')
)

# 每种分析最多处理的函数数（控制测试时长）
N_SAMPLE = 15

pytestmark = pytest.mark.skipif(
    not os.path.isdir(_REPO_PATH),
    reason=f'minizip-ng 仓库未找到，跳过：{_REPO_PATH}',
)


# ==================================================================
# 日志
# ==================================================================

def _setup_logger() -> logging.Logger:
    log_dir  = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'minizip_ng_step7_{ts}.log')

    logger = logging.getLogger('minizip_ng_step7')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(logging.Formatter(
            '%(asctime)s  %(levelname)-7s  %(message)s', datefmt='%H:%M:%S'
        ))
        logger.addHandler(fh)

    logger.info('=' * 70)
    logger.info('minizip-ng Step 7 集成测试')
    logger.info(f'仓库   : {_REPO_PATH}')
    logger.info(f'日志   : {log_file}')
    logger.info(f'样本量 : 每类 {N_SAMPLE} 个函数')
    logger.info('=' * 70)
    return logger


_log = _setup_logger()


# ==================================================================
# 日志辅助：打印字段抽样
# ==================================================================

def _log_field_sample(
    results: dict[int, list[str]],
    field_name: str,
    n: int = 10,
) -> None:
    _log.info(f'')
    _log.info(f'┌── {field_name} 结果抽样（前 {n} 个有数据的函数）')
    shown = 0
    for fid, items in results.items():
        if not items:
            continue
        _log.info(f'│  func_id={fid}  共 {len(items)} 条')
        for i, item in enumerate(items, 1):
            _log.info(f'│    [{i}] {item}')
        shown += 1
        if shown >= n:
            break
    if shown == 0:
        _log.info('│  （所有函数均无数据）')
    _log.info('└' + '─' * 62)


# ==================================================================
# Fixtures（模块级）
# ==================================================================

@pytest.fixture(scope='module')
def db():
    ts       = datetime.now().strftime('%Y%m%d_%H%M')
    db_dir   = os.path.join(DATA_DIR, 'test_db')
    os.makedirs(db_dir, exist_ok=True)
    db_file  = os.path.join(db_dir, f'db_minizip-ng_step7_{ts}.db')
    init_db(db_file)
    _log.info(f'[db] {db_file}')
    return db_file


@pytest.fixture(scope='module')
def repo_id(db):
    _log.info('── 前置 [1/8] init_repo')
    rid = init_repo(_REPO_PATH, db_path=db)
    _log.info(f'repo_id = {rid}')
    return rid


@pytest.fixture(scope='module')
def language_ready(repo_id, db):
    _log.info('── 前置 [2/8] analyze_repo_language')
    r = analyze_repo_language(repo_id, db_path=db)
    _log.info(f'主语言：{r.get("main")}')
    return r


@pytest.fixture(scope='module')
def area_ready(language_ready, repo_id, db):
    _log.info('── 前置 [3/8] analyze_repo_area（LLM）')
    r = analyze_repo_area(repo_id, db_path=db)
    _log.info(f'area 数：{len(r)}')
    return r


@pytest.fixture(scope='module')
def file_ready(area_ready, repo_id, db):
    _log.info('── 前置 [4/8] analyze_area_file')
    r = analyze_area_file(repo_id, db_path=db)
    _log.info(f'file 数：{sum(len(v) for v in r.values())}')
    return r


@pytest.fixture(scope='module')
def func_ready(file_ready, repo_id, db):
    _log.info('── 前置 [5/8] analyze_file_language + analyze_file_func')
    analyze_file_language(repo_id, db_path=db)
    r = analyze_file_func(repo_id, db_path=db)
    _log.info(f'func 数：{sum(len(v) for v in r.values())}')
    return r


@pytest.fixture(scope='module')
def cg_ready(func_ready, repo_id, db):
    _log.info('── 前置 [6/8] build_callgraph')
    path = build_callgraph(repo_id, db_path=db)
    _log.info(f'调用图：{path}')
    return path


@pytest.fixture(scope='module')
def cg_analyzed(cg_ready, repo_id, db):
    _log.info('── 前置 [7/8] analyze_func_callgraph')
    r = analyze_func_callgraph(repo_id, db_path=db, callgraph_path=cg_ready)
    _log.info(f'callgraph 写库：{len(r)} 个函数')
    return r


@pytest.fixture(scope='module')
def sample_c_func_ids(cg_analyzed, repo_id, db) -> list[int]:
    """
    取 N_SAMPLE 个 C 语言、有 callgraph 数据的函数 id 作为测试样本。
    选取标准：有 callee（有实际调用，更有分析价值）。
    """
    all_files = FileDB.list_by_repo(repo_id, db_path=db)
    c_file_ids = {f['id'] for f in all_files if f.get('language') == 'C'}

    all_funcs = FuncDB.list_by_repo(repo_id, db_path=db)

    # 优先有 callee 的函数
    candidates = [
        f for f in all_funcs
        if f.get('file_id') in c_file_ids
        and isinstance(f.get('callgraph'), dict)
        and f['callgraph'].get('callees')
    ]

    # 补充无 callee 的函数以凑够样本
    if len(candidates) < N_SAMPLE:
        extra = [
            f for f in all_funcs
            if f.get('file_id') in c_file_ids
            and f['id'] not in {c['id'] for c in candidates}
        ]
        candidates += extra

    ids = [f['id'] for f in candidates[:N_SAMPLE]]
    _log.info(f'[sample_c_func_ids] 选取 {len(ids)} 个 C 函数：{ids}')
    return ids


# ── Step 7 fixtures ─────────────────────────────────────────────

@pytest.fixture(scope='module')
def precond_results(cg_analyzed, sample_c_func_ids, repo_id, db):
    _log.info('── Step 7a analyze_func_precondition')
    r = analyze_func_precondition(
        repo_id, db_path=db, func_ids=sample_c_func_ids, skip_if_exists=False
    )
    _log.info(f'写库：{len(r)} 个函数')
    _log_field_sample(r, 'precondition')
    return r


@pytest.fixture(scope='module')
def postcond_results(precond_results, sample_c_func_ids, repo_id, db):
    _log.info('── Step 7b analyze_func_postcondition')
    r = analyze_func_postcondition(
        repo_id, db_path=db, func_ids=sample_c_func_ids, skip_if_exists=False
    )
    _log.info(f'写库：{len(r)} 个函数')
    _log_field_sample(r, 'postcondition')
    return r


@pytest.fixture(scope='module')
def exception_results(postcond_results, sample_c_func_ids, repo_id, db):
    _log.info('── Step 7c analyze_func_exception')
    r = analyze_func_exception(
        repo_id, db_path=db, func_ids=sample_c_func_ids, skip_if_exists=False
    )
    _log.info(f'写库：{len(r)} 个函数')
    _log_field_sample(r, 'exception')
    return r


@pytest.fixture(autouse=True)
def _log_case(request):
    _log.info(f'')
    _log.info(f'─' * 70)
    _log.info(f'▶ {request.node.name}')
    yield
    _log.info(f'◀ {request.node.name}  完成')


# ==================================================================
# 测试：analyze_func_precondition
# ==================================================================

class TestPrecondition:

    def test_returns_dict_with_func_ids(self, precond_results, sample_c_func_ids):
        """返回值是 dict，键为所有传入的 func_id。"""
        assert isinstance(precond_results, dict)
        for fid in sample_c_func_ids:
            assert fid in precond_results, f'func_id={fid} 不在返回结果中'
        _log.info(f'✓ 返回 dict 覆盖所有 {len(sample_c_func_ids)} 个样本 func_id')

    def test_values_are_string_lists(self, precond_results):
        """每个值必须是字符串列表。"""
        for fid, items in precond_results.items():
            assert isinstance(items, list), \
                f'func_id={fid} 的值类型应为 list，实为 {type(items)}'
            for item in items:
                assert isinstance(item, str) and item.strip(), \
                    f'func_id={fid} 含空/非字符串条目：{item!r}'
        _log.info('✓ 所有值均为非空字符串列表')

    def test_at_least_some_funcs_have_preconditions(self, precond_results):
        """
        样本中至少 30% 的函数应有前置条件（minizip-ng 大量函数有 NULL 参数检查）。
        """
        nonempty = sum(1 for v in precond_results.values() if v)
        ratio    = nonempty / len(precond_results) if precond_results else 0
        assert ratio >= 0.30, (
            f'仅 {nonempty}/{len(precond_results)} 个函数有前置条件（{ratio:.0%}），'
            '过低，SA 或 LLM 可能有问题'
        )
        _log.info(f'✓ {nonempty}/{len(precond_results)} 个函数有前置条件（{ratio:.0%}）')

    def test_items_not_too_long(self, precond_results):
        """每条条目不应超过 200 字（过长说明 LLM 输出格式有误）。"""
        for fid, items in precond_results.items():
            for item in items:
                assert len(item) <= 200, \
                    f'func_id={fid} 条目过长（{len(item)} 字）：{item[:80]}…'
        _log.info('✓ 所有条目长度 ≤ 200 字')

    def test_db_field_written(self, precond_results, db):
        """DB 中 func.precondition 字段应为 list（dao 层自动反序列化）。"""
        for fid in list(precond_results.keys())[:20]:
            rec = FuncDB.get_by_id(fid, db_path=db)
            assert rec is not None
            field = rec.get('precondition')
            assert isinstance(field, list), \
                f'func_id={fid} DB.precondition 应为 list，实为 {type(field)}'
        _log.info('✓ DB 字段 precondition 格式正确')

    def test_skip_if_exists_works(self, precond_results, sample_c_func_ids, repo_id, db):
        """
        skip_if_exists=True 时，再次运行对已有数据的函数应全部跳过，
        结果仍为 dict 但不重新写库（通过比对条数来验证）。
        """
        # 先记录已有条目数
        before = {
            fid: len(items)
            for fid, items in precond_results.items()
            if items
        }

        r2 = analyze_func_precondition(
            repo_id, db_path=db,
            func_ids=sample_c_func_ids,
            skip_if_exists=True,   # 应全部跳过
        )
        # skip_if_exists=True 时，已有数据的 func_id 不在返回字典中
        for fid in before:
            assert fid not in r2 or r2[fid] == [], \
                f'func_id={fid} 本应被跳过，但出现在结果中'
        _log.info(f'✓ skip_if_exists=True 正确跳过 {len(before)} 个已有数据的函数')


# ==================================================================
# 测试：analyze_func_postcondition
# ==================================================================

class TestPostcondition:

    def test_returns_dict_with_func_ids(self, postcond_results, sample_c_func_ids):
        assert isinstance(postcond_results, dict)
        for fid in sample_c_func_ids:
            assert fid in postcond_results
        _log.info(f'✓ 返回 dict 覆盖所有 {len(sample_c_func_ids)} 个样本 func_id')

    def test_values_are_string_lists(self, postcond_results):
        for fid, items in postcond_results.items():
            assert isinstance(items, list)
            for item in items:
                assert isinstance(item, str) and item.strip(), \
                    f'func_id={fid} 含空条目：{item!r}'
        _log.info('✓ 所有值均为非空字符串列表')

    def test_at_least_some_funcs_have_postconditions(self, postcond_results):
        """
        几乎所有有函数体的函数都应有后置条件（至少有返回值语义）。
        阈值设为 50%。
        """
        nonempty = sum(1 for v in postcond_results.values() if v)
        ratio    = nonempty / len(postcond_results) if postcond_results else 0
        assert ratio >= 0.50, (
            f'仅 {nonempty}/{len(postcond_results)} 个函数有后置条件（{ratio:.0%}），过低'
        )
        _log.info(f'✓ {nonempty}/{len(postcond_results)} 个函数有后置条件（{ratio:.0%}）')

    def test_db_field_written(self, postcond_results, db):
        for fid in list(postcond_results.keys())[:20]:
            rec = FuncDB.get_by_id(fid, db_path=db)
            assert rec is not None
            field = rec.get('postcondition')
            assert isinstance(field, list), \
                f'func_id={fid} DB.postcondition 类型错误：{type(field)}'
        _log.info('✓ DB 字段 postcondition 格式正确')

    def test_postcondition_covers_return_semantics(self, postcond_results):
        """
        至少一半的有数据函数的后置条件中，应提及"返回"相关信息，
        表明 LLM 正确分析了返回值语义。
        """
        nonempty_funcs = [items for items in postcond_results.values() if items]
        if not nonempty_funcs:
            pytest.skip('无后置条件数据，跳过语义校验')

        # 检查是否有关键词出现
        ret_keywords = re.compile(
            r'返回|return|成功|失败|Z_OK|错误码|结果|NULL|指针', re.I
        )
        cnt = sum(
            1 for items in nonempty_funcs
            if any(ret_keywords.search(item) for item in items)
        )
        ratio = cnt / len(nonempty_funcs)
        assert ratio >= 0.40, (
            f'仅 {cnt}/{len(nonempty_funcs)} 个函数后置条件包含返回值信息（{ratio:.0%}），过低'
        )
        _log.info(
            f'✓ {cnt}/{len(nonempty_funcs)} 个函数后置条件包含返回值相关信息（{ratio:.0%}）'
        )


# ==================================================================
# 测试：analyze_func_exception
# ==================================================================

class TestException:

    def test_returns_dict_with_func_ids(self, exception_results, sample_c_func_ids):
        assert isinstance(exception_results, dict)
        for fid in sample_c_func_ids:
            assert fid in exception_results
        _log.info(f'✓ 返回 dict 覆盖所有 {len(sample_c_func_ids)} 个样本 func_id')

    def test_values_are_string_lists(self, exception_results):
        for fid, items in exception_results.items():
            assert isinstance(items, list)
            for item in items:
                assert isinstance(item, str) and item.strip(), \
                    f'func_id={fid} 含空条目'
        _log.info('✓ 所有值均为非空字符串列表')

    def test_at_least_some_funcs_have_exception_info(self, exception_results):
        """minizip-ng 大量函数有错误处理，至少 40% 应有 exception 数据。"""
        nonempty = sum(1 for v in exception_results.values() if v)
        ratio    = nonempty / len(exception_results) if exception_results else 0
        assert ratio >= 0.40, (
            f'仅 {nonempty}/{len(exception_results)} 个函数有 exception 数据（{ratio:.0%}）'
        )
        _log.info(f'✓ {nonempty}/{len(exception_results)} 个函数有 exception 数据（{ratio:.0%}）')

    def test_db_field_written(self, exception_results, db):
        for fid in list(exception_results.keys())[:20]:
            rec = FuncDB.get_by_id(fid, db_path=db)
            assert rec is not None
            field = rec.get('exception')
            assert isinstance(field, list), \
                f'func_id={fid} DB.exception 类型错误：{type(field)}'
        _log.info('✓ DB 字段 exception 格式正确')

    def test_exception_items_not_too_long(self, exception_results):
        for fid, items in exception_results.items():
            for item in items:
                assert len(item) <= 300, \
                    f'func_id={fid} exception 条目过长（{len(item)} 字）'
        _log.info('✓ 所有 exception 条目长度 ≤ 300 字')

    def test_exception_mentions_error_handling(self, exception_results):
        """
        有数据的函数中，至少 35% 应包含错误处理相关词汇。
        """
        nonempty = [items for items in exception_results.values() if items]
        if not nonempty:
            pytest.skip('无 exception 数据，跳过语义校验')

        err_kw = re.compile(
            r'错误|异常|失败|检查|返回|错误码|未处理|NULL|errno|'
            r'error|fail|check|handle|return|exception|cleanup|释放',
            re.I
        )
        cnt   = sum(1 for items in nonempty
                    if any(err_kw.search(i) for i in items))
        ratio = cnt / len(nonempty)
        assert ratio >= 0.35, (
            f'仅 {cnt}/{len(nonempty)} 个函数 exception 数据含错误处理词汇（{ratio:.0%}）'
        )
        _log.info(
            f'✓ {cnt}/{len(nonempty)} 个函数 exception 包含错误处理词汇（{ratio:.0%}）'
        )


# ==================================================================
# 综合：三字段对比一致性
# ==================================================================

class TestThreeFieldsConsistency:

    def test_all_three_fields_present_in_db(
        self, precond_results, postcond_results, exception_results, db
    ):
        """
        三次分析处理的函数 id 应完全相同，
        且 DB 中三个字段均为 list 类型。
        """
        pre_ids  = set(precond_results.keys())
        post_ids = set(postcond_results.keys())
        exc_ids  = set(exception_results.keys())

        assert pre_ids == post_ids == exc_ids, (
            f'三组 func_id 集合不一致：\n'
            f'  precond  only={pre_ids - post_ids - exc_ids}\n'
            f'  postcond only={post_ids - pre_ids - exc_ids}\n'
            f'  except   only={exc_ids - pre_ids - post_ids}'
        )

        for fid in list(pre_ids)[:30]:
            rec = FuncDB.get_by_id(fid, db_path=db)
            assert rec is not None
            for field in ('precondition', 'postcondition', 'exception'):
                assert isinstance(rec.get(field), list), \
                    f'func_id={fid} DB.{field} 应为 list，实为 {type(rec.get(field))}'

        _log.info(
            f'✓ 三字段 func_id 集合一致（{len(pre_ids)} 个），'
            f'前 30 个函数 DB 字段类型正确'
        )

    def test_coverage_report(
        self, precond_results, postcond_results, exception_results
    ):
        """非断言的覆盖率报告，写入日志供人工审阅。"""
        def _stats(d: dict) -> tuple[int, int, float]:
            nonempty = sum(1 for v in d.values() if v)
            total    = len(d)
            avg_len  = (
                sum(len(v) for v in d.values() if v) / nonempty
                if nonempty else 0.0
            )
            return nonempty, total, avg_len

        for label, d in [
            ('precondition',  precond_results),
            ('postcondition', postcond_results),
            ('exception',     exception_results),
        ]:
            nonempty, total, avg = _stats(d)
            _log.info(
                f'  {label:<15s}  有数据={nonempty}/{total}  '
                f'({nonempty/total*100:.0f}%)  '
                f'平均条数={avg:.1f}'
            )