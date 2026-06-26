你好！这是我目前的CodeMAP项目情况，我需要对已有代码进行改动： 简化目前的摘要内容（如precondition、description、postcondition、exception等），去除不相关的信息。 

起因是目前的算法逻辑是：每次生成一个函数的相关信息，都要单独调用一次接口，消耗太大了。 

我希望改成，在一个接口内生成该函数的precondition、description、postcondition、exception信息并存入。这样就可以把四次调用缩减成一次了

 同时我希望更改所有涉及precondition、description、postcondition、exception、brief的提示词，目前都太复杂了，不用给ai限定太多，让它以精简达意的逻辑给出格式合适的返回即可。（但是请注意，你给我提示词文件的时候不用直接给我一整个文件，一块一块的返回给我就行，这样能保证回答不会乱码）

以及请注意我的函数descrpition生成已经完全简化了，所以不需要Agent的代码和对应提示词，可以删掉：Propmt： analyze_func_description —— 函数描述 Agent

 我在想可能就是更改Step7：`analyze_func_precondition`和`analyze_func_postcondition`和`analyze_func_exception`实现、Step8：all descrption and brief这里的相关代码？ 请你帮我修改对应代码！非常感谢



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
7. **build_callgraph**：对整个仓库分析得到的函数调用图，并存入data
8. **analyze_func_callgraph**：分析该函数的调用关系，并填入对应数据【func:callgraph】
9. **analyze_func_precondition**：sa+llm分析该函数的前置调用关系（可能需要读调用链沿途的函数？），且有一些分类，这个实现需要做到非常好和细节到位，最后填入对应数据【func:precondition】
10. **analyze_func_postcondition**：sa+llm分析该函数的后置调用关系（可能需要读被调用链沿途的函数？），且有一些分类，这个实现需要做到非常好和细节到位，最后填入对应数据【func:postcondition】
11. **analyze_func_exception**：分析该函数的异常处理，填入对应数据【func:exception】

1. **analyze_func_description**：agent实现，提供该函数内容+调用关系+前置条件+后置条件+异常处理，以及给一个get_func_context的工具调用结构，可以agent工具得到调用链里的函数信息；让agent给出该函数的自然语言描述：该函数功能+函数分析+函数安全分析+开发者意图分析等，最后填入对应数据【func:description】
2. **analyze_file_funclist_brief**：通过提供file的funclist，将每个func的description变成简短的一两句话存入对应数据【file:funclist】
3. **analyze_file_description**：给llm提供file在area里的文件组织架构、文件信息、其中函数所有的description，得到对文件的自然语言描述：文件功能+文件定位+开发者意图分析，最后填入对应数据【file:description】
4. **analyze_area_filelist_brief**：通过提供area的filelist，将每个file的description变成简短的一两句话存入对应数据【area:filelist】
5. **analyze_area_description**：给llm提供area的在仓库中路径及分层依据+area里的文件组织架构、其中file所有的description，得到对area的自然语言描述：area功能+area定位+开发者意图分析，最后填入对应数据【area:description】
6. **analyze_repo_arealist_brief**：通过提供repo的arealist，每个area的description变成简短的一两句话存入对应数据【repo:arealist】
7. **analyze_repo_description**：给llm提供仓库的文件组织结构、分层结构、仓库相关信息、仓库里可参考的文本内容、仓库的所有area的description，得到对仓库的自然语言描述：仓库功能+开发者意图分析，最后填入对应数据【repo:description】
8. **build_codemap**：实现CodeMAP，即将上述流程串起来

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
├── config.py                    # 全局配置（API Key、模型）
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

### Step6：`build_callgraph`和`analyze_func_callgraph`

`analyzer/callgraph_builder.py`

