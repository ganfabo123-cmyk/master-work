# 当前入口与旧版保留

dynamic_retrieval_test.py继续导出PROGRAM.handle_raw_trace(raw_trace)。默认工厂已接入
相邻skill-management-system的35项管理库，原.env继续用于查询embedding配置。

Trace转换、轨迹、触发策略和查询构造完整保留，原三个developer钩子继续生效。
默认最新用户输入触发，返回类型仍为本文件的RetrievalResult。
event_id、版本和通道信息在metadata中，可通过PROGRAM.feedback提交真实good/bad反馈。
每个Agent会话应单独创建实例，避免共享全局PROGRAM的轨迹。

API、策略替换、签名抽样复查及写入边界见../skill-management-system/INTEGRATION.md。
create_legacy_program()保留原skills_tests策略；原通用检索类和解析器仍可使用。

改动前完整旧版：../skill-management-system/backups/legacy-retrieval-20261015-180607/。
17个文件均按BACKUP_MANIFEST.json逐字节校验，含旧语料和缓存。
未复制.env和密钥，独立运行时从环境提供原embedding配置。
