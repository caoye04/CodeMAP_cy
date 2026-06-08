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
- 用minizip-ng这个仓库进行功能测试，路径（相对于codemap）`../../repo_4_codemap/minizip-ng/`
- AI调用统一用下面接口：https://api.ezai88.com/   gemini-2.5-flash  apitoken_me（已加密）

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

`test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_five_repo.py`（已实现不记录）

### Step3：`analyze_repo_area`实现

`config.py`

```
"""
config.py —— 全局配置入口
"""
import os

# ------------------------------------------------------------------
#  路径
# ------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(PROJECT_ROOT, 'data')
DB_PATH      = os.path.join(DATA_DIR, 'codemap.db')

# ------------------------------------------------------------------
#  LLM
# ------------------------------------------------------------------
LLM_API_KEY  = os.getenv('LLM_API_KEY',  'apitoken_me')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.ezai88.com')
LLM_MODEL    = os.getenv('LLM_MODEL',    'gemini-2.5-flash')

# ------------------------------------------------------------------
#  CodeQL（占位，后续填入）
# ------------------------------------------------------------------
CODEQL_BIN   = os.getenv('CODEQL_BIN', 'codeql')
```

`llm/client`

```
"""
llm/client.py
LLM 调用统一封装，支持 OpenAI 兼容接口（含 ezai88.com 代理）。

对外暴露：
  chat_completion()       → str
  chat_completion_json()  → dict | list
"""

import json
import os
import re
import sys
from typing import Optional, Union

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


# ==================================================================
#  核心调用
# ==================================================================

def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 8192,
    response_format: Optional[dict] = None,
    timeout: int = 180,
) -> str:
    """
    调用 LLM chat completion 接口，返回模型输出文本。

    Parameters
    ----------
    messages : list[dict]
        格式：[{"role": "system"/"user"/"assistant", "content": "..."}, ...]
    model : str | None
        模型名；不传则用 config.LLM_MODEL
    temperature : float
        随机性控制，0.0 = 最确定性
    max_tokens : int
        最大输出 token 数
    response_format : dict | None
        如 {"type": "json_object"} 开启 JSON 模式（部分接口支持）
    timeout : int
        HTTP 请求超时秒数

    Returns
    -------
    str
        模型生成的文本（choices[0].message.content）

    Raises
    ------
    RuntimeError
        网络错误、HTTP 错误或响应格式异常
    """
    base_url = LLM_BASE_URL.rstrip('/')
    url      = f"{base_url}/v1/chat/completions"
    _model   = model or LLM_MODEL

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type":  "application/json",
    }

    payload: dict = {
        "model":       _model,
        "messages":    messages,
        "temperature": temperature,
        "max_tokens":  max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"[LLM] 请求超时（>{timeout}s），建议增大 timeout 参数。")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"[LLM] 网络连接失败：{e}")
    except requests.exceptions.HTTPError:
        raise RuntimeError(
            f"[LLM] HTTP {resp.status_code} 错误：{resp.text[:400]}"
        )

    try:
        data    = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content
    except (KeyError, IndexError, ValueError) as e:
        raise RuntimeError(
            f"[LLM] 响应解析失败：{e}\n原始响应（前600字符）：{resp.text[:600]}"
        ) from e


def chat_completion_json(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 8192,
    timeout: int = 180,
) -> Union[dict, list]:
    """
    调用 LLM 并自动将输出解析为 Python dict / list。

    不强制依赖 response_format=json_object（兼容性更好），
    而是依靠 prompt 工程 + _extract_json() 健壮解析。

    Returns
    -------
    dict | list

    Raises
    ------
    ValueError   : 无法从输出中提取合法 JSON
    RuntimeError : 底层 HTTP 调用失败
    """
    raw = chat_completion(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    return _extract_json(raw)


# ==================================================================
#  JSON 健壮提取
# ==================================================================

def _extract_json(text: str) -> Union[dict, list]:
    """
    从 LLM 输出中健壮地提取 JSON。

    尝试顺序：
    1. 直接解析整段文本
    2. 从 ```json ... ``` 代码块提取
    3. 从 ``` ... ``` 代码块提取
    4. 找到最外层的 { ... } 或 [ ... ] 区间提取
    """
    stripped = text.strip()

    # 1. 直接解析
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 2 & 3. Markdown 代码块提取
    for pattern in [r'```json\s*\n?([\s\S]*?)\n?```', r'```\s*\n?([\s\S]*?)\n?```']:
        for m in re.finditer(pattern, text, re.DOTALL):
            candidate = m.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    # 4. 找最外层括号区间
    for open_c, close_c in [('{', '}'), ('[', ']')]:
        start = text.find(open_c)
        if start == -1:
            continue
        end = text.rfind(close_c)
        if end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

    raise ValueError(
        f"[LLM] 无法从输出中提取合法 JSON。\n"
        f"原始输出（前800字符）：\n{text[:800]}"
    )
```

`llm/prompts`

````
"""
llm/prompts.py
所有 LLM Prompt 模板集中管理。

命名规范：
  <STEP>_SYSTEM  —— system 消息（固定文本）
  <STEP>_USER    —— user 消息模板（含 {placeholder}）
"""

# ==================================================================
#  Step 3: analyze_repo_area —— 仓库模块划分
# ==================================================================

ANALYZE_REPO_AREA_SYSTEM = """\
你是一位资深软件架构师，擅长分析代码仓库结构并识别逻辑模块边界。

## 任务
根据给定的仓库目录结构和背景信息，将仓库划分为若干个逻辑 "area"（功能区域/模块），\
每个 area 代表一个内聚的功能单元。

## Area 概念说明
- 一个 area 通常对应一个独立的目录，但根目录下的核心散落文件也可构成一个 area
- 粒度适中：3-12 个 area 为宜（小型库偏少，大型单体仓库可更多）
- 每个 area 应具有明确、独立的职责，与其他 area 低耦合

## 严格输出要求
只输出合法 JSON，结构如下，不得包含任何额外解释文字：
```json
{
  "areas": [
    {
      "name":      "area 的英文短名称（snake_case，如 core_compression）",
      "path":      "相对仓库根的路径，如 'src/compress'；根目录用 '.'",
      "rationale": "分层依据（中文，1-3句，说明为何这是独立功能模块）",
      "brief":     "一句话简短描述（中文，不超过25字）"
    }
  ]
}
```

## 约束
path 必须是目录树中真实存在的路径（目录或 "."），不得捏造
同一 path 不得重复出现
不要把 .git、build、dist、pycache、node_modules 等构建/版本控制目录列入
若仓库根目录本身包含大量核心代码（无明显子目录分层），可将 "." 作为一个 area
"""
ANALYZE_REPO_AREA_USER = """\

## 仓库基本信息
仓库名：{repo_name}
主要语言：{main_language}

## 目标结构（最多展示3层）
```
{dir_tree}
```

## README 内容摘要
{readme_content}

请根据以上信息完成 area 划分，输出符合要求的 JSON。
"""
````

`analyzer/repo_analyzer.py`更新