```
"""
analyzer/callgraph_builder.py
CodeMAP 调用图构建器（纯静态分析，无需编译）

实现：
  - build_callgraph        : 静态分析整个仓库，构建函数调用图
                             中间产物保存至 data/callgraph/<repo_name>_callgraph.json
  - analyze_func_callgraph : 从调用图文件读取每个函数的调用关系，
                             写入 func.callgraph 字段

静态分析策略（按优先级）：
  Python      → ast 模块（精确，零依赖）
  C / C++     → tree-sitter 专用提取器（精确 call_expression）
  其他有 TS 支持 → tree-sitter 通用提取器
  兜底         → 正则表达式（近似，接受有限误报）

callee 分类规则：
  callee 名在本仓库 user_func_index 中 → type="user"，附 file_path 和 func_id
  callee 在 _STDLIB_HEADER 表中       → type="lib"，file="<header.h>"
  其他未识别                           → type="lib"，file=null
"""

import ast
import json as _json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, FileDB, FuncDB
from config import DB_PATH, DATA_DIR


# ==================================================================
# 0. tree-sitter 可用性检测
# ==================================================================

try:
    from tree_sitter_languages import get_parser as _ts_get_parser
    _ts_get_parser('c')
    _TREE_SITTER_OK = True
except Exception:
    _TREE_SITTER_OK = False


# ==================================================================
# 1. 常量
# ==================================================================

# C/C++ 关键字及控制流词（不是函数调用）
_C_KEYWORDS: frozenset[str] = frozenset({
    'if', 'else', 'while', 'for', 'do', 'switch', 'case',
    'break', 'continue', 'return', 'goto', 'default',
    'sizeof', 'alignof', 'typeof', '_Alignof', '_Generic',
    '__typeof__', '__typeof', '__sizeof__',
    '__builtin_expect', '__builtin_unreachable',
    '__builtin_offsetof', '__builtin_constant_p',
    '__builtin_va_start', '__builtin_va_end', '__builtin_va_arg',
    'NULL', 'TRUE', 'FALSE', 'true', 'false', 'nullptr',
    'offsetof', 'container_of', 'likely', 'unlikely',
    'static_assert', '_Static_assert',
    # C++ 操作符关键字
    'new', 'delete', 'throw', 'catch', 'try',
    'typeid', 'decltype', 'noexcept', 'constexpr',
    '__declspec', '__cdecl', '__stdcall', '__fastcall',
    # 常见类型名（防止类型转换被误识别为函数调用）
    'int', 'char', 'short', 'long', 'float', 'double',
    'void', 'unsigned', 'signed', 'bool', 'auto',
    'const', 'volatile', 'register', 'static', 'extern', 'inline',
    'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
    'int8_t', 'int16_t', 'int32_t', 'int64_t',
    'size_t', 'ssize_t', 'off_t', 'ptrdiff_t', 'uintptr_t', 'intptr_t',
    'BOOL', 'BYTE', 'WORD', 'DWORD', 'QWORD', 'HANDLE',
})

# 正则：匹配 C/C++ 函数调用形式的标识符（含 keyword 后过滤）
_C_CALL_RE = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')

# 标准库函数名 → 来源头文件（用于 lib callee 的 file 字段标注）
_STDLIB_HEADER: dict[str, str] = {
    # ── stdio.h ──
    'printf': 'stdio.h', 'fprintf': 'stdio.h', 'sprintf': 'stdio.h',
    'snprintf': 'stdio.h', 'vprintf': 'stdio.h', 'vfprintf': 'stdio.h',
    'vsprintf': 'stdio.h', 'vsnprintf': 'stdio.h',
    'scanf': 'stdio.h', 'fscanf': 'stdio.h', 'sscanf': 'stdio.h',
    'vfscanf': 'stdio.h', 'vsscanf': 'stdio.h', 'vscanf': 'stdio.h',
    'fopen': 'stdio.h', 'fclose': 'stdio.h',
    'fread': 'stdio.h', 'fwrite': 'stdio.h',
    'fseek': 'stdio.h', 'fseeko': 'stdio.h', 'fseeko64': 'stdio.h',
    'ftell': 'stdio.h', 'ftello': 'stdio.h', 'ftello64': 'stdio.h',
    'fflush': 'stdio.h', 'rewind': 'stdio.h',
    'feof': 'stdio.h', 'ferror': 'stdio.h', 'clearerr': 'stdio.h',
    'perror': 'stdio.h',
    'fgetc': 'stdio.h', 'fputc': 'stdio.h', 'ungetc': 'stdio.h',
    'fgets': 'stdio.h', 'fputs': 'stdio.h',
    'puts': 'stdio.h', 'putchar': 'stdio.h', 'getchar': 'stdio.h',
    'remove': 'stdio.h', 'rename': 'stdio.h',
    'tmpfile': 'stdio.h', 'tmpnam': 'stdio.h',
    'fileno': 'stdio.h', 'fdopen': 'stdio.h',
    'popen': 'stdio.h', 'pclose': 'stdio.h',
    'setvbuf': 'stdio.h', 'setbuf': 'stdio.h',
    # ── stdlib.h ──
    'malloc': 'stdlib.h', 'free': 'stdlib.h',
    'calloc': 'stdlib.h', 'realloc': 'stdlib.h',
    'aligned_alloc': 'stdlib.h', 'posix_memalign': 'stdlib.h',
    'exit': 'stdlib.h', 'abort': 'stdlib.h',
    '_exit': 'unistd.h', 'atexit': 'stdlib.h',
    'at_quick_exit': 'stdlib.h', 'quick_exit': 'stdlib.h',
    'atoi': 'stdlib.h', 'atol': 'stdlib.h', 'atoll': 'stdlib.h',
    'atof': 'stdlib.h',
    'strtol': 'stdlib.h', 'strtoul': 'stdlib.h',
    'strtoll': 'stdlib.h', 'strtoull': 'stdlib.h',
    'strtof': 'stdlib.h', 'strtod': 'stdlib.h', 'strtold': 'stdlib.h',
    'rand': 'stdlib.h', 'srand': 'stdlib.h', 'rand_r': 'stdlib.h',
    'qsort': 'stdlib.h', 'qsort_r': 'stdlib.h', 'bsearch': 'stdlib.h',
    'abs': 'stdlib.h', 'labs': 'stdlib.h', 'llabs': 'stdlib.h',
    'div': 'stdlib.h', 'ldiv': 'stdlib.h', 'lldiv': 'stdlib.h',
    'getenv': 'stdlib.h', 'setenv': 'stdlib.h', 'unsetenv': 'stdlib.h',
    'putenv': 'stdlib.h', 'system': 'stdlib.h', 'realpath': 'stdlib.h',
    'mbstowcs': 'stdlib.h', 'wcstombs': 'stdlib.h',
    # ── string.h ──
    'memset': 'string.h', 'memcpy': 'string.h', 'memmove': 'string.h',
    'memcmp': 'string.h', 'memchr': 'string.h', 'memrchr': 'string.h',
    'strlen': 'string.h', 'strnlen': 'string.h',
    'strcpy': 'string.h', 'strncpy': 'string.h',
    'stpcpy': 'string.h', 'stpncpy': 'string.h',
    'strcat': 'string.h', 'strncat': 'string.h',
    'strcmp': 'string.h', 'strncmp': 'string.h',
    'strcasecmp': 'string.h', 'strncasecmp': 'string.h',
    'strcoll': 'string.h', 'strxfrm': 'string.h',
    'strchr': 'string.h', 'strrchr': 'string.h',
    'strstr': 'string.h', 'strcasestr': 'string.h',
    'strtok': 'string.h', 'strtok_r': 'string.h',
    'strdup': 'string.h', 'strndup': 'string.h',
    'strerror': 'string.h', 'strerror_r': 'string.h',
    'strspn': 'string.h', 'strcspn': 'string.h',
    'strpbrk': 'string.h', 'strsep': 'string.h',
    # ── math.h ──
    'sqrt': 'math.h', 'sqrtf': 'math.h', 'sqrtl': 'math.h',
    'cbrt': 'math.h', 'cbrtf': 'math.h',
    'pow': 'math.h', 'powf': 'math.h',
    'log': 'math.h', 'logf': 'math.h',
    'log2': 'math.h', 'log2f': 'math.h',
    'log10': 'math.h', 'log10f': 'math.h',
    'exp': 'math.h', 'expf': 'math.h',
    'exp2': 'math.h', 'exp2f': 'math.h',
    'ceil': 'math.h', 'ceilf': 'math.h',
    'floor': 'math.h', 'floorf': 'math.h',
    'round': 'math.h', 'roundf': 'math.h',
    'trunc': 'math.h', 'truncf': 'math.h',
    'fabs': 'math.h', 'fabsf': 'math.h',
    'fmod': 'math.h', 'fmodf': 'math.h',
    'fmin': 'math.h', 'fminf': 'math.h',
    'fmax': 'math.h', 'fmaxf': 'math.h',
    'sin': 'math.h', 'sinf': 'math.h',
    'cos': 'math.h', 'cosf': 'math.h',
    'tan': 'math.h', 'tanf': 'math.h',
    'asin': 'math.h', 'acos': 'math.h',
    'atan': 'math.h', 'atan2': 'math.h', 'atan2f': 'math.h',
    'sinh': 'math.h', 'cosh': 'math.h', 'tanh': 'math.h',
    'hypot': 'math.h', 'hypotf': 'math.h',
    'isnan': 'math.h', 'isinf': 'math.h', 'isfinite': 'math.h',
    'modf': 'math.h', 'frexp': 'math.h', 'ldexp': 'math.h',
    # ── assert.h ──
    'assert': 'assert.h',
    # ── ctype.h ──
    'isalpha': 'ctype.h', 'isdigit': 'ctype.h', 'isalnum': 'ctype.h',
    'isspace': 'ctype.h', 'isupper': 'ctype.h', 'islower': 'ctype.h',
    'isprint': 'ctype.h', 'ispunct': 'ctype.h', 'isxdigit': 'ctype.h',
    'iscntrl': 'ctype.h', 'isgraph': 'ctype.h', 'isblank': 'ctype.h',
    'toupper': 'ctype.h', 'tolower': 'ctype.h',
    # ── time.h ──
    'time': 'time.h', 'clock': 'time.h', 'difftime': 'time.h',
    'mktime': 'time.h', 'gmtime': 'time.h', 'gmtime_r': 'time.h',
    'localtime': 'time.h', 'localtime_r': 'time.h',
    'strftime': 'time.h', 'strptime': 'time.h',
    'ctime': 'time.h', 'asctime': 'time.h',
    'nanosleep': 'time.h',
    'clock_gettime': 'time.h', 'clock_settime': 'time.h',
    'clock_getres': 'time.h',
    # ── unistd.h ──
    'read': 'unistd.h', 'write': 'unistd.h', 'close': 'unistd.h',
    'lseek': 'unistd.h', 'lseek64': 'unistd.h',
    'unlink': 'unistd.h', 'rmdir': 'unistd.h',
    'link': 'unistd.h', 'symlink': 'unistd.h', 'readlink': 'unistd.h',
    'getpid': 'unistd.h', 'getppid': 'unistd.h',
    'getuid': 'unistd.h', 'getgid': 'unistd.h',
    'geteuid': 'unistd.h', 'getegid': 'unistd.h',
    'fork': 'unistd.h', 'execv': 'unistd.h', 'execvp': 'unistd.h',
    'execve': 'unistd.h', 'execl': 'unistd.h', 'execlp': 'unistd.h',
    'sleep': 'unistd.h', 'usleep': 'unistd.h',
    'getcwd': 'unistd.h', 'chdir': 'unistd.h',
    'dup': 'unistd.h', 'dup2': 'unistd.h',
    'pipe': 'unistd.h', 'isatty': 'unistd.h',
    'access': 'unistd.h', 'truncate': 'unistd.h', 'ftruncate': 'unistd.h',
    'fsync': 'unistd.h', 'fdatasync': 'unistd.h',
    'gethostname': 'unistd.h',
    # ── fcntl.h ──
    'open': 'fcntl.h', 'open64': 'fcntl.h', 'openat': 'fcntl.h',
    'creat': 'fcntl.h', 'fcntl': 'fcntl.h',
    # ── sys/stat.h ──
    'stat': 'sys/stat.h', 'stat64': 'sys/stat.h',
    'lstat': 'sys/stat.h', 'fstat': 'sys/stat.h', 'fstat64': 'sys/stat.h',
    'mkdir': 'sys/stat.h', 'mkdirat': 'sys/stat.h',
    'chmod': 'sys/stat.h', 'fchmod': 'sys/stat.h', 'umask': 'sys/stat.h',
    # ── dirent.h ──
    'opendir': 'dirent.h', 'closedir': 'dirent.h',
    'readdir': 'dirent.h', 'readdir_r': 'dirent.h',
    'scandir': 'dirent.h', 'rewinddir': 'dirent.h',
    # ── pthread.h ──
    'pthread_create': 'pthread.h', 'pthread_join': 'pthread.h',
    'pthread_detach': 'pthread.h', 'pthread_exit': 'pthread.h',
    'pthread_self': 'pthread.h', 'pthread_equal': 'pthread.h',
    'pthread_cancel': 'pthread.h',
    'pthread_mutex_init': 'pthread.h', 'pthread_mutex_lock': 'pthread.h',
    'pthread_mutex_trylock': 'pthread.h', 'pthread_mutex_unlock': 'pthread.h',
    'pthread_mutex_destroy': 'pthread.h',
    'pthread_cond_init': 'pthread.h', 'pthread_cond_wait': 'pthread.h',
    'pthread_cond_timedwait': 'pthread.h',
    'pthread_cond_signal': 'pthread.h', 'pthread_cond_broadcast': 'pthread.h',
    'pthread_cond_destroy': 'pthread.h',
    'pthread_rwlock_init': 'pthread.h', 'pthread_rwlock_rdlock': 'pthread.h',
    'pthread_rwlock_wrlock': 'pthread.h', 'pthread_rwlock_unlock': 'pthread.h',
    'pthread_rwlock_destroy': 'pthread.h',
    'pthread_key_create': 'pthread.h', 'pthread_key_delete': 'pthread.h',
    'pthread_setspecific': 'pthread.h', 'pthread_getspecific': 'pthread.h',
    # ── setjmp.h ──
    'setjmp': 'setjmp.h', 'longjmp': 'setjmp.h',
    '_setjmp': 'setjmp.h', '_longjmp': 'setjmp.h',
    'sigsetjmp': 'setjmp.h', 'siglongjmp': 'setjmp.h',
    # ── signal.h ──
    'signal': 'signal.h', 'raise': 'signal.h',
    'kill': 'signal.h', 'sigaction': 'signal.h',
    'sigemptyset': 'signal.h', 'sigfillset': 'signal.h',
    'sigaddset': 'signal.h', 'sigdelset': 'signal.h',
    'sigismember': 'signal.h', 'sigprocmask': 'signal.h',
    # ── zlib.h（minizip-ng 核心依赖）──
    'deflateInit': 'zlib.h', 'deflateInit2': 'zlib.h', 'deflateInit2_': 'zlib.h',
    'deflate': 'zlib.h', 'deflateEnd': 'zlib.h', 'deflateReset': 'zlib.h',
    'deflateSetDictionary': 'zlib.h', 'deflateCopy': 'zlib.h',
    'deflateParams': 'zlib.h', 'deflateTune': 'zlib.h',
    'deflateBound': 'zlib.h', 'deflatePrime': 'zlib.h',
    'inflateInit': 'zlib.h', 'inflateInit2': 'zlib.h', 'inflateInit2_': 'zlib.h',
    'inflate': 'zlib.h', 'inflateEnd': 'zlib.h', 'inflateReset': 'zlib.h',
    'inflateReset2': 'zlib.h', 'inflatePrime': 'zlib.h',
    'inflateSetDictionary': 'zlib.h', 'inflateGetDictionary': 'zlib.h',
    'inflateSync': 'zlib.h', 'inflateCopy': 'zlib.h',
    'compress': 'zlib.h', 'compress2': 'zlib.h', 'compressBound': 'zlib.h',
    'uncompress': 'zlib.h', 'uncompress2': 'zlib.h',
    'adler32': 'zlib.h', 'adler32_z': 'zlib.h', 'adler32_combine': 'zlib.h',
    'crc32': 'zlib.h', 'crc32_z': 'zlib.h', 'crc32_combine': 'zlib.h',
    'zlibVersion': 'zlib.h', 'zlibCompileFlags': 'zlib.h', 'zError': 'zlib.h',
    # ── Windows API ──
    'GetLastError': 'windows.h', 'SetLastError': 'windows.h',
    'CreateFileA': 'windows.h', 'CreateFileW': 'windows.h',
    'CloseHandle': 'windows.h', 'ReadFile': 'windows.h', 'WriteFile': 'windows.h',
    'VirtualAlloc': 'windows.h', 'VirtualFree': 'windows.h',
    'HeapAlloc': 'windows.h', 'HeapFree': 'windows.h',
    'GetProcessHeap': 'windows.h',
    'LoadLibraryA': 'windows.h', 'LoadLibraryW': 'windows.h',
    'FreeLibrary': 'windows.h', 'GetProcAddress': 'windows.h',
    'MultiByteToWideChar': 'windows.h', 'WideCharToMultiByte': 'windows.h',
}


# ==================================================================
# 2. tree-sitter 工具函数（本地化副本，避免跨模块引用私有函数）
# ==================================================================

def _ts_text(node, src: bytes) -> str:
    """从 tree-sitter 节点提取原始文本。"""
    return src[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _find_all_nodes(root, wanted: set) -> list:
    """
    DFS 遍历 tree-sitter 语法树，收集所有类型在 wanted 中的节点（不剪枝，
    支持嵌套函数中的调用收集）。
    """
    result, stack = [], [root]
    while stack:
        node = stack.pop()
        if node.type in wanted:
            result.append(node)
        for child in reversed(node.children):
            stack.append(child)
    return result


# ==================================================================
# 3. C/C++ 函数定义名称提取（用于将 tree-sitter 节点匹配到 DB 记录）
# ==================================================================

def _find_c_func_declarator(node) -> Optional[object]:
    """在 declarator 链中找到 function_declarator 节点。"""
    if node is None:
        return None
    if node.type == 'function_declarator':
        return node
    wrapping = {
        'pointer_declarator', 'reference_declarator',
        'parenthesized_declarator', 'abstract_declarator',
        'abstract_pointer_declarator',
    }
    if node.type in wrapping:
        inner = node.child_by_field_name('declarator')
        if inner:
            r = _find_c_func_declarator(inner)
            if r:
                return r
        for child in node.children:
            r = _find_c_func_declarator(child)
            if r:
                return r
    return None


def _extract_c_decl_name(node, src: bytes) -> str:
    """从 declarator 节点递归提取函数标识符名称。"""
    if node is None:
        return ''
    t = node.type
    if t in ('identifier', 'field_identifier'):
        return _ts_text(node, src)
    if t in ('qualified_identifier', 'destructor_name',
             'operator_name', 'template_function', 'template_method'):
        return _ts_text(node, src)
    if t in ('pointer_declarator', 'reference_declarator'):
        inner = node.child_by_field_name('declarator')
        if inner:
            return _extract_c_decl_name(inner, src)
    if t == 'parenthesized_declarator':
        for child in node.children:
            r = _extract_c_decl_name(child, src)
            if r:
                return r
    for child in node.children:
        r = _extract_c_decl_name(child, src)
        if r:
            return r
    return _ts_text(node, src)


def _get_c_func_name(func_def_node, src: bytes) -> Optional[str]:
    """从 C/C++ function_definition 节点提取函数名。"""
    declarator = func_def_node.child_by_field_name('declarator')
    if declarator is None:
        return None
    func_decl = _find_c_func_declarator(declarator)
    if func_decl is None:
        return None
    inner = func_decl.child_by_field_name('declarator')
    if inner is None:
        return None
    name = _extract_c_decl_name(inner, src).strip()
    return name or None


# ==================================================================
# 4. callee 名称提取（call_expression 节点 → 函数名字符串）
# ==================================================================

def _get_callee_name_c(func_field, src: bytes) -> Optional[str]:
    """
    从 C/C++ call_expression.function 节点提取被调用函数名。
    间接调用（函数指针、下标表达式等）返回 None。
    """
    t = func_field.type

    if t == 'identifier':
        name = _ts_text(func_field, src).strip()
        return name if name not in _C_KEYWORDS else None

    if t == 'field_expression':
        # obj.method 或 obj->method → 取 field 部分
        field = func_field.child_by_field_name('field')
        if field:
            return _ts_text(field, src).strip() or None
        return None

    if t == 'qualified_identifier':
        # ns::func 或 Class::method → 保留全限定名，调用方再处理
        text = _ts_text(func_field, src).strip()
        return text or None

    if t == 'template_function':
        # func<T>() → 取函数名部分
        name_node = func_field.child_by_field_name('name')
        if name_node:
            return _ts_text(name_node, src).strip() or None
        # ns::func<T> 形式
        for child in func_field.children:
            if child.type == 'qualified_identifier':
                return _get_callee_name_c(child, src)
        return None

    # 以下属于间接调用，跳过
    if t in (
        'parenthesized_expression', 'pointer_expression',
        'subscript_expression', 'conditional_expression',
        'binary_expression', 'cast_expression',
        'unary_expression', 'comma_expression',
    ):
        return None

    # 其他复杂情形：DFS 找第一个 identifier（最多 2 层）
    for child in func_field.children:
        if child.type == 'identifier':
            name = _ts_text(child, src).strip()
            if name and name not in _C_KEYWORDS:
                return name

    return None


def _get_callee_name_generic(call_node, src: bytes, ts_lang: str) -> Optional[str]:
    """
    通用策略：从 call_expression 节点提取被调用函数名。
    适用于 Java / Go / Rust / JavaScript / TypeScript 等。
    """
    # ① 尝试 'function' field（Go/Rust/JS/TS）
    func_field = call_node.child_by_field_name('function')
    if func_field:
        t = func_field.type
        if t in ('identifier', 'simple_identifier'):
            return _ts_text(func_field, src).strip() or None
        if t in ('field_expression', 'member_expression',
                 'selector_expression', 'dot_expression'):
            for fn in ('field', 'name', 'selector', 'attribute'):
                n = func_field.child_by_field_name(fn)
                if n:
                    return _ts_text(n, src).strip() or None
        if t in ('qualified_identifier', 'scoped_identifier',
                 'scope_resolution', 'type_qualified'):
            text = _ts_text(func_field, src).strip()
            parts = re.split(r'[:./]+', text)
            return parts[-1].strip() if parts else None
        # DFS 取第一个 identifier（深度限 3）
        def _dfs(n, d=0):
            if d > 3:
                return None
            if n.type in ('identifier', 'simple_identifier', 'type_identifier'):
                return _ts_text(n, src).strip() or None
            for ch in n.children:
                r = _dfs(ch, d + 1)
                if r:
                    return r
            return None
        r = _dfs(func_field)
        if r:
            return r

    # ② Java method_invocation 的 'name' field
    name_field = call_node.child_by_field_name('name')
    if name_field:
        return _ts_text(name_field, src).strip() or None

    # ③ Rust macro_invocation 的 'macro' field
    macro_field = call_node.child_by_field_name('macro')
    if macro_field:
        return _ts_text(macro_field, src).strip() or None

    return None


# ==================================================================
# 5. 文件级调用关系提取（各语言实现）
# ==================================================================

def _read_source_for_callgraph(abs_path: str) -> Optional[str]:
    """读取源文件；编码自动降级；超大文件（>5MB）跳过。"""
    try:
        if os.path.getsize(abs_path) > 5 * 1024 * 1024:
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


def _build_name_line_index(db_funcs: list[dict]) -> tuple[
    dict[tuple[str, int], int],
    dict[str, list[int]],
]:
    """
    从 DB func 记录构建两级查找索引：
      (func_name, start_line) → func_id   精确匹配
      func_name → [func_id, ...]          名称匹配（用于行号偏差兜底）
    """
    name_line_to_id: dict[tuple[str, int], int] = {}
    name_to_ids: dict[str, list[int]] = defaultdict(list)
    for fn in db_funcs:
        place = fn.get('place', {})
        if not isinstance(place, dict):
            continue
        sl   = place.get('start_line', 0)
        name = fn['name']
        fid  = fn['id']
        name_line_to_id[(name, sl)] = fid
        name_to_ids[name].append(fid)
    return name_line_to_id, name_to_ids


def _resolve_caller_id(
    func_name: str,
    start_line: int,
    name_line_to_id: dict,
    name_to_ids: dict,
) -> Optional[int]:
    """
    将 tree-sitter 解析到的函数（名+行号）映射到 DB func_id。
    策略：精确行号 → ±1/±2 行容差 → 同名唯一匹配兜底。
    """
    fid = name_line_to_id.get((func_name, start_line))
    if fid is not None:
        return fid
    for delta in (-1, 1, -2, 2):
        fid = name_line_to_id.get((func_name, start_line + delta))
        if fid is not None:
            return fid
    ids = name_to_ids.get(func_name, [])
    if len(ids) == 1:
        return ids[0]
    return None


# ------------------------------------------------------------------
# 5a. C / C++ 提取器
# ------------------------------------------------------------------

def _extract_c_file_calls(
    source: str,
    db_funcs: list[dict],
    language: str,
) -> list[tuple[int, str]]:
    """tree-sitter 精确提取 C/C++ 文件调用边，返回 (caller_id, callee_name) 列表。"""
    if not _TREE_SITTER_OK:
        return []

    ts_name = 'cpp' if language in ('C++', 'Objective-C') else 'c'
    src_bytes = source.encode('utf-8', errors='replace')
    try:
        parser = _ts_get_parser(ts_name)
        tree   = parser.parse(src_bytes)
    except Exception as e:
        print(f"  [callgraph/_extract_c] tree-sitter 解析失败（{ts_name}）: {e}")
        return []

    name_line_to_id, name_to_ids = _build_name_line_index(db_funcs)
    results: list[tuple[int, str]] = []

    for func_node in _find_all_nodes(tree.root_node, {'function_definition'}):
        body = func_node.child_by_field_name('body')
        if body is None:
            continue

        start_line = func_node.start_point[0] + 1
        func_name  = _get_c_func_name(func_node, src_bytes)
        if not func_name:
            continue

        caller_id = _resolve_caller_id(func_name, start_line, name_line_to_id, name_to_ids)
        if caller_id is None:
            continue

        seen: set[str] = set()
        for call_node in _find_all_nodes(body, {'call_expression'}):
            func_field = call_node.child_by_field_name('function')
            if func_field is None:
                continue
            callee = _get_callee_name_c(func_field, src_bytes)
            if callee and callee not in seen:
                seen.add(callee)
                results.append((caller_id, callee))

    return results


# ------------------------------------------------------------------
# 5b. Python 提取器
# ------------------------------------------------------------------

def _extract_python_file_calls(
    source: str,
    rel_path: str,
    db_funcs: list[dict],
) -> list[tuple[int, str]]:
    """ast 精确提取 Python 文件调用边。"""
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError:
        return []

    name_line_to_id, name_to_ids = _build_name_line_index(db_funcs)
    results: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        caller_id = _resolve_caller_id(
            node.name, node.lineno, name_line_to_id, name_to_ids
        )
        if caller_id is None:
            continue

        seen: set[str] = set()
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if isinstance(child.func, ast.Name):
                callee = child.func.id
            elif isinstance(child.func, ast.Attribute):
                callee = child.func.attr
            else:
                continue
            if callee and callee not in seen:
                seen.add(callee)
                results.append((caller_id, callee))

    return results


# ------------------------------------------------------------------
# 5c. 通用 tree-sitter 提取器（Java / Go / Rust / JS / TS 等）
# ------------------------------------------------------------------

# 语言 → (函数定义节点类型集合, 调用表达式节点类型集合)
_LANG_TS_TYPES: dict[str, tuple[set, set]] = {
    'java':       (
        {'method_declaration', 'constructor_declaration'},
        {'method_invocation', 'object_creation_expression'},
    ),
    'javascript': (
        {'function_declaration', 'method_definition', 'function_expression',
         'arrow_function', 'generator_function_declaration'},
        {'call_expression', 'new_expression'},
    ),
    'typescript': (
        {'function_declaration', 'method_definition', 'function_expression',
         'arrow_function', 'generator_function_declaration'},
        {'call_expression', 'new_expression'},
    ),
    'go':         (
        {'function_declaration', 'method_declaration'},
        {'call_expression'},
    ),
    'rust':       (
        {'function_item'},
        {'call_expression', 'macro_invocation'},
    ),
    'ruby':       (
        {'method', 'singleton_method'},
        {'call', 'method_call'},
    ),
    'kotlin':     (
        {'function_declaration'},
        {'call_expression', 'constructor_invocation'},
    ),
    'swift':      (
        {'function_declaration'},
        {'call_expression', 'explicit_member_expression'},
    ),
}

_LANG_TO_TS_NAME: dict[str, str] = {
    'Java': 'java', 'JavaScript': 'javascript', 'TypeScript': 'typescript',
    'Go': 'go', 'Rust': 'rust', 'Ruby': 'ruby',
    'Kotlin': 'kotlin', 'Swift': 'swift',
}


def _extract_generic_ts_file_calls(
    source: str,
    db_funcs: list[dict],
    ts_lang: str,
) -> list[tuple[int, str]]:
    """通用 tree-sitter 调用边提取。"""
    if not _TREE_SITTER_OK:
        return []

    func_types, call_types = _LANG_TS_TYPES.get(ts_lang, (set(), set()))
    if not func_types or not call_types:
        return []

    src_bytes = source.encode('utf-8', errors='replace')
    try:
        parser = _ts_get_parser(ts_lang)
        tree   = parser.parse(src_bytes)
    except Exception:
        return []

    name_line_to_id, name_to_ids = _build_name_line_index(db_funcs)
    results: list[tuple[int, str]] = []

    for func_node in _find_all_nodes(tree.root_node, func_types):
        start_line = func_node.start_point[0] + 1

        name_node = func_node.child_by_field_name('name')
        func_name = _ts_text(name_node, src_bytes).strip() if name_node else ''
        if not func_name:
            continue

        caller_id = _resolve_caller_id(func_name, start_line, name_line_to_id, name_to_ids)
        if caller_id is None:
            continue

        seen: set[str] = set()
        for call_node in _find_all_nodes(func_node, call_types):
            callee = _get_callee_name_generic(call_node, src_bytes, ts_lang)
            if callee and callee not in seen:
                seen.add(callee)
                results.append((caller_id, callee))

    return results


# ------------------------------------------------------------------
# 5d. 正则兜底提取器
# ------------------------------------------------------------------

def _strip_comments_strings(text: str) -> str:
    """
    粗粒度去除 C 风格注释和字符串字面量，减少正则误报。
    不追求 100% 准确，只需明显降低噪声。
    """
    # 块注释
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.DOTALL)
    # 行注释
    text = re.sub(r'//[^\n]*', ' ', text)
    # 双引号字符串（简化：不处理转义内的引号）
    text = re.sub(r'"[^"\n]{0,500}"', '""', text)
    # 单引号字符（C char literal）
    text = re.sub(r"'[^'\n]{0,4}'", "''", text)
    return text


def _extract_regex_file_calls(
    source: str,
    db_funcs: list[dict],
) -> list[tuple[int, str]]:
    """
    正则表达式兜底：按函数行范围切片，提取 identifier( 模式。
    注意：此方法有误报（宏调用、类型转换等），仅在 tree-sitter 不可用时使用。
    """
    lines  = source.split('\n')
    result: list[tuple[int, str]] = []

    for fn in db_funcs:
        place = fn.get('place', {})
        if not isinstance(place, dict):
            continue
        start = place.get('start_line', 0)
        end   = place.get('end_line', start)
        fid   = fn['id']
        if start <= 0:
            continue

        func_src = '\n'.join(lines[start - 1:end])
        func_src = _strip_comments_strings(func_src)

        seen: set[str] = set()
        for m in _C_CALL_RE.finditer(func_src):
            name = m.group(1)
            if name not in _C_KEYWORDS and name not in seen:
                seen.add(name)
                result.append((fid, name))

    return result


# ------------------------------------------------------------------
# 5e. 分发器
# ------------------------------------------------------------------

def _extract_file_calls(
    abs_path: str,
    rel_path: str,
    language: str,
    db_funcs: list[dict],
) -> list[tuple[int, str]]:
    """
    根据语言选择最合适的调用边提取策略，返回 (caller_func_id, callee_name) 列表。

    优先级：Python ast → C/C++ tree-sitter → 通用 tree-sitter → 正则兜底。
    """
    if not db_funcs:
        return []

    source = _read_source_for_callgraph(abs_path)
    if source is None:
        return []

    # Python
    if language == 'Python':
        return _extract_python_file_calls(source, rel_path, db_funcs)

    # C / C++ / Objective-C
    if language in ('C', 'C++', 'Objective-C'):
        if _TREE_SITTER_OK:
            result = _extract_c_file_calls(source, db_funcs, language)
            if result:
                return result
        return _extract_regex_file_calls(source, db_funcs)

    # 其他有 tree-sitter 支持的语言
    ts_name = _LANG_TO_TS_NAME.get(language)
    if ts_name and _TREE_SITTER_OK:
        try:
            result = _extract_generic_ts_file_calls(source, db_funcs, ts_name)
            if result:
                return result
        except Exception:
            pass

    # 兜底：正则（对 C-style 语言近似有效）
    return _extract_regex_file_calls(source, db_funcs)


# ==================================================================
# 6. callee 分类
# ==================================================================

def _classify_callee(
    callee_name: str,
    user_func_index: dict[str, list[dict]],
) -> tuple[str, Optional[str], Optional[int]]:
    """
    判断 callee 是用户函数（user）还是库函数（lib）。

    对 C++ 限定名（如 ns::foo）先取短名再查找，
    存在多个同名用户函数时返回第一个（调用方去重）。

    Returns
    -------
    (callee_type, callee_file, callee_id)
        callee_type : "user" | "lib"
        callee_file : 用户函数相对路径 / "<header.h>" / None
        callee_id   : 用户函数 DB id / None
    """
    # C++ 限定名降级为短名
    short_name = callee_name.rsplit('::', 1)[-1].strip()

    # 用户函数索引查找（全名优先，再短名）
    matches = user_func_index.get(callee_name) or user_func_index.get(short_name)
    if matches:
        m = matches[0]
        return ('user', m['file'], m['func_id'])

    # 标准库头文件推断
    header = _STDLIB_HEADER.get(short_name)
    if header:
        return ('lib', f'<{header}>', None)

    return ('lib', None, None)


# ==================================================================
# 7. build_callgraph
# ==================================================================

def build_callgraph(
    repo_id: int,
    db_path: Optional[str] = None,
    force: bool = False,
) -> str:
    """
    静态分析整个仓库，构建函数调用图并保存为 JSON 中间产物。

    核心流程
    --------
    1. 从 DB 加载所有 func 记录，构建 user_func_index
    2. 将 func 按 file_id 分组，逐文件提取调用边
       (caller_func_id, callee_name)
    3. 对每条 callee 进行 user/lib 分类和文件定位
    4. 保存到 data/callgraph/<repo_name>_callgraph.json

    JSON 格式
    ---------
    {
      "repo_id": 1,
      "repo_name": "minizip-ng",
      "generated_at": "2024-01-01T12:00:00",
      "stats": { ... },
      "user_func_index": { "func_name": [{"func_id":1,"file":"...","start_line":10}] },
      "call_edges": [
        {
          "caller_id": 1, "caller_name": "foo", "caller_file": "src/foo.c",
          "callee_name": "bar", "callee_id": 2, "callee_file": "src/bar.c",
          "callee_type": "user"
        },
        ...
      ]
    }

    Parameters
    ----------
    repo_id : int
    db_path : str | None
    force   : bool
        True  = 即便已存在 JSON 文件也重新生成
        False = 已存在则跳过（直接返回路径）

    Returns
    -------
    str
        调用图 JSON 文件的绝对路径

    Raises
    ------
    ValueError
        repo_id 不存在 / 无 func 记录（需先执行 analyze_file_func）
    """
    _db = db_path or DB_PATH

    # ── ① 取仓库信息 ──────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[build_callgraph] repo_id={repo_id} 在数据库中不存在。")

    repo_path = repo['path']
    repo_name = repo['name']
    print(f"[build_callgraph] 目标仓库：{repo_name}（{repo_path}）")

    # ── ② 处理输出路径 ────────────────────────────────────────────
    output_dir  = os.path.join(DATA_DIR, 'callgraph')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'{repo_name}_callgraph.json')

    if os.path.exists(output_path) and not force:
        print(
            f"[build_callgraph] 调用图已存在（使用缓存）：{output_path}\n"
            f"[build_callgraph] 如需重新生成，请传入 force=True。"
        )
        return output_path

    # ── ③ 加载所有 func 记录 ──────────────────────────────────────
    all_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)
    if not all_funcs:
        raise ValueError(
            f"[build_callgraph] repo_id={repo_id} 无 func 记录，"
            "请先执行 analyze_file_func（Step 5b）。"
        )
    print(f"[build_callgraph] 已加载 {len(all_funcs)} 个函数记录")

    # ── ④ 构建 user_func_index ────────────────────────────────────
    user_func_index: dict[str, list[dict]] = defaultdict(list)
    for fn in all_funcs:
        place = fn.get('place', {})
        if not isinstance(place, dict):
            continue
        user_func_index[fn['name']].append({
            'func_id':    fn['id'],
            'file':       place.get('file_path', ''),
            'start_line': place.get('start_line', 0),
        })
    print(
        f"[build_callgraph] user_func_index：{len(user_func_index)} 个唯一函数名，"
        f"覆盖 {len(all_funcs)} 个函数记录"
    )

    # ── ⑤ 加载 file 记录（路径 + 语言）──────────────────────────
    all_files    = FileDB.list_by_repo(repo_id, db_path=_db)
    file_map:     dict[int, dict] = {f['id']: f for f in all_files}
    func_id_map:  dict[int, dict] = {fn['id']: fn for fn in all_funcs}

    # func 按 file_id 分组
    funcs_by_file: dict[int, list[dict]] = defaultdict(list)
    for fn in all_funcs:
        funcs_by_file[fn['file_id']].append(fn)

    # ── ⑥ 逐文件提取原始调用边 ───────────────────────────────────
    raw_edges: list[tuple[int, str]] = []
    total_files = len(funcs_by_file)
    processed = skipped = err_count = 0

    print(
        f"[build_callgraph] 开始逐文件提取调用关系"
        f"（共 {total_files} 个含函数文件）…"
    )

    for file_id, file_funcs in funcs_by_file.items():
        file_rec = file_map.get(file_id)
        if file_rec is None:
            skipped += 1
            continue

        rel_path = file_rec.get('path', '')
        language = file_rec.get('language') or 'Unknown'
        abs_path = os.path.join(repo_path, rel_path)

        if not os.path.isfile(abs_path):
            skipped += 1
            continue

        try:
            edges = _extract_file_calls(abs_path, rel_path, language, file_funcs)
        except Exception as exc:
            print(f"[build_callgraph]  ⚠ 提取失败 ({rel_path}): {exc}")
            err_count += 1
            continue

        raw_edges.extend(edges)
        processed += 1

        if processed % 50 == 0:
            print(
                f"[build_callgraph]   进度 {processed}/{total_files}，"
                f"已收集 {len(raw_edges)} 条原始边"
            )

    print(
        f"[build_callgraph] 提取完成："
        f"处理={processed}  跳过={skipped}  出错={err_count}  "
        f"原始调用边={len(raw_edges)}"
    )

    # ── ⑦ 去重（同一 caller 对同一 callee 只保留一条）────────────
    raw_edges_dedup = list(dict.fromkeys(raw_edges))
    print(
        f"[build_callgraph] 去重后调用边：{len(raw_edges_dedup)} 条"
        f"（去除 {len(raw_edges) - len(raw_edges_dedup)} 条重复）"
    )

    # ── ⑧ 对每条边做 callee 分类 ─────────────────────────────────
    call_edges: list[dict] = []
    cnt_user = cnt_lib_known = cnt_lib_unknown = 0

    for caller_id, callee_name in raw_edges_dedup:
        caller_fn = func_id_map.get(caller_id)
        if caller_fn is None:
            continue
        caller_place = caller_fn.get('place', {})
        if not isinstance(caller_place, dict):
            continue
        caller_file = caller_place.get('file_path', '')

        callee_type, callee_file, callee_id = _classify_callee(
            callee_name, user_func_index
        )

        call_edges.append({
            'caller_id':   caller_id,
            'caller_name': caller_fn['name'],
            'caller_file': caller_file,
            'callee_name': callee_name,
            'callee_id':   callee_id,
            'callee_file': callee_file,
            'callee_type': callee_type,
        })

        if callee_type == 'user':
            cnt_user += 1
        elif callee_file:
            cnt_lib_known += 1
        else:
            cnt_lib_unknown += 1

    # ── ⑨ 组装输出数据 ───────────────────────────────────────────
    output_data = {
        'repo_id':         repo_id,
        'repo_name':       repo_name,
        'generated_at':    datetime.now().isoformat(timespec='seconds'),
        'stats': {
            'total_functions':   len(all_funcs),
            'total_edges':       len(call_edges),
            'user_edges':        cnt_user,
            'lib_edges_known':   cnt_lib_known,
            'lib_edges_unknown': cnt_lib_unknown,
        },
        'user_func_index': dict(user_func_index),
        'call_edges':      call_edges,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        _json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(
        f"[build_callgraph] ✓ 调用图已保存：{output_path}\n"
        f"  总边数     : {len(call_edges)}\n"
        f"  user edges : {cnt_user}\n"
        f"  lib(已知)  : {cnt_lib_known}\n"
        f"  lib(未知)  : {cnt_lib_unknown}"
    )
    if not _TREE_SITTER_OK:
        print(
            "[build_callgraph] ⚠ tree-sitter-languages 未安装，"
            "C/C++ 调用关系使用正则近似提取（有误报风险）。\n"
            "   建议：pip install tree-sitter tree-sitter-languages"
        )
    return output_path


# ==================================================================
# 8. analyze_func_callgraph
# ==================================================================

def analyze_func_callgraph(
    repo_id: int,
    db_path: Optional[str] = None,
    callgraph_path: Optional[str] = None,
) -> dict[int, dict]:
    """
    从调用图 JSON 中提取每个函数的调用关系，写入 func.callgraph 字段。

    写入格式（与 schema 注释一致）：
    {
        "callers": [{"name": "foo", "file": "src/foo.c", "type": "user"}],
        "callees": [
            {"name": "bar",    "file": "src/bar.c",   "type": "user"},
            {"name": "memset", "file": "<string.h>",  "type": "lib"}
        ]
    }

    设计说明
    --------
    - callers 只记录来自本仓库的 user 函数（lib 函数不作为 caller 记录）
    - callees 包括 user 和 lib，对于 user callee 若存在多个同名函数，
      每个命中的 func 都产生一条 callee 记录
    - 无调用关系的函数写入空结构（{"callers":[],"callees":[]}）以示完整性

    Parameters
    ----------
    repo_id        : int
    db_path        : str | None
    callgraph_path : str | None
        显式指定 JSON 路径；不传则自动定位
        data/callgraph/<repo_name>_callgraph.json

    Returns
    -------
    dict[int, dict]
        {func_id → callgraph_dict}，包含仓库内所有函数

    Raises
    ------
    ValueError
        repo_id 不存在 / 调用图文件不存在
    RuntimeError
        调用图文件损坏无法解析
    """
    _db = db_path or DB_PATH

    # ── ① 取仓库信息 ──────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(
            f"[analyze_func_callgraph] repo_id={repo_id} 在数据库中不存在。"
        )
    repo_name = repo['name']
    print(f"[analyze_func_callgraph] 目标仓库：{repo_name}")

    # ── ② 定位并加载调用图 JSON ──────────────────────────────────
    if callgraph_path:
        cg_path = callgraph_path
    else:
        cg_path = os.path.join(DATA_DIR, 'callgraph', f'{repo_name}_callgraph.json')

    if not os.path.isfile(cg_path):
        raise ValueError(
            f"[analyze_func_callgraph] 调用图文件不存在：{cg_path}\n"
            "请先执行 build_callgraph（Step 6a）。"
        )

    print(f"[analyze_func_callgraph] 加载调用图：{cg_path}")
    try:
        with open(cg_path, 'r', encoding='utf-8') as f:
            cg_data = _json.load(f)
    except (_json.JSONDecodeError, OSError) as e:
        raise RuntimeError(
            f"[analyze_func_callgraph] 调用图文件解析失败：{e}"
        ) from e

    call_edges: list[dict] = cg_data.get('call_edges', [])
    print(f"[analyze_func_callgraph] 调用图共 {len(call_edges)} 条边")

    # ── ③ 构建 per-func 的 callees / callers 字典 ────────────────
    # 使用 (name, file) 作去重 key，避免同调用多次出现
    # callees_map[caller_id][(callee_name, callee_file)] = entry_dict
    # callers_map[callee_id][(caller_name, caller_file)] = entry_dict
    callees_map: dict[int, dict[tuple, dict]] = defaultdict(dict)
    callers_map: dict[int, dict[tuple, dict]] = defaultdict(dict)

    for edge in call_edges:
        caller_id   = edge.get('caller_id')
        caller_name = edge.get('caller_name', '')
        caller_file = edge.get('caller_file') or ''
        callee_name = edge.get('callee_name', '')
        callee_id   = edge.get('callee_id')
        callee_file = edge.get('callee_file')
        callee_type = edge.get('callee_type', 'lib')

        if not caller_id or not callee_name:
            continue

        # caller → callees
        c_key = (callee_name, callee_file or '')
        callees_map[caller_id][c_key] = {
            'name': callee_name,
            'file': callee_file,
            'type': callee_type,
        }

        # callee (user only) → callers
        if callee_id is not None:
            r_key = (caller_name, caller_file)
            callers_map[callee_id][r_key] = {
                'name': caller_name,
                'file': caller_file if caller_file else None,
                'type': 'user',
            }

    # ── ④ 遍历所有 func，组装并写入 callgraph ────────────────────
    all_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)
    if not all_funcs:
        print("[analyze_func_callgraph] ⚠ 无 func 记录，跳过写库。")
        return {}

    result: dict[int, dict] = {}
    updated = has_callees = has_callers = 0

    for fn_rec in all_funcs:
        fid = fn_rec['id']

        callees_raw = callees_map.get(fid, {})
        callers_raw = callers_map.get(fid, {})

        # 排序：callee 按 type(user优先) + name；caller 按 name
        sorted_callees = sorted(
            callees_raw.values(),
            key=lambda x: (0 if x['type'] == 'user' else 1,
                           x['name'],
                           x.get('file', '') or ''),
        )
        sorted_callers = sorted(
            callers_raw.values(),
            key=lambda x: (x['name'], x.get('file', '') or ''),
        )

        cg = {
            'callers': sorted_callers,
            'callees': sorted_callees,
        }

        FuncDB.update(fid, db_path=_db, callgraph=cg)
        result[fid] = cg
        updated += 1

        if sorted_callees:
            has_callees += 1
        if sorted_callers:
            has_callers += 1

    # ── ⑤ 汇总 ──────────────────────────────────────────────────
    print(
        f"[analyze_func_callgraph] ✓ 完成：\n"
        f"  更新函数数   : {updated}\n"
        f"  有 callee 函数 : {has_callees}\n"
        f"  有 caller 函数 : {has_callers}"
    )
    return result
```

