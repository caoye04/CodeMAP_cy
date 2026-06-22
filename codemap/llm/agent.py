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
        language      = func_rec.get("_language", "C"),   # 主要针对 C/C++ 仓库；调用方可通过 func_rec 传入
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