# CodeMAP项目

> CaoYe

[toc]

## 背景

- 对应需求：在我们目前研究工作的基础层，需要有代码摘要的实现；后续可以用于摘要检索
- 目前想法：构造CodeMAP，通过对项目做树状分级和对函数做详细摘要，来做成完备的结构化知识库

## CodeMAP设计

### CodeMAP层级设计

| 层级       | 说明                                                         |
| ---------- | ------------------------------------------------------------ |
| repo  仓库 | 仓库名  + 主要语言  + LLM描述+area列表                       |
| area  包   | Area名+路径+LLM描述+文件列表                                 |
| file  文件 | 文件名+语言+LLM描述+函数列表                                 |
| func  函数 | 函数名称+函数所在文件及行数+参数和返回值+LLM总结函数描述+函数调用关系+前置条件+前后置条件+异常处理 |

### CodeMAP算法设计流程

1. **init_repo**：得到仓库名，建立对应数据库并填入对应数据【repo:name】
2. **analyze_repo_language**：扫描仓库并分析语言占比情况，得出主要语言，并填入对应数据【repo:language】
3. **analyze_repo_area**：对仓库分层，并附上分层依据和对应的area具体路径，存data/analyze_repo_area，并填入对应数据【repo:arealist；area:name；area:path】
4. **analyze_area_file**：扫描area路径得到文件结构，存在data/analyze_area_file，并填入对应数据【area:filelist；file:name；file:path】
5.  **analyze_file_language**：分析文件的编程语言，并填入对应数据【file:language】
6. **analyze_file_func**：分析文件中所有的函数，并填入对应数据【file:funclist；func:name；func:place；func:io】
7. **build_callgraph**：用codeql对整个仓库的函数简历调用图
8. **analyze_func_callgraph**：分析该函数的调用关系，并填入对应数据【func:callgraph】
9. **analyze_func_precondition**：sa+llm分析该函数的前置调用关系，且有一些分类，这个实现需要做到非常好和细节到位，最后填入对应数据【func:precondition】
10. **analyze_func_postcondition**：sa+llm分析该函数的后置调用关系，且有一些分类，这个实现需要做到非常好和细节到位，最后填入对应数据【func:postcondition】
11. **analyze_func_exception**：分析该函数的异常处理，填入对应数据【func:exception】
12. **get_func_context**：通过输入函数名和路径，得到该函数的内容，如果数据库中有函数的一些补充信息也给出（命令行可选补充信息需求）
13. **analyze_func_description**：agent实现，提供该函数内容+调用关系+前置条件+后置条件+异常处理，以及给一个get_func_context的工具调用结构，可以agent工具得到调用链里的函数信息；让agent给出该函数的自然语言描述：该函数功能+函数分析+函数安全分析+开发者意图分析等，最后填入对应数据【func:description】
14. **analyze_file_funclist_description**：通过提供file的funclist，将每个func的description变成简短的一两句话存入对应数据【file:funclist】
15. **analyze_file_description**：给llm提供file在area里的文件组织架构、文件信息、其中函数所有的description，得到对文件的自然语言描述：文件功能+文件定位+开发者意图分析，最后填入对应数据【file:description】
16. **analyze_area_filelist_description**：通过提供area的filelist，将每个file的description变成简短的一两句话存入对应数据【area:filelist】
17. **analyze_area_description**：给llm提供area的在仓库中路径及分层依据+area里的文件组织架构、其中file所有的description，得到对area的自然语言描述：area功能+area定位+开发者意图分析，最后填入对应数据【area:description】
18. **analyze_repo_arealist_description**：通过提供repo的arealist，每个area的description变成简短的一两句话存入对应数据【repo:arealist】
19. **analyze_area_description**：给llm提供仓库的文件组织结构、分层结构、仓库相关信息、仓库里可参考的文本内容、仓库的所有area的description，得到对仓库的自然语言描述：仓库功能+开发者意图分析，最后填入对应数据【repo:description】
20. **build_codemap**：实现CodeMAP，即将上述流程串起来

### CodeMAP外部接口实现