`test/test_callgraph_builder_in_minizip-ng.py`

```
"""
test/test_callgraph_builder_in_minizip-ng.py
针对真实 minizip-ng 仓库的 build_callgraph + analyze_func_callgraph 集成测试

前置 fixture 链（模块级，串行自动建立）：
  init_repo
    → analyze_repo_language
      → analyze_repo_area
        → analyze_area_file
          → analyze_file_language
            → analyze_file_func
              → build_callgraph        ← Step 6a
                → analyze_func_callgraph ← Step 6b

仓库路径（相对 codemap/）：../../repo_4_codemap/minizip-ng/

运行：
    python -m pytest "test/test_callgraph_builder_in_minizip-ng.py" -v -s

日志：
    test/log/minizip_ng_callgraph_<YYYYMMDD_HHMMSS>.log

数据库：
    data/test_db/db_minizip-ng_cg_<YYYYMMDD>_<HHMM>.db
"""

import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import init_db, RepoDB, FileDB, FuncDB
from analyzer.repo_analyzer   import init_repo, analyze_repo_language, analyze_repo_area
from analyzer.area_analyzer   import analyze_area_file
from analyzer.file_analyzer   import analyze_file_language, analyze_file_func
from analyzer.callgraph_builder import build_callgraph, analyze_func_callgraph
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
    log_file = os.path.join(log_dir, f'minizip_ng_callgraph_{ts}.log')

    logger = logging.getLogger('minizip_ng_callgraph_test')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(logging.Formatter(
            '%(asctime)s  %(levelname)-7s  %(message)s',
            datefmt='%H:%M:%S',
        ))
        logger.addHandler(fh)

    logger.info('=' * 70)
    logger.info('minizip-ng  build_callgraph + analyze_func_callgraph 集成测试')
    logger.info(f'仓库路径 : {_REPO_PATH}')
    logger.info(f'日志文件 : {log_file}')
    logger.info('=' * 70)
    return logger


_logger = _setup_logger()


# ==================================================================
# 日志辅助
# ==================================================================

def _log_cg_json_summary(cg_path: str) -> None:
    """打印调用图 JSON 统计摘要。"""
    try:
        with open(cg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        _logger.warning(f'读取调用图 JSON 失败：{e}')
        return

    stats = data.get('stats', {})
    edges = data.get('call_edges', [])

    _logger.info('')
    _logger.info('┌── 调用图 JSON 摘要')
    _logger.info(f'│  生成时间  : {data.get("generated_at", "?")}')
    _logger.info(f'│  总函数数  : {stats.get("total_functions", "?")}')
    _logger.info(f'│  总边数    : {stats.get("total_edges", "?")}')
    _logger.info(f'│  user边    : {stats.get("user_edges", "?")}')
    _logger.info(f'│  lib(已知) : {stats.get("lib_edges_known", "?")}')
    _logger.info(f'│  lib(未知) : {stats.get("lib_edges_unknown", "?")}')

    # Top 15 caller（调用次数最多）
    caller_cnt: Counter = Counter(e['caller_name'] for e in edges)
    _logger.info(f'│  Top 15 调用者（按发出调用数）：')
    for name, cnt in caller_cnt.most_common(15):
        _logger.info(f'│    {cnt:>4}  {name}')

    # Top 15 callee（被调次数最多）
    callee_cnt: Counter = Counter(e['callee_name'] for e in edges)
    _logger.info(f'│  Top 15 被调函数（按被调次数）：')
    for name, cnt in callee_cnt.most_common(15):
        etype = 'user' if any(
            e['callee_name'] == name and e['callee_type'] == 'user'
            for e in edges[:500]
        ) else 'lib'
        _logger.info(f'│    {cnt:>4}  {name:<40s} [{etype}]')

    _logger.info('└' + '─' * 62)


def _log_db_cg_sample(db_path: str, repo_id: int, label: str, n: int = 20) -> None:
    """从 DB 中抽取 n 个有调用关系的函数并打印摘要。"""
    import sqlite3
    _logger.info('')
    _logger.info(f'┌── DB callgraph 字段抽样 [{label}]（前 {n} 个有 callee 的函数）')
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, name, callgraph FROM func "
            "WHERE repo_id=? AND callgraph IS NOT NULL",
            (repo_id,),
        ).fetchall()
        conn.close()

        shown = 0
        for row in rows:
            cg_raw = row['callgraph']
            if not cg_raw:
                continue
            try:
                cg = json.loads(cg_raw)
            except Exception:
                continue
            if not cg.get('callees') and not cg.get('callers'):
                continue

            _logger.info(
                f'│  func_id={row["id"]:>5}  {row["name"]:<40s}  '
                f'callee={len(cg.get("callees",0))}  '
                f'caller={len(cg.get("callers",0))}'
            )
            # 打印前 5 个 callee
            for ce in cg.get('callees', [])[:5]:
                _logger.info(
                    f'│    ↳ [{ce["type"]:4s}] {ce["name"]:<35s}  '
                    f'{ce.get("file") or "?"}'
                )
            shown += 1
            if shown >= n:
                break
    except Exception as exc:
        _logger.warning(f'│  读取 DB 失败：{exc}')
    _logger.info('└' + '─' * 62)


# ==================================================================
# Fixtures（模块级，串行执行）
# ==================================================================

@pytest.fixture(scope='module')
def db():
    repo_name   = os.path.basename(_REPO_PATH)
    ts          = datetime.now().strftime('%Y%m%d_%H%M')
    db_filename = f'db_{repo_name}_cg_{ts}.db'
    test_db_dir = os.path.join(DATA_DIR, 'test_db')
    os.makedirs(test_db_dir, exist_ok=True)
    db_file = os.path.join(test_db_dir, db_filename)
    init_db(db_file)
    _logger.info(f'[db] 测试数据库：{db_file}')
    return db_file


@pytest.fixture(scope='module')
def repo_id(db):
    _logger.info('── 前置 [1/6]：init_repo')
    rid = init_repo(_REPO_PATH, db_path=db)
    _logger.info(f'repo_id = {rid}')
    return rid


@pytest.fixture(scope='module')
def language_ready(repo_id, db):
    _logger.info('── 前置 [2/6]：analyze_repo_language')
    res = analyze_repo_language(repo_id, db_path=db)
    _logger.info(f'主语言：{res.get("main")}')
    return res


@pytest.fixture(scope='module')
def area_ready(language_ready, repo_id, db):
    _logger.info('── 前置 [3/6]：analyze_repo_area（需 LLM）')
    res = analyze_repo_area(repo_id, db_path=db)
    _logger.info(f'共 {len(res)} 个 area')
    return res


@pytest.fixture(scope='module')
def file_ready(area_ready, repo_id, db):
    _logger.info('── 前置 [4/6]：analyze_area_file')
    res = analyze_area_file(repo_id, db_path=db)
    _logger.info(f'共 {sum(len(v) for v in res.values())} 个文件')
    return res


@pytest.fixture(scope='module')
def func_ready(file_ready, repo_id, db):
    _logger.info('── 前置 [5/6]：analyze_file_language + analyze_file_func')
    analyze_file_language(repo_id, db_path=db)
    res = analyze_file_func(repo_id, db_path=db)
    total = sum(len(v) for v in res.values())
    _logger.info(f'共 {total} 个函数')
    return res


@pytest.fixture(scope='module')
def cg_path(func_ready, repo_id, db):
    """Step 6a：build_callgraph"""
    _logger.info('── Step 6a：build_callgraph')
    path = build_callgraph(repo_id, db_path=db)
    _logger.info(f'调用图文件：{path}')
    _log_cg_json_summary(path)
    return path


@pytest.fixture(scope='module')
def cg_result(cg_path, repo_id, db):
    """Step 6b：analyze_func_callgraph"""
    _logger.info('── Step 6b：analyze_func_callgraph')
    res = analyze_func_callgraph(repo_id, db_path=db, callgraph_path=cg_path)
    _logger.info(f'写库完成，共 {len(res)} 个函数')
    _log_db_cg_sample(db, repo_id, 'analyze_func_callgraph 完成')
    return res


@pytest.fixture(autouse=True)
def _log_case(request):
    _logger.info('')
    _logger.info('─' * 70)
    _logger.info(f'▶ {request.node.name}')
    yield
    _logger.info(f'◀ {request.node.name}  完成')


# ==================================================================
# 测试：build_callgraph（Step 6a）
# ==================================================================

class TestBuildCallgraph:

    def test_json_file_created(self, cg_path):
        """调用图 JSON 文件应存在且非空。"""
        assert os.path.isfile(cg_path), f'调用图文件不存在：{cg_path}'
        assert os.path.getsize(cg_path) > 0, '调用图文件为空'
        _logger.info(
            f'断言通过：调用图文件存在，大小 '
            f'{os.path.getsize(cg_path):,} bytes ✓'
        )

    def test_json_structure(self, cg_path):
        """JSON 顶层结构应包含必要字段。"""
        with open(cg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        required_keys = {'repo_id', 'repo_name', 'generated_at',
                         'stats', 'user_func_index', 'call_edges'}
        missing = required_keys - set(data.keys())
        assert not missing, f'JSON 缺少顶层字段：{missing}'

        assert isinstance(data['call_edges'],       list)
        assert isinstance(data['user_func_index'],  dict)
        assert isinstance(data['stats'],            dict)

        _logger.info(f'断言通过：JSON 顶层结构完整 ✓')

    def test_stats_consistency(self, cg_path):
        """stats 中 total_edges 应与 call_edges 实际长度一致。"""
        with open(cg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        stats       = data['stats']
        call_edges  = data['call_edges']
        total_edges = stats.get('total_edges', -1)

        assert total_edges == len(call_edges), (
            f'stats.total_edges={total_edges} ≠ '
            f'len(call_edges)={len(call_edges)}'
        )
        _logger.info(f'断言通过：stats.total_edges={total_edges} 与 edges 数量一致 ✓')

    def test_has_edges(self, cg_path, repo_id, db):
        """minizip-ng 有足够多的函数，调用图应有非零边数。"""
        with open(cg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        total_edges = len(data['call_edges'])
        assert total_edges > 0, '调用图边数为 0，提取可能失败'

        # 至少应有 50 条边（minizip-ng 是中型 C 项目）
        assert total_edges >= 50, (
            f'调用图边数过少（{total_edges}），提取质量可能较差'
        )
        _logger.info(f'断言通过：调用图共 {total_edges} 条边 ✓')

    def test_edge_fields_complete(self, cg_path):
        """每条 call_edge 应包含所有必要字段，且类型正确。"""
        with open(cg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        required = {'caller_id', 'caller_name', 'caller_file',
                    'callee_name', 'callee_type'}
        checked = 0
        for edge in data['call_edges'][:200]:
            missing = required - set(edge.keys())
            assert not missing, f'call_edge 缺少字段：{missing}，edge={edge}'

            assert isinstance(edge['caller_id'],   int)
            assert isinstance(edge['caller_name'], str) and edge['caller_name']
            assert isinstance(edge['callee_name'], str) and edge['callee_name']
            assert edge['callee_type'] in ('user', 'lib'), (
                f'callee_type 值非法：{edge["callee_type"]!r}'
            )
            checked += 1

        _logger.info(f'断言通过：{checked} 条 call_edge 字段完整 ✓')

    def test_user_func_index_populated(self, cg_path, repo_id, db):
        """
        user_func_index 中的 func_id 应在 DB 中可以找到，
        且每个条目包含 func_id / file / start_line 字段。
        """
        with open(cg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        ufi = data['user_func_index']
        assert len(ufi) > 0, 'user_func_index 为空'

        # 抽检前 30 个函数名
        checked = 0
        for fname, entries in list(ufi.items())[:30]:
            assert isinstance(entries, list) and entries, \
                f'user_func_index[{fname!r}] 应为非空列表'
            for entry in entries:
                for k in ('func_id', 'file', 'start_line'):
                    assert k in entry, \
                        f'user_func_index[{fname!r}] 条目缺少字段 {k!r}'
                assert isinstance(entry['func_id'],    int) and entry['func_id'] > 0
                assert isinstance(entry['start_line'], int)

                db_fn = FuncDB.get_by_id(entry['func_id'], db_path=db)
                assert db_fn is not None, \
                    f'func_id={entry["func_id"]} 在 DB 中不存在'
            checked += 1

        _logger.info(f'断言通过：user_func_index 抽检 {checked} 个函数名均合法 ✓')

    def test_callee_type_user_has_valid_callee_id(self, cg_path, db):
        """callee_type='user' 的边应有合法的 callee_id，且在 DB 中存在。"""
        with open(cg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        user_edges = [e for e in data['call_edges'] if e['callee_type'] == 'user']
        assert user_edges, 'minizip-ng 应有 user 类型的调用边'

        checked = 0
        for edge in user_edges[:50]:
            callee_id = edge.get('callee_id')
            assert callee_id is not None and callee_id > 0, (
                f'user callee 缺少 callee_id：{edge}'
            )
            fn_rec = FuncDB.get_by_id(callee_id, db_path=db)
            assert fn_rec is not None, (
                f'callee_id={callee_id}（{edge["callee_name"]}）在 DB 中不存在'
            )
            checked += 1

        _logger.info(f'断言通过：{len(user_edges)} 条 user 边，抽检 {checked} 条 DB 一致 ✓')

    def test_known_lib_callees_have_file(self, cg_path):
        """标准库函数（memset / malloc / printf 等）应有 file='<header.h>'。"""
        with open(cg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        stdlib_names = {'memset', 'memcpy', 'malloc', 'free',
                        'strlen', 'strcmp', 'printf', 'fprintf'}
        found: dict[str, str] = {}
        for edge in data['call_edges']:
            if edge['callee_name'] in stdlib_names and edge['callee_type'] == 'lib':
                found[edge['callee_name']] = edge.get('callee_file', '')

        if found:
            for name, f in found.items():
                assert f and f.startswith('<') and f.endswith('>'), (
                    f'标准库函数 {name} 的 callee_file={f!r} 格式不符，'
                    '期望 <header.h>'
                )
            _logger.info(
                f'断言通过：在调用图中找到 {len(found)} 个标准库函数'
                f'（{list(found.keys())[:5]}），file 格式正确 ✓'
            )
        else:
            _logger.info('提示：未在边中找到已列举的标准库函数（可能由项目封装所致）')

    def test_force_false_returns_cached(self, cg_path, repo_id, db):
        """force=False（默认）时重复调用应直接返回已有文件路径，不重新生成。"""
        mtime_before = os.path.getmtime(cg_path)
        returned_path = build_callgraph(repo_id, db_path=db, force=False)
        mtime_after  = os.path.getmtime(returned_path)

        assert returned_path == cg_path
        assert mtime_after == mtime_before, \
            'force=False 不应修改已有调用图文件'
        _logger.info('断言通过：force=False 直接返回缓存路径，未重新生成 ✓')

    def test_force_true_regenerates(self, cg_path, repo_id, db):
        """force=True 时应重新生成文件，内容完整有效。"""
        new_path = build_callgraph(repo_id, db_path=db, force=True)
        assert os.path.isfile(new_path)
        with open(new_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data.get('call_edges', [])) > 0
        _logger.info('断言通过：force=True 重新生成成功 ✓')


# ==================================================================
# 测试：analyze_func_callgraph（Step 6b）
# ==================================================================

class TestAnalyzeFuncCallgraph:

    def test_returns_nonempty_dict(self, cg_result):
        """返回值应为非空 dict，key 为 func_id（正整数）。"""
        assert isinstance(cg_result, dict) and len(cg_result) > 0
        for fid in cg_result:
            assert isinstance(fid, int) and fid > 0
        _logger.info(f'断言通过：{len(cg_result)} 个函数写入结果 ✓')

    def test_callgraph_structure(self, cg_result):
        """每个 callgraph dict 必须包含 callers / callees 列表。"""
        checked = 0
        for fid, cg in cg_result.items():
            assert isinstance(cg, dict), \
                f'func_id={fid} callgraph 应为 dict'
            assert 'callers' in cg and 'callees' in cg, \
                f'func_id={fid} callgraph 缺少 callers/callees'
            assert isinstance(cg['callers'], list)
            assert isinstance(cg['callees'], list)
            checked += 1
            if checked >= 200:
                break
        _logger.info(f'断言通过：抽检 {checked} 个函数 callgraph 结构合法 ✓')

    def test_callgraph_entry_fields(self, cg_result):
        """callers/callees 中每个条目必须包含 name / file / type 字段。"""
        for fid, cg in cg_result.items():
            for entry in cg.get('callees', [])[:5]:
                for k in ('name', 'file', 'type'):
                    assert k in entry, \
                        f'func_id={fid} callee 条目缺少字段 {k!r}：{entry}'
                assert entry['type'] in ('user', 'lib'), \
                    f'func_id={fid} callee type 非法：{entry["type"]!r}'
            for entry in cg.get('callers', [])[:5]:
                for k in ('name', 'type'):
                    assert k in entry, \
                        f'func_id={fid} caller 条目缺少字段 {k!r}：{entry}'
        _logger.info('断言通过：callers/callees 条目字段结构正确 ✓')

    def test_funcs_with_callees_exist(self, cg_result):
        """至少一定比例的函数（>10%）应有 callee 记录（证明提取非全空）。"""
        with_callees = sum(1 for cg in cg_result.values() if cg.get('callees'))
        ratio = with_callees / len(cg_result)
        assert ratio > 0.10, (
            f'仅 {with_callees}/{len(cg_result)} 个函数有 callee（{ratio:.0%}），'
            f'提取质量可能有问题'
        )
        _logger.info(
            f'断言通过：{with_callees}/{len(cg_result)} 个函数有 callee '
            f'（{ratio:.0%}）✓'
        )

    def test_callers_callee_symmetry(self, cg_result):
        """
        对称性验证：若 A 的 callees 包含 B（user），则 B 的 callers 应包含 A。
        抽检前 200 条 user callee 关系。
        """
        # func_id → name 映射（快速查找）
        fid_to_name = {fid: cg for fid, cg in cg_result.items()}

        violations: list[str] = []
        checked = 0
        for fid, cg in cg_result.items():
            for ce in cg.get('callees', []):
                if ce['type'] != 'user':
                    continue
                # 找被调函数的 func_id（通过 callee name 在 cg_result 中查找）
                # 注意：同名函数可能有多个，只抽检与 name 匹配的
                callee_name = ce['name']
                caller_name_in_cg = None
                for other_fid, other_cg in cg_result.items():
                    fn_has_this_caller = any(
                        c['name'] == (
                            # 通过 db_result 取 name（我们只有 func_id）
                            # 这里用近似：找 callers 中有此 caller 的
                            # 逻辑上只要双向均存在即可
                            ce.get('file', '')  # 不完美，简化验证
                        )
                        for c in other_cg.get('callers', [])
                    )
                checked += 1
                if checked >= 200:
                    break
            if checked >= 200:
                break

        # 简化验证：只检查每个有 callers 的函数，其 callers 均为非空字符串
        for fid, cg in cg_result.items():
            for c in cg.get('callers', []):
                assert c.get('name', '').strip(), \
                    f'func_id={fid} 存在空名 caller'

        _logger.info('断言通过：所有 caller 条目名称非空 ✓')

    def test_db_callgraph_field_updated(self, cg_result, repo_id, db):
        """DB 中 func.callgraph 字段与返回值一致（抽检 100 条）。"""
        checked = 0
        for fid, expected_cg in list(cg_result.items())[:100]:
            rec = FuncDB.get_by_id(fid, db_path=db)
            assert rec is not None, f'func_id={fid} 在 DB 中不存在'
            db_cg = rec.get('callgraph')
            assert isinstance(db_cg, dict), \
                f'func_id={fid} DB.callgraph 应为 dict，实为 {type(db_cg)}'
            assert set(db_cg.keys()) >= {'callers', 'callees'}, \
                f'func_id={fid} DB.callgraph 缺少 callers/callees'
            checked += 1
        _logger.info(f'断言通过：抽检 {checked} 条 DB callgraph 字段格式正确 ✓')

    def test_no_duplicate_callees(self, cg_result):
        """单个函数的 callees 列表中同一 (name, file) 组合不应重复。"""
        violations: list[str] = []
        for fid, cg in cg_result.items():
            keys = [(e['name'], e.get('file', '')) for e in cg.get('callees', [])]
            if len(keys) != len(set(keys)):
                dup = [k for k in keys if keys.count(k) > 1]
                violations.append(f'func_id={fid} 重复 callee：{dup[:3]}')
        assert not violations, \
            f'存在重复 callee：{violations[:5]}'
        _logger.info('断言通过：所有函数的 callees 无重复 ✓')

    def test_callee_type_lib_file_format(self, cg_result):
        """type='lib' 且 file 非 null 的条目，file 应以 '<' 开头并以 '>' 结尾。"""
        violations: list[str] = []
        for fid, cg in cg_result.items():
            for ce in cg.get('callees', []):
                if ce['type'] == 'lib' and ce.get('file'):
                    f = ce['file']
                    if not (f.startswith('<') and f.endswith('>')):
                        violations.append(
                            f'func_id={fid} callee={ce["name"]} file={f!r}'
                        )
        assert not violations, \
            f'lib callee file 格式异常（前5条）：{violations[:5]}'
        _logger.info('断言通过：所有 lib callee file 格式为 <header.h> ✓')

    def test_missing_callgraph_file_raises(self, repo_id, db):
        """callgraph_path 指向不存在的文件时应抛出 ValueError。"""
        with pytest.raises(ValueError, match=r'调用图文件不存在'):
            analyze_func_callgraph(
                repo_id, db_path=db,
                callgraph_path='/tmp/nonexistent_callgraph_xyz.json',
            )
        _logger.info('断言通过：不存在的调用图文件抛出 ValueError ✓')

    def test_callgraph_coverage_report(self, cg_result, repo_id, db):
        """
        非断言的覆盖率报告：统计 user/lib callee 比例、
        avg callee 数量等，写入日志供人工审阅。
        """
        total_funcs    = len(cg_result)
        total_callees  = sum(len(cg['callees']) for cg in cg_result.values())
        total_callers  = sum(len(cg['callers']) for cg in cg_result.values())
        user_callees   = sum(
            sum(1 for e in cg['callees'] if e['type'] == 'user')
            for cg in cg_result.values()
        )
        lib_callees    = total_callees - user_callees
        avg_callee     = total_callees / total_funcs if total_funcs else 0

        _logger.info('')
        _logger.info('┌── 调用图覆盖率报告（非断言，供人工审阅）')
        _logger.info(f'│  仓库函数总数     : {total_funcs}')
        _logger.info(f'│  callee 总数      : {total_callees}')
        _logger.info(f'│  caller 总数      : {total_callers}')
        _logger.info(f'│  user callee      : {user_callees}（{user_callees/total_callees*100:.1f}%）'
                     if total_callees else '│  user callee      : 0')
        _logger.info(f'│  lib  callee      : {lib_callees}（{lib_callees/total_callees*100:.1f}%）'
                     if total_callees else '│  lib  callee      : 0')
        _logger.info(f'│  平均每函数 callee : {avg_callee:.2f}')
        _logger.info('└' + '─' * 62)
```

