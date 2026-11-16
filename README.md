# stgCalendar — Solar Term Ganzhi Calendar

用于节气查询、公历转干支和干支时段查找的 Python 库。
优先采用紫金山天文台、香港天文台公布的节气资料，保留来源信息；缺项时可在明确同意后使用第三方估算。
本项目为第三方独立实现。

## 功能

- 查询单个节气或全年 24 节气，内置 1900—2027 年节气记录。
- 将公历时间换算为年、月、日、时干支（四柱），支持时区处理。
- 按完整干支或仅按地支，查找指定范围内对应的公历时段。
- 追踪节气资料来源，支持手动更新年度数据。

## 快速开始

需要 Python 3.11+。

```bash
git clone https://github.com/HaoOuyang49/stgCalendar.git
cd stgCalendar
python -m pip install -e ".[calendar]"
```

命令行查询：

```bash
python -m stg_calendar term 2026 立冬
python -m stg_calendar year 2027
python -m stg_calendar at "2026-11-05T14:02:00+08:00"
```

Python 调用：

```python
from stg_calendar import calendar_at, get_term

print(get_term(2026, "立冬")["time"])  # 2026-11-07T17:52:00+08:00
print(calendar_at("2026-11-05T14:02:00+08:00")["pillars"])
```

内置官方节气表公布到分钟，显示秒数不代表秒级精度。时间换算采用本地钟表时间，具体边界与确认机制见接口文档。

## 文档与反馈

- [接口、时间约定与数据更新](docs/api.md)
- [数据来源与覆盖说明](DATA_SOURCES.md)
- [贡献指南](CONTRIBUTING.md)
- [问题反馈](https://github.com/HaoOuyang49/stgCalendar/issues)
