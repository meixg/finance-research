# AGENTS.md

This file provides guidance to any coding agent when working with code in this repository.

## Overview

finance-research 是一个金融数据分析项目，提供两个可复用的 AI agent skill：

| Skill | 目录 | 功能 |
|-------|------|------|
| **finance-data** | `skills/finance-data/` | 从 Yahoo Finance 拉取股票/ETF/指数历史行情数据，本地缓存 |
| **dca-backtest** | `skills/dca-backtest/` | 定投（DCA）回测引擎，计算收益率、年化收益率（XIRR），生成收益曲线图 |

两个 skill 的关系：**dca-backtest 依赖于 finance-data 获取行情数据**，回测逻辑本身不包含数据拉取。

## Skill 加载机制

Skills 注册在 `skills-lock.json` 中，会被自动加载到 `.agents/skills/`、`.claude/skills/`、`.pi/skills/`、`.trae-cn/skills/` 等目录。

**`skills/` 目录是唯一的数据源**，其他目录（`.agents/skills/` 等）都是通过以下命令注册添加的引用或副本：

```bash
npx skills add ./skills -y
```

该命令会扫描 `skills/` 下的每个子目录，将其注册到 `skills-lock.json` 并同步到各 agent 工具对应的目录中。编辑 skill 时请始终修改 `skills/` 下的源文件，然后重新执行该命令更新注册。

## 运行依赖

```bash
pip install yfinance pandas numpy matplotlib
```

## 可用命令

### 数据拉取（finance-data）

```bash
# 单标的
python skills/finance-data/scripts/fetch_data.py --tickers 510300.SS:沪深300

# 多标的
python skills/finance-data/scripts/fetch_data.py --tickers "510300.SS:沪深300,SPY:标普500" --output data.csv --summary
```

### 定投回测（dca-backtest）

```bash
# 单标的回测
python skills/dca-backtest/scripts/run_backtest.py --index csi300

# 多标的对比回测
python skills/dca-backtest/scripts/run_backtest.py --index csi300,sp500,hsi

# 自定义参数 + 保存折线图
python skills/dca-backtest/scripts/run_backtest.py --index csi300 \
    --start 2015-01-01 --end 2024-12-31 \
    --amount 2000 --invest-dayofweek 3 --fee-rate 0.001 \
    --save-plot chart.png --output trades.csv
```

## 代码架构

```
skills/
├── finance-data/                          # 数据拉取 skill
│   ├── SKILL.md                           # skill 描述与使用指南
│   ├── scripts/
│   │   ├── finance_lib.py                 # 核心函数库（可 import）
│   │   └── fetch_data.py                  # CLI 入口
│   └── references/
│       └── api.md                         # API 参考文档
│
└── dca-backtest/                          # 回测 skill
    ├── SKILL.md                           # skill 描述与使用指南
    ├── scripts/
    │   ├── backtest_core.py               # 纯回测引擎（不含数据拉取）
    │   └── run_backtest.py                # CLI 入口（编排 finance-data + 回测）
    └── references/
        └── api.md                         # API 参考文档
```

### 数据流

```
finance_lib.fetch_data(ticker, start, end)
        │
        ▼ 返回 pd.DataFrame (index=date, columns=[adj_close])
        │
backtest_core.run_backtest_on_df(df, start, end, amount, ...)
        │
        ▼ 返回 (label, records, df, metrics)
        │
    plot_single / plot_comparison  ──→ 折线图
    print_result / print_comparison  ──→ 终端输出
    save_records  ──→ CSV 文件
```

### 关键设计原则

1. **职责分离**：`finance-data` 只负责数据获取与缓存；`dca-backtest` 只负责回测逻辑与绘图
2. **纯函数式回测引擎**：`backtest_core.py` 的入口函数 `run_backtest_on_df()` 接收已准备好的 DataFrame，不接触网络或文件 I/O
3. **本地缓存**：数据首次下载后缓存到 `skills/finance-data/.cache/`，避免重复下载
4. **复权价格**：使用 Yahoo Finance 的 `auto_adjust=True`，价格已折算分红/拆股

## 代码风格指南

