# 接口与约定

`get_term(year, name, source_zone=None, **policy)` 查询一个节气。
`terms_for_year(year, source_zone=None, **policy)` 查询完整 24 项。
年份均以北京时间资料年份为准；显示时区转换不改变来源年份。

`calendar_at(timestamp, source_zone=None, **policy)` 输出当地钟表四柱、当前节气和换月节气。
时间必须含时分及偏移，或者另给 IANA 时区名。`now` 使用指定时区或设备当前时区。
命名时区的夏令时歧义时刻须提供明确偏移。年以立春、月以十二节、日以当地 23:00 为界。

三个策略开关互相独立，默认均为 False：

| 参数 | 含义 |
| --- | --- |
| `allow_estimated_terms` | 官方缺项时，调用方已取得使用第三方估算的同意 |
| `require_second_precision` | 调用方请求秒级分辨率；不等于秒级准确性保证 |
| `accept_minute_boundaries` | 调用方接受从官方公布分钟起点切换 |

需要确认时抛出 `ResultConfirmationRequired` 子类，`.to_dict()` 提供可序列化的原因、依据和选项。
输入错误为 ValueError；缺少 IANA 时区资料可能为 ZoneInfoNotFoundError。

## 候选时段匹配

这个接口接收调用方提供的干支或地支候选，不生成预测或概率。
`start` 和 `end` 必须为带时区的 datetime，`zone` 为 tzinfo 对象。

```python
from datetime import datetime
from solar_term_calendar import resolve_windows_report

start = datetime.fromisoformat("2025-11-07T12:03:00+08:00")
end = datetime.fromisoformat("2025-11-07T12:05:00+08:00")
timing = {
    "unit": "month",
    "candidates": [{"pillar": "丁亥", "rule": "caller-supplied-filter"}],
}
report = resolve_windows_report(timing, start, end, start.tzinfo)
print(report["windows"][0]["start"])  # 2025-11-07T12:04:00+08:00
```

`unit` 可为 `hour`、`day`、`month`、`year`。候选写 `pillar` 或 `branch`，并给 `rule` 标签。
可传 `secondary_candidates`，仅合并 unit 相同的条目。返回窗口含起点、不含终点，裁剪到搜索范围。
四种尺度的最大搜索跨度分别为 31、370、3660、36600 天。
年/月边界也遵守官方优先与估算确认；时/日按当地钟表边界计算。

`resolve_windows` 保留只返回窗口列表的低层接口；需要来源信息时使用 `resolve_windows_report`。

## 数据版本与更新

`term_data_version` 是已载入节气值及更新版次的 SHA-256 指纹；不等同软件版本。
`SOLAR_TERM_CALENDAR_UPDATES` 指定可选 JSON 更新文件，默认使用包内空更新表。
新进程载入已审核更新后，更新优先于原年度表和历史表。
导入器验证结构而非官方真实性，审核责任仍在数据维护者。

本版本仅有部分回归测试；`validated_year_range` 和 `accuracy_bound_seconds` 保留 null。