1. **get_repo**：把仓库所有信息展示（仓库名 + 主要语言 + LLM描述 + area列表）
2. **get_repo_language**：把仓库语言信息展示，涉及了哪些语言，各自占比大概多少
3. **get_repo_area**：展示仓库分层情况和依据+每个area简短的一句话描述
4. **get_repo_description**：把仓库的描述展示
5. **get_area**：把该area所有信息展示（Area名+路径+LLM描述+文件列表）
6. **get_area_path**：展示area具体路径
7. **get_area_file**：展示area的所有文件结构+每个文件简短的一句话描述
8. **get_area_description**：展示are的llm描述
9. **get_file**：展示该文件的所有信息（文件名+语言+LLM描述+函数列表）
10. **get_file_language**：展示文件的语言
11. **get_file_func**：展示文件中所有的函数情况+每个函数简短的一句话描述
12. **get_file_description**：展示文件的llm描述信息
13. **get_func_place**：展示该函数所在文件及行数
14. **get_func_io**：展示该函数的输入参数和返回值
15. **get_func_callgraph**：展示该函数的调用关系，caller、callee（进行用户自定义函数和库函数分类）
16. **get_func_precondition**：展示该函数的前置条件，以及相关的llm解释语言
17. **get_func_postcondition**：展示函数后置条件，以及相关的llm解释语言
18. **get_func_exception**：展示函数异常处理，以及相关的llm解释语言
19. **get_func_description**：展示该函数的llm总结描述（该函数的具体功能，函数数据流调用流分析，该函数有无安全漏洞）

### 实现思路

- 逐个函数进行实现、功能单元测试

- 用SQLite存储CodeMAP的每层信息
- 用minizip-ng这个仓库进行功能测试，路径（相对于codemap）`../../minizip-ng/`

### 仓库架构

```
codemap/
├── README.md
├── requirements.txt
├── config.py                    # 全局配置（API Key、模型、CodeQL路径等）
├── main.py                      # build_codemap 主流程入口
├── cli.py                       # 命令行工具（get_* 系列接口）
│
├── db/
│   ├── schema.sql               # 建表DDL，直接可读
│   └── dao.py                   # 数据库增删改查统一封装
│
├── analyzer/                    # 分析算法层，按层级拆分
│   ├── repo_analyzer.py         # init_repo / analyze_repo_*
│   ├── area_analyzer.py         # analyze_area_*
│   ├── file_analyzer.py         # analyze_file_*
│   ├── func_analyzer.py         # analyze_func_* / get_func_context
│   └── callgraph_builder.py     # build_callgraph / analyze_func_callgraph (CodeQL)
│
├── llm/
│   ├── client.py                # LLM调用统一封装（方便切换模型）
│   ├── agent.py                 # Agent实现，供 analyze_func_description 使用
│   └── prompts.py               # 所有prompt模板集中管理
│
├── get/                        # 外部展示接口层
│   ├── repo_get.py             # get_repo_*
│   ├── area_get.py             # get_area_*
│   ├── file_get.py             # get_file_*
│   └── func_get.py             # get_func_*
│
├── test/                        # 单元功能测试
│   └── 逐个算法功能进行测试        
│
└── data/                        # 中间产物存储（不入库的JSON）
    ├── analyze_repo_area/       # step3 产物
    └── analyze_area_file/       # step4 产物
```

## 开发流程

### step1：数据库算法搭建

`db/schema.sql`