```
# init_repo / analyze_repo_*
"""
analyzer/repo_analyzer.py
CodeMAP 仓库层分析器

实现：
  - init_repo              : 初始化仓库记录，建库建表，写入 repo:name / repo:path
  - analyze_repo_language  : 扫描仓库文件，统计语言字节数和占比，写入 repo:language
  - analyze_repo_area      : LLM 分析仓库模块划分，写入 area 表 / repo:arealist
"""

import json as _json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB, AreaDB
from config import DB_PATH, DATA_DIR

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

# ==================================================================
#  analyze_repo_area —— 辅助：目录树 & README
# ==================================================================

def _build_dir_tree(repo_path: str, max_depth: int = 3, max_chars: int = 8000) -> str:
    """
    生成仓库目录树字符串（类 Unix `tree` 命令格式）。

    Parameters
    ----------
    repo_path : str
        仓库根目录绝对路径
    max_depth : int
        最大递归深度（从根算起，根的直接子项为第 1 层）
    max_chars : int
        输出字符上限，超出后追加截断提示

    Returns
    -------
    str
        多行字符串，可直接放入 prompt
    """
    lines: list[str] = []
    root_name = os.path.basename(repo_path.rstrip(os.sep))
    lines.append(f"{root_name}/")

    def _walk(path: str, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return

        try:
            raw = list(os.scandir(path))
        except PermissionError:
            return

        # 过滤忽略目录和隐藏目录
        entries = [
            e for e in raw
            if not (e.is_dir() and (e.name in _IGNORE_DIRS or e.name.startswith('.')))
        ]
        # 排序：目录在前，同类按名称字母序（忽略大小写）
        entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

        for i, entry in enumerate(entries):
            is_last   = (i == len(entries) - 1)
            connector = '└── ' if is_last else '├── '
            suffix    = '/' if entry.is_dir() else ''
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")

            if entry.is_dir() and depth < max_depth:
                child_prefix = prefix + ('    ' if is_last else '│   ')
                _walk(entry.path, child_prefix, depth + 1)

    _walk(repo_path, '', 1)

    result = '\n'.join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + '\n...(目录树已截断，超过字符上限)'
    return result


def _read_readme(repo_path: str, max_chars: int = 3000) -> str:
    """
    读取仓库根目录的 README 文件内容（截取前 max_chars 字符）。

    Returns
    -------
    str
        README 内容，或 "（未找到 README 文件）"
    """
    candidates = [
        'README.md', 'README.rst', 'README.txt', 'README',
        'readme.md', 'readme.rst', 'readme.txt', 'readme',
        'Readme.md', 'Readme.rst',
    ]
    for name in candidates:
        full_path = os.path.join(repo_path, name)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(max_chars)
            file_size = os.path.getsize(full_path)
            suffix = '\n\n...(README 已截断，仅展示前部分)' if file_size > max_chars else ''
            print(f"[analyze_repo_area] 读取 README：{name}（{len(content)} 字符）")
            return content + suffix
        except OSError:
            continue
    return '（未找到 README 文件）'


# ==================================================================
#  analyze_repo_area
# ==================================================================

def analyze_repo_area(
    repo_id: int,
    db_path: str | None = None,
    force: bool = False,
) -> list[dict]:
    """
    使用 LLM 对仓库进行模块划分（area 分层），并将结果持久化到数据库和中间文件。

    流程
    ----
    1. 构建仓库目录树（最多 3 层）
    2. 读取 README（作为 LLM 背景输入）
    3. 调用 LLM 生成 area 划分方案（name / path / rationale / brief）
    4. 校验 LLM 给出的 path 在磁盘上确实存在，去掉无效项
    5. 中间产物 JSON → data/analyze_repo_area/<repo_name>.json
    6. 写数据库：
       - area 表：为每个 area 创建记录（name / path / rationale）
       - repo 表：更新 arealist 字段（存简要索引）

    Parameters
    ----------
    repo_id : int
        目标仓库的 id（由 init_repo 返回）
    db_path : str | None
        SQLite 数据库路径；不传则使用 config.DB_PATH
    force : bool
        若已存在 area 记录，True = 先删除再重建，False = 抛出 ValueError

    Returns
    -------
    list[dict]
        已入库的 area 信息列表，每项：
        {
            "area_id":   int,
            "name":      str,
            "path":      str,   # 相对仓库根
            "rationale": str,
            "brief":     str,
        }

    Raises
    ------
    ValueError
        repo_id 不存在 / force=False 且已有 area 记录 / LLM 无有效输出
    RuntimeError
        LLM API 调用失败
    """
    _db = db_path or DB_PATH

    # ── ① 取仓库信息 ────────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_repo_area] repo_id={repo_id} 在数据库中不存在。"
        )

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[analyze_repo_area] 目标仓库：{repo_name}（{repo_path}）")

    # ── ② 处理已有 area 记录 ────────────────────────────────────────
    existing = AreaDB.list_by_repo(repo_id, db_path=_db)
    if existing:
        if force:
            for a in existing:
                AreaDB.delete(a['id'], db_path=_db)
            print(f"[analyze_repo_area] 已清除 {len(existing)} 条旧 area 记录。")
        else:
            raise ValueError(
                f"[analyze_repo_area] repo_id={repo_id} 已有 {len(existing)} 个 area 记录。"
                " 如需重新分析，请传入 force=True。"
            )

    # ── ③ 收集上下文信息 ────────────────────────────────────────────
    language_info = repo.get('language') or {}
    main_language = (
        language_info.get('main', 'Unknown')
        if isinstance(language_info, dict)
        else 'Unknown'
    )

    dir_tree       = _build_dir_tree(repo_path, max_depth=3)
    readme_content = _read_readme(repo_path)

    print(
        f"[analyze_repo_area] 上下文准备完毕 | "
        f"主语言：{main_language} | "
        f"目录树：{len(dir_tree)} 字符 | "
        f"README：{len(readme_content)} 字符"
    )

    # ── ④ 调用 LLM ──────────────────────────────────────────────────
    # 延迟导入：仅在需要时加载 LLM 模块，避免无关步骤引入额外依赖
    from llm.client  import chat_completion_json
    from llm.prompts import ANALYZE_REPO_AREA_SYSTEM, ANALYZE_REPO_AREA_USER
    import config as _cfg

    user_content = ANALYZE_REPO_AREA_USER.format(
        repo_name      = repo_name,
        main_language  = main_language,
        dir_tree       = dir_tree,
        readme_content = readme_content,
    )

    messages = [
        {"role": "system", "content": ANALYZE_REPO_AREA_SYSTEM},
        {"role": "user",   "content": user_content},
    ]

    print(f"[analyze_repo_area] 调用 LLM（模型：{_cfg.LLM_MODEL}）…")
    llm_raw = chat_completion_json(messages=messages, temperature=0.3)
    print(f"[analyze_repo_area] LLM 响应已接收，开始解析…")

    # ── ⑤ 解析 LLM 输出结构 ────────────────────────────────────────
    if isinstance(llm_raw, dict) and 'areas' in llm_raw:
        areas_raw: list[dict] = llm_raw['areas']
    elif isinstance(llm_raw, list):
        areas_raw = llm_raw
    else:
        raise ValueError(
            f"[analyze_repo_area] LLM 输出结构不符合预期（类型：{type(llm_raw)}）：\n"
            f"{_json.dumps(llm_raw, ensure_ascii=False, indent=2)[:600]}"
        )

    # ── ⑥ 字段提取 + 路径校验 + 去重 ───────────────────────────────
    seen_paths: set[str] = set()
    validated:  list[dict] = []

    for item in areas_raw:
        name      = str(item.get('name',      '')).strip()
        path      = str(item.get('path',      '')).strip()
        rationale = str(item.get('rationale', '')).strip()
        brief     = str(item.get('brief',     '')).strip()

        # 必填字段检查
        if not name or not path:
            print(f"[analyze_repo_area] ⚠ 跳过缺少 name/path 的条目：{item}")
            continue

        # 路径去重
        if path in seen_paths:
            print(f"[analyze_repo_area] ⚠ 跳过重复 path：{path}")
            continue
        seen_paths.add(path)

        # 磁盘存在性校验
        abs_path = repo_path if path == '.' else os.path.join(repo_path, path)
        if not os.path.exists(abs_path):
            print(f"[analyze_repo_area] ⚠ path 在磁盘上不存在，已跳过：{path}")
            continue

        validated.append({
            'name':      name,
            'path':      path,
            'rationale': rationale,
            'brief':     brief,
        })

    if not validated:
        raise ValueError(
            "[analyze_repo_area] 所有 LLM 输出的 area 均未通过校验，请查看上方日志。"
        )

    # ── ⑦ 保存中间产物 JSON ─────────────────────────────────────────
    output_dir = os.path.join(DATA_DIR, 'analyze_repo_area')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{repo_name}.json")

    intermediate = {
        'repo_id':       repo_id,
        'repo_name':     repo_name,
        'repo_path':     repo_path,
        'main_language': main_language,
        'llm_raw':       llm_raw,
        'areas':         validated,
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        _json.dump(intermediate, f, ensure_ascii=False, indent=2)
    print(f"[analyze_repo_area] ✓ 中间产物 → {output_path}")

    # ── ⑧ 写入数据库 ────────────────────────────────────────────────
    arealist: list[dict] = []

    for area_data in validated:
        area_id = AreaDB.create(
            repo_id   = repo_id,
            name      = area_data['name'],
            path      = area_data['path'],
            rationale = area_data['rationale'],
            db_path   = _db,
        )
        area_data['area_id'] = area_id  # 回写 id，供调用方使用

        arealist.append({
            'area_id': area_id,
            'name':    area_data['name'],
            'brief':   area_data['brief'],
        })

        print(
            f"[analyze_repo_area]   + [{area_id:3d}] "
            f"{area_data['name']:30s}  path={area_data['path']}"
        )

    # 更新 repo.arealist（简要索引）
    RepoDB.update(repo_id, db_path=_db, arealist=arealist)

    print(
        f"[analyze_repo_area] ✓ 完成：{len(validated)} 个 area 已入库，"
        f"repo.arealist 已更新。"
    )
    return validated
```

