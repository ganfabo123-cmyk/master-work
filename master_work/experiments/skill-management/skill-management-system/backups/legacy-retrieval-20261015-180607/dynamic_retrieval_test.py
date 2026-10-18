"""
动态检索固定入口。

此文件只负责导入并创建程序实例。开发者实现检索程序时只修改 retrieval_program.py。
外部 Runtime 调用 PROGRAM.handle_raw_trace(raw_trace) 后会得到统一的 RetrievalResult。
本入口不消费检索结果。
"""

from retrieval_program import create_developer_program


PROGRAM = create_developer_program()
