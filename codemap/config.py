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
LLM_API_KEY  = os.getenv('LLM_API_KEY',  'sk-MJjAy6jCzTNL2paHSbrFE9LVArxlkoFzevM145VXOW83xSKv')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.ezai88.com')
LLM_MODEL    = os.getenv('LLM_MODEL',    'gemini-2.5-flash')

# ------------------------------------------------------------------
#  CodeQL（占位，后续填入）
# ------------------------------------------------------------------
CODEQL_BIN   = os.getenv('CODEQL_BIN', 'codeql')   # codeql 可执行文件路径