```
-- CodeMAP Database Schema
-- SQLite 3.x
-- 字段中 JSON 类型存储为 TEXT，由 dao.py 层自动序列化/反序列化

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;   -- 写性能优化，适合分析任务的多次小更新

-- ============================================================
--  repo 仓库层
-- ============================================================
CREATE TABLE IF NOT EXISTS repo (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,          -- 仓库名，唯一
    path        TEXT    NOT NULL,                 -- 本地绝对路径
    -- language: {"main": "C", "stats": [{"lang": "C", "pct": 80.2, "bytes": 123456}, ...]}
    language    TEXT,
    description TEXT,                             -- LLM 生成的仓库描述
    -- arealist: [{"area_id": 1, "name": "core", "brief": "核心压缩逻辑"}, ...]
    arealist    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
--  area 包/模块层
-- ============================================================
CREATE TABLE IF NOT EXISTS area (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id     INTEGER NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,                 -- area 名称，如 "compress"
    path        TEXT    NOT NULL,                 -- 相对仓库根的路径，如 "src/compress"
    rationale   TEXT,                             -- LLM 给出的分层依据（自然语言）
    description TEXT,                             -- LLM 生成的 area 描述
    -- filelist: [{"file_id": 3, "name": "deflate.c", "brief": "实现 DEFLATE 压缩"}, ...]
    filelist    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(repo_id, path)
);

-- ============================================================
--  file 文件层
-- ============================================================
CREATE TABLE IF NOT EXISTS file (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id     INTEGER NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
    area_id     INTEGER NOT NULL REFERENCES area(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,                 -- 文件名，如 "deflate.c"
    path        TEXT    NOT NULL,                 -- 相对仓库根的完整路径
    language    TEXT,                             -- "C" / "C++" / "Python" 等
    description TEXT,                             -- LLM 生成的文件描述
    -- funclist: [{"func_id": 5, "name": "deflate_init", "brief": "初始化压缩流"}, ...]
    funclist    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(repo_id, path)
);

-- ============================================================
--  func 函数层
-- ============================================================
CREATE TABLE IF NOT EXISTS func (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id         INTEGER NOT NULL REFERENCES repo(id)  ON DELETE CASCADE,
    area_id         INTEGER NOT NULL REFERENCES area(id)  ON DELETE CASCADE,
    file_id         INTEGER NOT NULL REFERENCES file(id)  ON DELETE CASCADE,
    name            TEXT    NOT NULL,             -- 函数名
    signature       TEXT,                         -- 完整签名（兼容 C++ 重载）
    -- place: {"file_path": "src/deflate.c", "start_line": 42, "end_line": 105}
    place           TEXT,
    -- io: {
    --   "params": [{"name": "strm", "type": "z_streamp", "desc": "压缩流指针"}],
    --   "returns": {"type": "int", "desc": "Z_OK 或错误码"}
    -- }
    io              TEXT,
    -- callgraph: {
    --   "callers": [{"name": "compress2", "file": "compress.c", "type": "user"}],
    --   "callees": [{"name": "memset", "file": "<stdlib.h>", "type": "lib"}]
    -- }
    callgraph       TEXT,
    -- precondition: {
    --   "param_checks": [...],
    --   "state_checks": [...],
    --   "resource_checks": [...],
    --   "llm_summary": "..."
    -- }
    precondition    TEXT,
    -- postcondition: {
    --   "state_mutations": [...],
    --   "return_guarantees": [...],
    --   "side_effects": [...],
    --   "llm_summary": "..."
    -- }
    postcondition   TEXT,
    -- exception: {
    --   "handled": [{"type": "NULL_PTR", "handler": "return Z_STREAM_ERROR"}],
    --   "unhandled": [...],
    --   "llm_summary": "..."
    -- }
    exception       TEXT,
    description     TEXT,                         -- LLM 生成的函数完整描述
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    -- 同文件内函数名+起始行唯一，支持 C++ 重载场景
    UNIQUE(file_id, name, signature)
);

-- ============================================================
--  自动更新 updated_at 触发器
-- ============================================================
CREATE TRIGGER IF NOT EXISTS trg_repo_updated
    AFTER UPDATE ON repo FOR EACH ROW
    BEGIN UPDATE repo SET updated_at = datetime('now') WHERE id = OLD.id; END;

CREATE TRIGGER IF NOT EXISTS trg_area_updated
    AFTER UPDATE ON area FOR EACH ROW
    BEGIN UPDATE area SET updated_at = datetime('now') WHERE id = OLD.id; END;

CREATE TRIGGER IF NOT EXISTS trg_file_updated
    AFTER UPDATE ON file FOR EACH ROW
    BEGIN UPDATE file SET updated_at = datetime('now') WHERE id = OLD.id; END;

CREATE TRIGGER IF NOT EXISTS trg_func_updated
    AFTER UPDATE ON func FOR EACH ROW
    BEGIN UPDATE func SET updated_at = datetime('now') WHERE id = OLD.id; END;

-- ============================================================
--  常用查询索引
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_area_repo   ON area(repo_id);
CREATE INDEX IF NOT EXISTS idx_file_area   ON file(area_id);
CREATE INDEX IF NOT EXISTS idx_file_repo   ON file(repo_id);
CREATE INDEX IF NOT EXISTS idx_func_file   ON func(file_id);
CREATE INDEX IF NOT EXISTS idx_func_repo   ON func(repo_id);
CREATE INDEX IF NOT EXISTS idx_func_name   ON func(name);       -- 支持按名搜索
```

`db/dao.py`

