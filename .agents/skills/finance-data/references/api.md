# finance_lib API 参考

`finance_lib.py` 提供可直接 import 的 Python 函数，用于在分析脚本中拉取金融数据。

## 安装依赖

```bash
pip install yfinance pandas numpy
```

## 导入

```python
import sys
sys.path.insert(0, "skills/finance-data/scripts")

from finance_lib import (
    fetch_data,
    fetch_multiple,
    to_csv,
    PREDEFINED_TICKERS,
    resolve_predefined,
    set_cache_dir,
)
```

## 函数参考

### `fetch_data(ticker, start, end, verbose=True)`

获取单个标的的 Adjusted Close 数据，优先使用本地缓存。

| 参数 | 类型 | 说明 |
|------|------|------|
| ticker | str | Yahoo Finance 代码，如 `"510300.SS"` |
| start | date | 起始日期 |
| end | date | 结束日期 |
| verbose | bool | 是否打印进度信息（默认 True） |

返回: `pd.DataFrame`，index 为 date 类型，含 `adj_close` 列。

```python
from datetime import date
df = fetch_data("SPY", date(2020, 1, 1), date(2024, 12, 31))
print(df.head())
```

---

### `fetch_multiple(ticker_specs, start, end, verbose=True)`

同时拉取多个标的的数据并合并为一个 DataFrame。

| 参数 | 类型 | 说明 |
|------|------|------|
| ticker_specs | List[Tuple[str, str]] | `[(ticker, label), ...]` 列表 |
| start | date | 起始日期 |
| end | date | 结束日期 |
| verbose | bool | 是否打印进度信息 |

返回: `pd.DataFrame`，每列名为 `"{label}_adj_close"`。

```python
specs = [("510300.SS", "沪深300"), ("SPY", "标普500")]
df = fetch_multiple(specs, date(2020,1,1), date(2024,12,31))
```

---

### `to_csv(df, output_path, include_date=True)`

将 DataFrame 保存为 CSV 文件（UTF-8 with BOM，兼容 Excel）。

| 参数 | 类型 | 说明 |
|------|------|------|
| df | pd.DataFrame | 要保存的 DataFrame |
| output_path | str | 输出文件路径 |
| include_date | bool | 是否将 index(date) 作为列写入 |

返回: str（保存的文件路径）。

---

### `PREDEFINED_TICKERS`

预定义标的名字典，key 为简称，value 为 `{"ticker": ..., "name": ..., "market": ...}`。

| key | ticker | name | market |
|-----|--------|------|--------|
| csi300 | 510300.SS | 沪深300 | CN |
| sp500 | SPY | 标普500 | US |
| nasdaq100 | 513100.SS | 纳斯达克100 | CN |
| hsi | 2800.HK | 恒生指数 | HK |
| hstech | 3032.HK | 恒生科技 | HK |
| vxus | VXUS | 全球除美 | US |
| gem50 | 159949.SZ | 创业板50 | CN |
| star50 | 588000.SS | 科创50 | CN |
| cninet | 513050.SS | 中概互联 | CN |
| nikkei225 | 513000.SS | 日经225 | CN |
| dax30 | 513030.SS | 德国30 | CN |
| gold | 518880.SS | 黄金ETF | CN |
| govtbond30 | 511090.SS | 30年国债 | CN |

---

### `resolve_predefined(name)`

根据预定义名称获取 `(ticker, label)`。

```python
ticker, label = resolve_predefined("csi300")
# ("510300.SS", "沪深300")
```

---

### `set_cache_dir(path)`

设置缓存目录路径（默认在 `scripts/../.cache/`）。

```python
set_cache_dir("/path/to/custom/cache")
```

## 完整示例

```python
import sys
import pandas as pd
from datetime import date

sys.path.insert(0, "skills/finance-data/scripts")
from finance_lib import fetch_multiple, to_csv

# 拉取沪深300和标普500数据
specs = [
    ("510300.SS", "沪深300"),
    ("SPY", "标普500"),
]
df = fetch_multiple(specs, date(2020, 1, 1), date(2024, 12, 31))

# 计算每日收益率
returns = df.pct_change().dropna()

# 相关性
corr = df.corr()

# 保存
to_csv(df, "data.csv")
```
