#!/usr/bin/env python3
"""
多起点定投策略对比分析脚本

研究问题：
  从 2010、2015、2020 三个时间起点开始定投，每周二投入固定金额，
  到 2026-06-16，不同标的的收益表现如何？

标的分类：
  - 人民币标的（1000元/周）：沪深300、黄金ETF、纳斯达克100、中概互联、创业板50
  - 美元标的（150美元/周）：标普500、全球除美(VXUS)
  - 港股标的（150美元等值港币/周）：恒生指数(2800.HK)
"""

import os
import sys
from datetime import date, datetime
from typing import List, Tuple, Dict, Optional
import json

import numpy as np
import pandas as pd

# ── 项目路径 ──
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "skills", "finance-data", "scripts"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "skills", "dca-backtest", "scripts"))

from finance_lib import fetch_data, fetch_multiple
from backtest_core import (
    run_backtest_on_df,
    calculate_metrics,
    generate_invest_dates,
    run_backtest,
    plot_single,
    plot_comparison,
    setup_chinese_font,
    format_money,
)

# ══════════════════════════════════════════════════════════════════
#  配置
# ══════════════════════════════════════════════════════════════════

# 三个回测起点
START_DATES = [
    date(2010, 1, 1),
    date(2015, 1, 1),
    date(2020, 1, 1),
]

END_DATE = date.today()  # 2026-06-16

# 标的定义: (简称, ticker, 名称, 货币, 每周投入金额)
ASSETS = [
    # ── 人民币标的（1000元/周）──
    ("csi300",  "510300.SS", "沪深300",  "CNY", 1000),
    ("gem50",   "159949.SZ", "创业板50", "CNY", 1000),
    ("cninet",  "513050.SS", "中概互联", "CNY", 1000),
    ("gold",    "518880.SS", "黄金ETF",  "CNY", 1000),
    ("nasdaq100", "513100.SS", "纳斯达克100", "CNY", 1000),
    # ── 美元标的（150美元/周）──
    ("sp500",   "SPY",       "标普500",  "USD", 150),
    ("vxus",    "VXUS",      "全球除美", "USD", 150),
    # ── 港股标的（150美元等值港币/周 ≈ 1167 HKD）──
    ("hsi",     "2800.HK",   "恒生指数", "HKD", 1167),
]

FEE_RATE = 0.001   # 0.1% 申购费率
DAY_OF_WEEK = 1     # 周二


# ══════════════════════════════════════════════════════════════════
#  数据准备
# ══════════════════════════════════════════════════════════════════

def prepare_all_data() -> Dict[str, pd.DataFrame]:
    """拉取所有标的历史数据。"""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)

    dfs = {}
    earliest_start = min(START_DATES)  # 2010-01-01

    for key, ticker, name, currency, amount in ASSETS:
        print(f"\n[{name}] 拉取数据 {ticker} ...")
        try:
            df = fetch_data(ticker, earliest_start, END_DATE, verbose=True)
            # 清理 NaN 行（Yahoo Finance 有时会在最后一个交易日返回 NaN）
            before = len(df)
            df = df.dropna()
            if len(df) < before:
                print(f"  ⚠ 已清理 {before - len(df)} 行 NaN 数据")
            dfs[key] = df
            print(f"  ✓ {len(df)} 行, {df.index[0]} ~ {df.index[-1]}")
        except Exception as e:
            print(f"  ✗ 失败: {e}")

    return dfs


# ══════════════════════════════════════════════════════════════════
#  执行回测
# ══════════════════════════════════════════════════════════════════