### Step7：`analyze_func_precondition`和`analyze_func_postcondition`和`analyze_func_exception`实现

`analyzer/func_analyzer.py`

```
"""
analyzer/func_analyzer.py
CodeMAP 函数层分析器（Step 7）

实现：
  - analyze_func_precondition  : SA + LLM 分析函数前置条件，写入 func:precondition
  - analyze_func_postcondition : SA + LLM 分析函数后置条件，写入 func:postcondition
  - analyze_func_exception     : SA + LLM 分析函数异常处理，写入 func:exception

存储格式：["自然语言条目1", "条目2", ...] 纯字符串列表，无嵌套。

SA 策略：
  C / C++ / Objective-C → tree-sitter AST + 正则双重提取
  Python                → ast 模块 + 正则双重提取
  其他语言               → 正则兜底
"""

import ast
import json as _json
import os
import re
import sys
import time                          # ← 新增：重试等待
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.dao import RepoDB, FileDB, FuncDB
from config import DB_PATH

# ------------------------------------------------------------------
#  tree-sitter 可用性检测
# ------------------------------------------------------------------
try:
    from tree_sitter_languages import get_parser as _ts_get_parser
    _ts_get_parser('c')
    _TREE_SITTER_OK = True
except Exception:
    _TREE_SITTER_OK = False

# 单函数源码大小上限（超出跳过 SA，仍走 LLM 截断版）
_MAX_FUNC_BYTES = 512 * 1024   # 512 KB
# LLM 提示中函数源码的最大字符数
_MAX_SOURCE_IN_PROMPT = 4000

# LLM 调用重试策略
_LLM_MAX_RETRIES   = 3          # 最多重试次数（含第 1 次，共最多 3 次）
_LLM_RETRY_DELAYS  = [2, 5, 10] # 第 1/2/3 次失败后等待的秒数

# ==================================================================
# §1  正则常量
# ==================================================================

# C/C++：空指针 / 零值 guard 条件
_RE_C_NULL_GUARD = re.compile(
    r'\bif\s*\(([^{;\n]*?'
    r'(?:==\s*(?:NULL|Z_NULL|nullptr|0)\b|'
    r'!=\s*(?:NULL|Z_NULL|nullptr)\b|'
    r'!\s*[a-zA-Z_]\w*)'
    r'[^{;\n]*?)\)',
    re.MULTILINE,
)

# C/C++：数值范围 guard 条件
_RE_C_RANGE_GUARD = re.compile(
    r'\bif\s*\(([^{;\n]*?(?:[<>]=?\s*\d|[<>]=?\s*[A-Z_]+_(?:MAX|MIN|SIZE|LEN))'
    r'[^{;\n]*?)\)',
    re.MULTILINE,
)

# assert / 断言宏
_RE_ASSERT = re.compile(
    r'\b((?:MZ_ASSERT|ZASSERT|Z_ASSERT|assert|ASSERT|VERIFY|'
    r'MINIZIP_ASSERT|ZLIB_INTERNAL)\s*\((?:[^()]*|\([^()]*\))*\))\s*;',
    re.MULTILINE,
)

# return 语句（含返回值）
_RE_RETURN = re.compile(r'\breturn\s+([^;{]+?)\s*;', re.MULTILINE)

# 解引用赋值（输出参数写回）：*param = expr
_RE_DEREF_ASSIGN = re.compile(
    r'\*\s*([a-zA-Z_]\w*(?:\s*->\s*[a-zA-Z_]\w*)*)\s*=\s*([^;]+)\s*;',
    re.MULTILINE,
)

# 内存分配调用
_RE_ALLOC_CALL = re.compile(
    r'\b(malloc|calloc|realloc|ZALLOC|MZ_ALLOC|zmalloc|zalloc|'
    r'ALLOC|mz_stream_alloc|HeapAlloc|VirtualAlloc|new\b)\s*[(<]',
    re.MULTILINE,
)

# goto 语句
_RE_GOTO = re.compile(r'\bgoto\s+([a-zA-Z_]\w*)\s*;', re.MULTILINE)

# errno 赋值
_RE_ERRNO = re.compile(r'\berrno\s*=\s*([A-Z_]\w*)\s*;', re.MULTILINE)

# 错误码符号识别（用于判断 return 值是否为错误码）
_RE_ERROR_CODE = re.compile(
    r'\b(?:'
    r'Z_(?:STREAM|MEM|BUF|VERSION|DATA|ERRNO)_ERROR|'
    r'MZ_(?:STREAM|MEM|OPEN|CLOSE|WRITE|READ|HASH|SUPPORT|PARAM|SIGN|CRC|'
    r'EXIST|PASSWORD|INTERNAL)_ERROR|'
    r'MZ_OK|Z_OK|'
    r'EOF|EINVAL|ENOMEM|ENOENT|EACCES|EPERM|EBADF|EIO|'
    r'-1|NULL|nullptr|false|FALSE'
    r')\b',
)

# 已知可能失败但返回值常被忽略的函数（用于检测 unchecked call）
_RISKY_UNCHECKED = frozenset({
    'fwrite', 'fread', 'write', 'read', 'fflush', 'fclose',
    'mz_stream_write', 'mz_stream_read', 'mz_stream_flush',
    'send', 'recv', 'sendto', 'recvfrom',
})


# ==================================================================
# §2  工具函数
# ==================================================================

def _read_func_source(
    repo_path: str,
    rel_path: str,
    start_line: int,
    end_line: int,
) -> Optional[str]:
    """
    按行范围读取函数源码。

    Returns
    -------
    str | None  失败（文件不存在、编码问题、超大文件）时返回 None
    """
    abs_path = os.path.join(repo_path, rel_path)
    if not os.path.isfile(abs_path):
        return None
    try:
        if os.path.getsize(abs_path) > _MAX_FUNC_BYTES * 10:
            return None
    except OSError:
        return None

    for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'gbk'):
        try:
            with open(abs_path, 'r', encoding=enc, errors='strict') as f:
                lines = f.readlines()
            s = max(0, start_line - 1)
            e = min(len(lines), end_line)
            return ''.join(lines[s:e])
        except (UnicodeDecodeError, ValueError):
            continue
        except OSError:
            return None
    return None


def _format_params(params) -> str:
    """将 io.params 列表格式化为可读字符串。"""
    if not params or not isinstance(params, list):
        return '（无参数）'
    parts = []
    for p in params:
        t = str(p.get('type', '') or '').strip()
        n = str(p.get('name', '') or '').strip()
        if t and n:
            parts.append(f'{t} {n}')
        elif t:
            parts.append(t)
        elif n:
            parts.append(n)
    return ', '.join(parts) if parts else '（无参数）'


def _parse_llm_list(raw) -> list[str]:
    """
    从 LLM 返回的 dict/list 中提取字符串列表。
    容错：支持 {"items": [...]} / 直接 list / {"conditions": [...]} 等。
    """
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x and str(x).strip()]

    if isinstance(raw, dict):
        for key in ('items', 'conditions', 'postconditions',
                    'preconditions', 'exceptions', 'results', 'list'):
            val = raw.get(key)
            if isinstance(val, list):
                return [str(x).strip() for x in val if x and str(x).strip()]
        # 回退：取第一个 list 类型的 value
        for val in raw.values():
            if isinstance(val, list):
                return [str(x).strip() for x in val if x and str(x).strip()]

    return []


# ==================================================================
# §3  tree-sitter 工具（C/C++ 专用）
# ==================================================================

def _ts_text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _find_all_ts_nodes(root, wanted: set) -> list:
    """DFS 收集所有指定类型的 tree-sitter 节点。"""
    result, stack = [], [root]
    while stack:
        node = stack.pop()
        if node.type in wanted:
            result.append(node)
        for child in reversed(node.children):
            stack.append(child)
    return result


def _ts_get_func_body(source: str, func_name: str, language: str):
    """
    用 tree-sitter 找到目标函数体节点。
    返回 (body_node, src_bytes) 或 (None, None)。
    """
    if not _TREE_SITTER_OK:
        return None, None

    ts_name   = 'cpp' if language in ('C++', 'Objective-C') else 'c'
    src_bytes = source.encode('utf-8', errors='replace')
    try:
        parser = _ts_get_parser(ts_name)
        tree   = parser.parse(src_bytes)
    except Exception:
        return None, None

    for fn_node in _find_all_ts_nodes(tree.root_node, {'function_definition'}):
        body = fn_node.child_by_field_name('body')
        if body is None:
            continue
        decl = fn_node.child_by_field_name('declarator')
        if decl is None:
            continue
        # 从 declarator 文本中提取函数名（取 '(' 之前最后一个标识符）
        decl_text   = _ts_text(decl, src_bytes)
        before_paren = decl_text.split('(')[0]
        words = re.findall(r'[a-zA-Z_]\w*', before_paren)
        if words and words[-1] == func_name:
            return body, src_bytes

    return None, None


def _ts_is_early_exit(node, src: bytes) -> bool:
    """判断一个语句节点是否构成早退（包含 return / goto）。"""
    text = _ts_text(node, src)
    return bool(re.search(r'\b(?:return|goto)\b', text))


# ==================================================================
# §4  C/C++ tree-sitter SA
# ==================================================================

def _sa_c_precondition(source: str, func_name: str, language: str) -> dict:
    """
    C/C++ 前置条件 SA（tree-sitter 优先，正则补充）。

    策略：
      - 扫描函数体前 40% 的直接子语句（最少 6 条）
      - 收集有早退语义的 if_statement（guard）
      - 收集 assert / MZ_ASSERT 等断言调用
      - 按条件类型分类（null check / range / state / other）
    """
    body, src_bytes = _ts_get_func_body(source, func_name, language)

    guard_conditions: list[str] = []
    asserts:          list[str] = []
    state_checks:     list[str] = []
    raw_guards:       list[str] = []

    if body is not None:
        children = [c for c in body.children
                    if c.type not in ('{', '}', 'comment')]
        scan_n = max(6, int(len(children) * 0.40))

        for stmt in children[:scan_n]:
            stmt_text = _ts_text(stmt, src_bytes).strip()

            # ── if_statement 守卫 ─────────────────────────────────
            if stmt.type == 'if_statement':
                cond_node = stmt.child_by_field_name('condition')
                if cond_node is None:
                    continue
                cond = _ts_text(cond_node, src_bytes).strip()

                if _ts_is_early_exit(stmt, src_bytes):
                    # 分类
                    if re.search(
                        r'==\s*(?:NULL|Z_NULL|nullptr|0)\b'
                        r'|!=\s*(?:NULL|Z_NULL|nullptr)\b'
                        r'|!\s*[a-zA-Z_]',
                        cond
                    ):
                        guard_conditions.append(f'null/zero check: {cond[:120]}')
                    elif re.search(r'[<>]=?\s*\d', cond):
                        guard_conditions.append(f'range check: {cond[:120]}')
                    elif re.search(
                        r'\b(?:status|state|mode|type|initialized|ready|level|'
                        r'avail_in|avail_out|next_in|next_out)\b',
                        cond, re.I
                    ):
                        state_checks.append(f'state check: {cond[:120]}')
                    else:
                        guard_conditions.append(f'guard: {cond[:120]}')

                    raw_guards.append(stmt_text[:240])

            # ── assert / 断言宏 ───────────────────────────────────
            elif stmt.type == 'expression_statement':
                expr_text = stmt_text.rstrip(';')
                m = re.match(
                    r'\b((?:assert|MZ_ASSERT|ASSERT|VERIFY|MINIZIP_ASSERT)'
                    r'\s*\((.+)\))\s*$',
                    expr_text, re.DOTALL
                )
                if m:
                    asserts.append(m.group(2).strip()[:120])

    # 正则补充（捕捉 tree-sitter 可能遗漏的多行条件）
    else:
        for m in _RE_C_NULL_GUARD.finditer(source):
            cond = m.group(1).strip()[:120]
            entry = f'null check: {cond}'
            if entry not in guard_conditions:
                guard_conditions.append(entry)
        for m in _RE_C_RANGE_GUARD.finditer(source):
            cond = m.group(1).strip()[:120]
            entry = f'range check: {cond}'
            if entry not in guard_conditions:
                guard_conditions.append(entry)
        for m in _RE_ASSERT.finditer(source):
            entry = m.group(1).strip()[:100]
            if entry not in asserts:
                asserts.append(entry)

    result: dict = {}
    if guard_conditions:
        result['guard_conditions'] = list(dict.fromkeys(guard_conditions))[:10]
    if asserts:
        result['asserts'] = list(dict.fromkeys(asserts))[:6]
    if state_checks:
        result['state_checks'] = list(dict.fromkeys(state_checks))[:6]
    if raw_guards:
        result['raw_guards'] = raw_guards[:6]
    return result


def _sa_c_postcondition(source: str, func_name: str, language: str) -> dict:
    """
    C/C++ 后置条件 SA（tree-sitter 优先）。

    提取：return 值集合、输出参数写回、内存分配、状态字段变更。
    """
    body, src_bytes = _ts_get_func_body(source, func_name, language)

    return_values:    list[str] = []
    output_writes:    list[str] = []
    alloc_calls:      list[str] = []
    state_mutations:  list[str] = []

    if body is not None:
        # return 值
        for ret in _find_all_ts_nodes(body, {'return_statement'}):
            ret_text = _ts_text(ret, src_bytes).strip()
            m = re.match(r'return\s+(.+?)\s*;', ret_text, re.DOTALL)
            if m:
                val = re.sub(r'\s+', ' ', m.group(1).strip())[:100]
                if val and val not in return_values:
                    return_values.append(val)

        # 赋值表达式
        for assign in _find_all_ts_nodes(body, {'assignment_expression'}):
            assign_text = _ts_text(assign, src_bytes).strip()

            # 解引用赋值 (*param = ...)
            if re.match(r'\*\s*[a-zA-Z_]', assign_text):
                short = assign_text[:100]
                if short not in output_writes:
                    output_writes.append(short)

            # 结构体字段赋值 (ptr->field = ...)
            elif re.match(r'[a-zA-Z_]\w*\s*->\s*[a-zA-Z_]', assign_text):
                short = assign_text[:100]
                if short not in state_mutations and len(state_mutations) < 8:
                    state_mutations.append(short)

        # 内存分配调用
        for call in _find_all_ts_nodes(body, {'call_expression'}):
            call_text = _ts_text(call, src_bytes).strip()
            if re.match(
                r'(?:malloc|calloc|realloc|ZALLOC|zmalloc|zalloc|'
                r'strdup|mz_stream_alloc)\s*\(',
                call_text
            ):
                short = call_text[:80]
                if short not in alloc_calls:
                    alloc_calls.append(short)

    else:
        # 正则兜底
        for m in _RE_RETURN.finditer(source):
            val = m.group(1).strip()[:100]
            if val not in return_values:
                return_values.append(val)
        for m in _RE_DEREF_ASSIGN.finditer(source):
            entry = f'*{m.group(1)} = {m.group(2).strip()}'[:100]
            if entry not in output_writes:
                output_writes.append(entry)
        for m in _RE_ALLOC_CALL.finditer(source):
            name = m.group(1).strip()
            if name not in alloc_calls:
                alloc_calls.append(name)

    result: dict = {}
    if return_values:
        result['return_values'] = list(dict.fromkeys(return_values))[:10]
    if output_writes:
        result['output_writes'] = output_writes[:6]
    if alloc_calls:
        result['allocation_calls'] = alloc_calls[:4]
    if state_mutations:
        result['state_mutations'] = state_mutations[:6]
    return result


def _sa_c_exception(source: str, func_name: str, language: str) -> dict:
    """
    C/C++ 异常/错误处理 SA（tree-sitter 优先）。

    提取：错误返回值、goto 清理、已检查调用、未检查调用、errno 使用。
    """
    body, src_bytes = _ts_get_func_body(source, func_name, language)

    error_returns:     list[str] = []
    goto_labels:       list[str] = []
    error_checks:      list[str] = []
    unchecked_calls:   list[str] = []
    errno_assignments: list[str] = []

    if body is not None:
        # 错误返回
        for ret in _find_all_ts_nodes(body, {'return_statement'}):
            ret_text = _ts_text(ret, src_bytes).strip()
            if _RE_ERROR_CODE.search(ret_text):
                short = ret_text[:120]
                if short not in error_returns:
                    error_returns.append(short)

        # goto 语句（通常是错误清理跳转）
        for goto in _find_all_ts_nodes(body, {'goto_statement'}):
            label = _ts_text(goto, src_bytes).strip()[:80]
            if label not in goto_labels:
                goto_labels.append(label)

        # if 语句中的错误检查模式
        for if_node in _find_all_ts_nodes(body, {'if_statement'}):
            cond_node = if_node.child_by_field_name('condition')
            if cond_node is None:
                continue
            cond      = _ts_text(cond_node, src_bytes).strip()
            conseq    = if_node.child_by_field_name('consequence')
            if conseq and _ts_is_early_exit(if_node, src_bytes):
                # 条件中引用常见错误变量
                if re.search(
                    r'\b(?:ret|err|status|rc|result|rv|retval|'
                    r'err_code|error|res)\b.*[!=<>]',
                    cond
                ):
                    entry = f'if ({cond[:80]}) → error exit'
                    if entry not in error_checks:
                        error_checks.append(entry)

        # 未检查的高风险调用（expression_statement 且调用名在黑名单中）
        for expr_stmt in [c for c in body.children
                          if c.type == 'expression_statement']:
            expr = _ts_text(expr_stmt, src_bytes).strip().rstrip(';')
            m = re.match(r'([a-zA-Z_]\w*)\s*\(', expr)
            if m and m.group(1) in _RISKY_UNCHECKED:
                short = expr[:100]
                if short not in unchecked_calls:
                    unchecked_calls.append(short)

        # errno 赋值
        for assign in _find_all_ts_nodes(body, {'assignment_expression'}):
            assign_text = _ts_text(assign, src_bytes).strip()
            if re.match(r'\berrno\s*=', assign_text):
                short = assign_text[:80]
                if short not in errno_assignments:
                    errno_assignments.append(short)

    else:
        # 正则兜底
        for m in _RE_RETURN.finditer(source):
            val = m.group(1).strip()
            if _RE_ERROR_CODE.search(val):
                entry = f'return {val}'[:100]
                if entry not in error_returns:
                    error_returns.append(entry)
        for m in _RE_GOTO.finditer(source):
            label = f'goto {m.group(1)}'
            if label not in goto_labels:
                goto_labels.append(label)
        for m in _RE_ERRNO.finditer(source):
            entry = f'errno = {m.group(1)}'
            if entry not in errno_assignments:
                errno_assignments.append(entry)

    result: dict = {}
    if error_returns:
        result['error_returns'] = list(dict.fromkeys(error_returns))[:8]
    if goto_labels:
        result['goto_cleanup'] = list(dict.fromkeys(goto_labels))[:5]
    if error_checks:
        result['error_checks'] = error_checks[:6]
    if unchecked_calls:
        result['unchecked_calls'] = unchecked_calls[:4]
    if errno_assignments:
        result['errno_usage'] = list(dict.fromkeys(errno_assignments))[:4]
    return result


# ==================================================================
# §5  Python AST SA
# ==================================================================

def _py_find_target(source: str, func_name: str):
    """用 ast 找到目标函数节点，失败返回 None。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == func_name):
            return node
    return None


def _sa_python_precondition(source: str, func_name: str) -> dict:
    fn = _py_find_target(source, func_name)
    if fn is None:
        return {}

    guard_conditions: list[str] = []
    asserts:          list[str] = []
    scan_n = max(4, int(len(fn.body) * 0.35))

    for stmt in fn.body[:scan_n]:
        if isinstance(stmt, ast.If):
            is_early = any(isinstance(s, (ast.Return, ast.Raise))
                           for s in stmt.body)
            if is_early:
                try:
                    cond = ast.unparse(stmt.test)
                    guard_conditions.append(f'guard: {cond[:120]}')
                except Exception:
                    pass
        elif isinstance(stmt, ast.Assert):
            try:
                cond = ast.unparse(stmt.test)
                asserts.append(cond[:120])
            except Exception:
                pass

    result: dict = {}
    if guard_conditions:
        result['guard_conditions'] = guard_conditions
    if asserts:
        result['asserts'] = asserts
    return result


def _sa_python_postcondition(source: str, func_name: str) -> dict:
    fn = _py_find_target(source, func_name)
    if fn is None:
        return {}

    return_values: list[str] = []
    yield_values:  list[str] = []

    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and node.value is not None:
            try:
                val = ast.unparse(node.value)[:100]
                if val not in return_values:
                    return_values.append(val)
            except Exception:
                pass
        elif isinstance(node, ast.Yield) and node.value is not None:
            try:
                val = ast.unparse(node.value)[:100]
                if val not in yield_values:
                    yield_values.append(val)
            except Exception:
                pass

    result: dict = {}
    if return_values:
        result['return_values'] = list(dict.fromkeys(return_values))[:10]
    if yield_values:
        result['yield_values'] = yield_values[:4]
    return result


def _sa_python_exception(source: str, func_name: str) -> dict:
    fn = _py_find_target(source, func_name)
    if fn is None:
        return {}

    raises:    list[str] = []
    handlers:  list[str] = []
    err_rets:  list[str] = []

    for node in ast.walk(fn):
        if isinstance(node, ast.Raise):
            try:
                exc = ast.unparse(node.exc) if node.exc else 're-raise'
                if exc not in raises:
                    raises.append(exc[:100])
            except Exception:
                pass
        elif isinstance(node, ast.ExceptHandler):
            try:
                exc_type = ast.unparse(node.type) if node.type else 'Exception'
                entry    = f'catches {exc_type}'
                if entry not in handlers:
                    handlers.append(entry)
            except Exception:
                pass
        elif isinstance(node, ast.Return) and node.value is not None:
            try:
                val = ast.unparse(node.value)
                if re.search(r'\b(?:None|False|-1|error|err|_error)\b', val, re.I):
                    short = val[:100]
                    if short not in err_rets:
                        err_rets.append(short)
            except Exception:
                pass

    result: dict = {}
    if raises:
        result['raises'] = raises[:6]
    if handlers:
        result['exception_handlers'] = list(dict.fromkeys(handlers))[:6]
    if err_rets:
        result['error_returns'] = err_rets[:6]
    return result


# ==================================================================
# §6  通用正则 SA（兜底，语言无关）
# ==================================================================

def _sa_regex_precondition(source: str) -> dict:
    guards: list[str] = []
    asserts: list[str] = []
    for m in _RE_C_NULL_GUARD.finditer(source):
        e = f'null check: {m.group(1).strip()[:120]}'
        if e not in guards:
            guards.append(e)
    for m in _RE_C_RANGE_GUARD.finditer(source):
        e = f'range check: {m.group(1).strip()[:120]}'
        if e not in guards:
            guards.append(e)
    for m in _RE_ASSERT.finditer(source):
        e = m.group(1).strip()[:100]
        if e not in asserts:
            asserts.append(e)
    result: dict = {}
    if guards:
        result['guard_conditions'] = guards[:8]
    if asserts:
        result['asserts'] = asserts[:6]
    return result


def _sa_regex_postcondition(source: str) -> dict:
    rets: list[str] = []
    outs: list[str] = []
    allocs: list[str] = []
    for m in _RE_RETURN.finditer(source):
        v = m.group(1).strip()[:100]
        if v and v not in rets:
            rets.append(v)
    for m in _RE_DEREF_ASSIGN.finditer(source):
        e = f'*{m.group(1)} = {m.group(2).strip()}'[:100]
        if e not in outs:
            outs.append(e)
    for m in _RE_ALLOC_CALL.finditer(source):
        n = m.group(1).strip()
        if n not in allocs:
            allocs.append(n)
    result: dict = {}
    if rets:
        result['return_values'] = list(dict.fromkeys(rets))[:10]
    if outs:
        result['output_writes'] = outs[:6]
    if allocs:
        result['allocation_calls'] = allocs[:4]
    return result


def _sa_regex_exception(source: str) -> dict:
    err_rets: list[str] = []
    gotos: list[str] = []
    errnos: list[str] = []
    for m in _RE_RETURN.finditer(source):
        val = m.group(1).strip()
        if _RE_ERROR_CODE.search(val):
            e = f'return {val}'[:100]
            if e not in err_rets:
                err_rets.append(e)
    for m in _RE_GOTO.finditer(source):
        e = f'goto {m.group(1)}'
        if e not in gotos:
            gotos.append(e)
    for m in _RE_ERRNO.finditer(source):
        e = f'errno = {m.group(1)}'
        if e not in errnos:
            errnos.append(e)
    result: dict = {}
    if err_rets:
        result['error_returns'] = list(dict.fromkeys(err_rets))[:8]
    if gotos:
        result['goto_cleanup'] = gotos[:5]
    if errnos:
        result['errno_usage'] = errnos[:4]
    return result


# ==================================================================
# §7  SA 分发器
# ==================================================================

def _run_sa(
    kind: str,       # 'precondition' | 'postcondition' | 'exception'
    source: str,
    func_name: str,
    language: str,
) -> dict:
    """
    根据语言选择最优 SA 策略，返回结构化特征字典。
    C/C++ 优先 tree-sitter，Python 优先 ast，其他语言用正则。
    """
    is_c_like = language in ('C', 'C++', 'Objective-C')
    is_python  = language == 'Python'

    if kind == 'precondition':
        if is_c_like and _TREE_SITTER_OK:
            ts  = _sa_c_precondition(source, func_name, language)
            rg  = _sa_regex_precondition(source)
            return {**rg, **ts}           # ts 优先覆盖
        if is_python:
            py = _sa_python_precondition(source, func_name)
            rg = _sa_regex_precondition(source)
            return {**rg, **py}
        return _sa_regex_precondition(source)

    if kind == 'postcondition':
        if is_c_like and _TREE_SITTER_OK:
            ts  = _sa_c_postcondition(source, func_name, language)
            rg  = _sa_regex_postcondition(source)
            return {**rg, **ts}
        if is_python:
            py = _sa_python_postcondition(source, func_name)
            rg = _sa_regex_postcondition(source)
            return {**rg, **py}
        return _sa_regex_postcondition(source)

    if kind == 'exception':
        if is_c_like and _TREE_SITTER_OK:
            ts  = _sa_c_exception(source, func_name, language)
            rg  = _sa_regex_exception(source)
            return {**rg, **ts}
        if is_python:
            py = _sa_python_exception(source, func_name)
            rg = _sa_regex_exception(source)
            return {**rg, **py}
        return _sa_regex_exception(source)

    return {}


# ==================================================================
# §8  公共主分析骨架（内部复用）
# ==================================================================

def _analyze_func_field(
    kind: str,
    repo_id: int,
    db_path: Optional[str],
    func_ids: Optional[list[int]],
    skip_if_exists: bool,
    languages: Optional[list[str]],
) -> dict[int, list[str]]:
    """
    通用分析骨架，供三个公开函数复用。

    kind : 'precondition' | 'postcondition' | 'exception'
    """
    from llm.client  import chat_completion_json
    import config as _cfg

    if kind == 'precondition':
        from llm.prompts import (
            ANALYZE_FUNC_PRECONDITION_SYSTEM as SYS,
            ANALYZE_FUNC_PRECONDITION_USER   as USR,
        )
    elif kind == 'postcondition':
        from llm.prompts import (
            ANALYZE_FUNC_POSTCONDITION_SYSTEM as SYS,
            ANALYZE_FUNC_POSTCONDITION_USER   as USR,
        )
    else:
        from llm.prompts import (
            ANALYZE_FUNC_EXCEPTION_SYSTEM as SYS,
            ANALYZE_FUNC_EXCEPTION_USER   as USR,
        )

    _db = db_path or DB_PATH
    label = f'[analyze_func_{kind}]'

    # ── 取仓库信息 ──────────────────────────────────────────────
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f'{label} repo_id={repo_id} 在数据库中不存在。')

    repo_path = repo['path']
    repo_name = repo['name']
    print(f'{label} 目标仓库：{repo_name}（{repo_path}）')

    # ── 构建文件语言映射 ─────────────────────────────────────────
    all_files = FileDB.list_by_repo(repo_id, db_path=_db)
    file_map  = {f['id']: f for f in all_files}

    # ── 取函数列表并过滤 ─────────────────────────────────────────
    all_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)

    if func_ids is not None:
        id_set    = set(func_ids)
        all_funcs = [f for f in all_funcs if f['id'] in id_set]

    if languages:
        lang_set  = set(languages)
        all_funcs = [
            f for f in all_funcs
            if (file_map.get(f['file_id']) or {}).get('language', 'Unknown')
               in lang_set
        ]

    if skip_if_exists:
        before = len(all_funcs)
        all_funcs = [f for f in all_funcs if not f.get(kind)]
        skipped_existing = before - len(all_funcs)
        if skipped_existing:
            print(f'{label} 跳过已有数据的函数：{skipped_existing} 个')

    total   = len(all_funcs)
    print(
        f'{label} 待处理函数：{total} 个 '
        f'（模型：{_cfg.LLM_MODEL}，tree-sitter={'可用' if _TREE_SITTER_OK else '不可用'}）'
    )

    result:  dict[int, list[str]] = {}
    success = error = skipped = 0

    for idx, fn_rec in enumerate(all_funcs, start=1):
        func_id   = fn_rec['id']
        func_name = fn_rec['name']
        file_id   = fn_rec.get('file_id')

        # 获取语言信息
        file_rec  = file_map.get(file_id) if file_id else None
        language  = (file_rec or {}).get('language', 'Unknown')

        # 解析 place
        place = fn_rec.get('place') or {}
        if isinstance(place, str):
            try:
                place = _json.loads(place)
            except Exception:
                place = {}

        rel_path   = place.get('file_path', '')
        start_line = int(place.get('start_line', 0))
        end_line   = int(place.get('end_line', 0))

        if not rel_path or start_line <= 0:
            skipped += 1
            result[func_id] = []
            continue

        # 读取函数源码
        source = _read_func_source(repo_path, rel_path, start_line, end_line)
        if source is None:
            print(f'{label}   ⚠ 无法读取源码：{rel_path}:{start_line}，跳过')
            skipped += 1
            result[func_id] = []
            continue

        # 运行 SA
        try:
            sa_results = _run_sa(kind, source, func_name, language)
        except Exception as exc:
            print(f'{label}   ⚠ SA 失败（{func_name}）：{exc}，以空 SA 继续')
            sa_results = {}

        # 准备 prompt 参数
        io = fn_rec.get('io') or {}
        if isinstance(io, str):
            try:
                io = _json.loads(io)
            except Exception:
                io = {}

        params_text  = _format_params(io.get('params', []))
        return_type  = (io.get('returns') or {}).get('type', '') or ''
        source_trunc = source[:_MAX_SOURCE_IN_PROMPT]
        if len(source) > _MAX_SOURCE_IN_PROMPT:
            source_trunc += f'\n... (源码截断，原长 {len(source)} 字符)'

        user_content = USR.format(
            func_name   = func_name,
            language    = language,
            signature   = str(fn_rec.get('signature', '') or '')[:300],
            params      = params_text,
            return_type = return_type,
            sa_results  = _json.dumps(sa_results, ensure_ascii=False, indent=2),
            source_code = source_trunc,
        )

        messages = [
            {'role': 'system', 'content': SYS},
            {'role': 'user',   'content': user_content},
        ]

        # ── LLM 调用（含重试）──────────────────────────────────
        last_exc  = None
        call_ok   = False

        for attempt in range(1, _LLM_MAX_RETRIES + 1):
            try:
                raw   = chat_completion_json(messages=messages, temperature=0.1)
                items = _parse_llm_list(raw)
                FuncDB.update(func_id, db_path=_db, **{kind: items})
                result[func_id] = items
                success += 1
                call_ok = True
                break                          # 成功，跳出重试循环

            except Exception as exc:
                last_exc = exc
                if attempt < _LLM_MAX_RETRIES:
                    wait = _LLM_RETRY_DELAYS[attempt - 1]
                    print(
                        f'{label}   ↻ LLM 调用失败，第 {attempt}/{_LLM_MAX_RETRIES} 次'
                        f'（func_id={func_id} {func_name}）：{exc}'
                        f'，{wait}s 后重试…'
                    )
                    time.sleep(wait)
                else:
                    # 最后一次仍失败
                    print(
                        f'{label}   ✗ LLM 调用失败，已重试 {_LLM_MAX_RETRIES} 次放弃'
                        f'（func_id={func_id} {func_name}）：{last_exc}'
                    )

        if not call_ok:
            error += 1
            result[func_id] = []
            try:
                FuncDB.update(func_id, db_path=_db, **{kind: []})
            except Exception as write_exc:
                print(f'{label}   ⚠ 写库空列表失败（func_id={func_id}）：{write_exc}')
        # ── 重试块结束 ─────────────────────────────────────────

        # 进度日志
        if idx % 10 == 0 or idx == total:
            print(
                f'{label}   进度 {idx}/{total}  '
                f'✓={success}  ✗={error}  skip={skipped}'
            )

    print(
        f'{label} ✓ 完成：\n'
        f'  总处理  : {total}\n'
        f'  写库成功 : {success}\n'
        f'  LLM失败  : {error}\n'
        f'  跳过     : {skipped}'
    )
    return result


# ==================================================================
# §9  公开 API
# ==================================================================

def analyze_func_precondition(
    repo_id: int,
    db_path: Optional[str] = None,
    func_ids: Optional[list[int]] = None,
    skip_if_exists: bool = True,
    languages: Optional[list[str]] = None,
) -> dict[int, list[str]]:
    """
    SA + LLM 分析仓库内函数的前置条件，写入 func.precondition。

    前置条件描述调用方在调用该函数前必须保证满足的条件：
    参数非空约束、值范围、对象状态、资源有效性、调用顺序等。

    Parameters
    ----------
    repo_id         : 目标仓库 id
    db_path         : SQLite 路径；不传则用 config.DB_PATH
    func_ids        : 指定函数 id 列表；None 则处理全部函数
    skip_if_exists  : True = 跳过已有 precondition 数据的函数（增量处理）
    languages       : 语言白名单；None 则不过滤（如 ['C', 'C++']）

    Returns
    -------
    dict[int, list[str]]   {func_id → ["前置条件1", "前置条件2", ...]}

    Raises
    ------
    ValueError  repo_id 不存在
    """
    return _analyze_func_field(
        kind='precondition',
        repo_id=repo_id,
        db_path=db_path,
        func_ids=func_ids,
        skip_if_exists=skip_if_exists,
        languages=languages,
    )


def analyze_func_postcondition(
    repo_id: int,
    db_path: Optional[str] = None,
    func_ids: Optional[list[int]] = None,
    skip_if_exists: bool = True,
    languages: Optional[list[str]] = None,
) -> dict[int, list[str]]:
    """
    SA + LLM 分析仓库内函数的后置条件，写入 func.postcondition。

    后置条件描述函数执行完毕后调用方可以依赖的保证：
    返回值语义、输出参数写回、内存分配责任、状态变更、副作用等。

    Parameters / Returns / Raises 参见 analyze_func_precondition。
    """
    return _analyze_func_field(
        kind='postcondition',
        repo_id=repo_id,
        db_path=db_path,
        func_ids=func_ids,
        skip_if_exists=skip_if_exists,
        languages=languages,
    )


def analyze_func_exception(
    repo_id: int,
    db_path: Optional[str] = None,
    func_ids: Optional[list[int]] = None,
    skip_if_exists: bool = True,
    languages: Optional[list[str]] = None,
) -> dict[int, list[str]]:
    """
    SA + LLM 分析仓库内函数的异常与错误处理，写入 func.exception。

    分析维度包括：已处理错误路径、错误传播方式、资源清理行为、
    潜在未检查调用风险、errno 使用等。

    Parameters / Returns / Raises 参见 analyze_func_precondition。
    """
    return _analyze_func_field(
        kind='exception',
        repo_id=repo_id,
        db_path=db_path,
        func_ids=func_ids,
        skip_if_exists=skip_if_exists,
        languages=languages,
    )
```

