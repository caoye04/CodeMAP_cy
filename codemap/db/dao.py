# 数据库增删改查统一封装
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