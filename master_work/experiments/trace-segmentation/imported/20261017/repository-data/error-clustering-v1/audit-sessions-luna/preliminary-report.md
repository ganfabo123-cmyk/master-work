# Luna 全量错误聚类审查

本次以 GPT-5.6 Luna 审查三种策略的全部 201 组：native-code 14 组、exception-type 28 组、message-template 159 组。每组均读取 groups.json 的全部 evidence，并按 source_file/event_index 回到原始 JSONL 检查附近事件；未执行轨迹命令。

## 总体判断
错误识别与可复用经验是两个独立维度：相同错误码或模板不证明同根因；助手文本、源码片段和预期异常会造成误报。usable 只在触发、处理、原始验证和边界四项都有证据时计入。

### native-code
共 14 组；归组：{'consistent': 13, 'mixed': 1}；经验证据：{'usable': 12, 'candidate': 2}；usable 比率 12/14，candidate 比率 2/14。

### exception-type
共 28 组；归组：{'consistent': 23, 'false_positive': 2, 'mixed': 3}；经验证据：{'usable': 23, 'unsupported': 2, 'candidate': 3}；usable 比率 23/28，candidate 比率 3/28。

### message-template
共 159 组；归组：{'consistent': 155, 'insufficient': 1, 'false_positive': 3}；经验证据：{'usable': 150, 'candidate': 5, 'unsupported': 4}；usable 比率 150/159，candidate 比率 5/159。

## 具体组例
证据较好的组例：native-code-782199a88f4c、native-code-f9479c34ae84、native-code-847c28ada68a。这些组的 source_evidence 同时保留了原始 JSONL 文件、事件索引、命中短引文和附近事件，并且审查到具体处理后的工具结果。
问题较明显的组例：native-code-c6460e120c75、exception-type-6bcb03e30a18、exception-type-a7f9674cc5fa、exception-type-70e920a2bb7b、exception-type-a3d3eaa4aede、exception-type-c6c0bd63aa9d。其中 exception-type 的 CodeGenError/LexError 与 message-template 的 struct codegenerror/struct lexerror/struct parseerror 是源码中的类型声明，属于 false_positive；NativeCommandError、ParseError、RemoteException 等 mixed 组把助手复述和实际工具结果混在一起，不能直接当作同一根因。
message-template 的 changelog 组只说明文档内容，若无失败命令和后续验证只能列 candidate 或 unsupported。这里不把错误数量或簇紧密度当作质量分数。

## 全量核对
已审查 201/201 组。group_id 唯一性核对由生成过程读取三份 groups.json 后完成；策略合计为 14+28+159=201，无重复 group_id。
