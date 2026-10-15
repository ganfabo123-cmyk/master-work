"""
动态检索固定入口。

此文件只负责导入并创建程序实例。当前默认接入skill管理系统，触发策略保留在retrieval_program.py。
外部 Runtime 调用 PROGRAM.handle_raw_trace(raw_trace) 后会得到统一的 RetrievalResult。
本入口不消费检索结果。
"""

from retrieval_program import create_developer_program


PROGRAM = create_developer_program()
