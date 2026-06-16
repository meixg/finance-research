# backtest_core API 参考

`backtest_core.py` 提供纯回测函数库——**不含数据拉取**，数据获取请使用 `finance-data` skill 的 `finance_lib`。

## 安装依赖

```bash
pip install pandas numpy matplotlib
```

> `yfinance` 由 finance-data skill 使用，本 skill 的直接依赖仅为 pandas + numpy + matplotlib。

## 完整使用流程

```python
import sys
from datetime import date

# ── 第一步：用 finance-data 拉取数据 ──
sys.path.insert(0, "skills/finance-data/scripts")
from finance_lib import fetch_data

df = fetch_data("510300.SS", date(2018, 1, 1), date(2024, 12, 31))

# ── 第二步：用 dca-backtest 执行回测 ──
sys.path.insert(0, "skills/dca-backtest/scripts")
from backtest_core import run_backtest_on_df, plot_single, save_records

label, records, df, metrics = run_backtest_on_df(
    df=df, start=date(2018, 1, 1), end=date(2024, 12, 31),
    amount=2000, dayofweek=1, fee_rate=0.001, label="沪深300",
)

print(f"收益率: {metrics['return_rate']*100:.2f}%")
print(f"年化:   {metrics['annualized_return']*100:.2f}%")

# 保存明细 + 绘图
save_records(records, "trades.csv")
plot_single(records, df, metrics, "沪深300", save_path="chart.png")
```

## 函数参考

### 日期工具

#### `generate_invest_dates(start, end, dayofweek)`

生成定投日期列表。遇到非交易日自动顺延到下一个交易日。

| 参数 | 类型 | 说明 |
|------|------|------|
| start | date | 起始日期 |
| end | date | 结束日期 |
| dayofweek | int | 定投星期几，0=周一…6=周日 |

返回: `List[date]`

#### `parse_date(s)`

解析 `"YYYY-MM-DD"` 格式的日期字符串为 date 对象。

---

### 回测引擎

#### `run_backtest(df, invest_dates, amount, fee_rate)`

执行定投回测（低阶 API，需自行生成定投日期）。

| 参数 | 类型 | 说明 |
|------|------|------|
| df | pd.DataFrame | 含 `adj_close` 列，index 为 date |
| invest_dates | List[date] | 定投日期列表 |
| amount | float | 每次定投金额 |
| fee_rate | float | 申购费率 |

返回: `List[TradeRecord]`

#### `run_backtest_on_df(df, start, end, amount, dayofweek, fee_rate, label, verbose)`

高阶 API——自动生成定投日期、执行回测、计算指标（**数据需提前通过 finance-data 获取**）。

| 参数 | 说明 |
|------|------|
| df | 含 `adj_close` 列的 DataFrame |
| start / end | 回测起止日期 |
| amount | 每次定投金额 |
| dayofweek | 定投星期几 |
| fee_rate | 申购费率 |
| label | 标的名称（仅用于显示） |
| verbose | 是否打印详细信息 |

返回: `(label, records, df, metrics)`

---

### 指标计算

#### `calculate_metrics(records, final_price, start, end)`

从交易记录计算回测指标返回字典：

| 字段 | 说明 |
|------|------|
| start_date | 回测起始日 |
| end_date | 回测结束日 |
| invest_count | 定投次数 |
| total_cost | 总投入成本 |
| total_shares | 持有总份额 |
| final_price | 期末净值 |
| final_value | 期末总市值 |
| total_profit | 累计盈亏 |
| return_rate | 定投收益率 |
| annualized_return | 年化收益率（XIRR） |
| lump_sum_return | 同期一次性投入收益率 |

#### `calculate_xirr(cash_flows)`

使用牛顿法计算 XIRR。`cash_flows: [(金额, date)]`，流出为负，流入为正。

---

### 输出

| 函数 | 说明 |
|------|------|
| `print_result(metrics, label)` | 打印格式化回测结果 |
| `print_comparison(results)` | 打印多标的对比汇总表 |
| `save_records(records, path)` | 保存交易明细为 CSV |

### 绘图

| 函数 | 说明 |
|------|------|
| `plot_single(records, df, metrics, label, save_path)` | 绘制成本 vs 市值曲线 |
| `plot_comparison(all_results, save_path)` | 绘制多标市值对比曲线 |

`all_results` 格式: `List[Tuple[str, List[TradeRecord], pd.DataFrame, dict]]`

---

## 数据结构

```python
@dataclass
class TradeRecord:
    date: date
    price: float
    invest_amount: float
    fee: float
    shares: float
    total_shares: float
    total_cost: float
```

---

## 数据拉取参考

数据获取请使用 `skills/finance-data/scripts/finance_lib.py`，主要函数：

```python
from finance_lib import fetch_data, fetch_multiple, PREDEFINED_TICKERS

# 单标
df = fetch_data("SPY", start, end)

# 多标
df = fetch_multiple([("SPY", "标普500"), ("510300.SS", "沪深300")], start, end)
```

详见 `skills/finance-data/references/api.md`。
