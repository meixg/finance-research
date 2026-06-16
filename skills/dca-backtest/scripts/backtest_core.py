#!/usr/bin/env python3
"""
backtest_core — 定投回测核心函数库

纯回测引擎，不包含数据拉取逻辑。
数据获取请使用 finance-data skill 的 finance_lib。
"""

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ── 数据类型 ─────────────────────────────────────────────────────
@dataclass
class TradeRecord:
    date: date
    price: float          # 当日 Adjusted Close
    invest_amount: float  # 定投金额
    fee: float            # 申购费
    shares: float         # 本次买入份额
    total_shares: float   # 累计份额
    total_cost: float     # 累计投入成本


# ── 日期工具 ─────────────────────────────────────────────────────
def parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"无效日期格式: {s}，请使用 YYYY-MM-DD")


def align_to_trading_day(target: date, trading_days: pd.DatetimeIndex) -> Optional[date]:
    """把目标日期顺延到最近的交易日。"""
    while target not in trading_days:
        target += timedelta(days=1)
        if target > trading_days[-1]:
            return None
    return target


def generate_invest_dates(start: date, end: date, dayofweek: int) -> List[date]:
    """
    生成回测区间内的定投日期列表（按星期几）。
    若目标日为节假日/非交易日，自动顺延到下一个交易日。
    """
    dates: List[date] = []
    current = start
    while current.weekday() != dayofweek:
        current += timedelta(days=1)
    while current <= end:
        dates.append(current)
        current += timedelta(days=7)
    return dates


# ── 回测引擎 ─────────────────────────────────────────────────────
def run_backtest(
    df: pd.DataFrame,
    invest_dates: List[date],
    amount: float,
    fee_rate: float,
) -> List[TradeRecord]:
    """
    执行定投回测。

    Args:
        df: 包含 'adj_close' 列的 DataFrame，index 为 date
        invest_dates: 定投日期列表（由 generate_invest_dates 生成）
        amount: 每次定投金额
        fee_rate: 申购费率（如 0.001 = 0.1%）

    Returns:
        交易记录列表
    """
    trading_days = df.index
    records: List[TradeRecord] = []
    total_shares = 0.0
    total_cost = 0.0

    for d in invest_dates:
        tradeday = align_to_trading_day(d, trading_days)
        if tradeday is None:
            continue

        price = float(df.loc[tradeday, "adj_close"])
        fee = amount * fee_rate
        net_amount = amount - fee
        shares = net_amount / price

        total_shares += shares
        total_cost += amount

        records.append(
            TradeRecord(
                date=tradeday,
                price=price,
                invest_amount=amount,
                fee=fee,
                shares=shares,
                total_shares=total_shares,
                total_cost=total_cost,
            )
        )

    return records


def run_backtest_on_df(
    df: pd.DataFrame,
    start: date,
    end: date,
    amount: float,
    dayofweek: int,
    fee_rate: float,
    label: str = "",
    verbose: bool = True,
) -> Tuple[str, List[TradeRecord], pd.DataFrame, dict]:
    """
    对已获取的 DataFrame 执行完整回测（生成日期 → 执行回测 → 计算指标）。

    数据获取不在本函数中完成，请先用 finance-data skill 的 fetch_data / fetch_multiple 获取 df。

    Args:
        df: 包含 'adj_close' 列的 DataFrame，index 为 date
        start: 回测起始日期
        end: 回测结束日期
        amount: 每次定投金额
        dayofweek: 定投星期几（0=周一…6=周日）
        fee_rate: 申购费率
        label: 标的名称（仅用于显示）
        verbose: 是否打印详细信息

    Returns:
        (label, records, df, metrics)
    """
    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    if verbose:
        print(f"\n{'─' * 50}")
        print(f"  标的: {label}")
        print(f"{'─' * 50}")
        print(f"  数据就绪，共 {len(df)} 个交易日")

    invest_dates = generate_invest_dates(start, end, dayofweek)
    if verbose:
        print(
            f"  定投计划: 每{day_names[dayofweek]} {amount:,.0f} 元，"
            f"共 {len(invest_dates)} 个定投日"
        )

    records = run_backtest(df, invest_dates, amount, fee_rate)
    if not records:
        print("  未产生有效交易，请检查日期是否在数据范围内。", file=sys.stderr)
        return label, [], df, {}

    last_date = min(end, df.index[-1])
    final_price = float(df.loc[last_date, "adj_close"])
    metrics = calculate_metrics(records, final_price, start, last_date)

    if verbose:
        print_result(metrics, label)

    return label, records, df, metrics