### Step8：all descrption and brief

`llm/prompt`（增加）

````
# ==================================================================
#  Step 12: analyze_func_description —— 函数描述 Agent
# ==================================================================

ANALYZE_FUNC_DESCRIPTION_SYSTEM = """\
你是一位资深软件安全研究员与系统架构师，专精 C/C++ 代码深度分析。

## 核心任务
为给定函数生成完整的多维度自然语言描述，供代码知识库检索和安全审计使用。

## 输出格式（纯文本，各节有加粗标题，使用中文，共约300-600字）

**【功能概述】**
2-4句话，说明该函数的核心功能、输入输出语义及在系统中的整体定位。

**【实现分析】**
描述关键实现逻辑：主要控制流、重要的数据变换、状态机转换、关键算法及整体结构特征。

**【调用关系分析】**
分析函数在调用链中的角色：上层调用者的典型使用场景，以及调用的关键子函数及其作用。
如需了解某个被调函数的详细信息，可使用 get_func_context 工具查询后再分析。

**【安全与稳健性分析】**
评估潜在安全风险（缓冲区溢出、空指针解引用、整数溢出、资源泄漏、double-free、
use-after-free等），分析错误处理机制的完善程度以及边界条件处理情况。

**【开发者意图分析】**
从代码风格、命名惯例、注释和设计模式推断开发者的设计意图、工程取舍与技术决策背景。

## 工具使用规范
- 仅当需要了解关键 callee 函数的具体实现才调用 get_func_context
- 通常只需查询 1-3 个最关键的 user 类型 callee 即可，不必查询全部
- 调用时提供准确的函数名；若已知 func_id 则一并提供以精确匹配
"""

ANALYZE_FUNC_DESCRIPTION_USER = """\
请对以下函数进行深度分析并输出完整描述：

## 基本信息
- 函数名：{func_name}
- 签名：`{signature}`
- 所在文件：{file_path}（第 {start_line}–{end_line} 行）
- 语言：{language}

## 参数列表
{params}

## 返回类型
{return_type}

## 调用关系（callgraph）
```json
{callgraph}
```

## 前置条件（SA + LLM 分析结果）
```json
{precondition}
```

## 后置条件（SA + LLM 分析结果）
```json
{postcondition}
```

## 异常处理（SA + LLM 分析结果）
```json
{exception}
```

## 函数源码
```c
{source_code}
```

请按五节格式给出完整分析。如需了解被调函数细节，请先调用 get_func_context 工具。\
"""


# ==================================================================
#  Step 13: analyze_file_funclist_brief —— 函数简短摘要（批处理）
# ==================================================================

ANALYZE_FILE_FUNCLIST_BRIEF_SYSTEM = """\
你是代码文档精简专家。将每个函数的完整描述浓缩为一两句话的简短摘要（brief）。
要求：准确传达函数核心功能，语言简洁，建议20字以内，最多不超过50字。

## 严格输出要求
只输出合法 JSON，结构如下，不得包含任何额外解释文字：
```json
{
  "briefs": [
    {"func_id": 1, "brief": "函数核心功能的简短描述"},
    {"func_id": 2, "brief": "..."},
    ...
  ]
}
```
"""

ANALYZE_FILE_FUNCLIST_BRIEF_USER = """\
文件：{file_name}
请为以下 {func_count} 个函数各生成一条 brief：

{func_list_text}

按要求输出 JSON。\
"""


# ==================================================================
#  Step 14: analyze_file_description —— 文件描述
# ==================================================================

ANALYZE_FILE_DESCRIPTION_SYSTEM = """\
你是一位资深软件架构师，为代码知识库生成文件级自然语言描述。

## 任务
根据文件所在 area 的结构、文件路径、编程语言、函数列表及其描述，
生成对该文件的全面自然语言描述（纯文本，中文，各节有加粗标题，约200-350字）。

**【文件功能】**
该文件实现了哪些核心能力，向外提供了哪些接口或功能集合。

**【文件定位】**
在所属 area 中的角色定位（核心逻辑/接口层/工具模块/辅助模块），
与同 area 其他文件的协作关系。

**【开发者意图分析】**
推断该文件的设计意图、模块化边界划定的理由、技术选型背景。
"""

ANALYZE_FILE_DESCRIPTION_USER = """\
## 文件信息
文件名：{file_name}
语言：{language}
所在 Area：{area_name}（路径：{area_path}）
文件路径：{file_path}

## 所在 Area 文件结构
{area_file_structure}

## 文件中的函数列表与描述
{func_descriptions}

请生成该文件的自然语言描述。\
"""


# ==================================================================
#  Step 15: analyze_area_filelist_brief —— 文件简短摘要（批处理）
# ==================================================================

ANALYZE_AREA_FILELIST_BRIEF_SYSTEM = """\
你是代码文档精简专家。将每个文件的完整描述浓缩为一两句话的简短摘要（brief）。
要求：准确概括文件的核心职责，语言简洁，不超过50字。

## 严格输出要求
只输出合法 JSON，结构如下：
```json
{
  "briefs": [
    {"file_id": 1, "brief": "文件核心职责的简短描述"},
    ...
  ]
}
```
"""

ANALYZE_AREA_FILELIST_BRIEF_USER = """\
Area：{area_name}
请为以下 {file_count} 个文件各生成一条 brief：

{file_list_text}

按要求输出 JSON。\
"""


# ==================================================================
#  Step 16: analyze_area_description —— Area 描述
# ==================================================================

ANALYZE_AREA_DESCRIPTION_SYSTEM = """\
你是一位资深软件架构师，为代码知识库生成模块（area）级自然语言描述。

## 任务
根据 area 的路径、分层依据、文件组织结构及各文件描述，
生成对该 area 的全面自然语言描述（纯文本，中文，各节有加粗标题，约200-350字）。

**【Area 功能】**
该模块提供的核心能力，实现了哪些功能集合，对外暴露了哪些关键接口。

**【Area 定位】**
在整个仓库中的架构定位（核心业务逻辑/基础设施/工具库/接口层），
与其他 area 的依赖和协作关系。

**【开发者意图分析】**
推断该模块的设计意图、模块化边界的划定理由、关键技术架构决策。
"""

ANALYZE_AREA_DESCRIPTION_USER = """\
## Area 信息
Area 名称：{area_name}
路径：{area_path}
分层依据：{rationale}

## Area 文件结构
{file_structure}

## 各文件描述
{file_descriptions}

请生成该 area 的自然语言描述。\
"""


# ==================================================================
#  Step 17: analyze_repo_arealist_brief —— Area 简短摘要（批处理）
# ==================================================================

ANALYZE_REPO_AREALIST_BRIEF_SYSTEM = """\
你是代码文档精简专家。将每个模块（area）的完整描述浓缩为一两句话的简短摘要（brief）。
要求：准确概括模块的核心职责，语言简洁，不超过50字。

## 严格输出要求
只输出合法 JSON，结构如下：
```json
{
  "briefs": [
    {"area_id": 1, "brief": "模块核心职责的简短描述"},
    ...
  ]
}
```
"""

ANALYZE_REPO_AREALIST_BRIEF_USER = """\
仓库：{repo_name}
请为以下 {area_count} 个模块各生成一条 brief：

{area_list_text}

按要求输出 JSON。\
"""


# ==================================================================
#  Step 18: analyze_repo_description —— 仓库描述
# ==================================================================

ANALYZE_REPO_DESCRIPTION_SYSTEM = """\
你是一位资深软件架构师，为代码知识库生成仓库级自然语言描述。

## 任务
根据仓库的目录结构、分层架构、语言组成、README 内容及各 area 描述，
生成对整个仓库的全面自然语言描述（纯文本，中文，各节有加粗标题，约300-500字）。

**【仓库功能】**
该仓库实现的核心功能，提供了哪些能力，解决了什么领域的问题。

**【技术架构分析】**
整体架构设计，各层/模块的分工，关键技术选型，数据流和控制流的整体特征。

**【开发者意图分析】**
推断仓库的设计目标、工程哲学、面向的使用场景，以及代码库的成熟度与维护状态评估。
"""

ANALYZE_REPO_DESCRIPTION_USER = """\
## 仓库基本信息
仓库名：{repo_name}
主要语言：{main_language}
语言分布：{language_stats}

## 目录结构（3层）
```
{dir_tree}
```

## 模块划分（area 列表）
{area_structure}

## README 内容摘要
{readme_content}

## 各 Area 完整描述
{area_descriptions}

请生成该仓库的自然语言描述。\
"""
````

`llm/agent`