`test/test_repo_analyzer_analyze_repo_area_in_minizip-ng.py`（已实现不记录）

`test/test_repo_analyzer_analyze_repo_area_in_five_repo.py`（已实现不记录）

### step4：`analyze_area_file`实现

`analyzer/area_analyzer.py`

```
"""
analyzer/area_analyzer.py
CodeMAP Area 层分析器

实现：
  - analyze_area_file : 扫描每个 area 路径下的文件结构，
                        写入 file 表并更新 area.filelist，
                        中间产物保存至 data/analyze_area_file/<repo_name>.json
"""

import json as _json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, AreaDB, FileDB
from config import DB_PATH, DATA_DIR


# ------------------------------------------------------------------
#  ① 过滤黑名单：需要跳过的文件扩展名
#     原则：二进制、编译产物、媒体、打包归档、临时文件 —— 无代码分析价值
# ------------------------------------------------------------------
_SKIP_EXTENSIONS: frozenset[str] = frozenset({
    # 编译 / 链接产物
    '.o', '.obj', '.a', '.lib', '.so', '.dll', '.dylib',
    '.exe', '.out', '.elf', '.ko', '.lo', '.la',
    # Python 字节码
    '.pyc', '.pyo', '.pyd',
    # Java 字节码 / 打包
    '.class', '.jar', '.war', '.ear',
    # Node 构建产物
    '.map',
    # 图片
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico',
    '.svg', '.webp', '.tiff', '.tif', '.raw', '.heic',
    # 音视频
    '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.wav', '.flac', '.ogg', '.webm',
    # 压缩包 / 归档
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.zst', '.lz4', '.lzma',
    # 字体
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    # Office / PDF
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods',
    # 数据库文件
    '.db', '.sqlite', '.sqlite3',
    # 其他二进制数据
    '.bin', '.dat', '.iso', '.img',
    # 调试符号
    '.pdb',
    # 覆盖率 / 性能分析产物
    '.gcda', '.gcno', '.profraw', '.profdata',
    # 临时 / 备份
    '.bak', '.swp', '.swo', '.orig', '.tmp', '.temp',
    # 锁文件（带扩展名的）
    '.lock',
    # 证书 / 密钥
    '.pem', '.key', '.crt', '.cer', '.p12', '.pfx', '.der',
    # 版本控制补丁（不属于源码）
    '.patch', '.diff',
})

# ------------------------------------------------------------------
#  ② 过滤黑名单：需要跳过的具体文件名（小写比较）
# ------------------------------------------------------------------
_SKIP_FILENAMES: frozenset[str] = frozenset({
    # 系统残留
    '.ds_store', 'thumbs.db', 'desktop.ini',
    # 包管理锁文件
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'poetry.lock', 'pipfile.lock', 'cargo.lock',
    'composer.lock', 'gemfile.lock', 'mix.lock', 'packages.lock.json',
    # VCS 配置（隐藏文件过滤已覆盖大部分，这里补充非隐藏的）
    '.gitignore', '.gitattributes', '.gitmodules', '.gitkeep',
    # 编辑器 / 格式化配置
    '.editorconfig', '.clang-format', '.clang-tidy',
    '.prettierrc', '.eslintrc', '.babelrc', '.stylelintrc',
    # Docker / CI 元信息
    '.npmignore', '.dockerignore', '.mailmap',
    # compile_commands.json：clang 工具链产物，非源码
    'compile_commands.json',
})

# ------------------------------------------------------------------
#  ③ 遍历时跳过的目录（与 repo_analyzer.py 完全保持一致）
# ------------------------------------------------------------------
_IGNORE_DIRS: frozenset[str] = frozenset({
    '.git', '.svn', '.hg',
    '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache',
    'node_modules',
    '.venv', 'venv', 'env', '.env',
    'build', 'dist', '.build', 'out', 'target', 'cmake-build-debug',
    '.idea', '.vscode',
    'vendor',
})


# ==================================================================
#  内部辅助函数
# ==================================================================

def _is_useful_file(filename: str) -> bool:
    """
    判断文件名是否值得纳入 CodeMAP 分析。

    过滤逻辑（按顺序）：
      1. 以 '.' 开头的隐藏文件 → 跳过
      2. 扩展名在 _SKIP_EXTENSIONS 黑名单 → 跳过
      3. 文件名（小写）在 _SKIP_FILENAMES 黑名单 → 跳过
      4. 其余文件 → 保留（宁可多扫，后续步骤可按语言再做筛选）

    Parameters
    ----------
    filename : str
        仅文件名，不含路径

    Returns
    -------
    bool
    """
    if filename.startswith('.'):
        return False

    _, ext = os.path.splitext(filename)
    if ext.lower() in _SKIP_EXTENSIONS:
        return False

    if filename.lower() in _SKIP_FILENAMES:
        return False

    return True


def _scan_area_files(
    area_abs_path: str,
    repo_path: str,
    other_area_abs_paths: set[str],
) -> list[dict]:
    """
    递归扫描 area 目录，返回所有有效文件的 name + path 列表。

    关键设计：**不递归进入属于其他 area 的子目录**，从根源上避免
    同一文件被重复归属到多个 area（当 area 路径存在包含关系时尤其重要，
    例如 area='.' 与 area='src/' 同时存在）。

    Parameters
    ----------
    area_abs_path : str
        当前 area 目录的绝对路径
    repo_path : str
        仓库根目录的绝对路径（用于计算 file 的相对路径）
    other_area_abs_paths : set[str]
        其他所有 area 的绝对路径集合；遇到匹配的子目录时跳过

    Returns
    -------
    list[dict]
        每项 {"name": str, "path": str}
        path 相对于仓库根，统一使用 '/' 分隔符
    """
    collected: list[dict] = []

    for root, dirs, filenames in os.walk(area_abs_path, topdown=True):
        # ---------- 过滤子目录 ----------
        dirs_keep: list[str] = []
        for d in sorted(dirs):
            # 忽略列表 & 隐藏目录
            if d in _IGNORE_DIRS or d.startswith('.'):
                continue
            # 属于另一个独立 area 的目录 → 不递归，由该 area 自行扫描
            child_abs = os.path.normpath(os.path.join(root, d))
            if child_abs in other_area_abs_paths:
                continue
            dirs_keep.append(d)
        dirs[:] = dirs_keep

        # ---------- 收集文件 ----------
        for filename in sorted(filenames):
            if not _is_useful_file(filename):
                continue

            file_abs = os.path.join(root, filename)
            try:
                rel_path = os.path.relpath(file_abs, repo_path)
                # 统一使用 '/' 分隔符（Windows 兼容）
                rel_path = rel_path.replace(os.sep, '/')
            except ValueError:
                # Windows 跨盘符时 relpath 可能抛 ValueError
                continue

            collected.append({
                'name': filename,
                'path': rel_path,
            })

    return collected


# ==================================================================
#  analyze_area_file
# ==================================================================

def analyze_area_file(
    repo_id: int,
    db_path: str | None = None,
    force: bool = False,
) -> dict[int, list[dict]]:
    """
    扫描仓库每个 area 路径下的文件，写入 file 表并更新 area.filelist。

    流程
    ----
    1. 读取仓库信息和所有 area 记录
    2. 预计算各 area 的绝对路径，构造互斥集合（防重叠扫描）
    3. 对每个 area 递归扫描文件，_is_useful_file() 过滤无效文件
    4. 将文件写入 file 表（name / path），防御性地检测路径重复
    5. 更新 area.filelist（file_id + name，brief 留空待后续步骤填充）
    6. 汇总写出中间产物 JSON → data/analyze_area_file/<repo_name>.json

    数据库写入字段
    --------------
    - file.name   : 文件名（basename）
    - file.path   : 相对仓库根的路径，'/' 分隔
    - area.filelist: [{"file_id": int, "name": str, "brief": ""}]

    Parameters
    ----------
    repo_id : int
        目标仓库 id（由 init_repo 返回）
    db_path : str | None
        SQLite 数据库路径；不传则使用 config.DB_PATH
    force : bool
        若已存在 file 记录：
          True  = 先清除所有旧 file 记录再重建
          False = 抛出 ValueError

    Returns
    -------
    dict[int, list[dict]]
        键为 area_id，值为该 area 下已入库的文件列表，每项：
        {
            "file_id": int,
            "name":    str,
            "path":    str,  # 相对仓库根，'/' 分隔
        }

    Raises
    ------
    ValueError
        · repo_id 在数据库中不存在
        · 该仓库尚无 area 记录（需先执行 analyze_repo_area）
        · force=False 且已有 file 记录
    """
    _db = db_path or DB_PATH

    # ── ① 取仓库信息 ────────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_area_file] repo_id={repo_id} 在数据库中不存在。"
        )

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[analyze_area_file] 目标仓库：{repo_name}（{repo_path}）")

    # ── ② 取 area 列表 ──────────────────────────────────────────────
    areas = AreaDB.list_by_repo(repo_id, db_path=_db)
    if not areas:
        raise ValueError(
            f"[analyze_area_file] repo_id={repo_id} 无 area 记录，"
            "请先执行 analyze_repo_area。"
        )
    print(f"[analyze_area_file] 共 {len(areas)} 个 area，开始扫描文件…")

    # ── ③ 处理已有 file 记录 ────────────────────────────────────────
    existing_files = FileDB.list_by_repo(repo_id, db_path=_db)
    if existing_files:
        if force:
            for f in existing_files:
                FileDB.delete(f['id'], db_path=_db)
            print(f"[analyze_area_file] 已清除 {len(existing_files)} 条旧 file 记录。")
        else:
            raise ValueError(
                f"[analyze_area_file] repo_id={repo_id} 已有 {len(existing_files)} 个 file 记录。"
                " 如需重新扫描，请传入 force=True。"
            )

    # ── ④ 预计算各 area 绝对路径 ────────────────────────────────────
    # normpath 确保路径字符串可直接用集合匹配，Windows 下统一反斜杠
    area_abs_map: dict[int, str] = {}
    for area in areas:
        rel = area['path']
        abs_p = (
            repo_path
            if rel == '.'
            else os.path.normpath(os.path.join(repo_path, rel))
        )
        area_abs_map[area['id']] = abs_p

    # ── ⑤ 逐 area 扫描文件 ──────────────────────────────────────────
    result: dict[int, list[dict]]   = {}
    all_area_records: list[dict]    = []   # 用于中间产物 JSON

    for area in areas:
        area_id       = area['id']
        area_name     = area['name']
        area_path_rel = area['path']
        area_abs      = area_abs_map[area_id]

        # 路径不存在时发出警告并跳过（LLM 给出的路径可能已被删除/重命名）
        if not os.path.exists(area_abs):
            print(
                f"[analyze_area_file] ⚠ area '{area_name}' 路径不存在，"
                f"已跳过：{area_abs}"
            )
            result[area_id] = []
            continue

        # 当前 area 以外的所有 area 绝对路径（扫描时不递归进入）
        other_abs: set[str] = {
            p for aid, p in area_abs_map.items() if aid != area_id
        }

        print(
            f"[analyze_area_file]   扫描 area [{area_id:3d}] "
            f"'{area_name}'（{area_path_rel}）…"
        )

        raw_files = _scan_area_files(area_abs, repo_path, other_abs)
        print(f"[analyze_area_file]     → 发现 {len(raw_files)} 个有效文件")

        # ── ⑥ 写入 file 表 ──────────────────────────────────────────
        area_filelist:      list[dict] = []   # 写回 area.filelist
        area_file_records:  list[dict] = []   # 供调用方和中间产物使用

        for file_info in raw_files:
            file_name = file_info['name']
            file_path = file_info['path']   # 相对仓库根

            # 防御：若同一路径已存在（area 路径部分重叠时），不重复创建
            existing_file = FileDB.get_by_path(repo_id, file_path, db_path=_db)
            if existing_file is not None:
                file_id = existing_file['id']
                print(
                    f"[analyze_area_file]     ⚠ 路径已存在（area 路径重叠？）："
                    f"{file_path} → 复用 file_id={file_id}"
                )
            else:
                file_id = FileDB.create(
                    repo_id = repo_id,
                    area_id = area_id,
                    name    = file_name,
                    path    = file_path,
                    db_path = _db,
                )

            area_filelist.append({
                'file_id': file_id,
                'name':    file_name,
                'brief':   '',      # 留给 analyze_area_filelist_description（step16）填充
            })
            area_file_records.append({
                'file_id': file_id,
                'name':    file_name,
                'path':    file_path,
            })

        # ── ⑦ 更新 area.filelist ────────────────────────────────────
        AreaDB.update(area_id, db_path=_db, filelist=area_filelist)

        result[area_id] = area_file_records
        all_area_records.append({
            'area_id':    area_id,
            'area_name':  area_name,
            'area_path':  area_path_rel,
            'file_count': len(area_file_records),
            'files':      area_file_records,
        })

        print(
            f"[analyze_area_file]     ✓ '{area_name}'："
            f"{len(area_file_records)} 个文件已入库"
        )

    # ── ⑧ 保存中间产物 JSON ─────────────────────────────────────────
    output_dir  = os.path.join(DATA_DIR, 'analyze_area_file')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{repo_name}.json")

    total_files = sum(len(v) for v in result.values())
    intermediate = {
        'repo_id':   repo_id,
        'repo_name': repo_name,
        'repo_path': repo_path,
        'summary': {
            'total_areas': len(areas),
            'total_files': total_files,
        },
        'areas': all_area_records,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        _json.dump(intermediate, f, ensure_ascii=False, indent=2)
    print(f"[analyze_area_file] ✓ 中间产物 → {output_path}")

    print(
        f"[analyze_area_file] ✓ 完成：{len(areas)} 个 area，"
        f"共 {total_files} 个文件已入库。"
    )
    return result
```