# ── 指标计算 ─────────────────────────────────────────────────────
def calculate_xirr(cash_flows: List[Tuple[float, date]]) -> Optional[float]:
    """
    使用牛顿法计算 XIRR（内部收益率）。
    cash_flows: [(金额, date), ...]，流出为负，流入为正。
    """
    if len(cash_flows) < 2:
        return None

    dates_ = [c[1] for c in cash_flows]
    amounts = np.array([c[0] for c in cash_flows], dtype=float)
    days = np.array([(d - dates_[0]).days for d in dates_], dtype=float)

    if np.all(amounts >= 0) or np.all(amounts <= 0):
        return None

    def npv(rate: float) -> float:
        return float(np.sum(amounts / ((1.0 + rate) ** (days / 365.0))))

    def npv_derivative(rate: float) -> float:
        return float(
            np.sum(
                -amounts * days / 365.0 / ((1.0 + rate) ** (days / 365.0 + 1.0))
            )
        )

    rate = 0.10
    for _ in range(100):
        try:
            f = npv(rate)
            fp = npv_derivative(rate)
            if abs(fp) < 1e-12:
                break
            new_rate = rate - f / fp
            if abs(new_rate - rate) < 1e-8:
                return new_rate
            rate = new_rate
        except (OverflowError, ZeroDivisionError):
            return None

    if abs(npv(rate)) < 1e-4:
        return rate
    return None


def calculate_metrics(
    records: List[TradeRecord],
    final_price: float,
    start: date,
    end: date,
) -> dict:
    """
    从交易记录计算回测指标。

    返回:
        start_date, end_date, invest_count, total_cost,
        total_shares, final_price, final_value, total_profit,
        return_rate, annualized_return (XIRR), lump_sum_return
    """
    if not records:
        return {}

    total_cost = records[-1].total_cost
    total_shares = records[-1].total_shares
    final_value = total_shares * final_price
    total_profit = final_value - total_cost
    return_rate = total_profit / total_cost

    cash_flows = [(-r.invest_amount, r.date) for r in records]
    cash_flows.append((final_value, end))
    xirr = calculate_xirr(cash_flows)

    lump_sum_return = 0.0
    if records:
        initial_price = records[0].price
        lump_sum_shares = total_cost / initial_price
        lump_sum_value = lump_sum_shares * final_price
        lump_sum_profit = lump_sum_value - total_cost
        lump_sum_return = lump_sum_profit / total_cost if total_cost else 0.0

    return {
        "start_date": start,
        "end_date": end,
        "invest_count": len(records),
        "total_cost": total_cost,
        "total_shares": total_shares,
        "final_price": final_price,
        "final_value": final_value,
        "total_profit": total_profit,
        "return_rate": return_rate,
        "annualized_return": xirr,
        "lump_sum_return": lump_sum_return,
    }


# ── 格式化与输出 ─────────────────────────────────────────────────
def format_money(value: float) -> str:
    return f"{value:,.2f}"


def print_result(metrics: dict, label: str = "标的") -> None:
    """打印单个回测结果。"""
    if not metrics:
        print("没有产生任何交易记录，无法计算收益。")
        return

    print(f"\n{'=' * 60}")
    print(f"  {label} 定投回测结果")
    print(f"{'=' * 60}")
    print(f"  回测区间:      {metrics['start_date']} 至 {metrics['end_date']}")
    print(f"  定投次数:      {metrics['invest_count']} 次")
    print(f"  总投入成本:    {format_money(metrics['total_cost'])} 元")
    print(f"  期末总资产:    {format_money(metrics['final_value'])} 元")
    print(f"  累计盈亏:      {format_money(metrics['total_profit'])} 元")
    print(f"  定投收益率:    {metrics['return_rate'] * 100:+.2f}%")
    if metrics["annualized_return"] is not None:
        print(f"  年化收益率:    {metrics['annualized_return'] * 100:+.2f}%")
    else:
        print(f"  年化收益率:    无法计算")
    print(f"  期末净值:      {metrics['final_price']:,.2f}")
    print(f"  持有份额:      {metrics['total_shares']:,.4f}")
    print(f"\n  📊 对比: 期初一次性投入收益率: {metrics['lump_sum_return'] * 100:+.2f}%")
    print(f"{'=' * 60}\n")


def print_comparison(results: List[Tuple[str, dict]]) -> None:
    """打印多个标的的对比汇总表。"""
    if not results:
        return

    print("\n" + "=" * 78)
    print("  多标的定投回测对比汇总")
    print("=" * 78)

    headers = [
        "标的", "定投次数", "总投入", "期末总值",
        "定投收益率", "年化(XIRR)", "一次性投入收益率",
    ]
    col_widths = [12, 10, 12, 12, 12, 12, 14]

    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print("  " + header_line)
    print("  " + "-" * (len(header_line)))

    for name, m in results:
        row = [
            name,
            str(m.get("invest_count", "-")),
            format_money(m.get("total_cost", 0)),
            format_money(m.get("final_value", 0)),
            f"{m.get('return_rate', 0) * 100:+.2f}%",
            f"{m.get('annualized_return', 0) * 100:+.2f}%"
            if m.get("annualized_return") is not None
            else "N/A",
            f"{m.get('lump_sum_return', 0) * 100:+.2f}%",
        ]
        print("  " + "  ".join(str(c).ljust(w) for c, w in zip(row, col_widths)))

    print("=" * 78 + "\n")


