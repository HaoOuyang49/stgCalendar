# solar-term-calendar

**Official-publication-first solar terms, with provenance and explicit fallback consent.**

采用官方公布历表的节气查询、本地公历钟表时间换算与来源追踪 Python 工具。
这是第三方独立项目，**不是紫金山天文台或香港天文台的官方软件，也未获得它们对本项目的认证**。

## 为什么做这个项目

提供可追溯的历表来源与明确的使用条件：查到了什么、来自哪份资料、公布到什么分辨率、
是否包含估算、调用方是否已经接受估算或分钟边界。可供日历、研究工具或其他应用复用。
它不以“显示到秒”宣称误差小于一秒，也不以软件测试通过宣称全部历史数据正确。

本项目从 MagicDoor 的在研历法模块独立抽取，使用 AI 辅助开发和整理；
历算的第三方依赖及官方资料来源分别列明。项目不包含奇门排盘、解盘、私有教材或其他库的审阅副本。

## 当前能力

- 单个节气与全年 24 节气查询，默认按 **紫金山天文台 → 香港天文台 → 经同意的 lunar-python 估算** 选择。
- 查询已录入的官方节气表可只用 Python 标准库，不联网、不需要安装历算依赖。
- 公历本地钟表时间转年/月/日/时干支：年以立春为界，月以十二节为界，当地 23:00 换干支日。
- 保留 IANA 时区和夏令时检查，不进行经度或真太阳时修正。
- 每项结果携带资料标题、官方链接、版次、数据指纹、分辨率、验证限制及确认状态。
- 支持干支或地支候选匹配到本地公历时段，区间含起点、不含终点。
- 年度紫金山表的完整性校验、差异预览和显式更新。

本地转录表覆盖：

| 来源 | 已录入范围 | 记录数 |
| --- | --- | ---: |
| 紫金山天文台 | 1900—2026 全年；2027 年前四个节气 | 3052 |
| 香港天文台 | 2027 年全年，补紫金山缺项 | 24 |

两家按优先级合并后，1900—2027 共 3072 项。覆盖描述的是**本地录入情况**，不是保证误差界限，
也不是断言机构尚未发布其他资料。可运行 `coverage` 查看实际记录。

## 安装与运行

要求 Python 3.11+。当前从 GitHub 安装；本项目尚未发布到 PyPI。

```bash
git clone https://github.com/HaoOuyang49/solar-term-calendar.git
cd solar-term-calendar
python -m pip install -e .
python -m solar_term_calendar term 2026 立冬
python -m solar_term_calendar year 2027
python -m solar_term_calendar coverage
```

需要公历转四柱、命名时区或官方缺项时的可选估算：

```bash
python -m pip install -e ".[calendar]"
python -m solar_term_calendar at "2026-11-05T14:02:00+08:00"
python -m solar_term_calendar at now --timezone America/New_York
```

命令入口也可用 `solar-terms`。带偏移时间与 `--timezone` 在 `at` 模式中二选一。
没有偏移时，手动输入必须提供时区；夏令时歧义或不存在的当地时刻须用明确偏移。

## Python API

```python
from solar_term_calendar import calendar_at, get_term, terms_for_year

term = get_term(2026, "立冬")
print(term["time"])                              # 2026-11-07T17:52:00+08:00
print(term["source"]["provider"])                # pmo
print(term["precision"]["published_resolution"]) # minute
print(term["precision"]["accuracy_bound_seconds"]) # None

calendar = calendar_at("2026-11-05T14:02:00+08:00")
print(calendar["pillars"])

year = terms_for_year(2027)
print(len(year["terms"]))                        # 24
```

`get_term()` / `terms_for_year()` 的年份以**北京时间资料中的公历年份**为准。
传入 `source_zone="America/New_York"` 可转换显示时区，不改变资料归属年份。
命名时区需要系统时区资料，Windows 可通过 calendar 额外依赖获得 tzdata。

## 确认流程与精度边界

官方表公布到分钟。本库约定从该分钟起点切换，`:00` 并不表示已知真实交节秒数。
`accuracy_bound_seconds` 保留 null，不无依据地假定取整方式或误差范围。

- 官方缺项：默认抛出 `EstimatedTermConsentRequired`。确认后才能设置 `allow_estimated_terms=True`。
- 请求秒级分辨率但只有分钟表：抛出 `TermPrecisionConsentRequired`。
  明确接受分钟约定后设置 `accept_minute_boundaries=True`；结果仍标记未达到所请求分辨率。
- 输出到秒的第三方估算仍是估算，不能自动覆盖已录入的官方分钟表。
- 这些开关应由应用在取得用户实际选择后传入；pending 不算同意。

```python
from solar_term_calendar import get_term, ResultConfirmationRequired

try:
    result = get_term(2026, "立冬", require_second_precision=True)
except ResultConfirmationRequired as error:
    question = error.to_dict()  # status=needs_confirmation，含原因、依据和选项
    # 由调用方展示并收集用户选择，然后显式重试。
```

CLI 成功输出 JSON 到 stdout。需要确认时返回退出码 2，JSON 写到 stderr；不会输出半成品结果。
一般数据输入错误返回退出码 1；argparse 的语法错误仍可能是普通文本。

```bash
python -m solar_term_calendar term 2026 立冬 --require-second-precision
# 获得用户同意后：
python -m solar_term_calendar term 2026 立冬 --require-second-precision --accept-minute-boundaries
```

## 更新官方年表

人工核对紫金山官网新资料后准备 UTF-8 JSON，包含 `publication`、`source_url`、`terms`。
`terms` 必须为完整 24 项，时间格式为 `YYYY-MM-DDTHH:MM+08:00`。

```bash
python -m solar_term_calendar.update_terms 2028 reviewed-2028.json
# 核对差异后才应用：
python -m solar_term_calendar.update_terms 2028 reviewed-2028.json --apply
```

可通过环境变量 `SOLAR_TERM_CALENDAR_UPDATES` 指定仓库外的更新文件，避免修改安装目录。
工具只验证格式、月份、顺序和来源网址，不会自动证明人工录入正确。更新后启动新进程。
保存历史结果时同时保存输入、资料来源、边界约定及 `term_data_version`，便于复现。

## 测试与问题反馈

```bash
python -m pip install -e ".[calendar]"
python -m unittest discover -s tests -v
```

测试包括已知交节边界、换日、时区/夏令时、来源优先、估算/分钟确认、年表更新及数据结构检查。
这些是软件回归测试，不是所有公布值的独立天文精度认证。

发现问题请通过 [Issues](https://github.com/HaoOuyang49/solar-term-calendar/issues) 提供：
输入与时区、实际输出、预期输出、预期依据的官方资料链接/页码、包版本和资料指纹。

## 来源与许可

- [资料来源与数据边界](DATA_SOURCES.md)
- [贡献指南](CONTRIBUTING.md)
- [接口与时段匹配](docs/api.md)
- [模块提取记录](docs/extraction-provenance.json)
- 原创代码按 [MIT](LICENSE) 发布；原始出版物和第三方组件各自保留原有权利与条款。

日柱及相邻节气候选使用 `lunar-python`；IANA 时区资料由系统或 `tzdata` 提供。
本库不宣称天文算法全部由作者从零实现，也不宣称整体精度优于其他日历库。