`test/test_area_analyzer_analyze_area_file_in_minizip-ng.py`

```
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
```

### Step5：`analyze_file_language`和`analyze_file_func`实现

`llm/prompts.py`更新

````
# ==================================================================
#  Step 5: analyze_file_func —— 文件函数提取（LLM 兜底）
# ==================================================================

ANALYZE_FILE_FUNC_SYSTEM = """\
你是一位代码静态分析专家，擅长解析各种编程语言的函数结构。

## 任务
从给定的源代码文件中提取所有函数/方法定义，输出结构化 JSON。

## 严格输出要求
只输出合法 JSON，不含任何解释文字：
```json
{
  "functions": [
    {
      "name": "函数名（不含类名前缀，如 init_stream 而非 Stream::init_stream）",
      "signature": "完整函数签名字符串（与源码保持一致，含返回类型、函数名、参数列表）",
      "start_line": 42,
      "end_line": 105,
      "params": [
        {"name": "参数名", "type": "参数类型", "desc": ""}
      ],
      "returns": {"type": "返回值类型", "desc": ""}
    }
  ]
}
```

## 规则
- 仅提取有函数体（含 `{}` 或 Python 冒号+缩进块）的函数定义
- 若是头文件（.h / .hpp）：同时提取仅有声明（无函数体）的函数，此时 start_line = end_line = 声明首行
- Python：提取所有 `def` 和 `async def`，包括嵌套函数和类方法
- C/C++：跳过 `#define` 宏，不提取纯类型别名声明
- 行号严格匹配源码 "行号 | 代码" 格式中的数字（从 1 开始）
- end_line 应为函数结束行（含闭合花括号 `}` 或 Python 最后一行缩进）
- 参数列表按源码顺序列出，包括 self、this 等
- 若函数无返回值，returns.type 填 "void"（C/C++）或 "None"（Python）
- 若文件中无函数，返回 {"functions": []}
"""

ANALYZE_FILE_FUNC_USER = """\
## 文件信息
文件名：{file_name}
编程语言：{language}
文件路径：{file_path}

## 源代码（含行号，格式：行号 | 代码）
```{lang_lower}
{numbered_content}
```

请提取所有函数并输出符合要求的 JSON。
"""
````

`analyzer/file_analyzer.py`

