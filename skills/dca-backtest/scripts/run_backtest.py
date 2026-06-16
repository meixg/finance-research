#!/usr/bin/env python3
"""
run_backtest.py — 定投回测统一入口

数据拉取委托给 finance-data skill 的 finance_lib 模块，
回测逻辑使用本 skill 的 backtest_core 模块。

用法:
    # 单标的
    python run_backtest.py --index csi300

    # 多标的对比
    python run_backtest.py --index csi300,sp500,hsi

    # 自定义 ticker
    python run_backtest.py --tickers "510300.SS:沪深300,SPY:标普500,2800.HK:恒生指数"

    # 自定义参数
    python run_backtest.py --index csi300,sp500 \\
        --start 2015-01-01 --end 2024-12-31 \\
        --amount 2000 --invest-dayofweek 3 --fee-rate 0.001 \\
        --save-plot comparison.png --output trades.csv
"""

import argparse
import os
import sys
from datetime import date, datetime
from typing import List, Tuple

# 回测引擎
from backtest_core import (
    run_backtest_on_df,
    print_comparison,
    save_records,
    plot_single,
    plot_comparison,
    parse_date,
)

# 数据拉取（finance-data skill）
FINANCE_LIB_PATH = os.path.join(
    os.path.dirname(__file__),  # skills/dca-backtest/scripts/
    "..", "..", "finance-data", "scripts",
)
sys.path.insert(0, os.path.abspath(FINANCE_LIB_PATH))

from finance_lib import (
    PREDEFINED_TICKERS,
    fetch_data,
    fetch_multiple,
    resolve_predefined,
)


