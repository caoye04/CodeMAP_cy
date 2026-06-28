IF YOU NEED HELP? 

1. 创建虚拟环境
python -m venv codemap_env
.\codemap_env\Scripts\activate
deactivate
rm -rf codemap_env

2. 安装本项目的依赖
pip install -r .\requriments.txt

3. 只测试数据库的读写存储功能，不涉及算法逻辑
python -m pytest test/test_just_db.py -v

4. 在手工构建的假仓库上进行 init_repo 和 analyze_repo_language 单元测试
python -m pytest test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_fake_repo.py -v

5. 在目标仓库minizip-ng上进行 init_repo 和 analyze_repo_language 单元测试
python -m pytest "test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_minizip-ng.py" -v

6. 在五个大小不一的仓库上进行 init_repo 和 analyze_repo_language 单元测试
python -m pytest "test/test_repo_analyzer_init_repo_and_analyze_repo_language_in_five_real_repo.py" -v -s

7. 在目标仓库minizip-ng上进行 analyze_repo_group 单元测试
python -m pytest "test/test_repo_analyzer_analyze_repo_group_in_minizip-ng.py" -v

8. 在五个大小不一的仓库上进行 analyze_repo_group 单元测试
python -m pytest "test/test_repo_analyzer_analyze_repo_group_in_five_repo.py" -v -s

9. 在目标仓库minizip-ng上进行 analyze_group_file 单元测试
python -m pytest "test/test_group_analyzer_analyze_group_file_in_minizip-ng.py" -v

10. 在目标仓库minizip-ng上进行 analyze_group_file 单元测试
python -m pytest "test/test_file_analyzer_in_minizip-ng.py" -v -s




CodeMAP算法设计流程

1. **init_repo**：得到仓库名，建立对应数据库并填入对应数据【repo:name】
2. **analyze_repo_language**：扫描仓库并分析语言占比情况，得出主要语言，并填入对应数据【repo:language】
3. **analyze_repo_group**：对仓库分层，并附上分层依据和对应的group具体路径，存data/analyze_repo_group，并填入对应数据【repo:grouplist；group:name；group:path】
4. **analyze_group_file**：扫描group路径得到文件结构，存在data/analyze_group_file，并填入对应数据【group:filelist；file:name；file:path】
5. **analyze_file_language**：分析文件的编程语言，并填入对应数据【file:language】
6. **analyze_file_func**：分析文件中所有的函数，并填入对应数据【file:funclist；func:name；func:place；func:io】
7. **build_callgraph**：对整个仓库分析得到的函数调用图，并存入data
8. **analyze_func_callgraph**：分析该函数的调用关系，并填入对应数据【func:callgraph】
9. **analyze_func_precondition**：sa+llm分析该函数的前置调用关系（可能需要读调用链沿途的函数？），且有一些分类，这个实现需要做到非常好和细节到位，最后填入对应数据【func:precondition】
10. **analyze_func_postcondition**：sa+llm分析该函数的后置调用关系（可能需要读被调用链沿途的函数？），且有一些分类，这个实现需要做到非常好和细节到位，最后填入对应数据【func:postcondition】
11. **analyze_func_exception**：分析该函数的异常处理，填入对应数据【func:exception】
12. **analyze_func_description**：agent实现，提供该函数内容+调用关系+前置条件+后置条件+异常处理，以及给一个get_func_context的工具调用结构，可以agent工具得到调用链里的函数信息；让agent给出该函数的自然语言描述：该函数功能+函数分析+函数安全分析+开发者意图分析等，最后填入对应数据【func:description】
13. **analyze_file_funclist_brief**：通过提供file的funclist，将每个func的description变成简短的一两句话存入对应数据【file:funclist】
14. **analyze_file_description**：给llm提供file在group里的文件组织架构、文件信息、其中函数所有的description，得到对文件的自然语言描述：文件功能+文件定位+开发者意图分析，最后填入对应数据【file:description】
15. **analyze_group_filelist_brief**：通过提供group的filelist，将每个file的description变成简短的一两句话存入对应数据【group:filelist】
16. **analyze_group_description**：给llm提供group的在仓库中路径及分层依据+group里的文件组织架构、其中file所有的description，得到对group的自然语言描述：group功能+group定位+开发者意图分析，最后填入对应数据【group:description】
17. **analyze_repo_grouplist_brief**：通过提供repo的grouplist，每个group的description变成简短的一两句话存入对应数据【repo:grouplist】
18. **analyze_repo_description**：给llm提供仓库的文件组织结构、分层结构、仓库相关信息、仓库里可参考的文本内容、仓库的所有group的description，得到对仓库的自然语言描述：仓库功能+开发者意图分析，最后填入对应数据【repo:description】
19. **build_codemap**：实现CodeMAP，即将上述流程串起来