```
"""
db/dao.py
CodeMAP 数据访问层 —— 对 SQLite 的所有读写统一由此经过。

设计原则：
- 所有 JSON 字段（language/arealist/filelist/funclist/place/io/
  callgraph/precondition/postcondition/exception）在写入时自动
  序列化，读取时自动反序列化，上层代码始终面对 Python dict/list。
- 每个表对应一个 *DB 类，方法命名统一：
    create / get_by_id / get_by_* / list_by_* / update / delete
- 所有写操作通过 get_connection() 上下文管理器保证事务原子性。
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Optional

# ------------------------------------------------------------------
#  路径配置（可被 config.py 覆盖）
# ------------------------------------------------------------------
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'codemap.db'
)
_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

# JSON 字段白名单，读取时自动反序列化
_JSON_FIELDS = {
    'language', 'arealist', 'filelist', 'funclist',
    'place', 'io', 'callgraph', 'precondition', 'postcondition', 'exception',
}


# ------------------------------------------------------------------
#  连接与初始化
# ------------------------------------------------------------------

def _resolve_path(db_path: Optional[str]) -> str:
    return db_path or _DEFAULT_DB_PATH


@contextmanager
def get_connection(db_path: Optional[str] = None):
    """
    获取数据库连接（上下文管理器）。
    成功退出时自动 commit，异常时自动 rollback。
    """
    path = _resolve_path(db_path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """初始化数据库，执行 schema.sql 完成建表。幂等操作，可重复调用。"""
    with open(_SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema = f.read()
    with get_connection(db_path) as conn:
        conn.executescript(schema)
    print(f"[dao] DB initialized at: {_resolve_path(db_path)}")


# ------------------------------------------------------------------
#  内部工具函数
# ------------------------------------------------------------------

def _dump(value: Any) -> Optional[str]:
    """Python 对象 → JSON 字符串；字符串原样返回；None 返回 None。"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    """Row → dict，JSON 字段自动反序列化。"""
    if row is None:
        return None
    d = dict(row)
    for key in _JSON_FIELDS:
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, ValueError):
                pass  # 保持原始字符串
    return d


def _rows_to_list(rows) -> list[dict]:
    return [_row_to_dict(r) for r in rows]


def _build_update(fields: dict, allowed: set) -> tuple[str, list]:
    """
    构造 UPDATE 的 SET 子句和参数列表。
    返回 (set_clause, values)，values 末尾不含 WHERE 参数。
    """
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        raise ValueError(f"No valid fields to update. Allowed: {allowed}")
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = [_dump(v) for v in updates.values()]
    return set_clause, values


# ==================================================================
#  RepoDB —— repo 表
# ==================================================================

class RepoDB:
    """repo 表 CRUD"""

    _UPDATABLE = {'name', 'path', 'language', 'description', 'arealist'}

    @staticmethod
    def create(name: str, path: str, db_path: Optional[str] = None) -> int:
        """
        新建 repo 记录。
        Returns: 新记录的 id
        """
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO repo (name, path) VALUES (?, ?)",
                (name, path),
            )
            return cur.lastrowid

    @staticmethod
    def get_by_id(repo_id: int, db_path: Optional[str] = None) -> Optional[dict]:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM repo WHERE id = ?", (repo_id,)
            ).fetchone()
            return _row_to_dict(row)

    @staticmethod
    def get_by_name(name: str, db_path: Optional[str] = None) -> Optional[dict]:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM repo WHERE name = ?", (name,)
            ).fetchone()
            return _row_to_dict(row)

    @staticmethod
    def list_all(db_path: Optional[str] = None) -> list[dict]:
        with get_connection(db_path) as conn:
            rows = conn.execute("SELECT * FROM repo ORDER BY name").fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def update(repo_id: int, db_path: Optional[str] = None, **fields) -> None:
        """
        更新 repo 字段，支持关键字参数传入任意合法字段。
        示例：RepoDB.update(1, language={"main": "C", "stats": [...]})
        """
        set_clause, values = _build_update(fields, RepoDB._UPDATABLE)
        values.append(repo_id)
        with get_connection(db_path) as conn:
            conn.execute(f"UPDATE repo SET {set_clause} WHERE id = ?", values)

    @staticmethod
    def delete(repo_id: int, db_path: Optional[str] = None) -> None:
        """级联删除 repo 及其所有 area/file/func。"""
        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM repo WHERE id = ?", (repo_id,))


# ==================================================================
#  AreaDB —— area 表
# ==================================================================

class AreaDB:
    """area 表 CRUD"""

    _UPDATABLE = {'name', 'path', 'rationale', 'description', 'filelist'}

    @staticmethod
    def create(repo_id: int, name: str, path: str,
               rationale: Optional[str] = None,
               db_path: Optional[str] = None) -> int:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO area (repo_id, name, path, rationale) VALUES (?, ?, ?, ?)",
                (repo_id, name, path, rationale),
            )
            return cur.lastrowid

    @staticmethod
    def get_by_id(area_id: int, db_path: Optional[str] = None) -> Optional[dict]:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM area WHERE id = ?", (area_id,)
            ).fetchone()
            return _row_to_dict(row)

    @staticmethod
    def get_by_path(repo_id: int, path: str,
                    db_path: Optional[str] = None) -> Optional[dict]:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM area WHERE repo_id = ? AND path = ?",
                (repo_id, path),
            ).fetchone()
            return _row_to_dict(row)

    @staticmethod
    def list_by_repo(repo_id: int, db_path: Optional[str] = None) -> list[dict]:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM area WHERE repo_id = ? ORDER BY path",
                (repo_id,),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def update(area_id: int, db_path: Optional[str] = None, **fields) -> None:
        set_clause, values = _build_update(fields, AreaDB._UPDATABLE)
        values.append(area_id)
        with get_connection(db_path) as conn:
            conn.execute(f"UPDATE area SET {set_clause} WHERE id = ?", values)

    @staticmethod
    def delete(area_id: int, db_path: Optional[str] = None) -> None:
        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM area WHERE id = ?", (area_id,))


# ==================================================================
#  FileDB —— file 表
# ==================================================================

class FileDB:
    """file 表 CRUD"""

    _UPDATABLE = {'name', 'path', 'language', 'description', 'funclist'}

    @staticmethod
    def create(repo_id: int, area_id: int, name: str, path: str,
               db_path: Optional[str] = None) -> int:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO file (repo_id, area_id, name, path) VALUES (?, ?, ?, ?)",
                (repo_id, area_id, name, path),
            )
            return cur.lastrowid

    @staticmethod
    def get_by_id(file_id: int, db_path: Optional[str] = None) -> Optional[dict]:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM file WHERE id = ?", (file_id,)
            ).fetchone()
            return _row_to_dict(row)

    @staticmethod
    def get_by_path(repo_id: int, path: str,
                    db_path: Optional[str] = None) -> Optional[dict]:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM file WHERE repo_id = ? AND path = ?",
                (repo_id, path),
            ).fetchone()
            return _row_to_dict(row)

    @staticmethod
    def list_by_area(area_id: int, db_path: Optional[str] = None) -> list[dict]:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM file WHERE area_id = ? ORDER BY path",
                (area_id,),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def list_by_repo(repo_id: int, db_path: Optional[str] = None) -> list[dict]:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM file WHERE repo_id = ? ORDER BY path",
                (repo_id,),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def update(file_id: int, db_path: Optional[str] = None, **fields) -> None:
        set_clause, values = _build_update(fields, FileDB._UPDATABLE)
        values.append(file_id)
        with get_connection(db_path) as conn:
            conn.execute(f"UPDATE file SET {set_clause} WHERE id = ?", values)

    @staticmethod
    def delete(file_id: int, db_path: Optional[str] = None) -> None:
        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM file WHERE id = ?", (file_id,))


# ==================================================================
#  FuncDB —— func 表
# ==================================================================

class FuncDB:
    """func 表 CRUD"""

    _UPDATABLE = {
        'name', 'signature', 'place', 'io',
        'callgraph', 'precondition', 'postcondition', 'exception', 'description',
    }

    @staticmethod
    def create(repo_id: int, area_id: int, file_id: int,
               name: str,
               signature: Optional[str] = None,
               place: Optional[dict] = None,
               io: Optional[dict] = None,
               db_path: Optional[str] = None) -> int:
        """
        新建 func 记录。
        place 示例：{"file_path": "src/deflate.c", "start_line": 42, "end_line": 105}
        io    示例：{"params": [...], "returns": {...}}
        """
        with get_connection(db_path) as conn:
            cur = conn.execute(
                """INSERT INTO func
                   (repo_id, area_id, file_id, name, signature, place, io)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (repo_id, area_id, file_id, name,
                 signature, _dump(place), _dump(io)),
            )
            return cur.lastrowid

    @staticmethod
    def get_by_id(func_id: int, db_path: Optional[str] = None) -> Optional[dict]:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM func WHERE id = ?", (func_id,)
            ).fetchone()
            return _row_to_dict(row)

    @staticmethod
    def get_by_name_in_file(file_id: int, name: str,
                             db_path: Optional[str] = None) -> list[dict]:
        """同一文件内按名查找（C++ 可能返回多个重载）"""
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM func WHERE file_id = ? AND name = ?",
                (file_id, name),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def list_by_file(file_id: int, db_path: Optional[str] = None) -> list[dict]:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM func WHERE file_id = ? ORDER BY name",
                (file_id,),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def list_by_repo(repo_id: int, db_path: Optional[str] = None) -> list[dict]:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM func WHERE repo_id = ? ORDER BY name",
                (repo_id,),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def search_by_name(repo_id: int, keyword: str,
                       db_path: Optional[str] = None) -> list[dict]:
        """在 repo 范围内按函数名模糊搜索（用于 get_func_context）"""
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM func WHERE repo_id = ? AND name LIKE ?",
                (repo_id, f"%{keyword}%"),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def update(func_id: int, db_path: Optional[str] = None, **fields) -> None:
        """
        更新函数任意字段，dict/list 自动序列化为 JSON。
        示例：
            FuncDB.update(7, callgraph={"callers": [...], "callees": [...]})
            FuncDB.update(7, description="该函数负责...")
        """
        set_clause, values = _build_update(fields, FuncDB._UPDATABLE)
        values.append(func_id)
        with get_connection(db_path) as conn:
            conn.execute(f"UPDATE func SET {set_clause} WHERE id = ?", values)

    @staticmethod
    def delete(func_id: int, db_path: Optional[str] = None) -> None:
        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM func WHERE id = ?", (func_id,))
```

