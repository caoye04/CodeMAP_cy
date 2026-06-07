"""
test/test_just_db.py
数据库层单元测试 —— 覆盖四张表的 CRUD 和 JSON 自动序列化。
运行：python -m pytest test/test_just_db.py -v
"""

import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB, AreaDB, FileDB, FuncDB


@pytest.fixture
def db(tmp_path):
    """每个测试用独立的临时数据库，互不干扰。"""
    db_file = str(tmp_path / 'test_codemap.db')
    """固定一个数据库用于查看。"""
    # db_file = "data/test_db.db"
    # if os.path.exists(db_file):
    #     os.remove(db_file) 
    init_db(db_file)
    return db_file


# ==================================================================
#  Repo 测试
# ==================================================================

class TestRepoDB:

    def test_create_and_get(self, db):
        rid = RepoDB.create('zlib-ng', '/repos/zlib-ng', db_path=db)
        assert rid == 1
        repo = RepoDB.get_by_id(1, db_path=db)
        assert repo['name'] == 'zlib-ng'
        assert repo['path'] == '/repos/zlib-ng'

    def test_get_by_name(self, db):
        RepoDB.create('zlib-ng', '/repos/zlib-ng', db_path=db)
        repo = RepoDB.get_by_name('zlib-ng', db_path=db)
        assert repo is not None
        assert repo['id'] == 1

    def test_update_language_json(self, db):
        rid = RepoDB.create('zlib-ng', '/repos/zlib-ng', db_path=db)
        lang_data = {
            "main": "C",
            "stats": [
                {"lang": "C",      "pct": 82.3, "bytes": 500000},
                {"lang": "CMake",  "pct": 10.1, "bytes": 61000},
                {"lang": "Python", "pct": 5.2,  "bytes": 31000},
            ]
        }
        RepoDB.update(rid, db_path=db, language=lang_data)
        repo = RepoDB.get_by_id(rid, db_path=db)
        # DAO 应自动反序列化
        assert isinstance(repo['language'], dict)
        assert repo['language']['main'] == 'C'
        assert len(repo['language']['stats']) == 3

    def test_update_description(self, db):
        rid = RepoDB.create('zlib-ng', '/repos/zlib-ng', db_path=db)
        RepoDB.update(rid, db_path=db, description='一个高性能 zlib 兼容压缩库。')
        repo = RepoDB.get_by_id(rid, db_path=db)
        assert '高性能' in repo['description']

    def test_unique_name_constraint(self, db):
        RepoDB.create('zlib-ng', '/repos/zlib-ng', db_path=db)
        with pytest.raises(Exception):
            RepoDB.create('zlib-ng', '/other/path', db_path=db)

    def test_list_all(self, db):
        RepoDB.create('repo-a', '/a', db_path=db)
        RepoDB.create('repo-b', '/b', db_path=db)
        repos = RepoDB.list_all(db_path=db)
        assert len(repos) == 2

    def test_delete_cascades(self, db):
        rid = RepoDB.create('zlib-ng', '/repos/zlib-ng', db_path=db)
        aid = AreaDB.create(rid, 'core', 'src', db_path=db)
        fid = FileDB.create(rid, aid, 'deflate.c', 'src/deflate.c', db_path=db)
        FuncDB.create(rid, aid, fid, 'deflate_init', db_path=db)
        RepoDB.delete(rid, db_path=db)
        # 级联删除验证
        assert AreaDB.get_by_id(aid, db_path=db) is None
        assert FileDB.get_by_id(fid, db_path=db) is None


# ==================================================================
#  Area 测试
# ==================================================================

class TestAreaDB:

    def _setup_repo(self, db):
        return RepoDB.create('zlib-ng', '/repos/zlib-ng', db_path=db)

    def test_create_and_get(self, db):
        rid = self._setup_repo(db)
        aid = AreaDB.create(rid, 'compress', 'src/compress',
                             rationale='压缩相关实现集中在此目录', db_path=db)
        area = AreaDB.get_by_id(aid, db_path=db)
        assert area['name'] == 'compress'
        assert area['rationale'] == '压缩相关实现集中在此目录'

    def test_get_by_path(self, db):
        rid = self._setup_repo(db)
        AreaDB.create(rid, 'compress', 'src/compress', db_path=db)
        area = AreaDB.get_by_path(rid, 'src/compress', db_path=db)
        assert area is not None

    def test_update_filelist_json(self, db):
        rid = self._setup_repo(db)
        aid = AreaDB.create(rid, 'compress', 'src/compress', db_path=db)
        filelist = [
            {"file_id": 1, "name": "deflate.c", "brief": "DEFLATE 核心实现"},
            {"file_id": 2, "name": "trees.c",   "brief": "哈夫曼树构建"},
        ]
        AreaDB.update(aid, db_path=db, filelist=filelist)
        area = AreaDB.get_by_id(aid, db_path=db)
        assert isinstance(area['filelist'], list)
        assert area['filelist'][0]['name'] == 'deflate.c'

    def test_list_by_repo(self, db):
        rid = self._setup_repo(db)
        AreaDB.create(rid, 'compress', 'src/compress', db_path=db)
        AreaDB.create(rid, 'decompress', 'src/decompress', db_path=db)
        areas = AreaDB.list_by_repo(rid, db_path=db)
        assert len(areas) == 2