def run_all_backtests(dfs: Dict[str, pd.DataFrame]) -> List[dict]:
    """对所有标的×起点组合执行回测。"""
    results = []

    for key, ticker, name, currency, amount in ASSETS:
        if key not in dfs:
            print(f"  ⚠ 跳过 {name}，数据未就绪")
            continue

        df = dfs[key]

        for start in START_DATES:
            start_label = start.strftime("%Y-%m-%d")
            print(f"\n  [{name}] 起点={start_label}, 每周{amount}{currency} ...")

            try:
                label, records, df_out, metrics = run_backtest_on_df(
                    df=df,
                    start=start,
                    end=END_DATE,
                    amount=amount,
                    dayofweek=DAY_OF_WEEK,
                    fee_rate=FEE_RATE,
                    label=f"{name} ({start_label}起)",
                    verbose=False,
                )

                if metrics:
                    results.append({
                        "asset_key": key,
                        "ticker": ticker,
                        "asset_name": name,
                        "currency": currency,
                        "amount": amount,
                        "start_date": start_label,
                        "start_date_obj": start,
                        "end_date": END_DATE.strftime("%Y-%m-%d"),
                        "invest_count": metrics["invest_count"],
                        "total_cost": metrics["total_cost"],
                        "final_value": metrics["final_value"],
                        "total_profit": metrics["total_profit"],
                        "return_rate": metrics["return_rate"],
                        "annualized_return": metrics.get("annualized_return"),
                        "lump_sum_return": metrics["lump_sum_return"],
                        "records": records,
                        "df": df_out,
                    })
                    print(f"    ✓ 定投{metrics['invest_count']}次, "
                          f"收益率 {metrics['return_rate']*100:+.2f}%, "
                          f"年化 {metrics.get('annualized_return', 0)*100:+.2f}%")
                else:
                    print(f"    ✗ 无交易记录")

            except Exception as e:
                print(f"    ✗ 回测失败: {e}")

    return results


# ══════════════════════════════════════════════════════════════════
#  生成报表数据
# ══════════════════════════════════════════════════════════════════

def build_summary_table(results: List[dict]) -> pd.DataFrame:
    """构建汇总表格。"""
    rows = []
    for r in results:
        annualized = r["annualized_return"]
        annualized_str = f"{annualized*100:+.2f}%" if annualized is not None else "N/A"
        rows.append({
            "标的": r["asset_name"],
            "货币": r["currency"],
            "周投金额": f"{r['amount']:.0f} {r['currency']}",
            "起点": r["start_date"],
            "定投次数": r["invest_count"],
            "总投入": r["total_cost"],
            "期末总值": r["final_value"],
            "累计盈亏": r["total_profit"],
            "定投收益率": f"{r['return_rate']*100:+.2f}%",
            "年化收益率": annualized_str,
            "一次性投入收益率": f"{r['lump_sum_return']*100:+.2f}%",
        })
    return pd.DataFrame(rows)


def build_heatmap_data(results: List[dict]) -> Dict:
    """构建热力图数据（按起点×标的，收益率矩阵）。"""
    assets = list(set(r["asset_name"] for r in results))
    assets.sort()
    starts = [s.strftime("%Y-%m-%d") for s in START_DATES]

    return_rate_matrix = []
    annualized_matrix = []
    lump_sum_matrix = []

    for a in assets:
        rr_row = []
        ar_row = []
        lr_row = []
        for s in starts:
            match = [r for r in results if r["asset_name"] == a and r["start_date"] == s]
            if match:
                m = match[0]
                rr_row.append(round(m["return_rate"] * 100, 2))
                ar_row.append(round(m["annualized_return"] * 100, 2) if m["annualized_return"] else None)
                lr_row.append(round(m["lump_sum_return"] * 100, 2))
            else:
                rr_row.append(None)
                ar_row.append(None)
                lr_row.append(None)
        return_rate_matrix.append(rr_row)
        annualized_matrix.append(ar_row)
        lump_sum_matrix.append(lr_row)

    return {
        "assets": assets,
        "starts": starts,
        "return_rate": return_rate_matrix,
        "annualized": annualized_matrix,
        "lump_sum": lump_sum_matrix,
    }


# ══════════════════════════════════════════════════════════════════
#  生成图表
# ══════════════════════════════════════════════════════════════════