`config.py`

```
"""
config.py —— 全局配置入口
后续 API Key、模型名、CodeQL 路径等均在此集中管理。
"""
import os
# ------------------------------------------------------------------
#  路径
# ------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(PROJECT_ROOT, 'data')
DB_PATH      = os.path.join(DATA_DIR, 'codemap.db')

# ------------------------------------------------------------------
#  LLM（占位，后续填入）
# ------------------------------------------------------------------
LLM_API_KEY  = os.getenv('OPENAI_API_KEY', '')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
LLM_MODEL    = os.getenv('LLM_MODEL', 'gpt-4o')

# ------------------------------------------------------------------
#  CodeQL（占位，后续填入）
# ------------------------------------------------------------------
CODEQL_BIN   = os.getenv('CODEQL_BIN', 'codeql')   # codeql 可执行文件路径
```

`test/test_db.py`（已实现不记录）

### Step2：`init_repo` 和 `analyze_repo_language`实现

`analyzer/repo_analyzer.py`

```
"""
analyzer/repo_analyzer.py
CodeMAP 仓库层分析器

实现：
  - init_repo              : 初始化仓库记录，建库建表，写入 repo:name / repo:path
  - analyze_repo_language  : 扫描仓库文件，统计语言字节数和占比，写入 repo:language
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB
from config import DB_PATH

# ------------------------------------------------------------------
#  常量：扩展名 → 编程语言
# ------------------------------------------------------------------
_EXT_TO_LANG: dict[str, str] = {
    # C / C++
    '.c':     'C',
    '.h':     'C',        # C 头文件（.hpp/.hxx 单独归 C++）
    '.cpp':   'C++',
    '.cxx':   'C++',
    '.cc':    'C++',
    '.hpp':   'C++',
    '.hxx':   'C++',
    # Python
    '.py':    'Python',
    # Java
    '.java':  'Java',
    # JavaScript / TypeScript
    '.js':    'JavaScript',
    '.jsx':   'JavaScript',
    '.ts':    'TypeScript',
    '.tsx':   'TypeScript',
    # Go
    '.go':    'Go',
    # Rust
    '.rs':    'Rust',
    # Shell
    '.sh':    'Shell',
    '.bash':  'Shell',
    '.zsh':   'Shell',
    # CMake（文件名匹配见下方特判）
    '.cmake': 'CMake',
    # Ruby
    '.rb':    'Ruby',
    # Swift
    '.swift': 'Swift',
    # Kotlin
    '.kt':    'Kotlin',
    '.kts':   'Kotlin',
    # Scala
    '.scala': 'Scala',
    # Haskell
    '.hs':    'Haskell',
    # Assembly
    '.asm':   'Assembly',
    '.s':     'Assembly',
    # Lua
    '.lua':   'Lua',
    # Perl
    '.pl':    'Perl',
    '.pm':    'Perl',
    # Fortran
    '.f':     'Fortran',
    '.f90':   'Fortran',
    '.f95':   'Fortran',
    # R
    '.r':     'R',
    # MATLAB / Objective-C（.m 有歧义，优先 MATLAB；Obj-C 通常搭配 .mm）
    '.m':     'MATLAB',
    '.mm':    'Objective-C',
    # ---- 配置 / 文档类（统计但不作为主语言候选）----
    '.md':    'Markdown',
    '.rst':   'reStructuredText',
    '.yaml':  'YAML',
    '.yml':   'YAML',
    '.json':  'JSON',
    '.xml':   'XML',
    '.html':  'HTML',
    '.htm':   'HTML',
    '.css':   'CSS',
    '.sql':   'SQL',
    '.toml':  'TOML',
    '.ini':   'INI',
    '.cfg':   'INI',
}

# 遍历时跳过的目录（版本控制、构建产物、虚拟环境等）
_IGNORE_DIRS: set[str] = {
    '.git', '.svn', '.hg',
    '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache',
    'node_modules',
    '.venv', 'venv', 'env', '.env',
    'build', 'dist', '.build', 'out', 'target', 'cmake-build-debug',
    '.idea', '.vscode',
    'vendor',
}

# 不作为主语言候选的"非代码"语言集合
_NON_CODE_LANGS: set[str] = {
    'Markdown', 'reStructuredText',
    'YAML', 'JSON', 'XML', 'HTML', 'CSS',
    'SQL', 'TOML', 'INI',
}


# ==================================================================
#  init_repo
# ==================================================================

def init_repo(
    repo_path: str,
    repo_name: str | None = None,
    db_path: str | None = None,
    force: bool = False,
) -> int:
    """
    初始化仓库：建库建表，并在 repo 表中写入仓库基本信息。

    Parameters
    ----------
    repo_path : str
        仓库本地路径（绝对或相对均可，内部统一转为绝对路径）。
    repo_name : str | None
        仓库名称；若不传则取路径末尾目录名。
    db_path : str | None
        SQLite 数据库文件路径；不传则使用 config.DB_PATH。
    force : bool
        若同名 repo 已存在，True = 先删除再重建，False = 抛出 ValueError。

    Returns
    -------
    int
        新建 repo 记录的 id。

    Raises
    ------
    FileNotFoundError
        repo_path 不存在或不是目录。
    ValueError
        同名 repo 已存在且 force=False。
    """
    # ① 路径规范化
    abs_path = os.path.abspath(repo_path)
    if not os.path.isdir(abs_path):
        raise FileNotFoundError(
            f"[init_repo] 仓库路径不存在或不是目录：{abs_path}"
        )

    # ② 仓库名：优先用传入参数，否则取目录名
    name = repo_name or os.path.basename(abs_path.rstrip(os.sep))

    # ③ 建库建表（幂等：schema 里全部用 CREATE TABLE IF NOT EXISTS）
    _db = db_path or DB_PATH
    init_db(_db)

    # ④ 检查同名记录
    existing = RepoDB.get_by_name(name, db_path=_db)
    if existing is not None:
        if force:
            RepoDB.delete(existing['id'], db_path=_db)
            print(f"[init_repo] 已删除旧记录 id={existing['id']}，准备重建。")
        else:
            raise ValueError(
                f"[init_repo] 仓库 '{name}' 已存在（id={existing['id']}）。"
                "如需重建，请传入 force=True 或手动删除旧记录。"
            )

    # ⑤ 写入新记录
    repo_id = RepoDB.create(name, abs_path, db_path=_db)
    print(
        f"[init_repo] ✓ 仓库 '{name}' 已初始化\n"
        f"            repo_id = {repo_id}\n"
        f"            path    = {abs_path}\n"
        f"            db      = {_db}"
    )
    return repo_id


# ==================================================================
#  analyze_repo_language  —— 内部辅助
# ==================================================================

def _scan_language_bytes(repo_path: str) -> dict[str, int]:
    """
    递归遍历仓库目录，对每个可识别文件累加字节数，返回 {语言: 字节数}。

    忽略规则：
      - _IGNORE_DIRS 中的目录
      - 无法识别扩展名且无特殊文件名的文件
      - 读取文件大小失败的文件（SymLink 断链等）
    """
    lang_bytes: dict[str, int] = {}

    for root, dirs, files in os.walk(repo_path, topdown=True):
        # 原地过滤：让 os.walk 不再递归进入忽略目录
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith('.')]

        for filename in files:
            # --- 语言判定 ---
            _, ext = os.path.splitext(filename)
            lang = _EXT_TO_LANG.get(ext.lower())

            # 无扩展名的特殊文件名匹配
            if lang is None:
                lower_name = filename.lower()
                if lower_name in ('makefile', 'gnumakefile'):
                    lang = 'Makefile'
                elif filename == 'CMakeLists.txt':
                    lang = 'CMake'

            if lang is None:
                continue  # 无法识别，跳过

            # --- 字节数统计 ---
            file_path = os.path.join(root, filename)
            try:
                size = os.path.getsize(file_path)
            except OSError:
                continue

            lang_bytes[lang] = lang_bytes.get(lang, 0) + size

    return lang_bytes


# ==================================================================
#  analyze_repo_language
# ==================================================================

def analyze_repo_language(
    repo_id: int,
    db_path: str | None = None,
) -> dict:
    """
    扫描仓库目录，统计各语言字节数和占比，确定主要编程语言，并写入数据库。

    主语言判定规则（按优先级）：
      1. 若字节数最多的语言属于代码型语言（非 _NON_CODE_LANGS），直接选取；
      2. 否则在 stats 列表中顺延，取第一个代码型语言；
      3. 若所有语言均为非代码型，则以字节数最多者兜底（罕见情形）。

    Parameters
    ----------
    repo_id : int
        目标仓库的 id（由 init_repo 返回）。
    db_path : str | None
        SQLite 数据库路径；不传则使用 config.DB_PATH。

    Returns
    -------
    dict
        写入 repo.language 字段的内容，格式：
        {
            "main": "C",
            "stats": [
                {"lang": "C",     "pct": 82.30, "bytes": 500000},
                {"lang": "CMake", "pct": 10.10, "bytes":  61000},
                ...               # 按 bytes 降序排列
            ]
        }

    Raises
    ------
    ValueError
        repo_id 在数据库中不存在。
    """
    _db = db_path or DB_PATH

    # ① 取仓库信息
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_repo_language] repo_id={repo_id} 不存在于数据库。")

    repo_path = repo['path']
    print(f"[analyze_repo_language] 开始扫描：{repo_path}")

    # ② 扫描并统计字节数
    lang_bytes = _scan_language_bytes(repo_path)

    # ③ 处理空仓库边界情形
    if not lang_bytes:
        print("[analyze_repo_language] ⚠ 未识别到任何代码文件。")
        language_data: dict = {"main": "Unknown", "stats": []}
        RepoDB.update(repo_id, db_path=_db, language=language_data)
        return language_data

    # ④ 计算总字节数 & 构造 stats 列表（按字节数降序）
    total_bytes = sum(lang_bytes.values())
    stats: list[dict] = sorted(
        [
            {
                "lang":  lang,
                "pct":   round(b / total_bytes * 100, 2),
                "bytes": b,
            }
            for lang, b in lang_bytes.items()
        ],
        key=lambda x: x["bytes"],
        reverse=True,
    )

    # ⑤ 确定主要语言
    main_lang: str = stats[0]["lang"]          # 默认：字节数最多
    for entry in stats:
        if entry["lang"] not in _NON_CODE_LANGS:
            main_lang = entry["lang"]
            break
    # 若所有语言均为非代码型，则 main_lang 保持 stats[0]["lang"]（已赋默认值）

    # ⑥ 组装 language 数据并写库
    language_data = {"main": main_lang, "stats": stats}
    RepoDB.update(repo_id, db_path=_db, language=language_data)

    # ⑦ 控制台摘要
    print(f"[analyze_repo_language] ✓ 主语言：{main_lang}")
    top_n = min(5, len(stats))
    print(f"[analyze_repo_language]   语言分布（Top {top_n}）：")
    for entry in stats[:top_n]:
        bar = "█" * int(entry["pct"] / 2)
        print(
            f"    {entry['lang']:18s} {entry['pct']:6.2f}%  "
            f"{entry['bytes']:>12,} bytes  {bar}"
        )

    return language_data
```

`test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_fake_repo.py`（已实现不记录）

`test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_minizip-ng.py`（已实现不记录）

`test_repo_analyzer_init_repo_and_analyze_repo_language_in_five_real_repo.py`（已实现不记录）