- Python 3.12+，类型注解（`typing` 模块）
- 函数参数用类型注解，返回值标注类型
- CLI 脚本用 `argparse` 解析参数
- 使用 `@dataclass` 定义纯数据类（如 `TradeRecord`）
- 中文字段名用于用户可见输出（CSV 列名、打印内容），内部变量用英文
- 文件编码统一使用 `utf-8-sig`（兼容 Excel 打开 CSV）
- 绘图使用 matplotlib，自动配置中文字体

## 预定义标的清单

| 简称 | Ticker | 名称 | 市场 |
|------|--------|------|------|
| csi300 | 510300.SS | 沪深300 | CN |
| sp500 | SPY | 标普500 | US |
| hsi | 2800.HK | 恒生指数 | HK |
| vxus | VXUS | 全球除美 | US |
| cninet | 513050.SS | 中概互联 | CN |
| gem50 | 159949.SZ | 创业板50 | CN |
| star50 | 588000.SS | 科创50 | CN |
| gold | 518880.SS | 黄金ETF | CN |
| nasdaq100 | 513100.SS | 纳斯达克100 | CN |
| hstech | 3032.HK | 恒生科技 | HK |
| nikkei225 | 513000.SS | 日经225 | CN |
| dax30 | 513030.SS | 德国30 | CN |
| govtbond30 | 511090.SS | 30年国债 | CN |

## 回测指标说明

| 指标 | 计算方式 |
|------|----------|
| 定投收益率 | `(期末总值 - 总投入) / 总投入` |
| 年化收益率 (XIRR) | 使用牛顿法求解现金流内部收益率，考虑每笔资金的时间价值 |
| 一次性投入收益率 | 期初一次性买入相同金额、持有到期末的收益率（对比基准） |

## 研究工作流

每次发起新的 research 时，遵循以下标准化工作流程：

### 步骤一：创建工作目录

在 `projects/` 目录下创建一个以研究主题命名的文件夹：

```bash
mkdir -p projects/<research-topic-name>
cd projects/<research-topic-name>
```

文件夹名称应简短、有描述性（如 `csi300-dca-analysis`、`sp500-vs-hsi-comparison`）。

### 步骤二：记录研究过程

在文件夹中创建 `notes.md`，在研究过程中持续追加记录：

- 尝试过的思路和方法（包括失败的）
- 关键发现和数据来源
- 遇到的问题和解决方案
- 临时的代码片段或中间结果
- 任何值得记录的 learnings

```markdown
# Research Notes: <主题>

## 2024-06-16
- 尝试了 XXX 方法，但发现数据缺失...
- 改用 YYY 方法后解决
- 关键发现：...
```

### 步骤三：完成研究报告

研究结束后，在文件夹中生成两份报告：

1. **`README.md`** — 简洁的研究报告，包含背景、方法、结果、结论，适合直接在 GitHub 浏览
2. **`index.html`** — 详细的 HTML 页面报告（可包含图表、表格、交互元素等），自包含（无外部依赖）

### 步骤四：提交代码

提交时只包含研究过程中**新创建的文件**，不要包含研究过程中拉取的已有仓库的完整副本。

**提交包含：**

- `notes.md` — 研究过程记录
- `README.md` — 研究报告
- `index.html` — 详细 HTML 报告
- 研究中编写的任何代码文件（`.py`、`.js` 等）
- 如果改动了已有仓库的代码，用 `git diff` 生成 patch 文件保存为 `.patch`，而不是提交整个仓库副本
- 适当的小型二进制文件（如图表图片），不超过 2MB

**不要包含：**

- 拉取的已有仓库的完整代码副本
- 临时文件或中间产物（`.pyc`、`__pycache__` 等）
- 超过 2MB 的二进制文件

### 最终目录结构示例

```
projects/
└── csi300-dca-analysis/
    ├── notes.md              # 研究过程记录
    ├── README.md              # 研究报告
    ├── index.html             # 详细 HTML 报告
    ├── fetch_data.py          # 编写的代码
    ├── analysis.py            # 编写的代码
    └── chart.png              # 生成的图表（< 2MB）
```

## 重要提示

- **不要直接编辑 `.agents/`、`.claude/`、`.pi/`、`.trae-cn/` 下的 skill 副本**，请始终修改 `skills/` 下的源文件
- 数据缓存目录 `skills/finance-data/.cache/` 已被 `.gitignore` 忽略，不会提交到版本控制
- 修改 skill 后如需更新注册，运行 `npx skills add ./skills/<skill-name>` 或手动更新 `skills-lock.json` 中的 hash