def generate_charts(results: List[dict], output_dir: str) -> List[str]:
    """生成所有图表，返回图片路径列表。"""
    os.makedirs(output_dir, exist_ok=True)
    setup_chinese_font()
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use("Agg")

    chart_paths = []

    # 1. 每个资产在每个起点的收益曲线
    for r in results:
        key = f"{r['asset_key']}_{r['start_date']}"
        save_path = os.path.join(output_dir, f"curve_{key}.png")
        try:
            plot_single(
                r["records"], r["df"],
                {
                    "start_date": r["start_date_obj"],
                    "end_date": END_DATE,
                    "invest_count": r["invest_count"],
                    "total_cost": r["total_cost"],
                    "final_value": r["final_value"],
                    "total_profit": r["total_profit"],
                    "return_rate": r["return_rate"],
                    "annualized_return": r["annualized_return"],
                    "final_price": r["records"][-1].price if r["records"] else 0,
                    "total_shares": r["records"][-1].total_shares if r["records"] else 0,
                    "lump_sum_return": r["lump_sum_return"],
                },
                label=f"{r['asset_name']} (起点{r['start_date']})",
                save_path=save_path,
            )
            chart_paths.append(save_path)
        except Exception as e:
            print(f"  ⚠ 绘图失败 {save_path}: {e}")

    # 2. 每个起点下，所有资产的对比曲线
    for start in START_DATES:
        start_label = start.strftime("%Y-%m-%d")
        same_start = [r for r in results if r["start_date"] == start_label]

        if len(same_start) > 1:
            save_path = os.path.join(output_dir, f"comparison_{start_label}.png")
            plot_data = [
                (r["asset_name"], r["records"], r["df"], {
                    "end_date": END_DATE,
                    "final_value": r["final_value"],
                    "total_cost": r["total_cost"],
                })
                for r in same_start
            ]

            plt.figure(figsize=(14, 7))
            colors = ["#E8833A", "#4A7FB5", "#6BB36B", "#C75A5A", "#9B59B6", "#5B9BD5", "#F39C12", "#1ABC9C"]

            for i, (name, records_, df_, _) in enumerate(plot_data):
                dates_ = [rec.date for rec in records_]
                value_line = [
                    rec.total_shares * float(df_.loc[rec.date, "adj_close"])
                    for rec in records_
                ]
                if END_DATE in df_.index and END_DATE not in dates_:
                    dates_.append(END_DATE)
                    value_line.append(r["final_value"])

                color = colors[i % len(colors)]
                plt.plot(dates_, value_line, label=name, linewidth=2, color=color)

            plt.title(f"多标对比 — 起点 {start_label}（账户市值）")
            plt.xlabel("日期")
            plt.ylabel("金额")
            plt.legend()
            plt.grid(True, linestyle="--", alpha=0.4)
            plt.tight_layout()
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            plt.close()
            chart_paths.append(save_path)

    # 3. 每个资产下，三个起点的收益率对比柱状图
    import matplotlib.pyplot as plt
    asset_names = list(set(r["asset_name"] for r in results))
    asset_names.sort()
    start_labels = [s.strftime("%Y-%m-%d") for s in START_DATES]
    bar_colors = ["#4A7FB5", "#E8833A", "#6BB36B"]

    # 按货币分组
    currency_groups = {}
    for r in results:
        cur = r["currency"]
        asset_name = r["asset_name"]
        if cur not in currency_groups:
            currency_groups[cur] = []
        if asset_name not in currency_groups[cur]:
            currency_groups[cur].append(asset_name)

    for cur, assets_in_group in currency_groups.items():
        save_path = os.path.join(output_dir, f"bar_comparison_{cur}.png")
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f"{cur} 标的 — 不同起点定投收益率对比", fontsize=16)

        for idx, s in enumerate(start_labels):
            ax = axes[idx]
            x_labels = []
            values = []
            colors_list = []
            for ai, an in enumerate(assets_in_group):
                match = [r for r in results if r["asset_name"] == an and r["start_date"] == s]
                if match:
                    x_labels.append(an)
                    values.append(match[0]["return_rate"] * 100)
                    colors_list.append(bar_colors[ai % len(bar_colors)])

            bars = ax.bar(range(len(x_labels)), values, color=colors_list, width=0.6)
            ax.set_title(f"起点 {s}")
            ax.set_xticks(range(len(x_labels)))
            ax.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=9)
            ax.axhline(y=0, color="gray", linewidth=0.5)
            ax.set_ylabel("定投收益率 (%)")

            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                        f"{val:+.1f}%", ha="center", va="bottom", fontsize=8)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        chart_paths.append(save_path)

    # 4. 年化收益率对比柱状图
    for cur, assets_in_group in currency_groups.items():
        save_path = os.path.join(output_dir, f"xirr_comparison_{cur}.png")
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f"{cur} 标的 — 不同起点年化收益率(XIRR)对比", fontsize=16)

        for idx, s in enumerate(start_labels):
            ax = axes[idx]
            x_labels = []
            values = []
            colors_list = []
            for ai, an in enumerate(assets_in_group):
                match = [r for r in results if r["asset_name"] == an and r["start_date"] == s]
                if match and match[0]["annualized_return"] is not None:
                    x_labels.append(an)
                    values.append(match[0]["annualized_return"] * 100)
                    colors_list.append(bar_colors[ai % len(bar_colors)])

            bars = ax.bar(range(len(x_labels)), values, color=colors_list, width=0.6)
            ax.set_title(f"起点 {s}")
            ax.set_xticks(range(len(x_labels)))
            ax.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=9)
            ax.axhline(y=0, color="gray", linewidth=0.5)
            ax.set_ylabel("年化收益率 (XIRR, %)")

            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                        f"{val:+.1f}%", ha="center", va="bottom", fontsize=8)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        chart_paths.append(save_path)

    return chart_paths


