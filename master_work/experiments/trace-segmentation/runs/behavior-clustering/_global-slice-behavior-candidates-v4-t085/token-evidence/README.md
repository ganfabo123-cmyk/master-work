# 候选簇加权词证据

每个候选簇由其全部 slice 的可用事件正文和参数值提取 Top-K 词。词频按事件类别加权，再用全体 slice 的 document frequency 做 IDF；该结果是可追溯词证据，不是行为名称。
