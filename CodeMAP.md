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

---

1. **init_repo**：得到仓库名，建立对应数据库并填入对应数据【repo:name】
2. **analyze_repo_language**：扫描仓库并分析语言占比情况，得出主要语言，并填入对应数据【repo:language】
3. **analyze_repo_area**：对仓库分层，并附上分层依据和对应的area具体路径，存data/analyze_repo_area，并填入对应数据【repo:arealist；area:name；area:path】
4. **analyze_area_file**：扫描area路径得到文件结构，存在data/analyze_area_file，并填入对应数据【area:filelist；file:name；file:path】
5. **analyze_file_language**：分析文件的编程语言，并填入对应数据【file:language】
6. **analyze_file_func**：分析文件中所有的函数，并填入对应数据【file:funclist；func:name；func:place；func:io】

---

1. **build_callgraph**：用codeql对整个仓库分析得到的函数调用图，并存入data
2. **analyze_func_callgraph**：分析该函数的调用关系，并填入对应数据【func:callgraph】
3. **analyze_func_precondition**：sa+llm分析该函数的前置调用关系，且有一些分类，这个实现需要做到非常好和细节到位，最后填入对应数据【func:precondition】
4. **analyze_func_postcondition**：sa+llm分析该函数的后置调用关系，且有一些分类，这个实现需要做到非常好和细节到位，最后填入对应数据【func:postcondition】
5. **analyze_func_exception**：分析该函数的异常处理，填入对应数据【func:exception】
6. **get_func_context**：通过输入函数名和路径，得到该函数的内容，如果数据库中有函数的一些补充信息也给出（命令行可选补充信息需求）
7. **analyze_func_description**：agent实现，提供该函数内容+调用关系+前置条件+后置条件+异常处理，以及给一个get_func_context的工具调用结构，可以agent工具得到调用链里的函数信息；让agent给出该函数的自然语言描述：该函数功能+函数分析+函数安全分析+开发者意图分析等，最后填入对应数据【func:description】
8. **analyze_file_funclist_description**：通过提供file的funclist，将每个func的description变成简短的一两句话存入对应数据【file:funclist】
9. **analyze_file_description**：给llm提供file在area里的文件组织架构、文件信息、其中函数所有的description，得到对文件的自然语言描述：文件功能+文件定位+开发者意图分析，最后填入对应数据【file:description】
10. **analyze_area_filelist_description**：通过提供area的filelist，将每个file的description变成简短的一两句话存入对应数据【area:filelist】
11. **analyze_area_description**：给llm提供area的在仓库中路径及分层依据+area里的文件组织架构、其中file所有的description，得到对area的自然语言描述：area功能+area定位+开发者意图分析，最后填入对应数据【area:description】
12. **analyze_repo_arealist_description**：通过提供repo的arealist，每个area的description变成简短的一两句话存入对应数据【repo:arealist】
13. **analyze_area_description**：给llm提供仓库的文件组织结构、分层结构、仓库相关信息、仓库里可参考的文本内容、仓库的所有area的description，得到对仓库的自然语言描述：仓库功能+开发者意图分析，最后填入对应数据【repo:description】
14. **build_codemap**：实现CodeMAP，即将上述流程串起来

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

### Step5：`analyze_file_language`和`analyze_file_func`实现

`analyzer/file_analyzer.py`

