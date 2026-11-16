# stgCalendar — Solar Term Ganzhi Calendar

采用官方公布历表的节气查询与公历时间换算 Python 库，支持资料来源追踪。
本项目是第三方独立实现，不是紫金山天文台或香港天文台的官方软件。

## 功能

- 查询单个节气或全年 24 节气，优先使用已录入的紫金山天文台资料，其次使用香港天文台资料；缺项时，经调用方明确同意才使用 `lunar-python` 估算。
- 将公历时间换算为年、月、日、时干支（四柱），采用本地钟表时间，不作经度或真太阳时修正。
- 按完整干支（如“甲子”）或仅按地支（如“子”），在指定范围内查找对应的年、月、日或时辰区间。
- 节气记录附带资料链接、版次、数据指纹、分辨率和确认状态；支持年度紫金山节气表的校验、差异预览与手动更新。

## 安装与使用

要求 Python 3.11+。

```bash
git clone https://github.com/HaoOuyang49/stgCalendar.git
cd stgCalendar
python -m pip install -e .
python -m stg_calendar term 2026 立冬
python -m stg_calendar year 2027
```

按默认北京时间查询已录入的节气表，无需额外依赖，也不联网。
公历转四柱、时段匹配及缺项估算需要安装日历依赖；其中的 `tzdata` 也为 Windows 等环境提供命名时区资料：

```bash
python -m pip install -e ".[calendar]"
python -m stg_calendar at "2026-11-05T14:02:00+08:00"
python -m stg_calendar at now --timezone America/New_York
```

命令入口也可使用 `stg-calendar`。手动输入时间时，须包含 UTC 偏移量，或另给 `--timezone`，两者二选一。
夏令时切换导致的歧义或不存在的当地时间，须改用带明确 UTC 偏移量的输入。

### Python 示例

```python
from stg_calendar import calendar_at, get_term, terms_for_year

term = get_term(2026, "立冬")
print(term["time"])                # 2026-11-07T17:52:00+08:00
print(term["source"]["provider"])  # pmo

print(len(terms_for_year(2027)["terms"]))  # 24

# 需要安装 calendar 额外依赖
result = calendar_at("2026-11-05T14:02:00+08:00")
print(result["pillars"])
```

`get_term()` 和 `terms_for_year()` 的年份按北京时间资料中的公历年份确定。
`source_zone` 可改变结果的显示时区，不改变资料归属年份。
时段匹配的输入格式与示例见[接口文档](docs/api.md#候选时段匹配)。

## 数据覆盖

仓库内置转录表如下；运行 `python -m stg_calendar coverage` 可查看当前加载的数据。

| 来源 | 已录入范围 | 记录数 |
| --- | --- | ---: |
| 紫金山天文台 | 1900—2026 年全年；2027 年前四个节气 | 3052 |
| 香港天文台 | 2027 年全年 | 24 |

按来源优先级合并后，1900—2027 年共 3072 项。资料链接及转录说明见[数据来源](DATA_SOURCES.md)。
覆盖范围表示本地记录存在，不代表已逐项完成独立精度验证。

## 时间约定与确认

- 年干支以立春为界，月干支以十二节为界，日干支在当地 23:00 切换。
- 返回的时段包含开始时刻，不包含结束时刻，并裁剪到指定查询范围。
- 内置官方节气表公布到分钟，程序从该分钟起点切换；输出中的 `:00` 不表示已知真实交节秒数。`accuracy_bound_seconds` 为 `null`，不提供未经验证的误差保证。
- 官方记录缺项时，默认抛出 `EstimatedTermConsentRequired`；取得同意后，可用 `allow_estimated_terms=True` 重试。
- 请求秒级分辨率（`require_second_precision=True`）但只有分钟表时，抛出 `TermPrecisionConsentRequired`；接受分钟边界后，可用 `accept_minute_boundaries=True` 重试，结果仍标明未达到所请求分辨率。第三方估算输出到秒，也不代表误差小于一秒。

确认异常均继承 `ResultConfirmationRequired`，可用 `.to_dict()` 获取原因和选项，由调用方收集选择后重试。
CLI 查询成功时向 stdout 输出 JSON；需要确认时向 stderr 输出 JSON，退出码为 2。
完整参数与返回结构见[接口文档](docs/api.md)。

## 更新与贡献

人工核对紫金山年度资料后，准备包含 `publication`、`source_url` 和完整 24 项 `terms` 的 UTF-8 JSON。
时间格式为 `YYYY-MM-DDTHH:MM+08:00`。先预览，再决定是否写入：

```bash
python -m stg_calendar.update_terms 2028 reviewed-2028.json
python -m stg_calendar.update_terms 2028 reviewed-2028.json --apply
```

可通过环境变量 `STG_CALENDAR_UPDATES` 指定外部更新文件；更新后启动新进程加载。
工具检查结构、日期和来源网址格式，不会自动核实资料内容。

安装日历依赖后运行测试：

```bash
python -m unittest discover -s tests -v
```

报告问题请使用 [Issues](https://github.com/HaoOuyang49/stgCalendar/issues)，提供输入、时区、输出、版本及预期依据。
修改代码或数据前请阅读[贡献指南](CONTRIBUTING.md)。
