---
name: finance-data
description: 金融数据拉取与缓存。当用户需要拉取股票/ETF/指数的历史行情数据（如日K线、收盘价、复权价），查询某个标的的历史价格，获取金融时间序列数据做分析/回测/可视化时使用。支持主流中国市场（沪深300ETF等）、美股市场（SPY、VXUS等）、港股市场（盈富基金等）以及任意 Yahoo Finance 可查的标的。请优先使用此 skill，不要自己写爬虫或手动下载数据。
---

# Finance Data — 金融数据拉取 Skill

提供从 Yahoo Finance 拉取历史行情数据并本地缓存的能力。支持任意 Yahoo Finance 可查的股票/ETF/指数代码。

## 依赖

运行脚本前需安装依赖：

```bash
pip install yfinance pandas numpy
```

## 快速开始

### 核心功能

本 skill 通过 `scripts/fetch_data.py` 提供以下能力：

1. **拉取单标的历史数据** — 指定 ticker、起始/结束日期，获取日线 Adjusted Close 数据
2. **拉取多标的数据** — 同时获取多个标的，统一输出
3. **本地缓存** — 数据首次下载后缓存到 `.cache/`，后续优先读取
4. **数据输出** — 输出为 pandas DataFrame 或 CSV 文件

### 用法

```bash
python scripts/fetch_data.py --tickers 510300.SS:沪深300,SPY:标普500 --start 2020-01-01 --end 2024-12-31
```

### 推荐的工作流程

1. 先确定用户需要哪些标的（ticker 代码）和日期范围
2. 运行 `fetch_data.py` 获取数据
3. 将返回的 CSV/DataFrame 用于后续分析、绘图或回测

## 常用 Ticker 速查

| 描述 | Ticker | 说明 |
|------|--------|------|
| 沪深300 ETF | 510300.SS | 华泰柏瑞沪深300ETF |
| 标普500 ETF | SPY | SPDR S&P 500 ETF |
| 纳斯达克100 ETF | 513100.SS | 国泰纳斯达克100ETF |
| 恒生指数 ETF | 2800.HK | 盈富基金 |
| 恒生科技 ETF | 3032.HK | 恒生科技指数ETF |
| 全球除美 | VXUS | Vanguard Total International Stock ETF |
| 创业板50 ETF | 159949.SZ | 华安创业板50ETF |
| 科创50 ETF | 588000.SS | 华夏科创50ETF |
| 中概互联 ETF | 513050.SS | 易方达中概互联ETF |
| 日经225 ETF | 513000.SS | 华夏日经225ETF |
| 德国30 ETF | 513030.SS | 华安德国30ETF |
| 黄金 ETF | 518880.SS | 华安黄金ETF |
| 30年国债 ETF | 511090.SS | 鹏扬30年国债ETF |

> 如需查询其他未列出的 ticker，可让用户提供代码，或使用通用搜索。

## 数据拉取函数库

本 skill 也提供 Python 函数库 `scripts/finance_lib.py`，可在分析脚本中直接 import 使用。详情见 `references/api.md`。

## 输出格式

数据输出为 CSV，包含以下字段：

- **date**: 交易日期
- **adj_close**: 复权收盘价（已折算分红/拆股）
- 多标的时每个标的占一列，列名为 `{label}_adj_close`

## 数据说明

- 使用 Yahoo Finance 的 `auto_adjust=True`，返回的价格已复权（含分红、拆股调整）
- 数据只在首次拉取时从网络下载，后续优先使用本地 `.cache/` 目录中的缓存
- 缓存文件名规则：`.cache/{ticker}.pkl`（特殊字符替换为下划线）

## 回测集成

如需执行定投回测等分析，可与本 skill 的输出配合使用：

1. 先用本 skill 拉取数据（输出 CSV 或直接获取 DataFrame）
2. 在后续分析脚本中读取数据进行计算
3. 可参考 `scripts/dca_core_example.py` 示例

## 常见场景

### 场景一：用户想知道某只股票/ETF 的历史价格

1. 确认 ticker 代码（使用上表或询问用户）
2. 确认日期范围
3. 运行 `fetch_data.py` 获取数据
4. 用数据回答用户问题或做进一步分析

### 场景二：对比多个标的的历史走势

1. 收集所有待对比标的的 ticker
2. 用 `--tickers` 参数一次性拉取
3. 输出包含所有标的的 CSV，可用于后续绘图或分析

### 场景三：本地已有缓存，用户想查最新数据

1. 缓存会判断是否覆盖请求区间
2. 如果缓存未覆盖最新日期，自动从 Yahoo Finance 补充下载
3. 用户无需手动清理缓存