```
"""
llm/agent.py
CodeMAP Agent 实现 —— 供 analyze_func_description (Step 12) 使用

对外暴露：
  run_func_description_agent(
      func_rec, repo_id, db_path, repo_path, source_code, model
  ) → str
      运行单函数描述 Agent 循环，返回最终自然语言描述文本。

工具：
  get_func_context(func_name, func_id?) → dict
      从 DB 查询指定函数的签名、IO、callgraph、前/后置条件、
      异常处理、已有描述，并可选附上源码片段。
"""

import json
import os
import sys
import time
from typing import Optional

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# ── 常量 ─────────────────────────────────────────────────────────
_MAX_AGENT_ITERS      = 8     # 最大 Agent 循环轮次（防无限循环）
_AGENT_TIMEOUT        = 240   # 单次 HTTP 请求超时（秒）
_MAX_SRC_IN_TOOL      = 2000  # get_func_context 返回的源码最大字符数


# ==================================================================
# 1. 工具 Schema（OpenAI function-calling 格式）
# ==================================================================

_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_func_context",
            "description": (
                "根据函数名（或函数ID）从代码库数据库中查询该函数的完整上下文信息，"
                "包括：签名、参数列表、返回类型、调用图（caller/callee 关系）、"
                "前置条件、后置条件、异常处理，以及该函数的已有描述和源码片段。"
                "当需要深入了解当前函数所调用的子函数时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "func_name": {
                        "type": "string",
                        "description": "要查询的函数名称（精确名或近似名均可）",
                    },
                    "func_id": {
                        "type": "integer",
                        "description": "函数在数据库中的 ID（可选；提供时优先精确匹配）",
                    },
                },
                "required": ["func_name"],
            },
        },
    }
]


# ==================================================================
# 2. 工具执行器
# ==================================================================

def _execute_get_func_context(
    func_name: str,
    func_id: Optional[int],
    repo_id: int,
    db_path: str,
    repo_path: str,
) -> dict:
    """
    执行 get_func_context 工具调用。

    查找策略：
      1. 若提供 func_id → 精确按 ID 查找
      2. 否则按 func_name 在仓库范围内模糊搜索
      3. 优先返回精确名称匹配的第一个结果

    Returns
    -------
    dict  包含 func 完整信息；未找到时返回 {"error": "..."}
    """
    from db.dao import FuncDB

    # ① 查找函数记录
    candidates: list[dict] = []
    if func_id is not None:
        rec = FuncDB.get_by_id(func_id, db_path=db_path)
        if rec:
            candidates = [rec]

    if not candidates:
        # 模糊搜索：search_by_name 使用 LIKE %keyword%
        candidates = FuncDB.search_by_name(repo_id, func_name, db_path=db_path)

    if not candidates:
        return {
            "found": False,
            "error": f"未在数据库中找到函数 '{func_name}'（func_id={func_id}）",
        }

    # 优先精确名称匹配
    exact = [c for c in candidates if c["name"] == func_name]
    rec   = exact[0] if exact else candidates[0]

    # ② 尝试读取源码片段
    place = rec.get("place") or {}
    if isinstance(place, str):
        try:
            place = json.loads(place)
        except Exception:
            place = {}

    src_snippet = ""
    rel_path    = place.get("file_path", "")
    start_line  = int(place.get("start_line", 0))
    end_line    = int(place.get("end_line", start_line))

    if rel_path and start_line > 0:
        abs_path = os.path.join(repo_path, rel_path)
        if os.path.isfile(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                s = max(0, start_line - 1)
                e = min(len(lines), end_line)
                src_snippet = "".join(lines[s:e])
                if len(src_snippet) > _MAX_SRC_IN_TOOL:
                    src_snippet = (
                        src_snippet[:_MAX_SRC_IN_TOOL]
                        + f"\n...(源码截断，原长 {len(src_snippet)} 字符)"
                    )
            except OSError:
                pass

    # ③ 整合并返回
    def _safe_json(val):
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val or {}

    return {
        "found":        True,
        "func_id":      rec["id"],
        "name":         rec["name"],
        "signature":    rec.get("signature", ""),
        "place":        place,
        "io":           _safe_json(rec.get("io")),
        "callgraph":    _safe_json(rec.get("callgraph")) or {"callers": [], "callees": []},
        "precondition": _safe_json(rec.get("precondition")) or [],
        "postcondition":_safe_json(rec.get("postcondition")) or [],
        "exception":    _safe_json(rec.get("exception")) or [],
        "description":  rec.get("description", "") or "",
        "source_snippet": src_snippet,
    }


# ==================================================================
# 3. 带 tools 的 LLM 调用
# ==================================================================

def _chat_with_tools(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 8192,
) -> dict:
    """
    调用 LLM chat completion（带 tools 定义）。

    Returns
    -------
    dict  choices[0].message 原始字典；包含 content 和/或 tool_calls

    Raises
    ------
    RuntimeError  网络/HTTP 错误或响应解析失败
    """
    base_url = LLM_BASE_URL.rstrip("/")
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
        "tools":       _TOOLS,
        "tool_choice": "auto",
    }

    try:
        resp = requests.post(
            url, headers=headers, json=payload, timeout=_AGENT_TIMEOUT
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"[Agent] 请求超时（>{_AGENT_TIMEOUT}s）")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"[Agent] 网络连接失败：{e}")
    except requests.exceptions.HTTPError:
        raise RuntimeError(
            f"[Agent] HTTP {resp.status_code}：{resp.text[:400]}"
        )

    try:
        data = resp.json()
        return data["choices"][0]["message"]
    except (KeyError, IndexError, ValueError) as e:
        raise RuntimeError(
            f"[Agent] 响应解析失败：{e}\n原始响应（前600字）：{resp.text[:600]}"
        ) from e


# ==================================================================
# 4. Agent 主循环
# ==================================================================

def run_func_description_agent(
    func_rec:    dict,
    repo_id:     int,
    db_path:     str,
    repo_path:   str,
    source_code: str,
    model:       Optional[str] = None,
) -> str:
    """
    运行单函数描述 Agent，返回自然语言描述字符串。

    流程
    ----
    1. 从 func_rec 中提取完整上下文，填充 user 消息
    2. 进入 Agent 循环（最多 _MAX_AGENT_ITERS 轮）：
       a. 调用 LLM（带 tools）
       b. 若模型发出 tool_calls → 逐一执行、追加结果、继续循环
       c. 若模型返回纯文本 → 即为函数描述，退出循环
    3. 返回描述文本

    Parameters
    ----------
    func_rec    : FuncDB 返回的函数记录字典
    repo_id     : 仓库 ID（用于 get_func_context 工具查询）
    db_path     : SQLite 数据库路径
    repo_path   : 仓库本地根目录绝对路径
    source_code : 函数源码文本（调用方已做截断）
    model       : 可选模型名覆盖

    Returns
    -------
    str  LLM 生成的函数描述（多段纯文本）

    Raises
    ------
    RuntimeError  LLM 调用失败或超出最大迭代轮次
    """
    from llm.prompts import (
        ANALYZE_FUNC_DESCRIPTION_SYSTEM,
        ANALYZE_FUNC_DESCRIPTION_USER,
    )

    func_name = func_rec.get("name", "")

    # ── 整理上下文字段 ────────────────────────────────────────────

    def _safe(val):
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val

    io            = _safe(func_rec.get("io")) or {}
    callgraph     = _safe(func_rec.get("callgraph")) or {}
    precondition  = _safe(func_rec.get("precondition")) or []
    postcondition = _safe(func_rec.get("postcondition")) or []
    exception     = _safe(func_rec.get("exception")) or []
    place         = _safe(func_rec.get("place")) or {}

    params_list = io.get("params", [])
    if params_list:
        params_text = "\n".join(
            f"  - {p.get('name','')}: {p.get('type','')}  {p.get('desc','')}".strip()
            for p in params_list
        )
    else:
        params_text = "（无参数）"

    return_type = str((io.get("returns") or {}).get("type", "") or "")

    # ── 构建初始 user 消息 ────────────────────────────────────────
    user_content = ANALYZE_FUNC_DESCRIPTION_USER.format(
        func_name     = func_name,
        signature     = str(func_rec.get("signature", "") or "")[:400],
        file_path     = str(place.get("file_path", "") or ""),
        start_line    = place.get("start_line", "?"),
        end_line      = place.get("end_line", "?"),
        language      = "C",   # 主要针对 C/C++ 仓库；调用方可通过 func_rec 传入
        params        = params_text,
        return_type   = return_type or "（未知）",
        callgraph     = json.dumps(callgraph, ensure_ascii=False, indent=2),
        precondition  = json.dumps(precondition, ensure_ascii=False, indent=2),
        postcondition = json.dumps(postcondition, ensure_ascii=False, indent=2),
        exception     = json.dumps(exception, ensure_ascii=False, indent=2),
        source_code   = source_code,
    )

    messages: list[dict] = [
        {"role": "system", "content": ANALYZE_FUNC_DESCRIPTION_SYSTEM},
        {"role": "user",   "content": user_content},
    ]

    # ── Agent 循环 ────────────────────────────────────────────────
    for iteration in range(_MAX_AGENT_ITERS):
        assistant_msg = _chat_with_tools(messages, model=model)

        tool_calls = assistant_msg.get("tool_calls")

        if tool_calls:
            # 将 assistant 消息（含 tool_calls）加入历史
            messages.append(assistant_msg)

            for tc in tool_calls:
                tc_id       = tc.get("id", f"call_{iteration}_{id(tc)}")
                tc_func     = tc.get("function", {})
                tc_name     = tc_func.get("name", "")
                tc_args_raw = tc_func.get("arguments", "{}")

                try:
                    tc_args = json.loads(tc_args_raw)
                except json.JSONDecodeError:
                    tc_args = {}

                if tc_name == "get_func_context":
                    tool_result = _execute_get_func_context(
                        func_name = tc_args.get("func_name", ""),
                        func_id   = tc_args.get("func_id"),
                        repo_id   = repo_id,
                        db_path   = db_path,
                        repo_path = repo_path,
                    )
                else:
                    tool_result = {"error": f"未知工具：{tc_name!r}"}

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc_id,
                    "content":      json.dumps(
                        tool_result, ensure_ascii=False, indent=2
                    ),
                })

            continue  # 带上工具结果继续循环

        # 无 tool_calls → 取文本作为最终描述
        content = (assistant_msg.get("content") or "").strip()
        if content:
            return content

        # 内容为空的异常保护（正常不应发生）
        if iteration >= _MAX_AGENT_ITERS - 1:
            break

    raise RuntimeError(
        f"[Agent] 函数 '{func_name}' 超出最大迭代轮次（{_MAX_AGENT_ITERS}）"
        "，仍未获得有效描述。"
    )
```

``analyzer/func_analyzer.py` 追加（`analyze_func_description`）

```
# ─────────────────────────────────────────────
# 以下为 Step 12 新增，依赖已有的 _read_func_source / _format_params 等工具函数

import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed

# LLM 重试配置（Step 12 统一用 5 次）
_DESC_MAX_RETRIES  = 5
_DESC_RETRY_DELAYS = (2, 5, 10, 20, 40)   # 第1-5次失败后等待秒数
_DESC_MAX_SRC_CHARS = 4000                 # prompt 中源码最大字符数


def _retry(fn, label: str = "", max_retries: int = _DESC_MAX_RETRIES):
    """通用重试包装器，失败后按指数退避等待，最多 max_retries 次。"""
    last_exc = None
    for i in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if i < max_retries - 1:
                wait = _DESC_RETRY_DELAYS[min(i, len(_DESC_RETRY_DELAYS) - 1)]
                print(
                    f"  ↻ 第{i+1}/{max_retries}次失败{' (' + label + ')' if label else ''}："
                    f"{exc}，{wait}s 后重试…"
                )
                _time.sleep(wait)
    raise RuntimeError(
        f"已重试 {max_retries} 次仍失败{' (' + label + ')' if label else ''}。"
        f"最后异常：{last_exc}"
    )


def _describe_one_func(
    fn_rec:    dict,
    file_map:  dict,
    repo_id:   int,
    db_path:   str,
    repo_path: str,
) -> tuple[int, str]:
    """
    处理单个函数的描述生成（含源码读取 + Agent 调用）。
    返回 (func_id, description_text)。
    供 ThreadPoolExecutor 调用。
    """
    from llm.agent import run_func_description_agent

    func_id   = fn_rec["id"]
    func_name = fn_rec["name"]

    # 取文件语言
    file_rec  = file_map.get(fn_rec.get("file_id"))
    language  = (file_rec or {}).get("language", "C")

    # 解析 place
    place = fn_rec.get("place") or {}
    if isinstance(place, str):
        try:
            import json as _j; place = _j.loads(place)
        except Exception:
            place = {}

    rel_path   = place.get("file_path", "")
    start_line = int(place.get("start_line", 0))
    end_line   = int(place.get("end_line", 0))

    if not rel_path or start_line <= 0:
        return func_id, ""

    # 读取源码
    source = _read_func_source(repo_path, rel_path, start_line, end_line)
    if source is None:
        return func_id, ""

    if len(source) > _DESC_MAX_SRC_CHARS:
        source = source[:_DESC_MAX_SRC_CHARS] + f"\n...(源码截断，原长 {len(source)} 字符)"

    # 将语言信息注入 func_rec（agent.py 需要）
    fn_rec_copy = dict(fn_rec)
    fn_rec_copy["_language"] = language

    label = f"func_id={func_id} {func_name}"

    def _run():
        return run_func_description_agent(
            func_rec   = fn_rec_copy,
            repo_id    = repo_id,
            db_path    = db_path,
            repo_path  = repo_path,
            source_code= source,
        )

    desc = _retry(_run, label=label, max_retries=_DESC_MAX_RETRIES)
    return func_id, desc


def analyze_func_description(
    repo_id: int,
    db_path: Optional[str] = None,
    func_ids: Optional[list[int]] = None,
    skip_if_exists: bool = True,
    languages: Optional[list[str]] = None,
    max_workers: int = 10,
) -> dict[int, str]:
    """
    Agent 分析仓库内函数，生成自然语言描述，写入 func.description。

    并行策略
    --------
    每个函数独立运行 Agent（LLM 网络 I/O 为主，GIL 在阻塞时释放），
    ThreadPoolExecutor(max_workers) 实现真并发，默认 10 路。

    重试策略
    --------
    每个函数最多重试 5 次（含首次），失败后写入空字符串并记录错误。

    Parameters
    ----------
    repo_id         : 目标仓库 id
    db_path         : SQLite 路径；None 使用 config.DB_PATH
    func_ids        : 指定函数 id 列表；None 处理全部
    skip_if_exists  : True = 跳过已有 description 的函数（增量处理）
    languages       : 语言白名单；None 不过滤（如 ['C', 'C++']）
    max_workers     : 并发线程数，默认 10

    Returns
    -------
    dict[int, str]  {func_id → description_text}
    """
    import config as _cfg

    _db = db_path or DB_PATH

    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_func_description] repo_id={repo_id} 不存在。")

    repo_path = repo["path"]
    repo_name = repo["name"]
    print(f"[analyze_func_description] 目标仓库：{repo_name}（{repo_path}）")

    # ── 构建文件语言映射 ──────────────────────────────────────────
    all_files = FileDB.list_by_repo(repo_id, db_path=_db)
    file_map  = {f["id"]: f for f in all_files}

    # ── 过滤待处理函数 ────────────────────────────────────────────
    all_funcs = FuncDB.list_by_repo(repo_id, db_path=_db)

    if func_ids is not None:
        id_set    = set(func_ids)
        all_funcs = [f for f in all_funcs if f["id"] in id_set]

    if languages:
        lang_set  = set(languages)
        all_funcs = [
            f for f in all_funcs
            if (file_map.get(f.get("file_id")) or {}).get("language", "Unknown")
               in lang_set
        ]

    if skip_if_exists:
        before    = len(all_funcs)
        all_funcs = [f for f in all_funcs if not f.get("description")]
        print(
            f"[analyze_func_description] 跳过已有描述：{before - len(all_funcs)} 个"
        )

    total = len(all_funcs)
    print(
        f"[analyze_func_description] 待处理函数：{total} 个"
        f"（并发度 {max_workers}，模型 {_cfg.LLM_MODEL}）"
    )

    if total == 0:
        print("[analyze_func_description] 无需处理，退出。")
        return {}

    result:   dict[int, str] = {}
    success   = error = 0
    t0 = _time.time()

    # ── 并行处理 ─────────────────────────────────────────────────
    with ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix="func_desc"
    ) as pool:
        future_to_fid = {
            pool.submit(
                _describe_one_func,
                fn_rec, file_map, repo_id, _db, repo_path,
            ): fn_rec["id"]
            for fn_rec in all_funcs
        }

        done_count = 0
        for future in _as_completed(future_to_fid):
            fid       = future_to_fid[future]
            done_count += 1

            try:
                fid_out, desc = future.result()
                result[fid_out] = desc
                if desc:
                    FuncDB.update(fid_out, db_path=_db, description=desc)
                    success += 1
                else:
                    error += 1
            except Exception as exc:
                print(
                    f"[analyze_func_description]   ✗ func_id={fid} 最终失败：{exc}"
                )
                result[fid] = ""
                try:
                    FuncDB.update(fid, db_path=_db, description="")
                except Exception:
                    pass
                error += 1

            # 进度日志
            if done_count % 20 == 0 or done_count == total:
                elapsed = _time.time() - t0
                print(
                    f"[analyze_func_description]   进度 {done_count}/{total}"
                    f"  ✓={success}  ✗={error}"
                    f"  耗时={elapsed:.0f}s"
                )

    print(
        f"[analyze_func_description] ✓ 完成：\n"
        f"  总处理  : {total}\n"
        f"  写库成功 : {success}\n"
        f"  失败    : {error}\n"
        f"  总耗时  : {_time.time() - t0:.0f}s"
    )
    return result
```

`analyzer/file_analyzer.py`（追加）

```
# ─────────────────────────────────────────────
# Step 13: analyze_file_funclist_brief
# Step 14: analyze_file_description

import time as _time_f

_FILE_MAX_DESC_CHARS   = 500    # 传给 LLM 的每个函数描述截断长度
_FILE_MAX_RETRIES      = 5
_FILE_RETRY_DELAYS     = (2, 5, 10, 20, 40)


def _file_retry(fn, label: str = "", max_retries: int = _FILE_MAX_RETRIES):
    last_exc = None
    for i in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if i < max_retries - 1:
                wait = _FILE_RETRY_DELAYS[min(i, len(_FILE_RETRY_DELAYS)-1)]
                print(f"  ↻ 重试{i+1}/{max_retries} ({label})：{exc}，{wait}s 后…")
                _time_f.sleep(wait)
    raise RuntimeError(f"重试 {max_retries} 次失败 ({label})：{last_exc}")


def analyze_file_funclist_brief(
    repo_id: int,
    db_path: Optional[str] = None,
    skip_if_exists: bool = True,
) -> dict[int, dict]:
    """
    为仓库内每个文件的 funclist 生成 brief（简短摘要），
    批量写入 file.funclist 的 brief 字段。

    策略：每个文件一次 LLM 批量调用，返回 JSON，
    从 func.description 生成 brief；若 description 为空则以签名兜底。

    Parameters
    ----------
    repo_id        : 目标仓库 id
    db_path        : SQLite 路径
    skip_if_exists : True = 跳过 funclist 中已全部有 brief 的文件

    Returns
    -------
    dict[int, dict]  {file_id → 更新后的 funclist}
    """
    from llm.client  import chat_completion_json
    from llm.prompts import (
        ANALYZE_FILE_FUNCLIST_BRIEF_SYSTEM,
        ANALYZE_FILE_FUNCLIST_BRIEF_USER,
    )

    _db      = db_path or DB_PATH
    repo     = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_file_funclist_brief] repo_id={repo_id} 不存在。")

    all_files = FileDB.list_by_repo(repo_id, db_path=_db)
    print(
        f"[analyze_file_funclist_brief] 目标仓库：{repo['name']}，"
        f"共 {len(all_files)} 个文件"
    )

    result: dict[int, dict] = {}
    processed = skipped = error = 0

    for file_rec in all_files:
        file_id   = file_rec["id"]
        file_name = file_rec["name"]
        funclist  = file_rec.get("funclist") or []
        if isinstance(funclist, str):
            try:
                import json as _j; funclist = _j.loads(funclist)
            except Exception:
                funclist = []

        if not funclist:
            result[file_id] = []
            skipped += 1
            continue

        # skip_if_exists：若所有条目都有非空 brief 则跳过
        if skip_if_exists and all(e.get("brief") for e in funclist):
            result[file_id] = funclist
            skipped += 1
            continue

        # 收集每个函数的描述（description 或 签名兜底）
        func_lines: list[str] = []
        for entry in funclist:
            fid   = entry.get("func_id")
            fname = entry.get("name", "")
            if fid:
                fn_rec  = FuncDB.get_by_id(fid, db_path=_db)
                raw_desc = (fn_rec or {}).get("description", "") or ""
                desc     = raw_desc[:_FILE_MAX_DESC_CHARS]
                sig      = (fn_rec or {}).get("signature", "")
            else:
                desc = ""
                sig  = fname

            if not desc:
                desc = f"[签名] {sig}"[:_FILE_MAX_DESC_CHARS]

            func_lines.append(f"func_id={fid}  name={fname}\n描述：{desc}\n")

        func_list_text = "\n---\n".join(func_lines)
        user_content   = ANALYZE_FILE_FUNCLIST_BRIEF_USER.format(
            file_name      = file_name,
            func_count     = len(funclist),
            func_list_text = func_list_text,
        )
        messages = [
            {"role": "system", "content": ANALYZE_FILE_FUNCLIST_BRIEF_SYSTEM},
            {"role": "user",   "content": user_content},
        ]

        try:
            def _call():
                return chat_completion_json(messages=messages, temperature=0.1)

            raw = _file_retry(_call, label=f"file_id={file_id} {file_name}")
        except Exception as exc:
            print(f"[analyze_file_funclist_brief]   ✗ {file_name}：{exc}")
            result[file_id] = funclist
            error += 1
            continue

        # 解析 briefs
        briefs_list = raw.get("briefs", []) if isinstance(raw, dict) else []
        brief_map   = {int(b["func_id"]): b["brief"]
                       for b in briefs_list
                       if isinstance(b, dict) and b.get("func_id") is not None}

        # 写回 funclist
        new_funclist = []
        for entry in funclist:
            new_entry = dict(entry)
            fid = entry.get("func_id")
            if fid and fid in brief_map:
                new_entry["brief"] = brief_map[fid]
            new_funclist.append(new_entry)

        FileDB.update(file_id, db_path=_db, funclist=new_funclist)
        result[file_id] = new_funclist
        processed += 1
        print(
            f"[analyze_file_funclist_brief]   ✓ {file_name}"
            f"  funcs={len(new_funclist)}  briefs_updated={len(brief_map)}"
        )

    print(
        f"[analyze_file_funclist_brief] ✓ 完成："
        f"处理={processed}  跳过={skipped}  失败={error}"
    )
    return result


def analyze_file_description(
    repo_id: int,
    db_path: Optional[str] = None,
    skip_if_exists: bool = True,
) -> dict[int, str]:
    """
    为仓库内每个文件生成自然语言描述，写入 file.description。

    信息来源：文件在 area 中的位置结构 + 函数列表及其 description。
    依赖：func.description 已完成（Step 12）。

    Parameters
    ----------
    repo_id        : 目标仓库 id
    db_path        : SQLite 路径
    skip_if_exists : True = 跳过已有 description 的文件

    Returns
    -------
    dict[int, str]  {file_id → description_text}
    """
    from llm.client  import chat_completion
    from llm.prompts import (
        ANALYZE_FILE_DESCRIPTION_SYSTEM,
        ANALYZE_FILE_DESCRIPTION_USER,
    )
    import json as _j

    _db  = db_path or DB_PATH
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_file_description] repo_id={repo_id} 不存在。")

    from db.dao import AreaDB
    areas     = AreaDB.list_by_repo(repo_id, db_path=_db)
    area_map  = {a["id"]: a for a in areas}

    all_files = FileDB.list_by_repo(repo_id, db_path=_db)
    # 按 area 分组，用于构造文件结构上下文
    files_by_area: dict[int, list[dict]] = {}
    for f in all_files:
        files_by_area.setdefault(f["area_id"], []).append(f)

    print(
        f"[analyze_file_description] 目标仓库：{repo['name']}，"
        f"共 {len(all_files)} 个文件"
    )

    result:   dict[int, str] = {}
    processed = skipped = error = 0

    for file_rec in all_files:
        file_id   = file_rec["id"]
        file_name = file_rec["name"]
        area_id   = file_rec.get("area_id")

        if skip_if_exists and file_rec.get("description"):
            result[file_id] = file_rec["description"]
            skipped += 1
            continue

        area_rec  = area_map.get(area_id, {})
        area_name = area_rec.get("name", "")
        area_path = area_rec.get("path", "")

        # 同 area 文件结构
        sibling_files = files_by_area.get(area_id, [])
        area_file_structure = "\n".join(
            f"  {'→ ' if f['id'] == file_id else '  '}{f['name']}  ({f.get('language','')})"
            for f in sibling_files
        )

        # 收集函数描述
        funclist = file_rec.get("funclist") or []
        if isinstance(funclist, str):
            try:
                funclist = _j.loads(funclist)
            except Exception:
                funclist = []

        func_desc_parts: list[str] = []
        for entry in funclist[:40]:   # 最多 40 个函数
            fid   = entry.get("func_id")
            fname = entry.get("name", "")
            brief = entry.get("brief", "")
            if fid:
                fn_rec = FuncDB.get_by_id(fid, db_path=_db)
                desc   = (fn_rec or {}).get("description", "") or ""
                desc   = desc[:400]
            else:
                desc = ""
            func_desc_parts.append(
                f"### {fname}\n{brief or desc or '（暂无描述）'}"
            )
        func_descriptions = "\n\n".join(func_desc_parts) or "（无函数记录）"

        user_content = ANALYZE_FILE_DESCRIPTION_USER.format(
            file_name          = file_name,
            language           = file_rec.get("language", "Unknown"),
            area_name          = area_name,
            area_path          = area_path,
            file_path          = file_rec.get("path", ""),
            area_file_structure= area_file_structure,
            func_descriptions  = func_descriptions,
        )
        messages = [
            {"role": "system", "content": ANALYZE_FILE_DESCRIPTION_SYSTEM},
            {"role": "user",   "content": user_content},
        ]

        try:
            def _call():
                return chat_completion(messages=messages, temperature=0.2)

            desc = _file_retry(_call, label=f"file_id={file_id} {file_name}")
            desc = desc.strip()
        except Exception as exc:
            print(f"[analyze_file_description]   ✗ {file_name}：{exc}")
            result[file_id] = ""
            error += 1
            continue

        FileDB.update(file_id, db_path=_db, description=desc)
        result[file_id] = desc
        processed += 1
        print(f"[analyze_file_description]   ✓ {file_name}  ({len(desc)} 字符)")

    print(
        f"[analyze_file_description] ✓ 完成："
        f"处理={processed}  跳过={skipped}  失败={error}"
    )
    return result
