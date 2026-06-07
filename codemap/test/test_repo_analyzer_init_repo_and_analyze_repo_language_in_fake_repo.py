"""
test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_fake_repo.py
init_repo 和 analyze_repo_language 单元测试（含详细日志）

运行：
    python -m pytest test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_fake_repo.py -v

日志输出：
    test/log/test_<YYYYMMDD_HHMMSS>.log
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
#  日志初始化（模块级，整个测试会话共享同一个日志文件）
# ==================================================================

def _setup_logger() -> logging.Logger:
    """
    在 test/log/ 目录下按时间戳创建日志文件，返回配置好的 Logger。
    Logger 名为 'codemap_test'，幂等：若 handler 已存在则不重复添加。
    """
    log_dir = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'test_{timestamp}.log')

    logger = logging.getLogger('codemap_test')
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:          # 避免重复注册
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s  %(levelname)-7s  %(message)s',
            datefmt='%H:%M:%S',
        ))
        logger.addHandler(fh)

    logger.info('=' * 70)
    logger.info(f'测试会话开始  →  日志文件：{log_file}')
    logger.info('=' * 70)
    return logger


# 模块级单例 logger，所有 fixture / 测试均引用此对象
_logger = _setup_logger()


# ==================================================================
#  数据库快照辅助函数
# ==================================================================

def _dump_db(db_path: str, logger: logging.Logger, label: str = '') -> None:
    """
    直接连接 SQLite，将 repo 表所有记录格式化后写入日志。
    language 字段若为 JSON 字符串则自动反序列化，并展示 Top-5 语言分布。
    """
    tag = f'[DB快照{" · " + label if label else ""}]'
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM repo ORDER BY id').fetchall()
        conn.close()
    except Exception as exc:
        logger.warning(f'{tag} 读取失败：{exc}')
        return

    if not rows:
        logger.info(f'{tag} repo 表为空（0 条记录）')
        return

    logger.info(f'{tag} repo 表共 {len(rows)} 条记录：')
    for row in rows:
        d = dict(row)
        # language 可能以 JSON 字符串存储，尝试解析
        raw_lang = d.get('language')
        lang_obj = None
        if isinstance(raw_lang, str):
            try:
                lang_obj = json.loads(raw_lang)
            except Exception:
                pass
        elif isinstance(raw_lang, dict):
            lang_obj = raw_lang

        logger.info(
            f'  ┌ id={d["id"]}  name={d["name"]!r}  path={d["path"]!r}'
        )
        if lang_obj:
            logger.info(f'  │ language.main = {lang_obj.get("main")!r}')
            stats = lang_obj.get('stats') or []
            top = stats[:5]
            if top:
                logger.info(f'  │ language.stats（Top {len(top)}）：')
                for s in top:
                    bar = '█' * int(s['pct'] / 4)
                    logger.info(
                        f'  │   {s["lang"]:18s} {s["pct"]:6.2f}%  '
                        f'{s["bytes"]:>10,} bytes  {bar}'
                    )
        elif raw_lang is None:
            logger.info('  │ language = NULL（尚未分析）')
        else:
            logger.info(f'  │ language = {raw_lang!r}')
        logger.info('  └' + '─' * 50)


# ==================================================================
#  共用 Fixtures
# ==================================================================

@pytest.fixture(scope='function')
def logger():
    """向每个测试暴露模块级 logger。"""
    return _logger


@pytest.fixture(scope='function')
def db(tmp_path, request):
    """
    每个测试使用独立的临时数据库，互不干扰。
    测试结束后自动记录一次"测试结束时"的 DB 快照。
    """
    db_file = str(tmp_path / 'test_codemap.db')
    _logger.info(f'  [fixture:db] 创建临时数据库 → {db_file}')
    init_db(db_file)
    _logger.info('  [fixture:db] init_db() 完成，表结构就绪')

    yield db_file

    # teardown：记录最终状态
    _dump_db(db_file, _logger, label='测试结束时最终状态')


@pytest.fixture(scope='function')
def fake_repo(tmp_path):
    """
    构造最小化测试仓库：

    fake_repo/
    ├── main.c          (2 000 bytes)  → C
    ├── utils.c         (1 000 bytes)  → C
    ├── helper.h        (  500 bytes)  → C
    ├── README.md       (5 000 bytes)  → Markdown（不应成为主语言）
    ├── CMakeLists.txt  (  300 bytes)  → CMake
    ├── config.yaml     (  200 bytes)  → YAML
    ├── src/
    │   ├── compress.c  (3 000 bytes)  → C
    │   └── module.py   (  800 bytes)  → Python
    └── .git/
        └── config      (  100 bytes)  → 应被忽略
    """
    repo_dir = tmp_path / 'fake_repo'
    repo_dir.mkdir()

    root_files = {
        'main.c':        2000,
        'utils.c':       1000,
        'helper.h':       500,
        'README.md':     5000,
        'CMakeLists.txt': 300,
        'config.yaml':    200,
    }
    for fname, size in root_files.items():
        (repo_dir / fname).write_bytes(b'x' * size)

    src = repo_dir / 'src'
    src.mkdir()
    (src / 'compress.c').write_bytes(b'x' * 3000)
    (src / 'module.py').write_bytes(b'x' * 800)

    git_dir = repo_dir / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_bytes(b'x' * 100)   # 必须被忽略

    _logger.info(f'  [fixture:fake_repo] 构造测试仓库 → {repo_dir}')
    for fname, size in root_files.items():
        _logger.info(f'    {fname:<22s} {size:>5,} bytes')
    _logger.info(f'    {"src/compress.c":<22s} 3,000 bytes')
    _logger.info(f'    {"src/module.py":<22s}   800 bytes')
    _logger.info(f'    {"[忽略] .git/config":<22s}   100 bytes')

    return str(repo_dir)


# ==================================================================
#  autouse fixture：每个测试自动打印开始 / 结束分隔线
# ==================================================================

@pytest.fixture(autouse=True)
def _log_test_boundary(request):
    _logger.info('')
    _logger.info('─' * 70)
    _logger.info(f'▶ TEST START  {request.node.nodeid}')
    _logger.info('─' * 70)
    yield
    _logger.info(f'◀ TEST END    {request.node.nodeid}')
    _logger.info('')


# ==================================================================
#  TestInitRepo
# ==================================================================

class TestInitRepo:

    def test_returns_repo_id(self, fake_repo, db, logger):
        """正常调用应返回正整数 repo_id。"""
        logger.info('步骤1：调用 init_repo()，不传 repo_name')
        repo_id = init_repo(fake_repo, db_path=db)
        logger.info(f'步骤1 结果：repo_id = {repo_id}')
        _dump_db(db, logger, label='init_repo 调用后')

        logger.info('步骤2：断言 repo_id 是正整数')
        assert isinstance(repo_id, int) and repo_id > 0
        logger.info(f'步骤2 通过：repo_id={repo_id} 是正整数 ✓')

    def test_name_inferred_from_path(self, fake_repo, db, logger):
        """未传 repo_name 时，自动取目录名。"""
        logger.info('步骤1：调用 init_repo()，不传 repo_name，期望自动推断为 "fake_repo"')
        repo_id = init_repo(fake_repo, db_path=db)
        logger.info(f'步骤1 结果：repo_id = {repo_id}')
        _dump_db(db, logger, label='init_repo 调用后')

        logger.info('步骤2：从 DB 查询记录并校验 name 字段')
        repo = RepoDB.get_by_id(repo_id, db_path=db)
        logger.info(f'步骤2 DB 返回：name={repo["name"]!r}')
        assert repo['name'] == 'fake_repo'
        logger.info('步骤2 通过：name == "fake_repo" ✓')

    def test_custom_name(self, fake_repo, db, logger):
        """传入 repo_name 后，数据库中存储自定义名称。"""
        logger.info('步骤1：调用 init_repo()，repo_name="my-project"')
        repo_id = init_repo(fake_repo, repo_name='my-project', db_path=db)
        logger.info(f'步骤1 结果：repo_id = {repo_id}')
        _dump_db(db, logger, label='init_repo 调用后')

        logger.info('步骤2：校验 DB 中 name 字段为自定义名称')
        repo = RepoDB.get_by_id(repo_id, db_path=db)
        logger.info(f'步骤2 DB 返回：name={repo["name"]!r}')
        assert repo['name'] == 'my-project'
        logger.info('步骤2 通过：name == "my-project" ✓')

    def test_path_stored_as_absolute(self, fake_repo, db, logger):
        """数据库中 path 字段必须是绝对路径。"""
        logger.info('步骤1：调用 init_repo()')
        repo_id = init_repo(fake_repo, db_path=db)
        logger.info(f'步骤1 结果：repo_id = {repo_id}')
        _dump_db(db, logger, label='init_repo 调用后')

        logger.info('步骤2：校验 DB 中 path 是绝对路径')
        repo = RepoDB.get_by_id(repo_id, db_path=db)
        logger.info(f'步骤2 DB 返回：path={repo["path"]!r}')
        logger.info(f'步骤2 os.path.isabs() = {os.path.isabs(repo["path"])}')
        assert os.path.isabs(repo['path'])
        logger.info('步骤2 通过：path 是绝对路径 ✓')

    def test_path_not_exist_raises(self, db, logger):
        """路径不存在时应抛出 FileNotFoundError。"""
        bad_path = '/absolutely/nonexistent/path'
        logger.info(f'步骤1：使用不存在路径 {bad_path!r} 调用 init_repo()，期望 FileNotFoundError')
        _dump_db(db, logger, label='调用前（应为空表）')

        with pytest.raises(FileNotFoundError) as exc_info:
            init_repo(bad_path, db_path=db)

        logger.info(f'步骤1 通过：捕获到 FileNotFoundError → {exc_info.value} ✓')
        _dump_db(db, logger, label='异常后（应仍为空表）')

    def test_duplicate_name_raises(self, fake_repo, db, logger):
        """同名 repo 重复初始化（force=False）时应抛出 ValueError。"""
        logger.info('步骤1：第一次调用 init_repo()（应成功）')
        repo_id = init_repo(fake_repo, db_path=db)
        logger.info(f'步骤1 结果：repo_id = {repo_id}')
        _dump_db(db, logger, label='第一次 init_repo 后')

        logger.info('步骤2：同名第二次调用 init_repo()（force=False），期望 ValueError')
        with pytest.raises(ValueError, match='已存在') as exc_info:
            init_repo(fake_repo, db_path=db)

        logger.info(f'步骤2 通过：捕获到 ValueError → {exc_info.value} ✓')
        _dump_db(db, logger, label='重复调用后（记录数应不变）')

    def test_force_reinit(self, fake_repo, db, logger):
        """force=True 时，旧记录被删除，新记录正常写入。"""
        logger.info('步骤1：第一次 init_repo()，获取 old_id')
        old_id = init_repo(fake_repo, db_path=db)
        logger.info(f'步骤1 结果：old_id = {old_id}')
        _dump_db(db, logger, label='第一次初始化后')

        logger.info('步骤2：force=True 重新 init_repo()，旧记录应被删除')
        new_id = init_repo(fake_repo, db_path=db, force=True)
        logger.info(f'步骤2 结果：new_id = {new_id}')
        _dump_db(db, logger, label='force=True 重建后')

        logger.info(f'步骤3：校验 old_id={old_id} 已消失，new_id={new_id} 存在')
        old_rec = RepoDB.get_by_id(old_id, db_path=db)
        new_rec = RepoDB.get_by_id(new_id, db_path=db)
        logger.info(f'步骤3 get_by_id(old_id={old_id}) = {old_rec}')
        logger.info(f'步骤3 get_by_id(new_id={new_id}) = {new_rec}')
        assert old_rec is None
        assert new_rec is not None
        logger.info('步骤3 通过：旧记录已删除，新记录存在 ✓')

    def test_idempotent_db_init(self, fake_repo, db, logger):
        """多次调用 init_repo（不同仓库）不应因重复建表而报错。"""
        import tempfile, shutil

        logger.info('步骤1：初始化第一个仓库 fake_repo')
        init_repo(fake_repo, db_path=db)
        _dump_db(db, logger, label='第一个仓库后')

        second_repo = tempfile.mkdtemp()
        logger.info(f'步骤2：初始化第二个仓库 {second_repo!r}')
        try:
            init_repo(second_repo, db_path=db)
            _dump_db(db, logger, label='第二个仓库后')

            all_repos = RepoDB.list_all(db_path=db)
            logger.info(f'步骤3：list_all() 返回 {len(all_repos)} 条，期望 2')
            assert len(all_repos) == 2
            logger.info('步骤3 通过：repo 表共 2 条记录 ✓')
        finally:
            shutil.rmtree(second_repo, ignore_errors=True)


# ==================================================================
#  TestAnalyzeRepoLanguage
# ==================================================================

class TestAnalyzeRepoLanguage:

    def _init(self, fake_repo, db):
        return init_repo(fake_repo, db_path=db)

    def test_returns_dict_with_required_keys(self, fake_repo, db, logger):
        """返回值必须包含 main 和 stats 两个顶层键。"""
        logger.info('步骤1：初始化仓库')
        repo_id = self._init(fake_repo, db)
        logger.info(f'步骤1 结果：repo_id = {repo_id}')

        logger.info('步骤2：调用 analyze_repo_language()')
        result = analyze_repo_language(repo_id, db_path=db)
        logger.info(f'步骤2 返回 keys：{list(result.keys())}')
        logger.info(f'步骤2 main = {result["main"]!r}')
        logger.info(f'步骤2 stats 条数 = {len(result["stats"])}')
        for s in result['stats']:
            logger.info(f'    {s["lang"]:18s} {s["pct"]:6.2f}%  {s["bytes"]:>10,} bytes')
        _dump_db(db, logger, label='分析后')

        assert 'main' in result and 'stats' in result
        logger.info('步骤3 通过：返回值包含 main 和 stats ✓')

    def test_main_language_is_c(self, fake_repo, db, logger):
        """C 文件字节数最多（6 500 bytes），主语言应为 C。"""
        logger.info('步骤1：初始化仓库')
        repo_id = self._init(fake_repo, db)
        logger.info(f'步骤1 结果：repo_id = {repo_id}')

        logger.info('步骤2：调用 analyze_repo_language()，期望 main="C"')
        result = analyze_repo_language(repo_id, db_path=db)
        logger.info(f'步骤2 main = {result["main"]!r}')
        logger.info('步骤2 完整 stats：')
        for s in result['stats']:
            bar = '█' * int(s['pct'] / 4)
            logger.info(
                f'    {s["lang"]:18s} {s["pct"]:6.2f}%  {s["bytes"]:>10,} bytes  {bar}'
            )
        _dump_db(db, logger, label='分析后')

        assert result['main'] == 'C'
        logger.info('步骤3 通过：main == "C" ✓')

    def test_stats_sorted_descending(self, fake_repo, db, logger):
        """stats 应按字节数降序排列。"""
        logger.info('步骤1：初始化仓库并分析')
        repo_id = self._init(fake_repo, db)
        result = analyze_repo_language(repo_id, db_path=db)

        bytes_list = [s['bytes'] for s in result['stats']]
        logger.info(f'步骤2 bytes 序列（期望降序）：{bytes_list}')
        logger.info(f'步骤2 sorted 后：{sorted(bytes_list, reverse=True)}')
        logger.info(f'步骤2 是否降序：{bytes_list == sorted(bytes_list, reverse=True)}')

        assert bytes_list == sorted(bytes_list, reverse=True)
        logger.info('步骤3 通过：stats 按字节数降序排列 ✓')

    def test_c_bytes_correct(self, fake_repo, db, logger):
        """C 字节数 = 2000+1000+500+3000 = 6500，应精确匹配。"""
        logger.info('步骤1：初始化仓库并分析')
        repo_id = self._init(fake_repo, db)
        result = analyze_repo_language(repo_id, db_path=db)

        logger.info('步骤2：在 stats 中定位 C 语言条目')
        logger.info('步骤2 C 字节数期望值：main.c(2000) + utils.c(1000) + helper.h(500) + compress.c(3000) = 6500')
        c_entry = next((s for s in result['stats'] if s['lang'] == 'C'), None)
        logger.info(f'步骤2 C 条目：{c_entry}')

        assert c_entry is not None
        assert c_entry['bytes'] == 6500
        logger.info('步骤3 通过：C bytes == 6500 ✓')

    def test_git_dir_ignored(self, fake_repo, db, logger):
        """.git 目录中的文件（100 bytes）不得计入总字节数。"""
        logger.info('步骤1：初始化仓库并分析')
        repo_id = self._init(fake_repo, db)
        result = analyze_repo_language(repo_id, db_path=db)

        total = sum(s['bytes'] for s in result['stats'])
        logger.info('步骤2：计算 stats 总字节数')
        logger.info('步骤2 期望值：2000+1000+500+5000+300+200+3000+800 = 12800（.git/config 100 bytes 应被忽略）')
        logger.info(f'步骤2 实际总字节数 = {total:,}')
        logger.info('步骤2 各语言明细：')
        for s in result['stats']:
            logger.info(f'    {s["lang"]:18s} {s["bytes"]:>10,} bytes')

        assert total == 12800
        logger.info('步骤3 通过：total == 12,800，.git 目录已被忽略 ✓')

    def test_pct_sums_to_100(self, fake_repo, db, logger):
        """所有语言占比之和应约等于 100.0（浮点误差 < 0.1）。"""
        logger.info('步骤1：初始化仓库并分析')
        repo_id = self._init(fake_repo, db)
        result = analyze_repo_language(repo_id, db_path=db)

        total_pct = sum(s['pct'] for s in result['stats'])
        logger.info('步骤2：各语言占比明细：')
        for s in result['stats']:
            logger.info(f'    {s["lang"]:18s} {s["pct"]:6.2f}%')
        logger.info(f'步骤2 sum(pct) = {total_pct:.6f}（期望约 100.0，允许误差 < 0.1）')

        assert abs(total_pct - 100.0) < 0.1
        logger.info('步骤3 通过：占比之和约等于 100.0 ✓')

    def test_language_written_to_db(self, fake_repo, db, logger):
        """结果应同步写入数据库，且 DAO 自动反序列化为 dict。"""
        logger.info('步骤1：初始化仓库并分析')
        repo_id = self._init(fake_repo, db)
        analyze_repo_language(repo_id, db_path=db)

        logger.info('步骤2：从 DB 读取 repo 记录，校验 language 字段')
        repo = RepoDB.get_by_id(repo_id, db_path=db)
        _dump_db(db, logger, label='写入后再读取')

        lang = repo['language']
        logger.info(f'步骤2 language 类型：{type(lang).__name__}')
        logger.info(f'步骤2 language["main"] = {lang["main"]!r}')
        logger.info(f'步骤2 language["stats"] 类型：{type(lang["stats"]).__name__}，条数：{len(lang["stats"])}')

        assert isinstance(lang, dict)
        assert lang['main'] == 'C'
        assert isinstance(lang['stats'], list)
        logger.info('步骤3 通过：language 字段已正确写入并可反序列化为 dict ✓')

    def test_invalid_repo_id_raises(self, db, logger):
        """不存在的 repo_id 应抛出 ValueError。"""
        bad_id = 999
        logger.info(f'步骤1：使用不存在的 repo_id={bad_id} 调用 analyze_repo_language()，期望 ValueError')
        _dump_db(db, logger, label='调用前（应为空表）')

        with pytest.raises(ValueError, match='不存在') as exc_info:
            analyze_repo_language(bad_id, db_path=db)

        logger.info(f'步骤1 通过：捕获到 ValueError → {exc_info.value} ✓')

    def test_non_code_lang_skipped_as_main(self, tmp_path, db, logger):
        """字节数最多的是 Markdown 时，主语言应顺延为第一个代码型语言（Python）。"""
        logger.info('步骤1：构造文档主导型仓库（Markdown 字节数远超代码文件）')
        repo_dir = tmp_path / 'doc_heavy'
        repo_dir.mkdir()
        (repo_dir / 'DOCS.md').write_bytes(b'x' * 50_000)
        (repo_dir / 'README.md').write_bytes(b'x' * 10_000)
        (repo_dir / 'main.py').write_bytes(b'x' * 3_000)
        logger.info('步骤1 文件清单：')
        logger.info('    DOCS.md     50,000 bytes  → Markdown（非代码型）')
        logger.info('    README.md   10,000 bytes  → Markdown（非代码型）')
        logger.info('    main.py      3,000 bytes  → Python（应成为主语言）')

        logger.info('步骤2：初始化仓库并分析')
        repo_id = init_repo(str(repo_dir), db_path=db)
        result = analyze_repo_language(repo_id, db_path=db)
        logger.info(f'步骤2 main = {result["main"]!r}（期望 "Python"）')
        logger.info('步骤2 完整 stats：')
        for s in result['stats']:
            flag = '← 非代码型，跳过' if s['lang'] in ('Markdown',) else ''
            logger.info(f'    {s["lang"]:18s} {s["pct"]:6.2f}%  {s["bytes"]:>10,} bytes  {flag}')
        _dump_db(db, logger, label='分析后')

        assert result['main'] == 'Python'
        logger.info('步骤3 通过：main == "Python"（Markdown 被正确跳过）✓')

    def test_empty_repo_returns_unknown(self, tmp_path, db, logger):
        """仓库内无可识别文件时，main 应为 'Unknown'，stats 为空列表。"""
        logger.info('步骤1：构造无可识别扩展名文件的空仓库')
        empty_dir = tmp_path / 'empty_repo'
        empty_dir.mkdir()
        (empty_dir / 'no_ext_file').write_bytes(b'x' * 100)
        logger.info(f'步骤1 仓库路径：{empty_dir}')
        logger.info('步骤1 文件清单：no_ext_file（100 bytes，无法识别扩展名）')

        logger.info('步骤2：初始化仓库并分析，期望 main="Unknown"，stats=[]')
        repo_id = init_repo(str(empty_dir), db_path=db)
        result = analyze_repo_language(repo_id, db_path=db)
        logger.info(f'步骤2 main = {result["main"]!r}')
        logger.info(f'步骤2 stats = {result["stats"]}')
        _dump_db(db, logger, label='分析后')

        assert result['main'] == 'Unknown'
        assert result['stats'] == []
        logger.info('步骤3 通过：main="Unknown"，stats=[] ✓')

    def test_makefile_recognized(self, tmp_path, db, logger):
        """无扩展名的 Makefile 应被识别为 'Makefile' 语言。"""
        logger.info('步骤1：构造含 Makefile 的仓库')
        repo_dir = tmp_path / 'make_repo'
        repo_dir.mkdir()
        (repo_dir / 'Makefile').write_bytes(b'x' * 2000)
        (repo_dir / 'main.c').write_bytes(b'x' * 1000)
        logger.info('步骤1 文件清单：Makefile(2000), main.c(1000)')

        logger.info('步骤2：初始化仓库并分析，期望 "Makefile" 出现在 stats 中')
        repo_id = init_repo(str(repo_dir), db_path=db)
        result = analyze_repo_language(repo_id, db_path=db)
        langs = {s['lang'] for s in result['stats']}
        logger.info(f'步骤2 识别到的语言集合：{langs}')
        for s in result['stats']:
            logger.info(f'    {s["lang"]:18s} {s["pct"]:6.2f}%  {s["bytes"]:>10,} bytes')
        _dump_db(db, logger, label='分析后')

        assert 'Makefile' in langs
        logger.info('步骤3 通过：Makefile 已被识别 ✓')

    def test_cmake_lists_recognized(self, tmp_path, db, logger):
        """CMakeLists.txt 应被识别为 'CMake' 语言。"""
        logger.info('步骤1：构造含 CMakeLists.txt 的仓库')
        repo_dir = tmp_path / 'cmake_repo'
        repo_dir.mkdir()
        (repo_dir / 'CMakeLists.txt').write_bytes(b'x' * 2000)
        (repo_dir / 'main.c').write_bytes(b'x' * 1000)
        logger.info('步骤1 文件清单：CMakeLists.txt(2000), main.c(1000)')

        logger.info('步骤2：初始化仓库并分析，期望 "CMake" 出现在 stats 中')
        repo_id = init_repo(str(repo_dir), db_path=db)
        result = analyze_repo_language(repo_id, db_path=db)
        langs = {s['lang'] for s in result['stats']}
        logger.info(f'步骤2 识别到的语言集合：{langs}')
        for s in result['stats']:
            logger.info(f'    {s["lang"]:18s} {s["pct"]:6.2f}%  {s["bytes"]:>10,} bytes')
        _dump_db(db, logger, label='分析后')

        assert 'CMake' in langs
        logger.info('步骤3 通过：CMake 已被识别 ✓')