# ==================================================================
#  File 测试
# ==================================================================

class TestFileDB:

    def _setup(self, db):
        rid = RepoDB.create('zlib-ng', '/repos/zlib-ng', db_path=db)
        aid = AreaDB.create(rid, 'compress', 'src/compress', db_path=db)
        return rid, aid

    def test_create_and_get(self, db):
        rid, aid = self._setup(db)
        fid = FileDB.create(rid, aid, 'deflate.c', 'src/compress/deflate.c', db_path=db)
        f = FileDB.get_by_id(fid, db_path=db)
        assert f['name'] == 'deflate.c'
        assert f['area_id'] == aid

    def test_update_language(self, db):
        rid, aid = self._setup(db)
        fid = FileDB.create(rid, aid, 'deflate.c', 'src/compress/deflate.c', db_path=db)
        FileDB.update(fid, db_path=db, language='C')
        f = FileDB.get_by_id(fid, db_path=db)
        assert f['language'] == 'C'

    def test_list_by_area(self, db):
        rid, aid = self._setup(db)
        FileDB.create(rid, aid, 'deflate.c', 'src/compress/deflate.c', db_path=db)
        FileDB.create(rid, aid, 'trees.c',   'src/compress/trees.c',   db_path=db)
        files = FileDB.list_by_area(aid, db_path=db)
        assert len(files) == 2


# ==================================================================
#  Func 测试
# ==================================================================

class TestFuncDB:

    def _setup(self, db):
        rid = RepoDB.create('zlib-ng', '/repos/zlib-ng', db_path=db)
        aid = AreaDB.create(rid, 'compress', 'src/compress', db_path=db)
        fid = FileDB.create(rid, aid, 'deflate.c', 'src/compress/deflate.c', db_path=db)
        return rid, aid, fid

    def test_create_and_get(self, db):
        rid, aid, fid = self._setup(db)
        place = {"file_path": "src/compress/deflate.c", "start_line": 42, "end_line": 105}
        io    = {
            "params":  [{"name": "strm", "type": "z_streamp", "desc": "压缩流指针"}],
            "returns": {"type": "int", "desc": "Z_OK 或错误码"},
        }
        func_id = FuncDB.create(rid, aid, fid, 'deflate_init',
                                 place=place, io=io, db_path=db)
        func = FuncDB.get_by_id(func_id, db_path=db)
        # JSON 自动反序列化验证
        assert isinstance(func['place'], dict)
        assert func['place']['start_line'] == 42
        assert isinstance(func['io'], dict)
        assert func['io']['params'][0]['name'] == 'strm'

    def test_update_callgraph(self, db):
        rid, aid, fid = self._setup(db)
        func_id = FuncDB.create(rid, aid, fid, 'deflate_init', db_path=db)
        callgraph = {
            "callers": [{"name": "compress2",    "file": "compress.c",  "type": "user"}],
            "callees": [{"name": "memset",        "file": "<string.h>", "type": "lib"},
                        {"name": "deflate_reset", "file": "deflate.c",  "type": "user"}],
        }
        FuncDB.update(func_id, db_path=db, callgraph=callgraph)
        func = FuncDB.get_by_id(func_id, db_path=db)
        assert len(func['callgraph']['callees']) == 2
        assert func['callgraph']['callees'][0]['name'] == 'memset'

    def test_update_precondition(self, db):
        rid, aid, fid = self._setup(db)
        func_id = FuncDB.create(rid, aid, fid, 'deflate_init', db_path=db)
        pre = {
            "param_checks":    [{"param": "strm", "check": "!= NULL"}],
            "state_checks":    [],
            "resource_checks": [],
            "llm_summary":     "调用前必须确保 strm 不为空且已分配内存。",
        }
        FuncDB.update(func_id, db_path=db, precondition=pre)
        func = FuncDB.get_by_id(func_id, db_path=db)
        assert isinstance(func['precondition'], dict)
        assert '不为空' in func['precondition']['llm_summary']

    def test_search_by_name(self, db):
        rid, aid, fid = self._setup(db)
        FuncDB.create(rid, aid, fid, 'deflate_init',  db_path=db)
        FuncDB.create(rid, aid, fid, 'deflate_reset', signature='v2', db_path=db)
        FuncDB.create(rid, aid, fid, 'inflate_init',  db_path=db)
        results = FuncDB.search_by_name(rid, 'deflate', db_path=db)
        assert len(results) == 2

    def test_list_by_file(self, db):
        rid, aid, fid = self._setup(db)
        FuncDB.create(rid, aid, fid, 'deflate_init',  db_path=db)
        FuncDB.create(rid, aid, fid, 'deflate_reset', signature='v2', db_path=db)
        funcs = FuncDB.list_by_file(fid, db_path=db)
        assert len(funcs) == 2