def save_records(records: List[TradeRecord], output_path: str) -> None:
    """把交易明细保存为 CSV。"""
    data = [
        {
            "日期": r.date,
            "调整后收盘价": round(r.price, 4),
            "定投金额": r.invest_amount,
            "申购费": r.fee,
            "买入份额": round(r.shares, 4),
            "累计份额": round(r.total_shares, 4),
            "累计投入": r.total_cost,
        }
        for r in records
    ]
    pd.DataFrame(data).to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  交易明细已保存至: {output_path}")


# ── 绘图 ─────────────────────────────────────────────────────────
def setup_chinese_font() -> bool:
    """尝试配置 matplotlib 使用中文字体。"""
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm

    candidates = [
        "PingFang SC", "Heiti SC", "STHeiti",
        "Arial Unicode MS", "SimHei", "Microsoft YaHei",
        "WenQuanYi Micro Hei", "Noto Sans CJK SC",
        "Source Han Sans SC",
    ]
    installed = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            plt.rcParams["font.family"] = [name, "sans-serif"]
            plt.rcParams["axes.unicode_minus"] = False
            return True

    for font in fm.fontManager.ttflist:
        if any(kw in font.name for kw in ("CJK", "SC", "Hei")):
            plt.rcParams["font.family"] = [font.name, "sans-serif"]
            plt.rcParams["axes.unicode_minus"] = False
            return True
    return False


def plot_single(
    records: List[TradeRecord],
    df: pd.DataFrame,
    metrics: dict,
    label: str = "",
    save_path: Optional[str] = None,
) -> None:
    """
    绘制单个标的的收益曲线：投入成本 vs 账户市值。

    Args:
        records: 交易记录列表
        df: 原始行情数据（含 adj_close 列）
        metrics: 回测指标
        label: 标的名称
        save_path: 保存路径（可选，不指定则弹窗显示）
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("未安装 matplotlib，跳过绘图。请运行: pip install matplotlib")
        return

    setup_chinese_font()

    title_prefix = f"{label} " if label else ""

    dates = [r.date for r in records]
    cost_line = [r.total_cost for r in records]
    value_line = [
        r.total_shares * float(df.loc[r.date, "adj_close"]) for r in records
    ]

    final_date = metrics["end_date"]
    if final_date in df.index and final_date not in dates:
        dates.append(final_date)
        cost_line.append(cost_line[-1])
        value_line.append(metrics["final_value"])

    plt.figure(figsize=(12, 6))
    plt.plot(dates, cost_line, label="累计投入成本", linewidth=2, color="#4A7FB5")
    plt.plot(dates, value_line, label="账户总市值", linewidth=2, color="#E8833A")
    plt.fill_between(dates, cost_line, value_line, alpha=0.15, color="#E8833A")
    plt.title(f"{title_prefix}定投回测：投入成本 vs 账户市值")
    plt.xlabel("日期")
    plt.ylabel("金额（元）")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  收益曲线图已保存至: {save_path}")
    else:
        try:
            plt.show()
        except Exception as e:
            print(f"  无法显示图表窗口: {e}")
            print("  提示：可使用 --save-plot chart.png 保存到文件。")
    plt.close()


def plot_comparison(
    all_results: List[Tuple[str, List[TradeRecord], pd.DataFrame, dict]],
    save_path: Optional[str] = None,
) -> None:
    """
    绘制多个标的的对比曲线（账户市值对比）。

    Args:
        all_results: [(label, records, df, metrics), ...]
        save_path: 保存路径（可选）
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("未安装 matplotlib，跳过绘图。")
        return

    setup_chinese_font()

    plt.figure(figsize=(14, 7))
    colors = ["#E8833A", "#4A7FB5", "#6BB36B", "#C75A5A", "#9B59B6", "#5B9BD5"]

    for i, (name, records, df_, metrics_) in enumerate(all_results):
        dates = [r.date for r in records]
        value_line = [
            r.total_shares * float(df_.loc[r.date, "adj_close"])
            for r in records
        ]
        final_date = metrics_["end_date"]
        if final_date in df_.index and final_date not in dates:
            dates.append(final_date)
            value_line.append(metrics_["final_value"])

        color = colors[i % len(colors)]
        plt.plot(dates, value_line, label=f"{name}（市值）", linewidth=2, color=color)

    plt.title("多标的定投回测对比 — 账户总市值")
    plt.xlabel("日期")
    plt.ylabel("金额（元）")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  对比曲线图已保存至: {save_path}")
    else:
        try:
            plt.show()
        except Exception as e:
            print(f"  无法显示图表窗口: {e}")
    plt.close()
