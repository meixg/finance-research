---
name: dca-backtest
description: 定投回测分析工具。当用户需要对股票/ETF/指数做定投回测，计算历史收益率、年化收益率（XIRR），对比不同定投策略效果，或生成回测收益曲线图时使用。支持自定义定投金额、频率、费率、起止时间、多标的对比。这是金融数据分析的必备补充——只要用户提到"回测"、"定投回测"、"定投收益"、"历史回测"，都应触发此 skill。
---

# DCA Backtest — 定投回测 Skill

提供基于历史行情数据的定投策略回测引擎。**数据获取委托给 finance-data skill**，本 skill 专注于回测逻辑。

## 依赖

```bash
pip install yfinance pandas numpy matplotlib
```

> `yfinance` 由 finance-data skill 的数据拉取使用，本 skill 直接依赖 pandas + numpy + matplotlib。

## 快速开始

```bash
# 单标的回测
python scripts/run_backtest.py --index csi300

# 多标的对比回测
python scripts/run_backtest.py --index csi300,sp500,hsi

# 自定义参数
python scripts/run_backtest.py --index csi300 \
    --start 2015-01-01 --end 2024-12-31 \
    --amount 2000 --invest-dayofweek 3 --fee-rate 0.001
```

## 核心功能

### 回测引擎

本 skill 由两个模块组成：

| 模块 | 路径 | 负责 |
|------|------|------|
| **数据拉取** | `skills/finance-data/scripts/finance_lib.py` | 从 Yahoo Finance 下载数据，本地缓存 |
| **回测引擎** | `scripts/backtest_core.py` | 日期生成、定投回测、指标计算、绘图 |
| **CLI 入口** | `scripts/run_backtest.py` | 编排数据获取+回测流程 |

工作流程：

```
finance_lib.fetch_data()  ──→  backtest_core.run_backtest_on_df()  ──→  plot / CSV输出
```

### 主要能力

1. **单标的定投回测** — 指定标的、起止日期、定投金额和频率，输出完整回测结果
2. **多标的对比回测** — 同时回测多个标的，输出对比汇总表和合并曲线图
3. **红利再投资** — 使用 Yahoo Finance 复权收盘价（Adjusted Close），自动折算分红/拆股
4. **年化收益率 (XIRR)** — 使用牛顿法计算现金流内部收益率
5. **一次性投入对比** — 同时计算"期初一次性买入"的收益率做对比
6. **收益曲线图** — 绘制投入成本 vs 账户市值曲线
7. **交易明细 CSV** — 输出每次定投的详细记录

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-t, --tickers` | — | Yahoo Finance 代码，多个用逗号分隔，可带标签 |
| `-i, --index` | — | 预定义标的名: csi300,sp500,hsi,vxus,cninet,all |
| `--start` | 2018-01-01 | 回测起始日期 |
| `--end` | 今天 | 回测结束日期 |
| `--amount` | 1000 | 每次定投金额（元） |
| `--invest-dayofweek` | 1 (周二) | 定投星期几，0=周一…6=周日 |
| `--fee-rate` | 0 | 申购费率（如 0.001 = 0.1%） |
| `--no-plot` | — | 不绘图 |
| `--save-plot` | — | 折线图保存为图片文件 |
| `--output` | — | 交易明细 CSV 保存路径 |

> Ticker 预定义列表同 finance-data skill（csi300/sp500/hsi/vxus/cninet/gem50/star50/gold 等 13 个）。

## 回测流程

### 步骤一：拉取数据

CLI 自动调用 `finance_lib.fetch_data()` 从 Yahoo Finance 下载指定标的的复权收盘价数据，并使用本地缓存避免重复下载。

### 步骤二：执行回测

1. 生成定投日期列表（按指定星期几，顺延到最近交易日）
2. 在每个定投日按收盘价买入，扣除申购费
3. 记录每笔交易的份额、累计份额、累计成本
4. 计算期末总资产、总盈亏、收益率

### 步骤三：查看结果

输出包含：
- 回测区间、定投次数、总投入成本
- 期末总资产、累计盈亏
- 定投收益率、年化收益率（XIRR）
- 同期一次性投入收益率（对比基准）
- 收益曲线图（成本 vs 市值）

## 常见场景

### 场景一：回测单个标的的定投收益

```bash
python scripts/run_backtest.py --index csi300 \
    --start 2018-01-01 --end 2024-12-31 \
    --amount 2000
```

### 场景二：对比不同标的的定投表现

```bash
python scripts/run_backtest.py \
    --tickers "510300.SS:沪深300,SPY:标普500,2800.HK:恒生指数" \
    --start 2018-01-01 --end 2024-12-31 \
    --save-plot comparison.png
```

### 场景三：调整定投策略参数

```bash
python scripts/run_backtest.py --index csi300 \
    --start 2018-01-01 --amount 5000 --invest-dayofweek 0 --fee-rate 0.0015
```

## Python API 使用（不经过 CLI）

```python
import sys
from datetime import date

# 1. 导入数据拉取（finance-data）
sys.path.insert(0, "skills/finance-data/scripts")
from finance_lib import fetch_data

# 2. 导入回测引擎（dca-backtest）
sys.path.insert(0, "skills/dca-backtest/scripts")
from backtest_core import run_backtest_on_df, plot_single

# 3. 获取数据
df = fetch_data("510300.SS", date(2018, 1, 1), date(2024, 12, 31))

# 4. 执行回测
label, records, df, metrics = run_backtest_on_df(
    df=df, start=date(2018, 1, 1), end=date(2024, 12, 31),
    amount=2000, dayofweek=1, fee_rate=0.001, label="沪深300",
)

# 5. 绘图
plot_single(records, df, metrics, "沪深300", save_path="chart.png")
```

详见 `references/api.md`。

## 结果解读

- **定投收益率**: `(期末总值 - 总投入) / 总投入`
- **年化收益率 (XIRR)**: 考虑每笔现金流的实际时间价值的内部收益率
- **一次性投入收益率**: 期初一次性买入、持有到期末的收益率（对比基准）