```
"""
analyzer/file_analyzer.py
CodeMAP 文件层分析器

实现：
  - analyze_file_language : 检测每个文件的编程语言，写入 file:language
  - analyze_file_func     : 解析每个文件中的所有函数，写入：
                              file:funclist / func:name / func:place / func:io

语言策略
--------
  Python      → ast 模块（精确，零依赖）
  C / C++     → tree-sitter 专用提取器（精确签名和类型信息）
  其他已支持   → tree-sitter-languages 通用提取器（130+ 语言）
  兜底         → ctags（只拿名称和行号，io 留空）
  真正无解      → language=Unknown，跳过函数提取
"""

import ast
import json as _json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, FileDB, FuncDB
from config import DB_PATH, DATA_DIR


# ==================================================================
# 0. tree-sitter 可用性检测（延迟导入，避免强依赖）
# ==================================================================

try:
    from tree_sitter_languages import get_parser as _ts_get_parser
    _ts_get_parser('c')
    _TREE_SITTER_OK = True
except ImportError:
    _TREE_SITTER_OK = False


# ==================================================================
# 1. 语言映射常量
# ==================================================================

_EXT_TO_LANG: dict[str, str] = {
    # C / C++
    '.c': 'C', '.h': 'C',
    '.cpp': 'C++', '.cxx': 'C++', '.cc': 'C++',
    '.hpp': 'C++', '.hxx': 'C++',
    # Python
    '.py': 'Python',
    # Java
    '.java': 'Java',
    # JS / TS
    '.js': 'JavaScript', '.jsx': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript',
    # Go
    '.go': 'Go',
    # Rust
    '.rs': 'Rust',
    # Shell
    '.sh': 'Shell', '.bash': 'Shell', '.zsh': 'Shell',
    # 构建脚本
    '.cmake': 'CMake',
    # 其他
    '.rb': 'Ruby',
    '.swift': 'Swift',
    '.kt': 'Kotlin', '.kts': 'Kotlin',
    '.scala': 'Scala',
    '.hs': 'Haskell',
    '.asm': 'Assembly', '.s': 'Assembly',
    '.lua': 'Lua',
    '.pl': 'Perl', '.pm': 'Perl',
    '.f': 'Fortran', '.f90': 'Fortran', '.f95': 'Fortran',
    '.r': 'R',
    '.m': 'MATLAB', '.mm': 'Objective-C',
    # 文档 / 配置
    '.md': 'Markdown', '.rst': 'reStructuredText',
    '.yaml': 'YAML', '.yml': 'YAML',
    '.json': 'JSON', '.xml': 'XML',
    '.html': 'HTML', '.htm': 'HTML',
    '.css': 'CSS', '.sql': 'SQL',
    '.toml': 'TOML', '.ini': 'INI', '.cfg': 'INI',
}

_SPECIAL_NAMES: dict[str, str] = {
    'makefile':        'Makefile',
    'gnumakefile':     'Makefile',
    'cmakelists.txt':  'CMake',
    'dockerfile':      'Dockerfile',
    'gemfile':         'Ruby',
    'rakefile':        'Ruby',
    'vagrantfile':     'Ruby',
    'podfile':         'Ruby',
    'brewfile':        'Ruby',
}

# 显示名 → tree-sitter grammar 名
_LANG_TO_TS: dict[str, str] = {
    'C':           'c',
    'C++':         'cpp',
    'Python':      'python',
    'Java':        'java',
    'JavaScript':  'javascript',
    'TypeScript':  'typescript',
    'Go':          'go',
    'Rust':        'rust',
    'Ruby':        'ruby',
    'Swift':       'swift',
    'Kotlin':      'kotlin',
    'Lua':         'lua',
    'Shell':       'bash',
    'Haskell':     'haskell',
    'Scala':       'scala',
}

# tree-sitter grammar 名 → 函数定义节点类型列表
_TS_FUNC_TYPES: dict[str, list[str]] = {
    'c':           ['function_definition'],
    'cpp':         ['function_definition'],
    'python':      ['function_definition'],      # ast 优先；此为备用
    'java':        ['method_declaration', 'constructor_declaration'],
    'javascript':  ['function_declaration', 'method_definition', 'function_expression'],
    'typescript':  ['function_declaration', 'method_definition', 'function_expression'],
    'go':          ['function_declaration', 'method_declaration'],
    'rust':        ['function_item'],
    'ruby':        ['method', 'singleton_method'],
    'swift':       ['function_declaration'],
    'kotlin':      ['function_declaration'],
    'lua':         ['function_declaration', 'local_function'],
    'bash':        ['function_definition'],
    'haskell':     [],                            # 语法较特殊，暂不提取
    'scala':       ['function_declaration', 'function_definition'],
}

# 不提取函数的语言（文档、配置、数据类）
_NO_FUNC_LANGS: frozenset[str] = frozenset({
    'Markdown', 'reStructuredText', 'YAML', 'JSON', 'XML',
    'HTML', 'CSS', 'SQL', 'TOML', 'INI', 'CMake', 'Makefile',
    'Dockerfile', 'Assembly', 'MATLAB', 'R', 'Fortran', 'Unknown',
})

# 单文件解析大小上限（超出则跳过函数提取）
_MAX_FILE_BYTES = 5 * 1024 * 1024   # 5 MB


# ==================================================================
# 2. 语言检测
# ==================================================================

def _read_shebang(abs_path: str) -> Optional[str]:
    """读取文件首行 shebang，返回对应语言名或 None。"""
    try:
        with open(abs_path, 'rb') as f:
            first = f.read(128)
        line = first.split(b'\n', 1)[0].decode('utf-8', errors='ignore')
        if not line.startswith('#!'):
            return None
        lower = line.lower()
        if 'python'             in lower: return 'Python'
        if 'ruby'               in lower: return 'Ruby'
        if 'node'               in lower: return 'JavaScript'
        if 'perl'               in lower: return 'Perl'
        if 'lua'                in lower: return 'Lua'
        if '/bash' in lower or '/sh' in lower or '/zsh' in lower:
            return 'Shell'
    except OSError:
        pass
    return None


def _detect_language(filename: str, abs_path: str) -> str:
    """
    检测文件编程语言。

    优先级：
      1. 特殊文件名（Makefile / CMakeLists.txt 等）
      2. 扩展名映射
      3. shebang（#!）行
      4. 返回 'Unknown'
    """
    lower = filename.lower()
    if lower in _SPECIAL_NAMES:
        return _SPECIAL_NAMES[lower]

    _, ext = os.path.splitext(filename)
    lang = _EXT_TO_LANG.get(ext.lower())
    if lang:
        return lang

    shebang = _read_shebang(abs_path)
    if shebang:
        return shebang

    return 'Unknown'


# ==================================================================
# 3. 文件内容读取
# ==================================================================

def _read_source(abs_path: str) -> Optional[str]:
    """
    读取源文件文本，自动处理编码（UTF-8 → latin-1 兜底）。
    超过大小上限返回 None。
    """
    try:
        if os.path.getsize(abs_path) > _MAX_FILE_BYTES:
            return None
    except OSError:
        return None

    for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'gbk'):
        try:
            with open(abs_path, 'r', encoding=enc, errors='strict') as f:
                return f.read()
        except (UnicodeDecodeError, ValueError):
            continue
        except OSError:
            return None
    return None


# ==================================================================
# 4. Python 函数提取（ast 模块）
# ==================================================================

def _ast_unparse(node) -> str:
    """安全地反序列化 AST 注解节点；失败返回空字符串。"""
    if node is None:
        return ''
    try:
        return ast.unparse(node)
    except Exception:
        return ''


def _extract_python_funcs(source: str, rel_path: str) -> list[dict]:
    """
    用 ast 模块解析 Python 源文件，提取所有函数（含 async def、类方法、嵌套函数）。

    返回列表，每项：
    {
        name, signature, start_line, end_line,
        return_type, params[{name, type, desc}], file_path
    }
    """
    try:
        tree = ast.parse(source, filename=rel_path, type_comments=False)
    except SyntaxError:
        return []

    funcs: list[dict] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        func_name  = node.name
        start_line = node.lineno
        end_line   = getattr(node, 'end_lineno', node.lineno)

        params: list[dict] = []
        args = node.args

        # 普通位置参数
        for arg in args.args:
            params.append({
                'name': arg.arg,
                'type': _ast_unparse(arg.annotation),
                'desc': '',
            })

        # *args
        if args.vararg:
            params.append({
                'name': f'*{args.vararg.arg}',
                'type': _ast_unparse(args.vararg.annotation),
                'desc': '',
            })

        # keyword-only 参数
        for arg in args.kwonlyargs:
            params.append({
                'name': arg.arg,
                'type': _ast_unparse(arg.annotation),
                'desc': '',
            })

        # **kwargs
        if args.kwarg:
            params.append({
                'name': f'**{args.kwarg.arg}',
                'type': _ast_unparse(args.kwarg.annotation),
                'desc': '',
            })

        return_type = _ast_unparse(node.returns)

        # 构建签名字符串
        param_strs = []
        for p in params:
            param_strs.append(
                f"{p['name']}: {p['type']}" if p['type'] else p['name']
            )
        prefix    = 'async def ' if isinstance(node, ast.AsyncFunctionDef) else 'def '
        ret_hint  = f' -> {return_type}' if return_type else ''
        signature = f"{prefix}{func_name}({', '.join(param_strs)}){ret_hint}"

        funcs.append({
            'name':        func_name,
            'signature':   signature[:600],
            'start_line':  start_line,
            'end_line':    end_line,
            'return_type': return_type,
            'params':      params,
            'file_path':   rel_path,
        })

    return funcs


# ==================================================================
# 5. C/C++ 函数提取（tree-sitter 专用）
# ==================================================================

def _ts_text(node, src: bytes) -> str:
    """从 tree-sitter 节点提取对应源码字符串。"""
    return src[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _find_all_nodes(root, wanted: set) -> list:
    """
    DFS 遍历 tree-sitter 语法树，收集所有类型在 wanted 中的节点。
    不中止递归——以支持嵌套函数（如 C++ lambda、本地函数）。
    """
    result: list = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in wanted:
            result.append(node)
        # 反序入栈以保证左→右顺序
        for child in reversed(node.children):
            stack.append(child)
    return result


def _find_func_declarator(node):
    """
    在 C/C++ declarator 链中找到 function_declarator 节点。
    处理层：pointer_declarator / reference_declarator /
             parenthesized_declarator / abstract_declarator 等。
    """
    if node is None:
        return None
    if node.type == 'function_declarator':
        return node
    wrapping = {
        'pointer_declarator', 'reference_declarator',
        'parenthesized_declarator', 'abstract_declarator',
        'abstract_pointer_declarator', 'abstract_reference_declarator',
    }
    if node.type in wrapping:
        inner = node.child_by_field_name('declarator')
        if inner:
            r = _find_func_declarator(inner)
            if r:
                return r
        # 个别 grammar 版本 field 名不同：遍历直接子节点
        for child in node.children:
            r = _find_func_declarator(child)
            if r:
                return r
    return None


def _extract_decl_name(node, src: bytes) -> str:
    """
    从 C/C++ declarator 节点提取函数标识符名称。
    处理：identifier / qualified_identifier / destructor_name /
          operator_name / template_function / pointer_declarator 等。
    """
    if node is None:
        return ''
    t = node.type
    if t in ('identifier', 'field_identifier'):
        return _ts_text(node, src)
    if t in ('qualified_identifier', 'destructor_name',
             'operator_name', 'template_function', 'template_method'):
        return _ts_text(node, src)
    if t in ('pointer_declarator', 'reference_declarator',
             'abstract_pointer_declarator'):
        inner = node.child_by_field_name('declarator')
        if inner:
            return _extract_decl_name(inner, src)
    if t == 'parenthesized_declarator':
        for child in node.children:
            r = _extract_decl_name(child, src)
            if r:
                return r
    # 深度优先兜底：找第一个 identifier
    for child in node.children:
        r = _extract_decl_name(child, src)
        if r:
            return r
    return _ts_text(node, src)


def _extract_c_params(params_node, src: bytes) -> list[dict]:
    """从 C/C++ parameter_list 节点提取参数信息。"""
    if params_node is None:
        return []

    params: list[dict] = []
    for child in params_node.children:
        # 可变参数 ...
        raw = _ts_text(child, src).strip()
        if raw == '...':
            params.append({'name': '...', 'type': 'variadic', 'desc': ''})
            continue

        if child.type == 'variadic_parameter':
            params.append({'name': '...', 'type': 'variadic', 'desc': ''})
            continue

        if child.type not in ('parameter_declaration',
                               'optional_parameter_declaration'):
            continue

        type_node = child.child_by_field_name('type')
        decl_node = child.child_by_field_name('declarator')

        param_type = _ts_text(type_node, src).strip() if type_node else ''
        param_name = _extract_decl_name(decl_node, src).strip() if decl_node else ''

        # 跳过 void 单参数声明：`f(void)`
        if param_type == 'void' and not param_name:
            continue

        # 类型和名字都为空时，取整段文本作类型
        if not param_type and not param_name:
            if raw:
                params.append({'name': '', 'type': raw, 'desc': ''})
            continue

        params.append({'name': param_name, 'type': param_type, 'desc': ''})

    return params


def _extract_c_cpp_funcs(source: str, rel_path: str, lang: str = 'C') -> list[dict]:
    """
    用 tree-sitter 解析 C/C++ 源文件，仅提取有函数体的定义（跳过纯声明）。

    C++ 类内成员函数、模板函数、运算符重载均支持。
    """
    if not _TREE_SITTER_OK:
        return []

    ts_name = 'cpp' if lang == 'C++' else 'c'
    try:
        parser    = _ts_get_parser(ts_name)
        src_bytes = source.encode('utf-8', errors='replace')
        tree      = parser.parse(src_bytes)
    except Exception:
        print(f"[warn] tree-sitter 解析器加载失败（{ts_name}）：{e}")
        return []

    func_nodes = _find_all_nodes(tree.root_node, {'function_definition'})
    funcs: list[dict] = []

    for node in func_nodes:
        # 只提取有函数体的定义
        body = node.child_by_field_name('body')
        if body is None:
            continue

        # 返回类型
        type_node   = node.child_by_field_name('type')
        return_type = _ts_text(type_node, src_bytes).strip() if type_node else ''

        # 找 function_declarator
        declarator = node.child_by_field_name('declarator')
        func_decl  = _find_func_declarator(declarator)
        if func_decl is None:
            continue

        # 提取函数名
        inner_decl = func_decl.child_by_field_name('declarator')
        func_name  = _extract_decl_name(inner_decl, src_bytes).strip()
        if not func_name or func_name in ('(', ''):
            continue

        # 提取参数
        params_node = func_decl.child_by_field_name('parameters')
        params      = _extract_c_params(params_node, src_bytes)

        # 签名：body 之前的所有文本，合并为单行
        sig_raw  = src_bytes[node.start_byte:body.start_byte].decode('utf-8', errors='replace')
        signature = re.sub(r'\s+', ' ', sig_raw).strip()

        start_line = node.start_point[0] + 1   # tree-sitter 行号从 0 开始
        end_line   = node.end_point[0]   + 1

        funcs.append({
            'name':        func_name,
            'signature':   signature[:600],
            'start_line':  start_line,
            'end_line':    end_line,
            'return_type': return_type,
            'params':      params,
            'file_path':   rel_path,
        })

    return funcs


# ==================================================================
# 6. 通用 tree-sitter 函数提取（非 C/C++/Python）
# ==================================================================

def _ts_extract_name_generic(node, src: bytes, ts_lang: str) -> str:
    """
    通用策略提取函数名：先尝试 'name' field，再 DFS 找 identifier。
    """
    name_node = node.child_by_field_name('name')
    if name_node:
        return _ts_text(name_node, src).strip()

    # bash function_definition：name 在 word 子节点
    if ts_lang == 'bash':
        for child in node.children:
            if child.type == 'word':
                return _ts_text(child, src).strip()

    # DFS 找第一个 identifier（深度限 4 层）
    def _dfs(n, depth=0) -> str:
        if depth > 4:
            return ''
        if n.type in ('identifier', 'type_identifier', 'property_identifier',
                       'simple_identifier'):
            return _ts_text(n, src).strip()
        for ch in n.children:
            r = _dfs(ch, depth + 1)
            if r:
                return r
        return ''

    return _dfs(node)


def _ts_extract_params_generic(node, src: bytes) -> list[dict]:
    """
    通用策略提取函数参数：查找 parameters / formal_parameters /
    parameter_list 子节点，遍历其中的参数条目。
    """
    param_parent_names = (
        'parameters', 'formal_parameters', 'parameter_list',
        'params', 'lambda_parameters',
    )
    params_node = None
    for fname in param_parent_names:
        params_node = node.child_by_field_name(fname)
        if params_node:
            break
    if params_node is None:
        for child in node.children:
            if 'parameter' in child.type.lower():
                params_node = child
                break
    if params_node is None:
        return []

    param_types = {
        'parameter_declaration', 'formal_parameter', 'parameter',
        'required_parameter', 'optional_parameter', 'rest_parameter',
        'simple_parameter', 'typed_parameter', 'variadic_parameter',
        'self_parameter', 'receiver_parameter',
    }

    params: list[dict] = []
    for child in params_node.children:
        if child.type not in param_types:
            continue

        name_n = (child.child_by_field_name('name')
                  or child.child_by_field_name('pattern'))
        type_n = child.child_by_field_name('type')

        pname = _ts_text(name_n, src).strip() if name_n else ''
        ptype = _ts_text(type_n, src).strip() if type_n else ''

        if not pname and not ptype:
            raw = _ts_text(child, src).strip()
            if raw and raw not in (',', '(', ')'):
                params.append({'name': raw, 'type': '', 'desc': ''})
        else:
            params.append({'name': pname, 'type': ptype, 'desc': ''})

    return params


def _extract_generic_ts_funcs(source: str, rel_path: str, ts_lang: str) -> list[dict]:
    """
    用 tree-sitter 通用策略提取函数（适用于 Java / Go / Rust / Ruby 等）。
    """
    if not _TREE_SITTER_OK:
        return []

    func_node_types = _TS_FUNC_TYPES.get(ts_lang, [])
    if not func_node_types:
        return []

    try:
        parser    = _ts_get_parser(ts_lang)
        src_bytes = source.encode('utf-8', errors='replace')
        tree      = parser.parse(src_bytes)
    except Exception:
        return []

    func_nodes = _find_all_nodes(tree.root_node, set(func_node_types))
    funcs: list[dict] = []

    for node in func_nodes:
        func_name = _ts_extract_name_generic(node, src_bytes, ts_lang)
        if not func_name:
            continue

        params     = _ts_extract_params_generic(node, src_bytes)
        start_line = node.start_point[0] + 1
        end_line   = node.end_point[0]   + 1

        # 签名：取节点前几行（到函数体开始之前）
        raw_text   = _ts_text(node, src_bytes)
        lines      = raw_text.split('\n')
        sig_lines: list[str] = []
        for line in lines[:6]:
            sig_lines.append(line)
            stripped = line.rstrip()
            if stripped.endswith(('{', ':', '=>', 'do', '=')):
                break
        signature = ' '.join(l.strip() for l in sig_lines).strip()

        funcs.append({
            'name':        func_name,
            'signature':   signature[:600],
            'start_line':  start_line,
            'end_line':    end_line,
            'return_type': '',
            'params':      params,
            'file_path':   rel_path,
        })

    return funcs


# ==================================================================
# 7. ctags 兜底提取
# ==================================================================

def _extract_ctags_funcs(abs_path: str, rel_path: str) -> list[dict]:
    """
    用 Universal Ctags 提取函数名和行号（不依赖 tree-sitter）。
    需要系统已安装 ctags（支持 --output-format=json）。
    失败时静默返回空列表。
    """
    if not shutil.which('ctags'):
        return []

    try:
        proc = subprocess.run(
            [
                'ctags', '--output-format=json',
                '--fields=+ne', '--kinds-all=*',
                '--languages=all', '-f', '-', abs_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='replace',
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    func_kinds = {
        'function', 'method', 'constructor', 'destructor',
        'f', 'm', 'c', 'd',
    }

    funcs: list[dict] = []
    for line in proc.stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            entry = _json.loads(line)
        except _json.JSONDecodeError:
            continue

        kind = str(entry.get('kind', '')).lower()
        if kind not in func_kinds:
            continue

        name = entry.get('name', '').strip()
        if not name:
            continue

        start_line = int(entry.get('line', 0))
        if start_line == 0:
            continue

        end_data = entry.get('end', {})
        end_line = (
            int(end_data['line'])
            if isinstance(end_data, dict) and 'line' in end_data
            else start_line
        )

        sig = entry.get('signature', '')
        funcs.append({
            'name':        name,
            'signature':   f"{name}{sig}"[:600] if sig else name,
            'start_line':  start_line,
            'end_line':    end_line,
            'return_type': '',
            'params':      [],
            'file_path':   rel_path,
        })

    return funcs


# ==================================================================
# 8. 函数提取分发器
# ==================================================================

def _extract_funcs(abs_path: str, rel_path: str, language: str) -> list[dict]:
    """
    根据语言选择最合适的提取策略，按优先级降级：

      1. Python → ast（精确）
      2. C/C++  → tree-sitter 专用提取器
      3. 其他有 TS 支持 → 通用 tree-sitter 提取器
      4. ctags 兜底
      5. 放弃：返回 []

    返回列表每项：
    {name, signature, start_line, end_line, return_type, params, file_path}
    """
    if language in _NO_FUNC_LANGS:
        return []

    source = _read_source(abs_path)
    if source is None:
        return []

    # ── Python ──────────────────────────────────────────────────────
    if language == 'Python':
        return _extract_python_funcs(source, rel_path)

    # ── C / C++ / Objective-C ──────────────────────────────────────
    if language in ('C', 'C++', 'Objective-C'):
        if _TREE_SITTER_OK:
            result = _extract_c_cpp_funcs(source, rel_path, lang=language)
            if result:
                return result
        return _extract_ctags_funcs(abs_path, rel_path)

    # ── 通用 tree-sitter 语言 ───────────────────────────────────────
    ts_name = _LANG_TO_TS.get(language)
    if ts_name and _TREE_SITTER_OK:
        try:
            result = _extract_generic_ts_funcs(source, rel_path, ts_name)
            if result:
                return result
        except Exception:
            pass   # 降级到 ctags

    # ── ctags 兜底 ──────────────────────────────────────────────────
    return _extract_ctags_funcs(abs_path, rel_path)


# ==================================================================
# 9. analyze_file_language（Step 5a）
# ==================================================================

def analyze_file_language(
    repo_id: int,
    db_path: Optional[str] = None,
) -> dict[int, str]:
    """
    检测仓库内所有文件的编程语言，并写入 file.language 字段。

    幂等：对已写入 language 的文件也会覆盖更新（保证重跑一致性）。
    依赖：file 表中已有记录（请先执行 analyze_area_file）。

    Parameters
    ----------
    repo_id : int
        目标仓库 id（由 init_repo 返回）
    db_path : str | None
        SQLite 路径；不传则使用 config.DB_PATH

    Returns
    -------
    dict[int, str]
        {file_id → detected_language}

    Raises
    ------
    ValueError
        repo_id 在数据库中不存在
    """
    _db = db_path or DB_PATH

    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_file_language] repo_id={repo_id} 不存在于数据库。")

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[analyze_file_language] 目标仓库：{repo_name}（{repo_path}）")

    all_files = FileDB.list_by_repo(repo_id, db_path=_db)
    if not all_files:
        print("[analyze_file_language] ⚠ 无 file 记录，请先执行 analyze_area_file。")
        return {}

    result: dict[int, str] = {}

    for file_rec in all_files:
        file_id  = file_rec['id']
        filename = file_rec['name']
        rel_path = file_rec['path']
        abs_path = os.path.join(repo_path, rel_path)

        lang = _detect_language(filename, abs_path)
        FileDB.update(file_id, db_path=_db, language=lang)
        result[file_id] = lang

    # 打印语言分布摘要
    lang_dist = Counter(result.values())
    top = lang_dist.most_common(10)
    print(
        f"[analyze_file_language] ✓ 完成：{len(result)} 个文件已检测并写库。\n"
        f"[analyze_file_language]   语言分布（Top {len(top)}）："
    )
    for lang, cnt in top:
        bar = '█' * min(cnt, 40)
        print(f"    {lang:<22s} {cnt:>4} 个文件  {bar}")

    return result


# ==================================================================
# 10. analyze_file_func（Step 5b）
# ==================================================================

def analyze_file_func(
    repo_id: int,
    db_path: Optional[str] = None,
    force: bool = False,
    languages: Optional[list[str]] = None,
) -> dict[int, list[dict]]:
    """
    解析仓库内所有文件的函数，写入 func 表并更新 file.funclist。

    语言策略（按优先级）：
      Python      → ast 模块
      C / C++     → tree-sitter 专用提取器
      其他有支持   → tree-sitter 通用提取器
      兜底         → ctags（只含名称和行号，io 留空）
      无解         → 跳过

    依赖：
      - file 表已有记录（analyze_area_file 完成）
      - file.language 已填充（analyze_file_language 完成，否则降级用扩展名检测）

    Parameters
    ----------
    repo_id : int
        目标仓库 id
    db_path : str | None
        SQLite 路径；不传则使用 config.DB_PATH
    force : bool
        True  = 先清除仓库所有旧 func 记录再重建
        False = 已有 func 记录时抛出 ValueError
    languages : list[str] | None
        若提供，只处理指定语言的文件（如 ['C', 'C++']）；
        None 则处理全部文件

    Returns
    -------
    dict[int, list[dict]]
        键为 file_id，值为该文件已入库的函数列表，每项：
        {
            "func_id":     int,
            "name":        str,
            "signature":   str,
            "start_line":  int,
            "end_line":    int,
            "return_type": str,
            "params":      list[{name, type, desc}],
        }

    Raises
    ------
    ValueError
        · repo_id 不存在
        · force=False 且已存在 func 记录
    """
    _db = db_path or DB_PATH

    # ── 取仓库信息 ────────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_file_func] repo_id={repo_id} 不存在于数据库。")

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[analyze_file_func] 目标仓库：{repo_name}（{repo_path}）")

    # ── 处理已有 func 记录 ────────────────────────────────────────
    existing_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)
    if existing_funcs:
        if force:
            for fn in existing_funcs:
                FuncDB.delete(fn['id'], db_path=_db)
            print(f"[analyze_file_func] 已清除 {len(existing_funcs)} 条旧 func 记录。")
        else:
            raise ValueError(
                f"[analyze_file_func] repo_id={repo_id} 已有 {len(existing_funcs)} 条 func 记录。"
                " 如需重新提取，请传入 force=True。"
            )

    # ── 取 file 列表 ─────────────────────────────────────────────
    all_files = FileDB.list_by_repo(repo_id, db_path=_db)
    if not all_files:
        print("[analyze_file_func] ⚠ 无 file 记录，请先执行 analyze_area_file。")
        return {}

    # 按语言过滤（可选）
    if languages:
        lang_set  = set(languages)
        all_files = [f for f in all_files if f.get('language') in lang_set]
        print(f"[analyze_file_func] 语言过滤 {lang_set}，剩余 {len(all_files)} 个文件。")

    # ── 逐文件提取 ───────────────────────────────────────────────
    result:      dict[int, list[dict]] = {}
    total_funcs  = 0
    skip_count   = 0
    err_count    = 0

    for file_rec in all_files:
        file_id  = file_rec['id']
        area_id  = file_rec['area_id']
        filename = file_rec['name']
        rel_path = file_rec['path']
        abs_path = os.path.join(repo_path, rel_path)

        # file.language 可能尚未填写（analyze_file_language 未运行），此处兜底检测
        language = (
            file_rec.get('language')
            or _detect_language(filename, abs_path)
        )

        if not os.path.isfile(abs_path):
            print(f"[analyze_file_func] ⚠ 文件不存在，跳过：{rel_path}")
            skip_count += 1
            result[file_id] = []
            continue

        # 提取函数
        try:
            extracted = _extract_funcs(abs_path, rel_path, language)
        except Exception as exc:
            print(f"[analyze_file_func] ⚠ 提取异常（{rel_path}）：{exc}")
            err_count += 1
            extracted = []

        # ── 写入 func 表 ─────────────────────────────────────────
        file_func_records: list[dict] = []
        funclist_brief:    list[dict] = []
        seen_sigs:         set[tuple] = set()

        for fn in extracted:
            func_name = fn['name']
            signature = fn.get('signature', '')

            # 同文件内去重 key：(name, signature 前 200 字节)
            dedup = (func_name, signature[:200])
            if dedup in seen_sigs:
                continue
            seen_sigs.add(dedup)

            place: dict = {
                'file_path':  rel_path,
                'start_line': fn['start_line'],
                'end_line':   fn['end_line'],
            }
            io: dict = {
                'params':  fn.get('params', []),
                'returns': {
                    'type': fn.get('return_type', ''),
                    'desc': '',
                },
            }

            try:
                func_id = FuncDB.create(
                    repo_id   = repo_id,
                    area_id   = area_id,
                    file_id   = file_id,
                    name      = func_name,
                    signature = signature,
                    place     = place,
                    io        = io,
                    db_path   = _db,
                )
            except Exception as exc:
                # UNIQUE 冲突或其他 DB 错误 → 跳过该函数
                print(
                    f"[analyze_file_func]   ⚠ 函数入库失败 "
                    f"[{rel_path}:{fn['start_line']} {func_name}]: {exc}"
                )
                continue

            file_func_records.append({
                'func_id':     func_id,
                'name':        func_name,
                'signature':   signature,
                'start_line':  fn['start_line'],
                'end_line':    fn['end_line'],
                'return_type': fn.get('return_type', ''),
                'params':      fn.get('params', []),
            })
            funclist_brief.append({
                'func_id': func_id,
                'name':    func_name,
                'brief':   '',   # 后续 analyze_file_funclist_description 填充
            })

        # ── 更新 file.funclist ───────────────────────────────────
        FileDB.update(file_id, db_path=_db, funclist=funclist_brief)

        result[file_id] = file_func_records
        n = len(file_func_records)
        total_funcs += n

        if n > 0:
            print(
                f"[analyze_file_func]   ✓ {rel_path:<55s} "
                f"lang={language:<8s}  funcs={n}"
            )

    # ── 汇总输出 ─────────────────────────────────────────────────
    files_with_funcs = sum(1 for v in result.values() if v)
    print(
        f"\n[analyze_file_func] ✓ 完成：\n"
        f"  处理文件：{len(all_files)} 个\n"
        f"  含函数文件：{files_with_funcs} 个\n"
        f"  提取函数：{total_funcs} 个\n"
        f"  跳过文件：{skip_count} 个\n"
        f"  出错文件：{err_count} 个"
    )
    if not _TREE_SITTER_OK:
        print(
            "[analyze_file_func] ⚠ tree-sitter-languages 未安装，"
            "C/C++ 解析可能退化为 ctags 兜底。\n"
            "   建议：pip install tree-sitter tree-sitter-languages"
        )

    return result
```

`test/test_file_analyzer_in_minizip-ng.py`
