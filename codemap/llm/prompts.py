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