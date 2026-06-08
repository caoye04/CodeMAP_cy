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

7. 在目标仓库minizip-ng上进行 analyze_repo_area 单元测试
python -m pytest "test/test_repo_analyzer_analyze_repo_area_in_minizip-ng.py" -v

8. 在五个大小不一的仓库上进行 analyze_repo_area 单元测试
python -m pytest "test/test_repo_analyzer_analyze_repo_area_in_five_repo.py" -v -s

9. 在目标仓库minizip-ng上进行 analyze_area_file 单元测试
python -m pytest "test/test_area_analyzer_analyze_area_file_in_minizip-ng.py" -v