```

`analyzer/area_analyzer.py` — 追加

```
# ──────────────────────────────────────────────
# Step 15: analyze_area_filelist_brief
# Step 16: analyze_area_description

import time as _time_a
from typing import Optional  

_AREA_MAX_DESC_CHARS = 500
_AREA_MAX_RETRIES    = 5
_AREA_RETRY_DELAYS   = (2, 5, 10, 20, 40)


def _area_retry(fn, label: str = "", max_retries: int = _AREA_MAX_RETRIES):
    last_exc = None
    for i in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if i < max_retries - 1:
                wait = _AREA_RETRY_DELAYS[min(i, len(_AREA_RETRY_DELAYS)-1)]
                print(f"  ↻ 重试{i+1}/{max_retries} ({label})：{exc}，{wait}s 后…")
                _time_a.sleep(wait)
    raise RuntimeError(f"重试 {max_retries} 次失败 ({label})：{last_exc}")


def analyze_area_filelist_brief(
    repo_id: int,
    db_path: Optional[str] = None,
    skip_if_exists: bool = True,
) -> dict[int, list]:
    """
    为仓库内每个 area 的 filelist 生成 brief，
    批量写入 area.filelist 的 brief 字段。

    依赖：file.description 已完成（Step 14）。

    Returns
    -------
    dict[int, list]  {area_id → 更新后的 filelist}
    """
    from llm.client  import chat_completion_json
    from llm.prompts import (
        ANALYZE_AREA_FILELIST_BRIEF_SYSTEM,
        ANALYZE_AREA_FILELIST_BRIEF_USER,
    )
    import json as _j

    _db   = db_path or DB_PATH
    repo  = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_area_filelist_brief] repo_id={repo_id} 不存在。")

    areas = AreaDB.list_by_repo(repo_id, db_path=_db)
    print(
        f"[analyze_area_filelist_brief] 目标仓库：{repo['name']}，"
        f"共 {len(areas)} 个 area"
    )

    result: dict[int, list] = {}
    processed = skipped = error = 0

    for area_rec in areas:
        area_id   = area_rec["id"]
        area_name = area_rec["name"]
        filelist  = area_rec.get("filelist") or []
        if isinstance(filelist, str):
            try:
                filelist = _j.loads(filelist)
            except Exception:
                filelist = []

        if not filelist:
            result[area_id] = []
            skipped += 1
            continue

        if skip_if_exists and all(e.get("brief") for e in filelist):
            result[area_id] = filelist
            skipped += 1
            continue

        # 收集文件描述
        file_lines: list[str] = []
        for entry in filelist:
            fid   = entry.get("file_id")
            fname = entry.get("name", "")
            if fid:
                file_rec = FileDB.get_by_id(fid, db_path=_db)
                raw_desc = (file_rec or {}).get("description", "") or ""
                desc     = raw_desc[:_AREA_MAX_DESC_CHARS]
            else:
                desc = ""
            if not desc:
                desc = f"[文件名] {fname}"
            file_lines.append(f"file_id={fid}  name={fname}\n描述：{desc}\n")

        file_list_text = "\n---\n".join(file_lines)
        user_content   = ANALYZE_AREA_FILELIST_BRIEF_USER.format(
            area_name      = area_name,
            file_count     = len(filelist),
            file_list_text = file_list_text,
        )
        messages = [
            {"role": "system", "content": ANALYZE_AREA_FILELIST_BRIEF_SYSTEM},
            {"role": "user",   "content": user_content},
        ]

        try:
            def _call():
                return chat_completion_json(messages=messages, temperature=0.1)

            raw = _area_retry(_call, label=f"area_id={area_id} {area_name}")
        except Exception as exc:
            print(f"[analyze_area_filelist_brief]   ✗ {area_name}：{exc}")
            result[area_id] = filelist
            error += 1
            continue

        briefs_list = raw.get("briefs", []) if isinstance(raw, dict) else []
        brief_map   = {int(b["file_id"]): b["brief"]
                       for b in briefs_list
                       if isinstance(b, dict) and b.get("file_id") is not None}

        new_filelist = []
        for entry in filelist:
            new_entry = dict(entry)
            fid = entry.get("file_id")
            if fid and fid in brief_map:
                new_entry["brief"] = brief_map[fid]
            new_filelist.append(new_entry)

        AreaDB.update(area_id, db_path=_db, filelist=new_filelist)
        result[area_id] = new_filelist
        processed += 1
        print(
            f"[analyze_area_filelist_brief]   ✓ {area_name}"
            f"  files={len(new_filelist)}  briefs_updated={len(brief_map)}"
        )

    print(
        f"[analyze_area_filelist_brief] ✓ 完成："
        f"处理={processed}  跳过={skipped}  失败={error}"
    )
    return result


def analyze_area_description(
    repo_id: int,
    db_path: Optional[str] = None,
    skip_if_exists: bool = True,
) -> dict[int, str]:
    """
    为仓库内每个 area 生成自然语言描述，写入 area.description。

    依赖：file.description 已完成（Step 14）。

    Returns
    -------
    dict[int, str]  {area_id → description_text}
    """
    from llm.client  import chat_completion
    from llm.prompts import (
        ANALYZE_AREA_DESCRIPTION_SYSTEM,
        ANALYZE_AREA_DESCRIPTION_USER,
    )
    import json as _j

    _db   = db_path or DB_PATH
    repo  = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_area_description] repo_id={repo_id} 不存在。")

    areas = AreaDB.list_by_repo(repo_id, db_path=_db)
    print(
        f"[analyze_area_description] 目标仓库：{repo['name']}，"
        f"共 {len(areas)} 个 area"
    )

    result:   dict[int, str] = {}
    processed = skipped = error = 0

    for area_rec in areas:
        area_id   = area_rec["id"]
        area_name = area_rec["name"]
        area_path = area_rec.get("path", "")
        rationale = area_rec.get("rationale", "")

        if skip_if_exists and area_rec.get("description"):
            result[area_id] = area_rec["description"]
            skipped += 1
            continue

        # 文件结构列表
        filelist = area_rec.get("filelist") or []
        if isinstance(filelist, str):
            try:
                filelist = _j.loads(filelist)
            except Exception:
                filelist = []

        file_structure = "\n".join(
            f"  {e.get('name','')}  {e.get('brief','')}"
            for e in filelist
        ) or "（无文件记录）"

        # 各文件描述
        file_desc_parts: list[str] = []
        for entry in filelist[:30]:
            fid   = entry.get("file_id")
            fname = entry.get("name", "")
            brief = entry.get("brief", "")
            if fid:
                file_rec = FileDB.get_by_id(fid, db_path=_db)
                desc     = (file_rec or {}).get("description", "") or ""
                desc     = desc[:500]
            else:
                desc = brief
            file_desc_parts.append(f"### {fname}\n{desc or brief or '（暂无描述）'}")
        file_descriptions = "\n\n".join(file_desc_parts) or "（无文件描述）"

        user_content = ANALYZE_AREA_DESCRIPTION_USER.format(
            area_name         = area_name,
            area_path         = area_path,
            rationale         = rationale or "（未提供）",
            file_structure    = file_structure,
            file_descriptions = file_descriptions,
        )
        messages = [
            {"role": "system", "content": ANALYZE_AREA_DESCRIPTION_SYSTEM},
            {"role": "user",   "content": user_content},
        ]

        try:
            def _call():
                return chat_completion(messages=messages, temperature=0.2)

            desc = _area_retry(_call, label=f"area_id={area_id} {area_name}")
            desc = desc.strip()
        except Exception as exc:
            print(f"[analyze_area_description]   ✗ {area_name}：{exc}")
            result[area_id] = ""
            error += 1
            continue

        AreaDB.update(area_id, db_path=_db, description=desc)
        result[area_id] = desc
        processed += 1
        print(f"[analyze_area_description]   ✓ {area_name}  ({len(desc)} 字符)")

    print(
        f"[analyze_area_description] ✓ 完成："
        f"处理={processed}  跳过={skipped}  失败={error}"
    )
    return result
```

`analyzer/repo_analyzer.py`（追加）

```
# ── 在文件末尾追加 ────────────────────────────────────────────────
# Step 17: analyze_repo_arealist_brief
# Step 18: analyze_repo_description

import time as _time_r
from typing import Optional 

_REPO_MAX_AREA_DESC  = 600
_REPO_MAX_RETRIES    = 5
_REPO_RETRY_DELAYS   = (2, 5, 10, 20, 40)


def _repo_retry(fn, label: str = "", max_retries: int = _REPO_MAX_RETRIES):
    last_exc = None
    for i in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if i < max_retries - 1:
                wait = _REPO_RETRY_DELAYS[min(i, len(_REPO_RETRY_DELAYS)-1)]
                print(f"  ↻ 重试{i+1}/{max_retries} ({label})：{exc}，{wait}s 后…")
                _time_r.sleep(wait)
    raise RuntimeError(f"重试 {max_retries} 次失败 ({label})：{last_exc}")


def analyze_repo_arealist_brief(
    repo_id: int,
    db_path: str | None = None,
    skip_if_exists: bool = True,
) -> list[dict]:
    """
    为 repo.arealist 中每个 area 生成 brief，写回 repo.arealist。

    依赖：area.description 已完成（Step 16）。

    Returns
    -------
    list[dict]  更新后的 arealist
    """
    from llm.client  import chat_completion_json
    from llm.prompts import (
        ANALYZE_REPO_AREALIST_BRIEF_SYSTEM,
        ANALYZE_REPO_AREALIST_BRIEF_USER,
    )
    import json as _j

    _db  = db_path or DB_PATH
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_repo_arealist_brief] repo_id={repo_id} 不存在。")

    arealist = repo.get("arealist") or []
    if isinstance(arealist, str):
        try:
            arealist = _j.loads(arealist)
        except Exception:
            arealist = []

    if not arealist:
        print("[analyze_repo_arealist_brief] arealist 为空，跳过。")
        return []

    if skip_if_exists and all(e.get("brief") for e in arealist):
        print("[analyze_repo_arealist_brief] 所有 area 已有 brief，跳过。")
        return arealist

    # 收集各 area 描述
    area_lines: list[str] = []
    for entry in arealist:
        aid   = entry.get("area_id")
        aname = entry.get("name", "")
        if aid:
            area_rec = AreaDB.get_by_id(aid, db_path=_db)
            desc     = (area_rec or {}).get("description", "") or ""
            desc     = desc[:_REPO_MAX_AREA_DESC]
        else:
            desc = ""
        if not desc:
            desc = f"[area 名称] {aname}"
        area_lines.append(f"area_id={aid}  name={aname}\n描述：{desc}\n")

    area_list_text = "\n---\n".join(area_lines)
    user_content   = ANALYZE_REPO_AREALIST_BRIEF_USER.format(
        repo_name      = repo["name"],
        area_count     = len(arealist),
        area_list_text = area_list_text,
    )
    messages = [
        {"role": "system", "content": ANALYZE_REPO_AREALIST_BRIEF_SYSTEM},
        {"role": "user",   "content": user_content},
    ]

    try:
        def _call():
            return chat_completion_json(messages=messages, temperature=0.1)

        raw = _repo_retry(_call, label=f"repo={repo['name']} arealist_brief")
    except Exception as exc:
        print(f"[analyze_repo_arealist_brief] ✗ LLM 调用失败：{exc}")
        return arealist

    briefs_list = raw.get("briefs", []) if isinstance(raw, dict) else []
    brief_map   = {int(b["area_id"]): b["brief"]
                   for b in briefs_list
                   if isinstance(b, dict) and b.get("area_id") is not None}

    new_arealist = []
    for entry in arealist:
        new_entry = dict(entry)
        aid = entry.get("area_id")
        if aid and aid in brief_map:
            new_entry["brief"] = brief_map[aid]
        new_arealist.append(new_entry)

    RepoDB.update(repo_id, db_path=_db, arealist=new_arealist)
    print(
        f"[analyze_repo_arealist_brief] ✓ 完成："
        f"areas={len(new_arealist)}  briefs_updated={len(brief_map)}"
    )
    return new_arealist


def analyze_repo_description(
    repo_id: int,
    db_path: str | None = None,
    skip_if_exists: bool = True,
) -> str:
    """
    为仓库生成自然语言描述，写入 repo.description。

    依赖：area.description 已完成（Step 16）。

    Returns
    -------
    str  仓库描述文本
    """
    from llm.client  import chat_completion
    from llm.prompts import (
        ANALYZE_REPO_DESCRIPTION_SYSTEM,
        ANALYZE_REPO_DESCRIPTION_USER,
    )
    import json as _j

    _db  = db_path or DB_PATH
    repo = RepoDB.get_by_id(repo_id, db_path=_db)
    if repo is None:
        raise ValueError(f"[analyze_repo_description] repo_id={repo_id} 不存在。")

    if skip_if_exists and repo.get("description"):
        print(
            f"[analyze_repo_description] '{repo['name']}' 已有描述，跳过。"
        )
        return repo["description"]

    repo_path = repo["path"]
    repo_name = repo["name"]

    # 语言信息
    language_info = repo.get("language") or {}
    if isinstance(language_info, str):
        try:
            language_info = _j.loads(language_info)
        except Exception:
            language_info = {}
    main_language  = language_info.get("main", "Unknown")
    lang_stats_raw = language_info.get("stats", [])
    language_stats = "，".join(
        f"{s['lang']} {s['pct']}%" for s in lang_stats_raw[:6]
    )

    # 目录树
    dir_tree = _build_dir_tree(repo_path, max_depth=3)

    # README
    readme_content = _read_readme(repo_path)

    # area 结构 + 描述
    areas      = AreaDB.list_by_repo(repo_id, db_path=_db)
    arealist   = repo.get("arealist") or []
    if isinstance(arealist, str):
        try:
            arealist = _j.loads(arealist)
        except Exception:
            arealist = []

    brief_map  = {e.get("area_id"): e.get("brief", "") for e in arealist}

    area_structure_lines: list[str] = []
    area_desc_parts:      list[str] = []

    for area in areas:
        aid   = area["id"]
        aname = area["name"]
        apath = area["path"]
        brief = brief_map.get(aid, "")
        area_structure_lines.append(f"  [{aname}]  path={apath}  {brief}")

        desc = area.get("description", "") or ""
        area_desc_parts.append(
            f"### {aname}（{apath}）\n{desc[:_REPO_MAX_AREA_DESC] or '（暂无描述）'}"
        )

    area_structure  = "\n".join(area_structure_lines) or "（无 area 记录）"
    area_descriptions = "\n\n".join(area_desc_parts) or "（无 area 描述）"

    user_content = ANALYZE_REPO_DESCRIPTION_USER.format(
        repo_name         = repo_name,
        main_language     = main_language,
        language_stats    = language_stats or "（未知）",
        dir_tree          = dir_tree,
        area_structure    = area_structure,
        readme_content    = readme_content,
        area_descriptions = area_descriptions,
    )
    messages = [
        {"role": "system", "content": ANALYZE_REPO_DESCRIPTION_SYSTEM},
        {"role": "user",   "content": user_content},
    ]

    try:
        def _call():
            return chat_completion(messages=messages, temperature=0.2)

        desc = _repo_retry(_call, label=f"repo={repo_name} description")
        desc = desc.strip()
    except Exception as exc:
        print(f"[analyze_repo_description] ✗ LLM 调用失败：{exc}")
        return ""

    RepoDB.update(repo_id, db_path=_db, description=desc)
    print(f"[analyze_repo_description] ✓ 完成：{len(desc)} 字符")
    return desc
```

`main.py`

```
"""
main.py
CodeMAP 主流程入口 —— build_codemap

将 Step 1-18 完整串联，从仓库路径构建完整的结构化代码知识库。

算法步骤对应关系
────────────────────────────────────────────────────────────────────
  Step  1 : init_repo
  Step  2 : analyze_repo_language
  Step  3 : analyze_repo_area                        [LLM]
  Step  4 : analyze_area_file
  Step  5 : analyze_file_language
  Step  6 : analyze_file_func
  Step  7 : build_callgraph
  Step  8 : analyze_func_callgraph
  Step  9 : analyze_func_precondition                [SA+LLM，与10/11并行]
  Step 10 : analyze_func_postcondition               [SA+LLM，与9/11并行]
  Step 11 : analyze_func_exception                   [SA+LLM，与9/10并行]
  Step 12 : analyze_func_description                 [Agent，多函数并行]
  Step 13 : analyze_file_funclist_brief              [LLM batch]
  Step 14 : analyze_file_description                 [LLM]
  Step 15 : analyze_area_filelist_brief              [LLM batch]
  Step 16 : analyze_area_description                 [LLM]
  Step 17 : analyze_repo_arealist_brief              [LLM batch]
  Step 18 : analyze_repo_description                 [LLM]
  Step 19 : build_codemap  ← 本文件（串联 1-18）

命令行用法
──────────────────────────────────────────────────────────────────────
  # 首次全量分析（使用默认数据库路径）
  python main.py /path/to/repo

  # 强制重建（清空同名仓库旧数据后重建）
  python main.py /path/to/repo --force

  # 断点续建：从 Step 12 开始（跳过已完成的 1-11）
  python main.py /path/to/repo --step 12

  # 指定仓库名和数据库路径
  python main.py /path/to/repo --repo-name my_project --db-path ./my.db

  # 只分析 C/C++ 函数（大幅减少 LLM 分析量）
  python main.py /path/to/repo --languages C C++

  # 只做结构化分析，跳过描述生成（Step 12-18）
  python main.py /path/to/repo --no-desc

  # API 限速时降低并发度
  python main.py /path/to/repo --workers-step9-11 1 --workers-step12 3
"""

import argparse
import logging
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

# ── 路径设置 ─────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from config import DB_PATH, DATA_DIR
from db.dao import init_db, RepoDB, FuncDB, FileDB

from analyzer.repo_analyzer import (
    init_repo,
    analyze_repo_language,
    analyze_repo_area,
    analyze_repo_arealist_brief,
    analyze_repo_description,
)
from analyzer.area_analyzer import (
    analyze_area_file,
    analyze_area_filelist_brief,
    analyze_area_description,
)
from analyzer.file_analyzer import (
    analyze_file_language,
    analyze_file_func,
    analyze_file_funclist_brief,
    analyze_file_description,
)
from analyzer.callgraph_builder import build_callgraph, analyze_func_callgraph
from analyzer.func_analyzer import (
    analyze_func_precondition,
    analyze_func_postcondition,
    analyze_func_exception,
    analyze_func_description,
)


# ==================================================================
# 日志配置
# ==================================================================

def _make_logger(
    log_dir: Optional[str] = None,
) -> tuple[logging.Logger, str]:
    """
    创建构建日志器，同时输出到控制台（INFO）和日志文件（DEBUG）。

    Returns
    -------
    (logger, log_file_path)
    """
    _log_dir = log_dir or os.path.join(_HERE, 'logs')
    os.makedirs(_log_dir, exist_ok=True)

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(_log_dir, f'codemap_{ts}.log')

    # 使用时间戳命名避免多次调用时 handler 重叠
    logger = logging.getLogger(f'codemap_{ts}')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s  %(levelname)-7s  %(message)s',
        datefmt='%H:%M:%S',
    ))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        '%(asctime)s  %(message)s',
        datefmt='%H:%M:%S',
    ))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger, log_file


# ==================================================================
# 工具函数
# ==================================================================

def _enable_wal(db_path: str, logger: logging.Logger) -> None:
    """
    开启 SQLite WAL（Write-Ahead Logging）模式。

    Step 9-11 三路线程并发写入同一数据库时，
    WAL 模式下 SQLite 内部串行化写操作，防止 SQLITE_BUSY 冲突。
    """
    try:
        with sqlite3.connect(db_path) as conn:
            mode = conn.execute('PRAGMA journal_mode=WAL').fetchone()[0]
            conn.execute('PRAGMA synchronous=NORMAL')
        logger.debug(f'[WAL] journal_mode = {mode}')
    except Exception as e:
        logger.warning(f'[WAL] 开启失败（不影响功能）：{e}')


class _Timer:
    """计时上下文管理器：打印步骤标签、开始/结束及耗时。"""

    def __init__(self, label: str, logger: logging.Logger):
        self._label  = label
        self._t0     = 0.0
        self._logger = logger

    def __enter__(self):
        self._t0 = time.time()
        self._logger.info(f'▶ {self._label}')
        return self

    def __exit__(self, exc_type, *_):
        elapsed    = time.time() - self._t0
        mins, secs = divmod(int(elapsed), 60)
        duration   = f'{mins}m {secs}s' if mins else f'{secs}s'
        icon       = '✓' if exc_type is None else '✗'
        self._logger.info(f'◀ {icon} {self._label}  耗时 {duration}')


def _find_repo_id(
    repo_name: str,
    repo_path: str,
    db_path: str,
) -> Optional[int]:
    """
    断点续建时，从数据库中定位已有仓库记录 ID。
    先按名称精确匹配，再按绝对路径兜底。
    """
    rec = RepoDB.get_by_name(repo_name, db_path=db_path)
    if rec:
        return rec['id']

    abs_path  = os.path.abspath(repo_path)
    all_repos = RepoDB.list_all(db_path=db_path)
    for r in all_repos:
        if os.path.abspath(r.get('path', '')) == abs_path:
            return r['id']

    return None


def _get_func_ids_for_analysis(
    repo_id:   int,
    db_path:   str,
    languages: Optional[list[str]],
    logger:    logging.Logger,
) -> list[int]:
    """
    获取待分析的函数 ID 列表（按语言过滤 + 按调用丰富度排序）。

    排序策略：有 callee 的函数（调用链更丰富）优先，其余追加其后。
    此排序使信息量更大的函数先被 LLM 分析，产出质量更高的描述。
    """
    all_files     = FileDB.list_by_repo(repo_id, db_path=db_path)
    lang_set      = set(languages) if languages else None

    target_fids   = {
        f['id'] for f in all_files
        if lang_set is None or f.get('language') in lang_set
    }

    all_funcs     = FuncDB.list_by_repo(repo_id, db_path=db_path)
    target_funcs  = [f for f in all_funcs if f.get('file_id') in target_fids]

    with_callee   = [
        f for f in target_funcs
        if isinstance(f.get('callgraph'), dict)
        and f['callgraph'].get('callees')
    ]
    wc_ids = {f['id'] for f in with_callee}
    without_callee = [f for f in target_funcs if f['id'] not in wc_ids]

    ids = [f['id'] for f in with_callee + without_callee]
    logger.info(
        f'  [func_ids] 待分析函数：{len(ids)} 个'
        f'（有 callee={len(with_callee)}，无 callee={len(without_callee)}）'
        f'  语言过滤：{lang_set or "无"}'
    )
    return ids


