# Luna 全量错误聚类审查

本次按 slices-97 的 14 + 28 + 147 个组逐组审查，共 189 组；reviewed_group_count=189，组 ID 已校验无重复、无遗漏。判断只依据各成员切片范围内的 evidence、附近处理/验证上下文及 hydrated 原始事件索引。

## 总体判断

错误分组大多能准确定位到实际输出，但 message-template 大量是单成员、助手复述或测试失败文本，能形成可复用经验的比例有限。native-code 更容易保留命令、错误和修复链；exception-type 能识别错误类别，但同名异常跨项目时根因仍需看上下文；message-template 适合保留具体回归/测试语义，却容易把同一经验按测试名称拆碎，也容易把“失败信息”误当可用经验。

## 策略统计

- native-code: 14 组；usable 10/14 (71.4%)；candidate 2/14 (14.3%)；状态明细 `{'mixed/usable': 1, 'consistent/usable': 9, 'insufficient/unsupported': 2, 'consistent/candidate': 2}`
- exception-type: 28 组；usable 16/28 (57.1%)；candidate 3/28 (10.7%)；状态明细 `{'consistent/unsupported': 8, 'consistent/usable': 11, 'insufficient/unsupported': 1, 'mixed/usable': 4, 'insufficient/usable': 1, 'consistent/candidate': 3}`
- message-template: 147 组；usable 79/147 (53.7%)；candidate 38/147 (25.9%)；状态明细 `{'insufficient/usable': 14, 'consistent/unsupported': 21, 'consistent/usable': 65, 'consistent/candidate': 35, 'insufficient/unsupported': 9, 'insufficient/candidate': 3}`

## 具体例子

- 好的 native-code / native-code-782199a88f4c：exit-status:0x00000451，错误识别：mixed；可用经验：usable。同组证据文本存在多个具体变体，不能仅凭模板视为同根因。 经验：触发为 `exit-status:0x00000451`；切片内有处理动作并出现后续验证信号。适用范围限于该组成员的同类命令/错误上下文，不能据此推广到其他工具链或根因。
- 好的 native-code / native-code-f9479c34ae84：exit-status:0x00000460，错误识别：consistent；可用经验：usable。单成员，只能证明该轨迹中的具体实例。 经验：触发为 `exit-status:0x00000460`；切片内有处理动作并出现后续验证信号。适用范围限于该组成员的同类命令/错误上下文，不能据此推广到其他工具链或根因。
- 好的 exception-type / exception-type-05b6f58afac2：exception:CommandNotFoundException，错误识别：consistent；可用经验：usable。证据、处理与验证均位于该成员切片范围内。 经验：触发为 `exception:CommandNotFoundException`；切片内有处理动作并出现后续验证信号。适用范围限于该组成员的同类命令/错误上下文，不能据此推广到其他工具链或根因。
- 好的 message-template / message-template-430896dbdfc1：template:**4. <arg> stack overflow in headless — heap-allocate.**，错误识别：insufficient；可用经验：usable。部分/全部证据来自助手转述，需与工具结果区分；单成员，只能证明该轨迹中的具体实例。 经验：触发为 `template:**4. <arg> stack overflow in headless — heap-allocate.**`；切片内有处理动作并出现后续验证信号。适用范围限于该组成员的同类命令/错误上下文，不能据此推广到其他工具链或根因。
- 较弱 native-code / native-code-847c28ada68a：exit-status:0xC00000FD，错误识别：insufficient；可用经验：unsupported。部分/全部证据来自助手转述，需与工具结果区分；切片内未见明确处理动作。
- 较弱 native-code / native-code-c2d2ec92b28d：exit-status:0xC0000135，错误识别：insufficient；可用经验：unsupported。部分/全部证据来自助手转述，需与工具结果区分；切片内未见明确处理动作；单成员，只能证明该轨迹中的具体实例。
- 较弱 exception-type / exception-type-6aeeabc70f68：exception:AttributeError，错误识别：consistent；可用经验：unsupported。切片内未见明确处理动作；单成员，只能证明该轨迹中的具体实例。
- 较弱 exception-type / exception-type-6bcb03e30a18：exception:CodeGenError，错误识别：consistent；可用经验：unsupported。切片内未见明确处理动作；单成员，只能证明该轨迹中的具体实例。
- 较弱 exception-type / exception-type-7a6c11e8da23：exception:IllegalCallerException，错误识别：insufficient；可用经验：unsupported。部分/全部证据来自助手转述，需与工具结果区分；切片内未见明确处理动作；单成员，只能证明该轨迹中的具体实例。

## 语义重复与局限

- native-code 的 LNK1105 与 message-template-7a32…/ba50…/624…均指向 Windows 文件锁导致链接失败；应视为同一候选经验的不同粒度，不是多个独立 Skill。
- native-code 的 LNK2019/LNK1120 与 message-template-960…至 4cc…均涉及 g_verbose 未定义及其链接收尾；同样存在跨策略重复。
- exception-type 与 message-template 对 IllegalCallerException、MissingPropertyException、ModuleNotFoundError、UnicodeEncodeError 等有重叠；message-template 组常按测试/消息细节拆开，组数不等于经验数。
- 审查只使用 slices-97 的成员、evidence、context 和 hydrated 原始事件索引；切片 end_event 之外的修复/验证未计入。
- 单成员组可以支持局部经验，但不能单凭一次轨迹证明跨项目泛化；助手转述若无工具结果则降级。
- tool_output 可能是预期异常、编译器输出中的示例文字或包装错误，已结合 preceding_command/context 判断，无法仅凭 error_key 推断根因。

## 完成核对

三策略组数分别为 14、28、147；合计 189。audit.json 中 reviewed_group_count=189，所有 group_id 组成集合与三份输入 groups.json 的集合相等，且无重复。