# ══════════════════════════════════════════════════════════════════
#  HTML 报告生成
# ══════════════════════════════════════════════════════════════════

def generate_html_report(
    results: List[dict],
    summary_df: pd.DataFrame,
    heatmap: Dict,
    chart_dir: str,
    output_path: str,
) -> str:
    """生成自包含的 HTML 报告。"""
    # 对图表做 base64 内嵌
    import base64

    def img_to_b64(path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # 收集图表路径
    chart_dir_abs = os.path.abspath(chart_dir)
    chart_files = sorted([f for f in os.listdir(chart_dir_abs) if f.endswith(".png")])

    # 按类型分组
    curve_charts = [f for f in chart_files if f.startswith("curve_")]
    comp_charts = [f for f in chart_files if f.startswith("comparison_")]
    bar_charts = [f for f in chart_files if f.startswith("bar_")]
    xirr_charts = [f for f in chart_files if f.startswith("xirr_")]

    # 按货币分组汇总表
    cny_results = [r for r in results if r["currency"] == "CNY"]
    usd_results = [r for r in results if r["currency"] == "USD"]
    hkd_results = [r for r in results if r["currency"] == "HKD"]

    # 构建 HTML
    start_labels = [s.strftime("%Y-%m-%d") for s in START_DATES]
    asset_names = list(set(r["asset_name"] for r in results))
    asset_names.sort()

    # 分组
    currency_map = {}
    for r in results:
        currency_map[r["asset_name"]] = r["currency"]

    cny_assets = [a for a in asset_names if currency_map.get(a) == "CNY"]
    usd_assets = [a for a in asset_names if currency_map.get(a) == "USD"]
    hkd_assets = [a for a in asset_names if currency_map.get(a) == "HKD"]

    # 表格行
    def asset_row(r):
        ar = r["annualized_return"]
        ar_str = f"{ar*100:+.2f}%" if ar is not None else "<span class='na'>N/A</span>"
        color = "#e74c3c" if r["return_rate"] < 0 else "#27ae60"
        return f"""<tr>
            <td>{r['asset_name']}</td>
            <td>{r['start_date']}</td>
            <td>{r['invest_count']}</td>
            <td class="num">{r['total_cost']:,.0f}</td>
            <td class="num">{r['final_value']:,.0f}</td>
            <td class="num" style="color:{color}">{r['return_rate']*100:+.2f}%</td>
            <td class="num">{ar_str}</td>
            <td class="num">{r['lump_sum_return']*100:+.2f}%</td>
        </tr>"""

    cny_rows = "\n".join(asset_row(r) for r in cny_results)
    usd_rows = "\n".join(asset_row(r) for r in usd_results)
    hkd_rows = "\n".join(asset_row(r) for r in hkd_results)

    # 热力图
    def heatmap_table(matrix, title):
        rows_html = ""
        for i, asset in enumerate(heatmap["assets"]):
            cells = "".join(
                f"<td class='hm-cell' style='background-color:{_heat_color(v)}'>{v if v is not None else '—'}</td>"
                for v in matrix[i]
            )
            rows_html += f"<tr><td class='hm-label'>{asset}</td>{cells}</tr>"
        headers = "".join(f"<th>{s}</th>" for s in heatmap["starts"])
        return f"""
        <h3>{title}</h3>
        <table class='heatmap'>
            <tr><th>标的</th>{headers}</tr>
            {rows_html}
        </table>"""

    def _heat_color(v):
        if v is None:
            return "#f0f0f0"
        if v > 30:
            return "#1a9850"
        elif v > 15:
            return "#66bd63"
        elif v > 5:
            return "#a6d96a"
        elif v > 0:
            return "#d9ef8b"
        elif v > -10:
            return "#fee08b"
        elif v > -20:
            return "#fdae61"
        else:
            return "#d73027"

    # 图库
    def gallery_section(charts, title, cols=3):
        if not charts:
            return ""
        items = ""
        for ch in charts:
            b64 = img_to_b64(os.path.join(chart_dir_abs, ch))
            label = ch.replace(".png", "").replace("curve_", "").replace("comparison_", "对比-").replace("bar_", "柱状-").replace("xirr_", "年化-")
            items += f"""<div class="gallery-item">
                <img src="data:image/png;base64,{b64}" loading="lazy" onclick="openModal(this)" />
                <div class="gallery-label">{label}</div>
            </div>"""
        return f"""
        <h2>{title}</h2>
        <div class="gallery">
            {items}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>定投回测对比分析 — 多起点策略研究</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    background: #f5f7fa;
    color: #2c3e50;
    line-height: 1.8;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
h1 {{ font-size: 28px; margin-bottom: 8px; color: #1a1a2e; }}
.subtitle {{ color: #666; font-size: 16px; margin-bottom: 30px; }}

/* 信息卡片 */
.info-cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 30px;
}}
.card {{
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.card .label {{ font-size: 13px; color: #999; }}
.card .value {{ font-size: 22px; font-weight: 700; margin-top: 4px; }}

/* 表格 */
.section {{ margin-bottom: 40px; }}
.section h2 {{
    font-size: 22px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 3px solid #4A7FB5;
    color: #1a1a2e;
}}
.section h3 {{
    font-size: 18px;
    margin: 20px 0 12px;
    color: #2c3e50;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    margin-bottom: 20px;
}}
th {{
    background: #4A7FB5;
    color: #fff;
    padding: 12px 10px;
    font-size: 13px;
    font-weight: 600;
    text-align: center;
}}
td {{
    padding: 10px;
    font-size: 13px;
    text-align: center;
    border-bottom: 1px solid #eee;
}}
tr:hover {{ background: #f0f5ff; }}
.num {{ font-family: "SF Mono", "Menlo", monospace; font-size: 13px; }}
.positive {{ color: #27ae60; }}
.negative {{ color: #e74c3c; }}
.na {{ color: #999; }}

/* 货币分组标签 */
.currency-tag {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}}
.currency-cny {{ background: #e8f5e9; color: #2e7d32; }}
.currency-usd {{ background: #e3f2fd; color: #1565c0; }}
.currency-hkd {{ background: #fff3e0; color: #e65100; }}

/* 热力图 */
.heatmap {{ font-size: 13px; }}
.heatmap .hm-label {{ text-align: left; font-weight: 600; }}
.heatmap .hm-cell {{
    font-weight: 600;
    padding: 10px 14px;
    min-width: 80px;
}}

/* 图库 */
.gallery {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px;
    margin-bottom: 30px;
}}
.gallery-item {{
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    cursor: pointer;
    transition: transform 0.2s;
}}
.gallery-item:hover {{ transform: scale(1.02); }}
.gallery-item img {{
    width: 100%;
    display: block;
}}
.gallery-label {{
    padding: 8px 12px;
    font-size: 12px;
    color: #666;
    background: #fafafa;
}}

/* Modal */
.modal {{
    display: none;
    position: fixed;
    z-index: 999;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.85);
    justify-content: center;
    align-items: center;
}}
.modal img {{
    max-width: 90vw;
    max-height: 90vh;
    border-radius: 8px;
}}
.modal .close {{
    position: absolute;
    top: 20px; right: 30px;
    color: #fff;
    font-size: 36px;
    cursor: pointer;
}}

/* 快速导航 */
.toc {{
    background: #fff;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 30px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.toc a {{
    display: inline-block;
    margin: 4px 12px 4px 0;
    color: #4A7FB5;
    text-decoration: none;
    font-size: 14px;
}}
.toc a:hover {{ text-decoration: underline; }}

/* 结论 */
.conclusion {{
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 30px;
}}
.conclusion h2 {{ color: #fff; border-bottom-color: rgba(255,255,255,0.3); }}
.conclusion li {{ margin-bottom: 8px; }}

@media (max-width: 768px) {{
    .gallery {{ grid-template-columns: 1fr; }}
    th, td {{ font-size: 11px; padding: 6px 4px; }}
}}
</style>
</head>
<body>
<div class="container">

<h1>📊 多起点定投策略对比分析</h1>
<p class="subtitle">
    回测区间：2010-01-01 / 2015-01-01 / 2020-01-01 → {END_DATE}（{END_DATE.strftime("%Y年%m月%d日")}）<br>
    定投频率：每周二 · 费率：{FEE_RATE*100:.1f}% · CNY标的1000元/周 · USD标的150美元/周 · HKD标的1167港币/周
</p>

<div class="info-cards">
    <div class="card">
        <div class="label">回测组数</div>
        <div class="value">{len(results)}</div>
    </div>
    <div class="card">
        <div class="label">股票/ETF标的</div>
        <div class="value">{len(ASSETS)}</div>
    </div>
    <div class="card">
        <div class="label">时间起点</div>
        <div class="value">3</div>
    </div>
    <div class="card">
        <div class="label">回测截止</div>
        <div class="value" style="font-size:16px;">{END_DATE}</div>
    </div>
</div>

<div class="toc">
    <strong>📑 目录：</strong>
    <a href="#summary">汇总表</a>
    <a href="#heatmap">热力图</a>
    <a href="#cny">人民币标的</a>
    <a href="#usd">美元标的</a>
    <a href="#hkd">港股标的</a>
    <a href="#charts-all">收益曲线</a>
    <a href="#charts-comp">对比图</a>
    <a href="#charts-bar">柱状图</a>
    <a href="#conclusion">结论</a>
</div>

<!-- ═══════ 汇总表 ═══════ -->
<div class="section" id="summary">
    <h2>📋 汇总表</h2>
"""

    # 人民币
    if cny_rows:
        html += f"""
    <h3>🇨🇳 人民币标的 <span class="currency-tag currency-cny">CNY</span> — 每周 1000 元</h3>
    <table>
        <tr>
            <th>标的</th><th>起点</th><th>定投次数</th><th>总投入</th><th>期末总值</th>
            <th>定投收益率</th><th>年化(XIRR)</th><th>一次性投入收益率</th>
        </tr>
        {cny_rows}
    </table>"""

    if usd_rows:
        html += f"""
    <h3>🇺🇸 美元标的 <span class="currency-tag currency-usd">USD</span> — 每周 150 美元</h3>
    <table>
        <tr>
            <th>标的</th><th>起点</th><th>定投次数</th><th>总投入</th><th>期末总值</th>
            <th>定投收益率</th><th>年化(XIRR)</th><th>一次性投入收益率</th>
        </tr>
        {usd_rows}
    </table>"""

    if hkd_rows:
        html += f"""
    <h3>🇭🇰 港股标的 <span class="currency-tag currency-hkd">HKD</span> — 每周 1167 港币</h3>
    <table>
        <tr>
            <th>标的</th><th>起点</th><th>定投次数</th><th>总投入</th><th>期末总值</th>
            <th>定投收益率</th><th>年化(XIRR)</th><th>一次性投入收益率</th>
        </tr>
        {hkd_rows}
    </table>"""

    # ═══════ 热力图 ═══════
    html += f"""
</div>
<div class="section" id="heatmap">
    <h2>🔥 热力图</h2>
    <p>颜色越绿 = 收益越高，越红 = 亏损越大</p>
    {heatmap_table(heatmap["return_rate"], "定投收益率 (%)")}
    {heatmap_table(heatmap["annualized"], "年化收益率 XIRR (%)")}
    {heatmap_table(heatmap["lump_sum"], "一次性投入收益率 (%)")}
</div>
"""

    # ═══════ 图表 ═══════
    html += '<div class="section" id="charts-all">\n<h2>📈 收益曲线（按资产×起点）</h2>\n'
    # 按标的分组
    for asset_name in asset_names:
        asset_cur = currency_map.get(asset_name, "")
        tag_class = {"CNY": "currency-cny", "USD": "currency-usd", "HKD": "currency-hkd"}.get(asset_cur, "")
        html += f'<h3>{asset_name} <span class="currency-tag {tag_class}">{asset_cur}</span></h3>\n<div class="gallery">\n'
        for s in start_labels:
            ch_name = f"curve_{asset_name.lower().replace(' ', '_')}_{s}.png"
            # Find actual key
            match = [r for r in results if r["asset_name"] == asset_name and r["start_date"] == s]
            if match:
                key = f"{match[0]['asset_key']}_{s}.png"
                ch_name = f"curve_{key}"
                full_path = os.path.join(chart_dir_abs, ch_name)
                if os.path.exists(full_path):
                    b64 = img_to_b64(full_path)
                    html += f"""
        <div class="gallery-item">
            <img src="data:image/png;base64,{b64}" loading="lazy" onclick="openModal(this)" />
            <div class="gallery-label">起点 {s}</div>
        </div>"""
        html += '</div>\n'
    html += '</div>\n'

    # 对比曲线
    if comp_charts:
        html += f'<div class="section" id="charts-comp">\n<h2>📊 多标对比（按起点）</h2>\n<div class="gallery">\n'
        for ch in comp_charts:
            full_path = os.path.join(chart_dir_abs, ch)
            if os.path.exists(full_path):
                b64 = img_to_b64(full_path)
                label = ch.replace("comparison_", "").replace(".png", "")
                html += f"""
        <div class="gallery-item">
            <img src="data:image/png;base64,{b64}" loading="lazy" onclick="openModal(this)" />
            <div class="gallery-label">起点 {label}</div>
        </div>"""
        html += '</div>\n</div>\n'

    # 柱状图
    if bar_charts:
        html += f'<div class="section" id="charts-bar">\n<h2>📊 收益率/年化收益率对比</h2>\n<div class="gallery">\n'
        for ch in bar_charts + xirr_charts:
            full_path = os.path.join(chart_dir_abs, ch)
            if os.path.exists(full_path):
                b64 = img_to_b64(full_path)
                label = ch.replace(".png", "")
                label = label.replace("bar_comparison_", "收益率-").replace("xirr_comparison_", "年化收益率-")
                html += f"""
        <div class="gallery-item">
            <img src="data:image/png;base64,{b64}" loading="lazy" onclick="openModal(this)" />
            <div class="gallery-label">{label}</div>
        </div>"""
        html += '</div>\n</div>\n'

    # ═══════ 结论 ═══════
    # 计算一些关键发现
    best_dca = max(results, key=lambda r: r["return_rate"]) if results else None
    worst_dca = min(results, key=lambda r: r["return_rate"]) if results else None
    best_xirr = max([r for r in results if r["annualized_return"] is not None], key=lambda r: r["annualized_return"]) if results else None
    worst_xirr = min([r for r in results if r["annualized_return"] is not None], key=lambda r: r["annualized_return"]) if results else None

    # 统计每个起点下正收益比例
    pos_ratio_by_start = {}
    for s in start_labels:
        same = [r for r in results if r["start_date"] == s]
        if same:
            pos = sum(1 for r in same if r["return_rate"] > 0)
            pos_ratio_by_start[s] = (pos, len(same))

    html += f"""
<div class="section" id="conclusion">
    <div class="conclusion">
        <h2>💡 关键发现</h2>
        <ol>
"""
    if best_dca:
        html += f"<li><strong>最佳定投收益率：</strong>{best_dca['asset_name']}（起点{best_dca['start_date']}）— 定投收益率 <strong>{best_dca['return_rate']*100:+.2f}%</strong>，年化 <strong>{best_dca['annualized_return']*100:+.2f}%</strong></li>"
    if worst_dca:
        html += f"<li><strong>最差定投收益率：</strong>{worst_dca['asset_name']}（起点{worst_dca['start_date']}）— 定投收益率 <strong>{worst_dca['return_rate']*100:+.2f}%</strong></li>"
    if best_xirr:
        html += f"<li><strong>最佳年化收益：</strong>{best_xirr['asset_name']}（起点{best_xirr['start_date']}）— 年化 <strong>{best_xirr['annualized_return']*100:+.2f}%</strong></li>"

    for s, (pos, total) in pos_ratio_by_start.items():
        html += f"<li>起点 <strong>{s}</strong>：{pos}/{total} 个标的正收益（{pos/total*100:.0f}%）</li>"

    # 比较三种起点的平均表现
    for s in start_labels:
        same = [r for r in results if r["start_date"] == s]
        if same:
            avg_ret = np.mean([r["return_rate"] for r in same])
            avg_xirr = np.mean([r["annualized_return"] for r in same if r["annualized_return"] is not None])
            html += f"<li>起点 <strong>{s}</strong> 平均定投收益率 <strong>{avg_ret*100:+.2f}%</strong>，平均年化 <strong>{avg_xirr*100:+.2f}%</strong></li>"

    # 定投 vs 一次性投入对比
    dca_better = sum(1 for r in results if r["return_rate"] > r["lump_sum_return"])
    lump_better = sum(1 for r in results if r["lump_sum_return"] > r["return_rate"])
    html += f"<li><strong>定投 vs 一次性投入：</strong>定投跑赢 {dca_better}/{len(results)} 组，一次性投入跑赢 {lump_better}/{len(results)} 组</li>"

    html += f"""
        </ol>
        <p style="margin-top:16px;opacity:0.8;">
            📅 报告生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} · 数据来源：Yahoo Finance
        </p>
    </div>
</div>
"""

    # ═══════ Modal ═══════
    html += """
</div>

<!-- Modal -->
<div class="modal" id="imageModal" onclick="this.style.display='none'">
    <span class="close" onclick="document.getElementById('imageModal').style.display='none'">&times;</span>
    <img id="modalImage" src="" alt="放大查看">
</div>

<script>
function openModal(img) {
    document.getElementById('modalImage').src = img.src;
    document.getElementById('imageModal').style.display = 'flex';
}
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.getElementById('imageModal').style.display = 'none';
    }
});
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ HTML 报告已生成: {output_path}")
    return output_path


# ══════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════

def main():
    project_dir = os.path.dirname(__file__)
    data_dir = os.path.join(project_dir, "data")
    chart_dir = os.path.join(project_dir, "charts")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(chart_dir, exist_ok=True)

    # Step 1: 拉取数据
    print("=" * 60)
    print("  第一步：拉取历史数据")
    print("=" * 60)
    dfs = prepare_all_data()

    # Step 2: 执行回测
    print("\n" + "=" * 60)
    print("  第二步：执行全部回测")
    print("=" * 60)
    results = run_all_backtests(dfs)

    if not results:
        print("错误：没有生成任何回测结果。")
        return

    # Step 3: 生成汇总表
    print("\n" + "=" * 60)
    print("  第三步：生成汇总表和图表")
    print("=" * 60)
    summary_df = build_summary_table(results)
    summary_path = os.path.join(project_dir, "summary.csv")
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"  汇总表已保存: {summary_path}")

    heatmap = build_heatmap_data(results)

    # Step 4: 生成图表
    print("\n  生成图表 ...")
    chart_paths = generate_charts(results, chart_dir)
    print(f"  共生成 {len(chart_paths)} 张图表")

    # Step 5: 生成 HTML 报告
    print("\n" + "=" * 60)
    print("  第四步：生成 HTML 报告")
    print("=" * 60)
    output_path = os.path.join(project_dir, "index.html")
    generate_html_report(results, summary_df, heatmap, chart_dir, output_path)

    print("\n" + "=" * 60)
    print("  ✅ 全部完成！")
    print(f"  📊 HTML 报告: {output_path}")
    print(f"  📋 汇总 CSV:  {summary_path}")
    print(f"  🖼️  图表目录:  {chart_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