```
"""
analyzer/file_analyzer.py
CodeMAP File 层分析器

实现：
  - analyze_file_language : 根据文件扩展名确定编程语言，批量写入 file.language
  - analyze_file_func     : 提取文件中所有函数/方法，写入 func 表并更新 file.funclist

函数提取策略（按优先级）：
  Python       → Python ast 模块（精确，覆盖嵌套函数/方法）
  C/C++/其他   → Universal Ctags（若可用）+ 源码签名解析补充 io
  兜底          → LLM 全文提取（文件 ≤ _MAX_LINES_LLM 行时）
"""

import ast
import json as _json
import os
import re
import subprocess
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, FileDB, FuncDB
from config import DB_PATH, DATA_DIR


# ══════════════════════════════════════════════════════════════════
#  常量与映射表
# ══════════════════════════════════════════════════════════════════

_EXT_TO_LANG: dict[str, str] = {
    # C / C++
    '.c': 'C', '.h': 'C',
    '.cpp': 'C++', '.cxx': 'C++', '.cc': 'C++',
    '.hpp': 'C++', '.hxx': 'C++',
    # Python
    '.py': 'Python',
    # Java
    '.java': 'Java',
    # JavaScript / TypeScript
    '.js': 'JavaScript', '.jsx': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript',
    # Go
    '.go': 'Go',
    # Rust
    '.rs': 'Rust',
    # Shell
    '.sh': 'Shell', '.bash': 'Shell', '.zsh': 'Shell',
    # CMake
    '.cmake': 'CMake',
    # Ruby
    '.rb': 'Ruby',
    # Swift
    '.swift': 'Swift',
    # Kotlin
    '.kt': 'Kotlin', '.kts': 'Kotlin',
    # Scala
    '.scala': 'Scala',
    # Haskell
    '.hs': 'Haskell',
    # Assembly
    '.asm': 'Assembly', '.s': 'Assembly',
    # Lua
    '.lua': 'Lua',
    # Perl
    '.pl': 'Perl', '.pm': 'Perl',
    # Fortran
    '.f': 'Fortran', '.f90': 'Fortran', '.f95': 'Fortran',
    # MATLAB / Objective-C
    '.m': 'MATLAB', '.mm': 'Objective-C',
    # 配置 / 文档类
    '.md': 'Markdown', '.rst': 'reStructuredText',
    '.yaml': 'YAML', '.yml': 'YAML',
    '.json': 'JSON', '.xml': 'XML',
    '.html': 'HTML', '.htm': 'HTML',
    '.css': 'CSS', '.sql': 'SQL',
    '.toml': 'TOML', '.ini': 'INI', '.cfg': 'INI',
}

# 通常不含函数定义的语言 → 跳过函数提取
_NO_FUNC_LANGS: frozenset[str] = frozenset({
    'Markdown', 'reStructuredText', 'YAML', 'JSON', 'XML',
    'HTML', 'CSS', 'SQL', 'TOML', 'INI',
    'CMake', 'Makefile', 'Assembly', 'Unknown',
})

# ctags 语言名映射（Universal Ctags --languages 参数）
_CTAGS_LANG_MAP: dict[str, str] = {
    'C': 'C', 'C++': 'C++', 'Objective-C': 'ObjectiveC',
    'Python': 'Python', 'Java': 'Java',
    'JavaScript': 'JavaScript', 'TypeScript': 'TypeScript',
    'Go': 'Go', 'Rust': 'Rust', 'Ruby': 'Ruby',
    'Swift': 'Swift', 'Kotlin': 'Kotlin',
    'Scala': 'Scala', 'Lua': 'Lua', 'Shell': 'Sh',
}

# ctags kind 字符集合 → 视为"函数"
_FUNC_KINDS: frozenset[str] = frozenset({
    'f', 'function',
    'm', 'method',
    'p', 'prototype',
    's', 'subroutine',
    'procedure',
})

_MAX_LINES_LLM   = 3000       # 超过此行数时截断发给 LLM
_MAX_BYTES_READ  = 1_000_000  # 单文件最大读取字节（1 MB）

# ctags 可用性缓存（None = 未检测）
_ctags_ok: bool | None = None


# ══════════════════════════════════════════════════════════════════
#  语言检测
# ══════════════════════════════════════════════════════════════════

def _detect_language(file_name: str) -> str:
    """根据文件名/扩展名推断编程语言，无法识别返回 'Unknown'。"""
    _, ext = os.path.splitext(file_name)
    lang = _EXT_TO_LANG.get(ext.lower())
    if lang is None:
        lower = file_name.lower()
        if lower in ('makefile', 'gnumakefile'):
            lang = 'Makefile'
        elif file_name == 'CMakeLists.txt':
            lang = 'CMake'
    return lang or 'Unknown'


# ══════════════════════════════════════════════════════════════════
#  analyze_file_language
# ══════════════════════════════════════════════════════════════════

def analyze_file_language(
    repo_id: int,
    db_path: str | None = None,
    file_id: int | None = None,
) -> dict[int, str]:
    """
    根据文件扩展名确定编程语言并持久化到 file.language。

    Parameters
    ----------
    repo_id : int
        目标仓库 id（由 init_repo 返回）
    db_path : str | None
        SQLite 路径；不传则使用 config.DB_PATH
    file_id : int | None
        若指定，则只处理该文件；否则处理 repo 下所有文件

    Returns
    -------
    dict[int, str]
        {file_id: language} 映射，language 如 "C" / "Python" / "Unknown"

    Raises
    ------
    ValueError
        repo_id 或 file_id 在数据库中不存在
    """
    _db = db_path or DB_PATH

    # ① 校验仓库
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_file_language] repo_id={repo_id} 不存在于数据库。"
        )

    # ② 确定目标文件列表
    if file_id is not None:
        file_rec = FileDB.get_by_id(file_id, db_path=_db)
        if file_rec is None:
            raise ValueError(
                f"[analyze_file_language] file_id={file_id} 不存在于数据库。"
            )
        files = [file_rec]
    else:
        files = FileDB.list_by_repo(repo_id, db_path=_db)

    if not files:
        print(
            f"[analyze_file_language] ⚠ repo_id={repo_id} 暂无文件记录，"
            "请先执行 analyze_area_file。"
        )
        return {}

    # ③ 批量检测并写库
    result: dict[int, str]      = {}
    lang_counter: dict[str, int] = {}

    for f in files:
        lang = _detect_language(f['name'])
        FileDB.update(f['id'], db_path=_db, language=lang)
        result[f['id']] = lang
        lang_counter[lang] = lang_counter.get(lang, 0) + 1

    # ④ 打印摘要
    total = len(files)
    print(f"[analyze_file_language] ✓ 处理 {total} 个文件，语言分布：")
    for lang, cnt in sorted(lang_counter.items(), key=lambda x: -x[1]):
        bar = '█' * min(cnt, 40)
        print(f"    {lang:22s}: {cnt:4d}  {bar}")

    return result


# ══════════════════════════════════════════════════════════════════
#  文件读取工具
# ══════════════════════════════════════════════════════════════════

def _read_file_safe(file_path: str) -> str | None:
    """
    安全读取文本文件。
    - 超过 _MAX_BYTES_READ 返回 None
    - 含大量 NUL 字节（二进制）返回 None
    - 依次尝试 utf-8 / latin-1 编码
    """
    try:
        if os.path.getsize(file_path) > _MAX_BYTES_READ:
            return None
    except OSError:
        return None

    for enc in ('utf-8', 'latin-1'):
        try:
            with open(file_path, 'r', encoding=enc, errors='replace') as fh:
                content = fh.read()
            if content.count('\x00') > 20:   # 粗判二进制文件
                return None
            return content
        except OSError:
            return None
    return None


def _add_line_numbers(content: str) -> tuple[str, int]:
    """
    给内容每行加行号前缀，超过 _MAX_LINES_LLM 时截断并追加提示。

    Returns
    -------
    (numbered_str, total_line_count)
    """
    lines = content.splitlines()
    total = len(lines)
    selected = lines[:_MAX_LINES_LLM]
    numbered = '\n'.join(f"{i + 1:5d} | {line}" for i, line in enumerate(selected))
    if total > _MAX_LINES_LLM:
        numbered += (
            f'\n... (文件共 {total} 行，已截断，仅展示前 {_MAX_LINES_LLM} 行)'
        )
    return numbered, total


# ══════════════════════════════════════════════════════════════════
#  策略 1：Python ast 提取
# ══════════════════════════════════════════════════════════════════

def _ann_str(node) -> str:
    """安全地将 ast 注解节点转为字符串，失败时返回空串。"""
    if node is None:
        return ''
    try:
        return ast.unparse(node)
    except Exception:
        return ''


def _build_py_signature(node: 'ast.FunctionDef | ast.AsyncFunctionDef') -> str:
    """从 ast 函数节点构建完整签名字符串。"""
    ao = node.args
    parts: list[str] = []
    defaults_offset = len(ao.args) - len(ao.defaults)

    for i, arg in enumerate(ao.args):
        ann = f': {_ann_str(arg.annotation)}' if arg.annotation else ''
        di  = i - defaults_offset
        try:
            default = f' = {ast.unparse(ao.defaults[di])}' if di >= 0 else ''
        except Exception:
            default = ''
        parts.append(f"{arg.arg}{ann}{default}")

    if ao.vararg:
        ann = f': {_ann_str(ao.vararg.annotation)}' if ao.vararg.annotation else ''
        parts.append(f"*{ao.vararg.arg}{ann}")
    elif ao.kwonlyargs:
        parts.append('*')

    for i, arg in enumerate(ao.kwonlyargs):
        ann = f': {_ann_str(arg.annotation)}' if arg.annotation else ''
        kd  = ao.kw_defaults[i]
        try:
            default = f' = {ast.unparse(kd)}' if kd is not None else ''
        except Exception:
            default = ''
        parts.append(f"{arg.arg}{ann}{default}")

    if ao.kwarg:
        ann = f': {_ann_str(ao.kwarg.annotation)}' if ao.kwarg.annotation else ''
        parts.append(f"**{ao.kwarg.arg}{ann}")

    ret_ann = f' -> {_ann_str(node.returns)}' if node.returns else ''
    prefix  = 'async def ' if isinstance(node, ast.AsyncFunctionDef) else 'def '
    return f"{prefix}{node.name}({', '.join(parts)}){ret_ann}"


def _build_py_params(node: 'ast.FunctionDef | ast.AsyncFunctionDef') -> list[dict]:
    """从 ast 函数节点提取参数列表。"""
    ao     = node.args
    params: list[dict] = []

    for arg in ao.args:
        params.append({'name': arg.arg, 'type': _ann_str(arg.annotation), 'desc': ''})
    if ao.vararg:
        params.append({
            'name': f'*{ao.vararg.arg}',
            'type': _ann_str(ao.vararg.annotation),
            'desc': '',
        })
    for arg in ao.kwonlyargs:
        params.append({'name': arg.arg, 'type': _ann_str(arg.annotation), 'desc': ''})
    if ao.kwarg:
        params.append({
            'name': f'**{ao.kwarg.arg}',
            'type': _ann_str(ao.kwarg.annotation),
            'desc': '',
        })
    return params


def _extract_funcs_python(file_path: str) -> list[dict]:
    """
    使用 Python 内置 ast 模块提取函数/方法定义（含嵌套）。

    Returns
    -------
    list[dict]  键: name, signature, start_line, end_line, params, returns
    """
    content = _read_file_safe(file_path)
    if content is None:
        return []

    try:
        tree = ast.parse(content, filename=os.path.basename(file_path))
    except SyntaxError as e:
        print(f"[file_analyzer] Python 语法错误，跳过 AST 提取：{e}")
        return []

    functions: list[dict] = []

    class _Visitor(ast.NodeVisitor):
        def _handle(self, node: 'ast.FunctionDef | ast.AsyncFunctionDef') -> None:
            end_line = getattr(node, 'end_lineno', node.lineno)
            functions.append({
                'name':       node.name,
                'signature':  _build_py_signature(node),
                'start_line': node.lineno,
                'end_line':   end_line,
                'params':     _build_py_params(node),
                'returns':    {'type': _ann_str(node.returns), 'desc': ''},
            })
            self.generic_visit(node)   # 继续遍历嵌套函数

        def visit_FunctionDef(self, node):
            self._handle(node)

        def visit_AsyncFunctionDef(self, node):
            self._handle(node)

    _Visitor().visit(tree)
    return functions


# ══════════════════════════════════════════════════════════════════
#  策略 2：Universal Ctags 提取
# ══════════════════════════════════════════════════════════════════

def _check_ctags() -> bool:
    """检测 ctags 是否可用（结果进程生命周期内缓存）。"""
    global _ctags_ok
    if _ctags_ok is not None:
        return _ctags_ok
    try:
        r = subprocess.run(
            ['ctags', '--version'],
            capture_output=True, text=True, timeout=5,
        )
        _ctags_ok = (r.returncode == 0)
        if _ctags_ok:
            flavor = 'Universal Ctags' if 'Universal Ctags' in r.stdout else 'Exuberant/Unknown Ctags'
            print(f"[file_analyzer] ctags 可用（{flavor}）")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _ctags_ok = False
        print('[file_analyzer] ctags 不可用，将使用 LLM 兜底提取函数。')
    return _ctags_ok


def _parse_ctags_output(stdout: str) -> list[dict]:
    """
    解析 Universal Ctags u-ctags 格式输出，提取函数信息。

    字段格式（TAB 分隔）：
      name  filepath  pattern;"  kind  line:N  end:M  [signature:...]
    """
    functions: list[dict] = []
    seen: set[tuple[str, int]] = set()   # (name, start_line) 去重

    for raw_line in stdout.splitlines():
        if raw_line.startswith('!'):
            continue   # ctags 元信息行

        parts = raw_line.split('\t')
        if len(parts) < 4:
            continue

        name = parts[0].strip()
        if not name:
            continue

        # 解析后续字段（parts[3:] 之后为 "key:value" 或单字符 kind）
        fields: dict[str, str] = {}
        kind_raw = ''

        for part in parts[3:]:
            part = part.strip()
            if ':' in part:
                k, _, v = part.partition(':')
                k = k.strip()
                if k == 'kind':
                    kind_raw = v.strip()
                else:
                    fields[k] = v.strip()
            elif len(part) == 1 and part.isalpha() and not kind_raw:
                kind_raw = part

        # 过滤非函数类型
        if kind_raw.lower() not in _FUNC_KINDS:
            continue

        # 解析行号
        try:
            start_line = int(fields.get('line', 0))
        except (ValueError, TypeError):
            continue
        if start_line == 0:
            continue

        try:
            end_line = int(fields.get('end', start_line))
        except (ValueError, TypeError):
            end_line = start_line

        # 去重
        key = (name, start_line)
        if key in seen:
            continue
        seen.add(key)

        # ctags 的 signature 字段（不含返回类型，仅参数括号部分）
        ctags_sig = fields.get('signature', fields.get('S', ''))

        functions.append({
            'name':       name,
            'signature':  f"{name}{ctags_sig}".strip() if ctags_sig else name,
            'start_line': start_line,
            'end_line':   end_line,
            'params':     [],                           # 由 _enrich_ctags_io 补全
            'returns':    {'type': '', 'desc': ''},     # 由 _enrich_ctags_io 补全
        })

    return functions


def _extract_funcs_ctags(file_path: str, language: str) -> list[dict] | None:
    """
    用 Universal Ctags 提取函数列表。

    Returns
    -------
    list[dict]  成功时（可能为空列表）
    None        ctags 不可用或调用失败
    """
    if not _check_ctags():
        return None

    ctags_lang = _CTAGS_LANG_MAP.get(language)
    cmd: list[str] = [
        'ctags',
        '--fields=+neS',           # n=行号, e=结束行, S=签名（Universal Ctags）
        '--extras=-F',             # 排除文件级标签
        '--output-format=u-ctags', # Universal Ctags 格式（有明确 key:value 字段）
        '-f', '-',                 # 输出到 stdout
        file_path,
    ]
    if ctags_lang:
        cmd.insert(1, f'--languages={ctags_lang}')

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        print(f"[file_analyzer] ctags 超时：{os.path.basename(file_path)}")
        return None
    except Exception as e:
        print(f"[file_analyzer] ctags 执行异常：{e}")
        return None

    if result.returncode != 0:
        # --output-format=u-ctags 可能在 Exuberant Ctags 下失败
        return None

    return _parse_ctags_output(result.stdout)


# ══════════════════════════════════════════════════════════════════
#  C/C++ 签名解析 —— 为 ctags 结果补充 io 信息
# ══════════════════════════════════════════════════════════════════

# C/C++ 修饰符关键词，不属于返回类型本身
_C_QUALIFIERS: frozenset[str] = frozenset({
    'static', 'extern', 'inline', 'virtual', 'explicit',
    'constexpr', 'consteval', 'constinit', 'friend', 'override', 'final',
    '__inline__', '__forceinline', '__cdecl', '__stdcall',
    # 常见宏修饰（minizip-ng 风格）
    'ZEXPORT', 'ZEXPORTVA', 'MZ_EXPORT', 'MZ_EXTERN',
})


def _split_c_params(params_str: str) -> list[str]:
    """
    按逗号分割 C/C++ 参数字符串，正确处理括号/模板/函数指针嵌套。
    """
    result: list[str] = []
    depth   = 0
    current: list[str] = []
    for ch in params_str:
        if ch in '(<[{':
            depth += 1
            current.append(ch)
        elif ch in ')>]}':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            result.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        result.append(''.join(current).strip())
    return [p for p in result if p]


def _parse_c_io(signature: str) -> dict:
    """
    从 C/C++ 函数签名字符串解析参数列表和返回类型。

    示例输入：
      "int deflate_init(z_streamp strm, int level)"
      "static MZ_EXPORT void * mz_alloc(void *opaque, size_t items, size_t size)"

    Returns
    -------
    dict  {"params": [...], "returns": {"type": str, "desc": ""}}
    """
    io: dict = {'params': [], 'returns': {'type': '', 'desc': ''}}
    sig = signature.strip()

    # ── 找第一个 ( ──────────────────────────────────────────────────
    paren_open = sig.find('(')
    if paren_open == -1:
        return io

    before_paren = sig[:paren_open].strip()

    # ── 找对应的 ) ──────────────────────────────────────────────────
    depth = 1
    idx = paren_open + 1
    while idx < len(sig) and depth > 0:
        if sig[idx] == '(':
            depth += 1
        elif sig[idx] == ')':
            depth -= 1
        idx += 1
    params_str = sig[paren_open + 1: idx - 1].strip()

    # ── 提取返回类型 ─────────────────────────────────────────────────
    # before_paren 末尾的标识符是函数名，之前是返回类型（含修饰符）
    name_match = re.search(r'(\b\w+)\s*$', before_paren)
    if name_match:
        ret_raw = before_paren[: name_match.start()].strip()
    else:
        ret_raw = ''

    # 去掉存储类修饰符
    ret_parts = [t for t in ret_raw.split() if t not in _C_QUALIFIERS]
    io['returns']['type'] = ' '.join(ret_parts)

    # ── 参数解析 ─────────────────────────────────────────────────────
    if not params_str or params_str in ('void', ''):
        return io

    for param in _split_c_params(params_str):
        param = param.strip()
        if not param:
            continue
        if param == '...':
            io['params'].append({'name': '...', 'type': '...', 'desc': ''})
            continue

        # 处理数组形式：int arr[]  →  name=arr, type=int []
        arr_match = re.search(r'(\w+)\s*(\[\d*\])\s*$', param)
        if arr_match:
            pname = arr_match.group(1)
            ptype = (param[: arr_match.start()].strip()
                     + ' ' + arr_match.group(2)).strip()
        else:
            # 函数指针形式：void (*callback)(int) → 特殊处理
            fp_match = re.search(r'\(\s*\*\s*(\w+)\s*\)', param)
            if fp_match:
                pname = fp_match.group(1)
                ptype = param.replace(fp_match.group(0), '(*)', 1).strip()
            else:
                # 普通形式：最后一个标识符为参数名
                tokens = re.findall(r'\w+', param)
                if not tokens:
                    continue
                pname = tokens[-1]
                # 去掉末尾参数名（保留指针 * & 等符号）
                last_pos = param.rfind(pname)
                ptype = param[:last_pos].rstrip('*& \t')
                if not ptype:
                    ptype = pname
                    pname = ''

        io['params'].append({
            'name': pname,
            'type': ptype.strip(),
            'desc': '',
        })

    return io


def _enrich_ctags_io(
    funcs: list[dict],
    file_path: str,
    repo_rel_path: str,
) -> list[dict]:
    """
    读取源文件，为 ctags 提取的函数补充完整签名及 io 信息。

    做法：从 start_line 向后最多扫描 40 行，收集到第一个 '{' 或 ';' 止，
    拼成完整函数声明行，再用 _parse_c_io 解析。

    适用语言：C / C++ / Objective-C
    """
    content = _read_file_safe(file_path)
    if content is None:
        return funcs

    lines       = content.splitlines()
    total_lines = len(lines)

    for func in funcs:
        start = func['start_line']
        if start < 1 or start > total_lines:
            continue

        # 向后收集行，直到遇到 '{' 或 ';'
        collected: list[str] = []
        for li in range(start - 1, min(start + 40, total_lines)):
            row = lines[li].rstrip()
            # 去掉行注释
            row_no_comment = re.sub(r'//.*$', '', row)
            collected.append(row_no_comment)
            if '{' in row_no_comment or ';' in row_no_comment:
                break

        sig_raw = ' '.join(collected)
        # 去掉 '{' 及其后内容
        sig_raw = re.sub(r'\s*\{.*', '', sig_raw, flags=re.DOTALL).strip()
        # 去掉行尾 ';'
        sig_raw = sig_raw.rstrip(';').strip()
        # 压缩多余空白
        sig_raw = re.sub(r'\s+', ' ', sig_raw)

        if sig_raw:
            func['signature'] = sig_raw
            io = _parse_c_io(sig_raw)
            func['params']  = io['params']
            func['returns'] = io['returns']

    return funcs


# ══════════════════════════════════════════════════════════════════
#  策略 3：LLM 提取（通用兜底）
# ══════════════════════════════════════════════════════════════════

def _extract_funcs_llm(
    file_path: str,
    file_name: str,
    language: str,
    repo_rel_path: str,
) -> list[dict]:
    """
    调用 LLM 提取函数列表，适用于任意语言。
    文件超过 _MAX_LINES_LLM 行时截断（末尾部分函数可能丢失）。

    Returns
    -------
    list[dict]  提取成功则返回函数列表；失败返回 []
    """
    from llm.client  import chat_completion_json
    from llm.prompts import ANALYZE_FILE_FUNC_SYSTEM, ANALYZE_FILE_FUNC_USER
    import config as _cfg

    content = _read_file_safe(file_path)
    if content is None:
        print(f"[file_analyzer] 文件过大或无法读取，跳过 LLM 提取：{file_name}")
        return []

    numbered, total_lines = _add_line_numbers(content)
    if total_lines > _MAX_LINES_LLM:
        print(
            f"[file_analyzer] {file_name} 共 {total_lines} 行，"
            f"超限（{_MAX_LINES_LLM}），LLM 仅处理前 {_MAX_LINES_LLM} 行。"
        )

    # lang_lower 用于 Markdown 代码块高亮标注（去掉特殊字符）
    lang_lower = language.lower().replace('+', 'p').replace('#', 'sharp')

    user_msg = ANALYZE_FILE_FUNC_USER.format(
        file_name        = file_name,
        language         = language,
        file_path        = repo_rel_path,
        lang_lower       = lang_lower,
        numbered_content = numbered,
    )

    messages = [
        {'role': 'system', 'content': ANALYZE_FILE_FUNC_SYSTEM},
        {'role': 'user',   'content': user_msg},
    ]

    print(
        f"[file_analyzer] 调用 LLM 提取函数（{file_name}，"
        f"模型 {_cfg.LLM_MODEL}）…"
    )
    try:
        data = chat_completion_json(
            messages=messages, temperature=0.1, max_tokens=8192
        )
    except Exception as e:
        print(f"[file_analyzer] LLM 调用失败（{file_name}）：{e}")
        return []

    # 解析 LLM 输出
    if isinstance(data, dict) and 'functions' in data:
        raw_funcs = data['functions']
    elif isinstance(data, list):
        raw_funcs = data
    else:
        print(f"[file_analyzer] LLM 输出结构异常（{file_name}）：{type(data)}")
        return []

    functions: list[dict] = []
    for item in raw_funcs:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name', '')).strip()
        if not name:
            continue

        try:
            start_line = int(item.get('start_line', 0))
        except (ValueError, TypeError):
            start_line = 0
        try:
            end_line = int(item.get('end_line', start_line))
        except (ValueError, TypeError):
            end_line = start_line

        signature = str(item.get('signature', name)).strip()

        # 规范化 params
        raw_params = item.get('params', [])
        params: list[dict] = []
        if isinstance(raw_params, list):
            for p in raw_params:
                if isinstance(p, dict):
                    params.append({
                        'name': str(p.get('name', '')),
                        'type': str(p.get('type', '')),
                        'desc': str(p.get('desc', '')),
                    })

        # 规范化 returns
        raw_ret = item.get('returns', {})
        if isinstance(raw_ret, dict):
            returns = {
                'type': str(raw_ret.get('type', '')),
                'desc': str(raw_ret.get('desc', '')),
            }
        else:
            returns = {'type': str(raw_ret), 'desc': ''}

        functions.append({
            'name':       name,
            'signature':  signature,
            'start_line': start_line,
            'end_line':   end_line,
            'params':     params,
            'returns':    returns,
        })

    return functions


# ══════════════════════════════════════════════════════════════════
#  主调度：按语言选择最优提取策略
# ══════════════════════════════════════════════════════════════════

def _extract_functions(
    file_path: str,
    file_name: str,
    language: str,
    repo_rel_path: str,
) -> list[dict]:
    """
    函数提取入口，依次尝试：ast → ctags → LLM。

    Returns
    -------
    list[dict]  每项键：name, signature, start_line, end_line, params, returns
    """
    # ── ① 无函数类语言直接跳过 ──────────────────────────────────────
    if language in _NO_FUNC_LANGS:
        return []

    # ── ② Python：使用 ast 模块（精确） ─────────────────────────────
    if language == 'Python':
        funcs = _extract_funcs_python(file_path)
        print(f"[file_analyzer]   策略=ast  → {len(funcs)} 个函数")
        return funcs

    # ── ③ 尝试 ctags ─────────────────────────────────────────────────
    ctags_funcs = _extract_funcs_ctags(file_path, language)

    if ctags_funcs is not None:
        # ctags 可用
        if ctags_funcs:
            # 对 C/C++/Objective-C 补充 io 信息（从源码解析签名）
            if language in ('C', 'C++', 'Objective-C'):
                ctags_funcs = _enrich_ctags_io(ctags_funcs, file_path, repo_rel_path)
            print(f"[file_analyzer]   策略=ctags → {len(ctags_funcs)} 个函数")
            return ctags_funcs
        else:
            # ctags 返回空 → 对于 C/C++ 认为文件确实无函数；其他语言降级 LLM
            if language in ('C', 'C++', 'Objective-C'):
                print(f"[file_analyzer]   策略=ctags → 0 个函数（可信）")
                return []
            # 非 C/C++：ctags 可能不支持该语言格式，降级 LLM
            print(f"[file_analyzer]   ctags 无结果，降级 LLM")

    # ── ④ LLM 兜底 ───────────────────────────────────────────────────
    funcs = _extract_funcs_llm(file_path, file_name, language, repo_rel_path)
    print(f"[file_analyzer]   策略=LLM  → {len(funcs)} 个函数")
    return funcs


# ══════════════════════════════════════════════════════════════════
#  analyze_file_func
# ══════════════════════════════════════════════════════════════════

def analyze_file_func(
    repo_id: int,
    db_path: str | None = None,
    file_id: int | None = None,
    force: bool = False,
) -> dict[int, list[dict]]:
    """
    提取文件中所有函数/方法，写入 func 表并更新 file.funclist。

    流程
    ----
    1. 获取目标文件列表（全部或指定 file_id）
    2. 对每个文件调用 _extract_functions（ast / ctags / LLM 三档策略）
    3. 将提取结果写入 func 表，更新 file.funclist
    4. 支持 force 模式：已有记录时先清除再重建

    写入字段
    --------
    func.name      : 函数名
    func.signature : 完整签名字符串
    func.place     : {"file_path": str, "start_line": int, "end_line": int}
    func.io        : {"params": [...], "returns": {"type": str, "desc": str}}
    file.funclist  : [{"func_id": int, "name": str, "brief": ""}]

    Parameters
    ----------
    repo_id : int
        目标仓库 id
    db_path : str | None
        SQLite 路径；不传则使用 config.DB_PATH
    file_id : int | None
        若指定，则只处理该文件；否则处理 repo 下所有文件
    force : bool
        True = 若文件已有 func 记录则先全部删除再重建；
        False = 跳过已有记录（可用于断点续跑）

    Returns
    -------
    dict[int, list[dict]]
        {file_id: [{"func_id", "name", "start_line", "end_line"}, ...]}

    Raises
    ------
    ValueError
        repo_id 或 file_id 在数据库中不存在
    """
    _db = db_path or DB_PATH

    # ── ① 校验仓库 ──────────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_file_func] repo_id={repo_id} 不存在于数据库。"
        )
    repo_path = repo['path']

    # ── ② 确定目标文件列表 ──────────────────────────────────────────
    if file_id is not None:
        file_rec = FileDB.get_by_id(file_id, db_path=_db)
        if file_rec is None:
            raise ValueError(
                f"[analyze_file_func] file_id={file_id} 不存在于数据库。"
            )
        files = [file_rec]
    else:
        files = FileDB.list_by_repo(repo_id, db_path=_db)

    if not files:
        print(
            f"[analyze_file_func] ⚠ repo_id={repo_id} 暂无文件记录，"
            "请先执行 analyze_area_file。"
        )
        return {}

    total_funcs_all = 0
    result: dict[int, list[dict]] = {}

    for file_rec in files:
        fid       = file_rec['id']
        fname     = file_rec['name']
        fpath_rel = file_rec['path']
        area_id   = file_rec['area_id']

        # 优先取已分析的语言，否则实时推断
        language = file_rec.get('language') or _detect_language(fname)

        # 构建文件绝对路径
        file_abs = os.path.join(repo_path, fpath_rel.replace('/', os.sep))
        if not os.path.isfile(file_abs):
            print(f"[analyze_file_func] ⚠ 文件不存在，跳过：{fpath_rel}")
            result[fid] = []
            continue

        # ── ③ 处理已有 func 记录 ────────────────────────────────────
        existing_funcs = FuncDB.list_by_file(fid, db_path=_db)
        if existing_funcs:
            if force:
                for ef in existing_funcs:
                    FuncDB.delete(ef['id'], db_path=_db)
                print(
                    f"[analyze_file_func] force 模式：已清除 {len(existing_funcs)} 条旧记录"
                    f"（{fname}）"
                )
            else:
                # 断点续跑：保留已有数据
                result[fid] = [
                    {
                        'func_id':    ef['id'],
                        'name':       ef['name'],
                        'start_line': (ef.get('place') or {}).get('start_line', 0),
                        'end_line':   (ef.get('place') or {}).get('end_line',   0),
                    }
                    for ef in existing_funcs
                ]
                print(
                    f"[analyze_file_func] 跳过（已有 {len(existing_funcs)} 个 func）：{fname}"
                    " —— 传入 force=True 可强制重建"
                )
                total_funcs_all += len(existing_funcs)
                continue

        # ── ④ 提取函数 ──────────────────────────────────────────────
        print(f"[analyze_file_func] 处理：{fpath_rel}（{language}）")
        extracted = _extract_functions(file_abs, fname, language, fpath_rel)

        # ── ⑤ 写入 func 表 ──────────────────────────────────────────
        funclist:          list[dict] = []   # 写回 file.funclist
        file_func_results: list[dict] = []   # 供调用方使用

        for func_info in extracted:
            func_name  = func_info['name']
            signature  = func_info.get('signature') or func_name
            start_line = func_info.get('start_line', 0)
            end_line   = func_info.get('end_line', start_line)
            params     = func_info.get('params', [])
            returns    = func_info.get('returns', {'type': '', 'desc': ''})

            place: dict = {
                'file_path':  fpath_rel,
                'start_line': start_line,
                'end_line':   end_line,
            }
            io: dict = {
                'params':  params,
                'returns': returns,
            }

            try:
                func_id = FuncDB.create(
                    repo_id   = repo_id,
                    area_id   = area_id,
                    file_id   = fid,
                    name      = func_name,
                    signature = signature,
                    place     = place,
                    io        = io,
                    db_path   = _db,
                )
            except Exception as e:
                # UNIQUE 约束冲突（同名同签名同文件）→ 跳过，不终止整体流程
                print(
                    f"[analyze_file_func]   ⚠ 函数 '{func_name}' 写入失败"
                    f"（跳过）：{e}"
                )
                continue

            funclist.append({
                'func_id': func_id,
                'name':    func_name,
                'brief':   '',   # 留给 analyze_file_funclist_description（step14）填充
            })
            file_func_results.append({
                'func_id':    func_id,
                'name':       func_name,
                'start_line': start_line,
                'end_line':   end_line,
            })

        # ── ⑥ 更新 file.funclist ────────────────────────────────────
        FileDB.update(fid, db_path=_db, funclist=funclist)

        result[fid]      = file_func_results
        total_funcs_all += len(file_func_results)

        print(
            f"[analyze_file_func]   ✓ {fname}：{len(file_func_results)} 个函数已入库"
        )

    total_files = len(files)
    print(
        f"\n[analyze_file_func] ✓ 完成：处理 {total_files} 个文件，"
        f"共提取 {total_funcs_all} 个函数。"
    )
    return result
```

