#!/usr/bin/env python3
"""
fetch_data.py — 金融数据拉取 CLI

从 Yahoo Finance 拉取历史行情数据（复权收盘价），支持本地缓存。

用法:
    # 拉取单个标的
    python fetch_data.py --tickers 510300.SS:沪深300

    # 拉取多个标的对比
    python fetch_data.py --tickers "510300.SS:沪深300,SPY:标普500,2800.HK:恒生指数"

    # 指定日期范围
    python fetch_data.py --tickers SPY --start 2020-01-01 --end 2024-12-31

    # 输出到 CSV
    python fetch_data.py --tickers SPY --output sp500_data.csv

    # 使用预定义标的名
    python fetch_data.py --index csi300,sp500,hsi

    # 命令行查看数据概览
    python fetch_data.py --tickers SPY --summary
"""

import argparse
import sys
from datetime import date, datetime

from finance_lib import (
    PREDEFINED_TICKERS,
    fetch_data,
    fetch_multiple,
    to_csv,
)


def parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"无效日期格式: {s}，请使用 YYYY-MM-DD")


def parse_ticker_spec(spec: str):
    """解析 "--tickers" 参数值，返回 [(ticker, label), ...]"""
    result = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            ticker, label = part.split(":", 1)
            result.append((ticker.strip(), label.strip()))
        else:
            result.append((part, part))
    return result


def resolve_index_names(names_str: str):
    """解析 "--index" 参数值，返回 [(ticker, label), ...]"""
    names = [x.strip().lower() for x in names_str.split(",")]
    if "all" in names:
        names = list(PREDEFINED_TICKERS.keys())

    result = []
    for key in names:
        if key in PREDEFINED_TICKERS:
            cfg = PREDEFINED_TICKERS[key]
            result.append((cfg["ticker"], cfg["name"]))
        else:
            print(
                f"警告: 未知标的 '{key}'，跳过。可选: {', '.join(PREDEFINED_TICKERS.keys())}",
                file=sys.stderr,
            )
    return result


def build_parser():
    parser = argparse.ArgumentParser(
        description="金融数据拉取工具 — 从 Yahoo Finance 获取历史行情数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单标的
  python fetch_data.py --tickers 510300.SS:沪深300

  # 多标的对比
  python fetch_data.py --tickers "510300.SS:沪深300,SPY:标普500,2800.HK:恒生指数"

  # 使用预定义名
  python fetch_data.py --index csi300,sp500,hsi

  # 全部预定义标的
  python fetch_data.py --index all

  # 指定日期范围输出 CSV
  python fetch_data.py --tickers SPY --start 2020-01-01 --end 2024-12-31 --output spy.csv
        """,
    )
    parser.add_argument(
        "-t", "--tickers",
        type=str,
        default=None,
        help=(
            "Yahoo Finance 代码，多个用逗号分隔，可带标签（冒号分隔）。"
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
            + ", all。与 --tickers 二选一。"
        ),
    )
    parser.add_argument(
        "--start",
        type=parse_date,
        default=date(2020, 1, 1),
        help="起始日期，格式 YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        type=parse_date,
        default=date.today(),
        help="结束日期，格式 YYYY-MM-DD",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="输出 CSV 文件路径（可选）",
    )
    parser.add_argument(
        "-s", "--summary",
        action="store_true",
        help="打印数据概览（行数、日期范围、统计信息）",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.tickers and not args.index:
        parser.print_help()
        print("\n错误: 请指定 --tickers 或 --index。", file=sys.stderr)
        return 1

    if args.start >= args.end:
        print("错误: 起始日期必须早于结束日期。", file=sys.stderr)
        return 1

    # 解析标的列表
    if args.tickers:
        ticker_list = parse_ticker_spec(args.tickers)
    else:
        ticker_list = resolve_index_names(args.index)

    if not ticker_list:
        print("错误: 未解析出有效的标的。", file=sys.stderr)
        return 1

    labels = [label for _, label in ticker_list]
    print(f"📊 金融数据拉取 — {', '.join(labels)}")
    print(f"📅 区间: {args.start} ~ {args.end}")
    print()

    # 拉取数据
    if len(ticker_list) == 1:
        ticker, label = ticker_list[0]
        df = fetch_data(ticker, args.start, args.end)
    else:
        df = fetch_multiple(ticker_list, args.start, args.end)

    print(f"\n✅ 数据就绪！共 {len(df)} 个交易日")

    # 输出概览
    if args.summary:
        print(f"\n📈 数据概览:")
        print(f"   行数: {len(df)}")
        print(f"   日期范围: {df.index[0]} ~ {df.index[-1]}")
        print(f"\n   描述统计:")
        print(df.describe())
        print(f"\n   前5行:")
        print(df.head())
        print(f"\n   后5行:")
        print(df.tail())

    # 输出 CSV
    if args.output:
        path = to_csv(df, args.output)
        print(f"\n📁 数据已保存至: {path}")

    # 如果没有指定 --summary 也没有 --output，默认打印前10行
    if not args.summary and not args.output:
        print(f"\n   前10行:")
        print(df.head(10))
        print(f"\n   (共 {len(df)} 行。使用 --output 保存为 CSV 或 --summary 查看概览)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