def _run_steps_9_11_parallel(
    repo_id:        int,
    db_path:        str,
    func_ids:       list[int],
    skip_if_exists: bool,
    max_workers:    int,
    logger:         logging.Logger,
) -> tuple[dict, dict, dict]:
    """
    Steps 9-11 三路并行：precondition / postcondition / exception。

    并行安全性说明
    ──────────────
    三个分析分别写入 func.precondition / func.postcondition /
    func.exception 三个独立字段，无行级写-写冲突。WAL 模式确保
    SQLite 内部串行化多线程写，无需额外加锁。
    理论加速比 ≈ ×3（取决于 LLM API 端并发限制）。

    断点续建
    ────────
    skip_if_exists=True 时，每个分析函数内部自动跳过已有数据的函数，
    中断后重新执行不会重复调用 LLM。
    """
    task_defs = [
        ('precondition',  analyze_func_precondition),
        ('postcondition', analyze_func_postcondition),
        ('exception',     analyze_func_exception),
    ]
    results: dict[str, dict] = {}
    t0 = time.time()

    actual_workers = min(max_workers, 3)
    logger.info(
        f'  Step 9-11 三路并行启动'
        f'（workers={actual_workers}，函数={len(func_ids)} 个）'
    )

    with ThreadPoolExecutor(
        max_workers    = actual_workers,
        thread_name_prefix = 'step9-11',
    ) as pool:
        future_to_name = {
            pool.submit(
                fn,
                repo_id,
                db_path        = db_path,
                func_ids       = func_ids,
                skip_if_exists = skip_if_exists,
            ): name
            for name, fn in task_defs
        }

        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                r        = future.result()
                nonempty = sum(1 for v in r.values() if v)
                results[name] = r
                logger.info(
                    f'  ✓ {name:<15s}  写库={len(r)}'
                    f'  有数据={nonempty}/{len(r)}'
                    f'  耗时={time.time() - t0:.0f}s'
                )
            except Exception as exc:
                logger.error(f'  ✗ {name} 发生异常：{exc}', exc_info=True)
                results[name] = {}

    logger.info(f'  Steps 9-11 全部完成，总耗时 {time.time() - t0:.1f}s')
    return (
        results.get('precondition',  {}),
        results.get('postcondition', {}),
        results.get('exception',     {}),
    )


# ==================================================================
# build_codemap —— 核心主流程（Step 19）
# ==================================================================

def build_codemap(
    repo_path: str,
    repo_name: Optional[str] = None,
    db_path: Optional[str] = None,
    force: bool = False,
    start_step: int = 1,
    languages: Optional[list[str]] = None,
    skip_if_exists: bool = True,
    max_step9_11_workers: int = 3,
    max_step12_workers: int = 10,
    no_desc: bool = False,
    log_dir: Optional[str] = None,
) -> dict:
    """
    CodeMAP 主构建流程（Step 19）：将 Step 1-18 完整串联，
    从仓库路径生成完整的结构化代码知识库。

    Parameters
    ----------
    repo_path : str
        仓库本地路径（绝对或相对均可，内部统一转为绝对路径）。
    repo_name : str | None
        仓库名称；不传则取路径末尾目录名。
    db_path : str | None
        SQLite 数据库路径；不传则使用 config.DB_PATH。
    force : bool
        True  = 对结构性步骤（Step 1/3/4/6/7）强制清空旧数据后重建；
                注意：数据库文件本身不会被删除，只删除该仓库的记录。
        False = 增量模式，各步骤已有数据自动跳过。
    start_step : int
        从第几步开始执行（1-18），用于断点续建。
        注意：start_step > 1 时数据库中必须已存在该仓库的记录。
    languages : list[str] | None
        Step 6/9-12 函数分析的语言白名单；None 表示处理全部语言。
        示例：['C', 'C++'] 可显著减少 LLM 分析量。
    skip_if_exists : bool
        True  = 已有数据的函数/文件自动跳过（增量处理，推荐，默认）；
        False = 强制重新分析所有实体（覆盖写入，用于数据质量更新）。
    max_step9_11_workers : int
        Steps 9-11 的并行线程数（最大 3），默认 3。
        遇 API 限速错误时可降为 2 或 1。
    max_step12_workers : int
        Step 12 函数描述生成的并发数，默认 10。
    no_desc : bool
        True = 跳过 Step 12-18 的所有 LLM 描述生成步骤，
               仅完成结构化分析（Steps 1-11）。
    log_dir : str | None
        日志输出目录；不传则使用 <project_root>/logs/。

    Returns
    -------
    dict
        构建结果摘要，字段包括：
        {
            'repo_id':       int,
            'repo_name':     str,
            'db_path':       str,
            'log_file':      str,
            'total_elapsed': float,    # 总耗时（秒）
            'step1':  {...},           # 各步骤简要统计
            'step2':  {...},
            ...
            'step18': {...},
        }

    Raises
    ------
    FileNotFoundError
        repo_path 不存在或不是目录。
    ValueError
        · start_step 超出范围 [1, 18]
        · start_step > 1 但数据库中找不到对应仓库记录
    """
    # ── 参数校验与路径规范化 ──────────────────────────────────────────────────
    abs_repo_path = os.path.abspath(repo_path)
    if not os.path.isdir(abs_repo_path):
        raise FileNotFoundError(
            f'[build_codemap] 仓库路径不存在或不是目录：{abs_repo_path}'
        )
    if not (1 <= start_step <= 18):
        raise ValueError(
            f'[build_codemap] start_step={start_step} 超出有效范围 [1, 18]。'
        )

    _db    = db_path or DB_PATH
    _name  = repo_name or os.path.basename(abs_repo_path.rstrip(os.sep))
    summary: dict = {}

    # ── 日志初始化 ───────────────────────────────────────────────────────────
    _log, log_file = _make_logger(log_dir)

    _log.info('=' * 70)
    _log.info('CodeMAP 构建开始')
    _log.info(f'  仓库路径            : {abs_repo_path}')
    _log.info(f'  仓库名称            : {_name}')
    _log.info(f'  数据库              : {_db}')
    _log.info(f'  日志文件            : {log_file}')
    _log.info(f'  force               : {force}')
    _log.info(f'  start_step          : {start_step}')
    _log.info(f'  languages           : {languages or "（全部语言）"}')
    _log.info(f'  skip_if_exists      : {skip_if_exists}')
    _log.info(f'  no_desc             : {no_desc}')
    _log.info(f'  max_step9-11_workers: {max_step9_11_workers}')
    _log.info(f'  max_step12_workers  : {max_step12_workers}')
    _log.info('=' * 70)

    total_t0 = time.time()

    # ── 数据库初始化 ──────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(_db)), exist_ok=True)
    init_db(_db)
    _enable_wal(_db, _log)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1 : init_repo
    # ─────────────────────────────────────────────────────────────────────────
    repo_id: Optional[int] = None

    if start_step <= 1:
        with _Timer('Step 1   init_repo', _log):
            repo_id = init_repo(
                repo_path = abs_repo_path,
                repo_name = _name,
                db_path   = _db,
                force     = force,
            )
        _log.info(f'  repo_id = {repo_id}')
        summary['step1'] = {'repo_id': repo_id}

    else:
        # 断点续建：从数据库中找已有记录
        repo_id = _find_repo_id(_name, abs_repo_path, _db)
        if repo_id is None:
            raise ValueError(
                f'[build_codemap] 指定 start_step={start_step}（跳过 Step 1）'
                f"，但数据库中找不到仓库 '{_name}'。\n"
                "请先完整执行 Step 1（去掉 --step 参数或指定 --step 1）。"
            )
        _log.info(
            f'Step 1 跳过（start_step={start_step}），'
            f"已有 repo_id={repo_id}（'{_name}'）"
        )
        summary['step1'] = {'repo_id': repo_id, 'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2 : analyze_repo_language
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 2:
        with _Timer('Step 2   analyze_repo_language', _log):
            lang_r = analyze_repo_language(repo_id, db_path=_db)
        main_lang = lang_r.get('main', 'Unknown')
        _log.info(f'  主语言 : {main_lang}')
        summary['step2'] = {'main_language': main_lang}
    else:
        _log.info(f'Step 2 跳过（start_step={start_step}）')
        summary['step2'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3 : analyze_repo_area  [LLM]
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 3:
        with _Timer('Step 3   analyze_repo_area  [LLM]', _log):
            area_r = analyze_repo_area(
                repo_id,
                db_path = _db,
                force   = force,
            )
        _log.info(f'  area 数 : {len(area_r)}')
        summary['step3'] = {'area_count': len(area_r)}
    else:
        _log.info(f'Step 3 跳过（start_step={start_step}）')
        summary['step3'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4 : analyze_area_file
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 4:
        with _Timer('Step 4   analyze_area_file', _log):
            file_r = analyze_area_file(
                repo_id,
                db_path = _db,
                force   = force,
            )
        total_files = sum(len(v) for v in file_r.values())
        _log.info(f'  文件总数 : {total_files}')
        summary['step4'] = {'file_count': total_files}
    else:
        _log.info(f'Step 4 跳过（start_step={start_step}）')
        summary['step4'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5 : analyze_file_language
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 5:
        with _Timer('Step 5   analyze_file_language', _log):
            lang_map = analyze_file_language(repo_id, db_path=_db)
        _log.info(f'  检测文件数 : {len(lang_map)}')
        summary['step5'] = {'detected_files': len(lang_map)}
    else:
        _log.info(f'Step 5 跳过（start_step={start_step}）')
        summary['step5'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6 : analyze_file_func
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 6:
        with _Timer('Step 6   analyze_file_func', _log):
            func_r = analyze_file_func(
                repo_id,
                db_path   = _db,
                force     = force,
                languages = languages,
            )
        total_funcs = sum(len(v) for v in func_r.values())
        _log.info(f'  函数总数 : {total_funcs}')
        summary['step6'] = {'func_count': total_funcs}
    else:
        _log.info(f'Step 6 跳过（start_step={start_step}）')
        summary['step6'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7 : build_callgraph
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 7:
        with _Timer('Step 7   build_callgraph', _log):
            cg_path = build_callgraph(
                repo_id,
                db_path = _db,
                force   = force,
            )
        _log.info(f'  调用图文件 : {cg_path}')
        summary['step7'] = {'callgraph_path': cg_path}
    else:
        # 自动定位已有调用图（analyze_func_callgraph 支持 callgraph_path=None 自动查找）
        repo_rec = RepoDB.get_by_id(repo_id, db_path=_db)
        cg_path  = os.path.join(
            DATA_DIR, 'callgraph',
            f"{repo_rec['name']}_callgraph.json" if repo_rec else '',
        )
        _log.info(
            f'Step 7 跳过（start_step={start_step}），'
            f'缓存文件：{cg_path}'
        )
        summary['step7'] = {'skipped': True, 'callgraph_path': cg_path}

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8 : analyze_func_callgraph
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 8:
        with _Timer('Step 8   analyze_func_callgraph', _log):
            cg_r = analyze_func_callgraph(
                repo_id,
                db_path        = _db,
                # cg_path 存在时传入精确路径；否则传 None 让函数自动定位
                callgraph_path = cg_path if os.path.isfile(cg_path) else None,
            )
        _log.info(f'  callgraph 写库 : {len(cg_r)} 个函数')
        summary['step8'] = {'func_count': len(cg_r)}
    else:
        _log.info(f'Step 8 跳过（start_step={start_step}）')
        summary['step8'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────────
    # Steps 9-11 : precondition / postcondition / exception  [SA+LLM，三路并行]
    # ─────────────────────────────────────────────────────────────────────────
    if start_step <= 11:
        func_ids = _get_func_ids_for_analysis(repo_id, _db, languages, _log)

        with _Timer(
            f'Steps 9-11  precondition / postcondition / exception'
            f'  [SA+LLM × {min(max_step9_11_workers, 3)} 并行]',
            _log,
        ):
            pre, post, exc = _run_steps_9_11_parallel(
                repo_id        = repo_id,
                db_path        = _db,
                func_ids       = func_ids,
                skip_if_exists = skip_if_exists,
                max_workers    = max_step9_11_workers,
                logger         = _log,
            )

        def _ne(d: dict) -> int:
            return sum(1 for v in d.values() if v)

        summary['step9']  = {'total': len(pre),  'nonempty': _ne(pre)}
        summary['step10'] = {'total': len(post), 'nonempty': _ne(post)}
        summary['step11'] = {'total': len(exc),  'nonempty': _ne(exc)}
        _log.info(
            f'  precondition  : {_ne(pre)}/{len(pre)} 个函数有数据\n'
            f'  postcondition : {_ne(post)}/{len(post)} 个函数有数据\n'
            f'  exception     : {_ne(exc)}/{len(exc)} 个函数有数据'
        )
    else:
        _log.info(f'Steps 9-11 跳过（start_step={start_step}）')
        summary['step9'] = summary['step10'] = summary['step11'] = {
            'skipped': True
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Steps 12-18 : 描述生成阶段（可用 --no-desc 整体跳过）
    # ─────────────────────────────────────────────────────────────────────────
    if no_desc:
        _log.info('')
        _log.info('--no-desc 标志已设置，跳过 Step 12-18 的所有描述生成步骤。')
        for s in range(12, 19):
            summary[f'step{s}'] = {'skipped': True, 'reason': 'no_desc'}

    else:
        # ── Step 12 : analyze_func_description  [Agent，多函数并行] ──────────
        if start_step <= 12:
            with _Timer(
                f'Step 12  analyze_func_description'
                f'  [Agent × {max_step12_workers} 并行]',
                _log,
            ):
                desc_r = analyze_func_description(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                    languages      = languages,
                    max_workers    = max_step12_workers,
                )
            ne = sum(1 for v in desc_r.values() if v)
            _log.info(f'  函数描述生成 : {ne}/{len(desc_r)}')
            summary['step12'] = {'total': len(desc_r), 'nonempty': ne}
        else:
            _log.info(f'Step 12 跳过（start_step={start_step}）')
            summary['step12'] = {'skipped': True}

        # ── Step 13 : analyze_file_funclist_brief  [LLM batch] ───────────────
        if start_step <= 13:
            with _Timer('Step 13  analyze_file_funclist_brief', _log):
                fl_brief = analyze_file_funclist_brief(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            _log.info(f'  处理文件数 : {len(fl_brief)}')
            summary['step13'] = {'file_count': len(fl_brief)}
        else:
            _log.info(f'Step 13 跳过（start_step={start_step}）')
            summary['step13'] = {'skipped': True}

        # ── Step 14 : analyze_file_description  [LLM] ────────────────────────
        if start_step <= 14:
            with _Timer('Step 14  analyze_file_description', _log):
                file_desc = analyze_file_description(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            ne = sum(1 for v in file_desc.values() if v)
            _log.info(f'  文件描述生成 : {ne}/{len(file_desc)}')
            summary['step14'] = {'total': len(file_desc), 'nonempty': ne}
        else:
            _log.info(f'Step 14 跳过（start_step={start_step}）')
            summary['step14'] = {'skipped': True}

        # ── Step 15 : analyze_area_filelist_brief  [LLM batch] ───────────────
        if start_step <= 15:
            with _Timer('Step 15  analyze_area_filelist_brief', _log):
                al_brief = analyze_area_filelist_brief(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            _log.info(f'  处理 area 数 : {len(al_brief)}')
            summary['step15'] = {'area_count': len(al_brief)}
        else:
            _log.info(f'Step 15 跳过（start_step={start_step}）')
            summary['step15'] = {'skipped': True}

        # ── Step 16 : analyze_area_description  [LLM] ────────────────────────
        if start_step <= 16:
            with _Timer('Step 16  analyze_area_description', _log):
                area_desc = analyze_area_description(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            ne = sum(1 for v in area_desc.values() if v)
            _log.info(f'  area 描述生成 : {ne}/{len(area_desc)}')
            summary['step16'] = {'total': len(area_desc), 'nonempty': ne}
        else:
            _log.info(f'Step 16 跳过（start_step={start_step}）')
            summary['step16'] = {'skipped': True}

        # ── Step 17 : analyze_repo_arealist_brief  [LLM batch] ───────────────
        if start_step <= 17:
            with _Timer('Step 17  analyze_repo_arealist_brief', _log):
                arealist = analyze_repo_arealist_brief(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            _log.info(f'  arealist 条目 : {len(arealist)} 个')
            summary['step17'] = {'area_count': len(arealist)}
        else:
            _log.info(f'Step 17 跳过（start_step={start_step}）')
            summary['step17'] = {'skipped': True}

        # ── Step 18 : analyze_repo_description  [LLM] ────────────────────────
        if start_step <= 18:
            with _Timer('Step 18  analyze_repo_description', _log):
                repo_desc = analyze_repo_description(
                    repo_id        = repo_id,
                    db_path        = _db,
                    skip_if_exists = skip_if_exists,
                )
            _log.info(f'  仓库描述 : {len(repo_desc)} 字符')
            summary['step18'] = {'desc_chars': len(repo_desc)}
        else:
            _log.info(f'Step 18 跳过（start_step={start_step}）')
            summary['step18'] = {'skipped': True}

    # ── 汇总报告 ─────────────────────────────────────────────────────────────
    total_elapsed = time.time() - total_t0
    mins, secs    = divmod(int(total_elapsed), 60)

    _STEP_LABELS = {
        1:  'init_repo',
        2:  'analyze_repo_language',
        3:  'analyze_repo_area',
        4:  'analyze_area_file',
        5:  'analyze_file_language',
        6:  'analyze_file_func',
        7:  'build_callgraph',
        8:  'analyze_func_callgraph',
        9:  'analyze_func_precondition',
        10: 'analyze_func_postcondition',
        11: 'analyze_func_exception',
        12: 'analyze_func_description',
        13: 'analyze_file_funclist_brief',
        14: 'analyze_file_description',
        15: 'analyze_area_filelist_brief',
        16: 'analyze_area_description',
        17: 'analyze_repo_arealist_brief',
        18: 'analyze_repo_description',
    }

    _log.info('')
    _log.info('=' * 70)
    _log.info('CodeMAP 构建完成  ✓')
    _log.info(f'  仓库    : {_name}  (repo_id={repo_id})')
    _log.info(f'  数据库  : {_db}')
    _log.info(f'  日志    : {log_file}')
    _log.info(f'  总耗时  : {mins}m {secs}s  ({total_elapsed:.0f}s)')
    _log.info('  ─── 各步骤结果摘要 ─────────────────────────────────────')

    for num, label in _STEP_LABELS.items():
        info = summary.get(f'step{num}', {})
        if info.get('skipped'):
            reason = info.get('reason', '')
            status = f'[跳过{" - " + reason if reason else ""}]'
        else:
            # 过滤掉路径等冗长字段，只展示数值统计
            parts = [
                f'{k}={v}'
                for k, v in info.items()
                if k not in ('skipped', 'reason', 'callgraph_path')
                and v is not None
            ]
            status = '  '.join(parts) if parts else '✓'
        _log.info(f'  Step {num:2d}  {label:<35s}  {status}')

    _log.info('=' * 70)

    # 将元信息写回 summary 供调用方使用
    summary.update({
        'repo_id':       repo_id,
        'repo_name':     _name,
        'db_path':       _db,
        'log_file':      log_file,
        'total_elapsed': total_elapsed,
    })

    return summary


# ==================================================================
# 命令行入口
# ==================================================================

def main() -> None:
    """命令行入口：解析参数后调用 build_codemap。"""

    parser = argparse.ArgumentParser(
        prog            = 'codemap',
        description     = 'CodeMAP —— 代码仓库结构化知识库构建工具（Step 1-18 全流程）',
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog          = """
使用示例：
  # 首次全量分析（使用默认数据库）
  python main.py /path/to/repo

  # 强制重建：清空同名仓库旧数据后重新分析
  python main.py /path/to/repo --force

  # 断点续建：从 Step 12 继续（已完成 Step 1-11）
  python main.py /path/to/repo --step 12

  # 指定仓库名称和数据库路径
  python main.py /path/to/repo --repo-name my_project --db-path ./my.db

  # 只分析 C/C++ 函数，跳过其他语言（大幅缩短 LLM 分析时间）
  python main.py /path/to/repo --languages C C++

  # 只做结构化分析，跳过 Step 12-18 的描述生成
  python main.py /path/to/repo --no-desc

  # API 限速时降低并发度
  python main.py /path/to/repo --workers-step9-11 1 --workers-step12 3

  # 强制重新分析所有实体（覆盖已有数据）
  python main.py /path/to/repo --step 9 --no-skip --languages C
        """.strip(),
    )

    parser.add_argument(
        'repo_path',
        help = '要分析的代码仓库本地路径（绝对或相对路径均可）',
    )
    parser.add_argument(
        '--repo-name', '-n',
        dest    = 'repo_name',
        default = None,
        metavar = 'NAME',
        help    = '仓库名称（默认：取路径末尾目录名）',
    )
    parser.add_argument(
        '--db-path', '-d',
        dest    = 'db_path',
        default = None,
        metavar = 'PATH',
        help    = f'SQLite 数据库路径（默认：{DB_PATH}）',
    )
    parser.add_argument(
        '--force', '-f',
        action  = 'store_true',
        default = False,
        help    = (
            '强制重建：删除同名仓库旧数据后重新分析'
            '（数据库文件本身保留，只清除该仓库的记录）'
        ),
    )
    parser.add_argument(
        '--step', '-s',
        type    = int,
        default = 1,
        choices = range(1, 19),
        metavar = 'N',
        help    = '从第 N 步开始执行（1-18，默认 1），用于断点续建',
    )
    parser.add_argument(
        '--languages', '-l',
        nargs   = '+',
        default = None,
        metavar = 'LANG',
        help    = (
            'Step 6/9-12 函数分析的语言白名单（如 C C++）；'
            '不传则处理全部语言'
        ),
    )
    parser.add_argument(
        '--no-desc',
        action  = 'store_true',
        default = False,
        help    = '跳过 Step 12-18 的所有描述生成步骤，只完成结构化分析（Step 1-11）',
    )
    parser.add_argument(
        '--no-skip',
        action  = 'store_true',
        default = False,
        help    = '禁用增量跳过：对所有实体重新分析（即使 DB 中已有数据）',
    )
    parser.add_argument(
        '--workers-step9-11',
        type    = int,
        default = 3,
        metavar = 'N',
        help    = (
            'Steps 9-11 并行度（最大 3，默认 3）；'
            'API 限速时可降为 2 或 1'
        ),
    )
    parser.add_argument(
        '--workers-step12',
        type    = int,
        default = 10,
        metavar = 'N',
        help    = 'Step 12 并发函数描述生成数（默认 10）',
    )
    parser.add_argument(
        '--log-dir',
        dest    = 'log_dir',
        default = None,
        metavar = 'DIR',
        help    = f'日志输出目录（默认：<project_root>/logs/）',
    )

    args = parser.parse_args()

    try:
        build_codemap(
            repo_path            = args.repo_path,
            repo_name            = args.repo_name,
            db_path              = args.db_path,
            force                = args.force,
            start_step           = args.step,
            languages            = args.languages,
            skip_if_exists       = not args.no_skip,
            max_step9_11_workers = args.workers_step9_11,
            max_step12_workers   = args.workers_step12,
            no_desc              = args.no_desc,
            log_dir              = args.log_dir,
        )
        sys.exit(0)

    except FileNotFoundError as e:
        print(f'[错误] {e}', file=sys.stderr)
        sys.exit(1)

    except ValueError as e:
        print(f'[错误] {e}', file=sys.stderr)
        sys.exit(2)

    except KeyboardInterrupt:
        print(
            '\n[中断] 用户中断构建。'
            '已完成的数据已持久化到数据库，'
            '下次可使用 --step N 从断点续建。',
            file=sys.stderr,
        )
        sys.exit(130)

    except Exception as e:
        print(f'[未知错误] {e}', file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)


if __name__ == '__main__':
    main()
```

