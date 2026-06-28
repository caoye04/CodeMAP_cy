"""
llm/prompts.py
所有 LLM Prompt 模板集中管理。

命名规范：
  <STEP>_SYSTEM  —— system 消息（固定文本）
  <STEP>_USER    —— user 消息模板（含 {placeholder}）
"""

# ==================================================================
#  Step 3: analyze_repo_group —— 仓库模块划分
# ==================================================================

ANALYZE_REPO_AREA_SYSTEM = """\
你是一位资深软件架构师，擅长分析代码仓库结构并识别逻辑模块边界。

## 任务
根据给定的仓库目录结构和背景信息，将仓库划分为若干个逻辑 "group"（功能区域/模块），\
每个 group 代表一个内聚的功能单元。

## Group 概念说明
- 一个 group 通常对应一个独立的目录，但根目录下的核心散落文件也可构成一个 group
- 粒度适中：3-12 个 group 为宜（小型库偏少，大型单体仓库可更多）
- 每个 group 应具有明确、独立的职责，与其他 group 低耦合

## 严格输出要求
只输出合法 JSON，结构如下，不得包含任何额外解释文字：
```json
{
  "groups": [
    {
      "name":      "group 的英文短名称（snake_case，如 core_compression）",
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
若仓库根目录本身包含大量核心代码（无明显子目录分层），可将 "." 作为一个 group
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

请根据以上信息完成 group 划分，输出符合要求的 JSON。
"""


# ==================================================================
#  Step 7: analyze_func_all —— 前置条件 + 后置条件 + 异常处理 + 描述（单次调用）
# ==================================================================

ANALYZE_FUNC_SUMMARY_SYSTEM = """\
你是代码分析专家。分析给定函数，返回如下结构的 JSON，只输出 JSON，不含任何说明文字：

{
  "precondition":  ["调用该函数前需满足的条件，每项一句话，3-6条"],
  "postcondition": ["函数成功执行后的保证或副作用，每项一句话，3-6条"],
  "exception":     ["错误处理与异常情况，每项一句话，2-5条"],
  "description":   "该函数的简洁功能描述（2-4句，说明核心功能与关键逻辑）"
}

无内容的字段返回空列表 [] 或空字符串。
"""

ANALYZE_FUNC_SUMMARY_USER = """\
函数名：{func_name}　语言：{language}
签名：`{signature}`
参数：{params}　
返回类型：{return_type}

静态分析提取的信息（仅供参考）：
{sa_results}

函数源码：
```
{source_code}
```
"""

# ==================================================================
#  Step 8a: analyze_file_funclist_brief —— 函数 brief 批量生成
# ==================================================================

ANALYZE_FILE_FUNCLIST_BRIEF_SYSTEM = """\
为每个函数生成一句话的 brief（不超过30字）。
只输出 JSON，格式：{"briefs": [{"func_id": 1, "brief": "..."}, ...]}
"""

ANALYZE_FILE_FUNCLIST_BRIEF_USER = """\
文件：{file_name}，请为以下 {func_count} 个函数各生成一条 brief：

{func_list_text}
"""

# ==================================================================
#  Step 8b: analyze_file_description —— 文件描述
# ==================================================================

ANALYZE_FILE_DESCRIPTION_SYSTEM = """\
为给定的代码文件生成简洁的自然语言描述（100-200字）。
说明文件的核心功能、在模块中的定位，以及主要提供了哪些能力。
"""

ANALYZE_FILE_DESCRIPTION_USER = """\
文件：{file_name}（{language}）
所在模块：{group_name}（路径：{group_path}）
文件路径：{file_path}
所在 Group 文件结构:{group_file_structure}
函数列表与描述：{func_descriptions}
"""

# ==================================================================
#  Step 8c: analyze_group_filelist_brief —— 文件 brief 批量生成
# ==================================================================

ANALYZE_AREA_FILELIST_BRIEF_SYSTEM = """\
为每个文件生成一句话的 brief（不超过30字）。
只输出 JSON，格式：{"briefs": [{"file_id": 1, "brief": "..."}, ...]}
"""

ANALYZE_AREA_FILELIST_BRIEF_USER = """\
模块：{group_name}，请为以下 {file_count} 个文件各生成一条 brief：

{file_list_text}
"""

# ==================================================================
#  Step 8d: analyze_group_description —— 模块描述
# ==================================================================

ANALYZE_AREA_DESCRIPTION_SYSTEM = """\
为给定的代码模块（group）生成简洁的自然语言描述（150-250字）。
说明模块的核心功能、在仓库中的定位，以及包含了哪些主要能力。
"""

ANALYZE_AREA_DESCRIPTION_USER = """\
模块：{group_name}（路径：{group_path}）
分层依据：{rationale}
Group 文件结构：
{file_structure}

包含文件：
{file_structure}

各文件描述：
{file_descriptions}
"""

# ==================================================================
#  Step 8e: analyze_repo_grouplist_brief —— 模块 brief 批量生成
# ==================================================================

ANALYZE_REPO_AREALIST_BRIEF_SYSTEM = """\
为每个模块生成一句话的 brief（不超过30字）。
只输出 JSON，格式：{"briefs": [{"group_id": 1, "brief": "..."}, ...]}
"""

ANALYZE_REPO_AREALIST_BRIEF_USER = """\
仓库：{repo_name}，请为以下 {group_count} 个模块各生成一条 brief：

{group_list_text}
"""

# ==================================================================
#  Step 8f: analyze_repo_description —— 仓库描述
# ==================================================================

ANALYZE_REPO_DESCRIPTION_SYSTEM = """\
为给定的代码仓库生成简洁的自然语言描述（200-350字）。
说明仓库的整体功能与用途、技术架构特点，以及各模块的职责分工。
"""

ANALYZE_REPO_DESCRIPTION_USER = """\
仓库：{repo_name}（主要语言：{main_language}，语言分布：{language_stats}）

目录结构（3层）：
```
{dir_tree}
```

模块划分：
{group_structure}

README 摘要：
{readme_content}

各模块描述：
{group_descriptions}

请生成该仓库的自然语言描述。
"""