def resolve_ticker_list(
    tickers_arg: str = None,
    index_arg: str = None,
) -> List[Tuple[str, str]]:
    """
    解析 --tickers 或 --index 参数，返回 [(ticker, label), ...]。
    """
    if tickers_arg:
        result = []
        for part in tickers_arg.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                ticker, label = part.split(":", 1)
                result.append((ticker.strip(), label.strip()))
            else:
                result.append((part, part))
        return result

    if index_arg:
        names = [x.strip().lower() for x in index_arg.split(",")]
        if "all" in names:
            names = list(PREDEFINED_TICKERS.keys())

        result = []
        for key in names:
            if key in PREDEFINED_TICKERS:
                cfg = PREDEFINED_TICKERS[key]
                result.append((cfg["ticker"], cfg["name"]))
            else:
                print(
                    f"警告: 未知标的 '{key}'，跳过。"
                    f"可选: {', '.join(PREDEFINED_TICKERS.keys())}",
                    file=sys.stderr,
                )
        return result

    return []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="定投回测工具（红利再投资）— 支持单标回测与多标对比",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单标的
  python run_backtest.py --index csi300

  # 多标的对比
  python run_backtest.py --index csi300,sp500,hsi

  # 自定义 ticker 和标签
  python run_backtest.py --tickers "510300.SS:沪深300,SPY:标普500"

  # 全部预定义标的
  python run_backtest.py --index all

  # 完整参数
  python run_backtest.py --index csi300 --start 2015-01-01 --end 2024-12-31 \\
      --amount 2000 --invest-dayofweek 3 --fee-rate 0.001 \\
      --save-plot chart.png --output trades.csv
        """,
    )
    parser.add_argument(
        "-t", "--tickers",
        type=str,
        default=None,
        help=(
            "Yahoo Finance 代码，多个用逗号分隔，可带标签。"
            ' 如 "510300.SS:沪深300,SPY:标普500"'
        ),
    )
    parser.add_argument(
        "-i", "--index",
        type=str,
        default=None,
        help=(
            "预定义标的名（逗号分隔）。可选: "
            + ", ".join(PREDEFINED_TICKERS.keys())
            + ", all"
        ),
    )
    parser.add_argument(
        "--start",
        type=parse_date,
        default=date(2018, 1, 1),
        help="回测起始日期，格式 YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        type=parse_date,
        default=date.today(),
        help="回测结束日期，格式 YYYY-MM-DD",
    )
    parser.add_argument(
        "--amount",
        type=float,
        default=1000.0,
        help="每次定投金额（元）",
    )
    parser.add_argument(
        "--invest-dayofweek",
        type=int,
        default=1,
        help="定投星期几，0=周一，1=周二，...，6=周日",
    )
    parser.add_argument(
        "--fee-rate",
        type=float,
        default=0.0,
        help="申购费率（如 0.001 = 0.1%%）",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="不绘制收益曲线图",
    )
    parser.add_argument(
        "--save-plot",
        type=str,
        default=None,
        help="将曲线图保存为图片文件（如 chart.png）",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="交易明细 CSV 输出路径（多标的自动加后缀）",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.tickers and not args.index:
        parser.print_help()
        print("\n错误: 请指定 --tickers 或 --index。", file=sys.stderr)
        return 1

    if args.start >= args.end:
        print("错误：起始日期必须早于结束日期。", file=sys.stderr)
        return 1

    if not 0 <= args.invest_dayofweek <= 6:
        print("错误：--invest-dayofweek 必须在 0~6 之间。", file=sys.stderr)
        return 1

    # ── 第一步：解析标的 ──
    ticker_list = resolve_ticker_list(args.tickers, args.index)
    if not ticker_list:
        print("错误：未解析出有效的标的。", file=sys.stderr)
        return 1

    labels = [label for _, label in ticker_list]
    print(f"\n{'=' * 50}")
    print(f"  定投回测 — {', '.join(labels)}")
    print(f"  区间: {args.start} ~ {args.end}")
    print(f"  每期 {args.amount:,.0f} 元，费率 {args.fee_rate * 100:.2f}%")
    print(f"{'=' * 50}")

    # ── 第二步：使用 finance-data 拉取数据 ──
    print(f"\n{'─' * 50}")
    print(f"  📥 数据获取（finance-data skill）")
    print(f"{'─' * 50}")

    # 逐个标的获取数据
    data_frames: List[Tuple[str, str, pd.DataFrame]] = []
    for ticker, label in ticker_list:
        try:
            df = fetch_data(ticker, args.start, args.end)
            data_frames.append((ticker, label, df))
        except Exception as e:
            print(f"  ❌ {label} ({ticker}) 获取失败: {e}", file=sys.stderr)

    if not data_frames:
        print("错误：未获取到任何有效数据。", file=sys.stderr)
        return 1

    # ── 第三步：使用 backtest_core 执行回测 ──
    print(f"\n{'─' * 50}")
    print(f"  🔄 执行回测")
    print(f"{'─' * 50}")

    all_results: List[Tuple[str, List, object, dict]] = []

    for ticker, label, df in data_frames:
        result = run_backtest_on_df(
            df=df,
            start=args.start,
            end=args.end,
            amount=args.amount,
            dayofweek=args.invest_dayofweek,
            fee_rate=args.fee_rate,
            label=label,
        )
        if result[1]:  # 有交易记录
            all_results.append(result)

        # 单标的输出 CSV
        if args.output and len(data_frames) == 1 and result[1]:
            save_records(result[1], args.output)

    # 多标的输出 CSV（加后缀区分）
    if args.output and len(data_frames) > 1:
        base, ext = os.path.splitext(args.output)
        for label, records, _, _ in all_results:
            if records:
                path = f"{base}_{label}{ext}"
                save_records(records, path)

    # ── 第四步：对比汇总 + 绘图 ──
    comparison_data = [(label, m) for label, _, _, m in all_results if m]
    if len(comparison_data) > 1:
        print_comparison(comparison_data)

    do_plot = not args.no_plot
    if do_plot or args.save_plot:
        if len(all_results) == 1:
            label, records, df_, metrics_ = all_results[0]
            plot_single(records, df_, metrics_, label, args.save_plot)
        elif len(all_results) > 1:
            plot_comparison(all_results, args.save_plot)
        else:
            print("没有可绘图的回测结果。")

    print("\n✅ 回测完成！\n")
    return 0


if __name__ == "__main__":
    # 确保能找到 finance_lib
    sys.path.insert(0, os.path.abspath(FINANCE_LIB_PATH))
    import pandas as pd
    main()
