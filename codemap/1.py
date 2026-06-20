# debug_minizip.py（放在项目根目录下跑即可）
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from analyzer.file_analyzer import (
    _TREE_SITTER_OK,
    _extract_c_cpp_funcs,
    _read_source,
)

MINIZIP_PATH = r"C:\Users\caoye04\Desktop\repo_4_codemap\minizip-ng\minizip.c"

print(f"tree-sitter 可用：{_TREE_SITTER_OK}")

source = _read_source(MINIZIP_PATH)
print(f"文件读取：{'成功' if source else '失败'}")
if source:
    print(f"文件大小：{len(source)} 字节")

if _TREE_SITTER_OK and source:
    from tree_sitter_languages import get_parser
    parser = get_parser('c')
    tree = parser.parse(source.encode('utf-8', errors='replace'))

    # 看看 tree-sitter 实际解析出了多少 function_definition
    from analyzer.file_analyzer import _find_all_nodes
    nodes = _find_all_nodes(tree.root_node, {'function_definition'})
    print(f"\ntree-sitter 找到的 function_definition 节点数：{len(nodes)}")

    for n in nodes[:5]:   # 打印前 5 个，看看长什么样
        print(f"  行 {n.start_point[0]+1}–{n.end_point[0]+1}  declarator 结构：")
        decl = n.child_by_field_name('declarator')
        if decl:
            def _dump(node, indent=0):
                print(" " * (indent*2+4) + f"[{node.type}]")
                for ch in node.children:
                    _dump(ch, indent+1)
            _dump(decl)

    # 单独跑完整提取，看有无异常
    result = _extract_c_cpp_funcs(source, "minizip.c", lang='C')
    print(f"\n_extract_c_cpp_funcs 返回函数数：{len(result)}")
    for fn in result[:3]:
        print(f"  {fn['name']}  行{fn['start_line']}")