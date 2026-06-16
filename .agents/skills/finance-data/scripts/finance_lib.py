#!/usr/bin/env python3
"""
finance_lib — 金融数据拉取核心函数库

从 Yahoo Finance 拉取历史行情数据并本地缓存。
支持任意 Yahoo Finance 可查的股票/ETF/指数代码。

依赖:
    pip install yfinance pandas numpy
"""

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# 缓存目录（默认在脚本所在目录的 .cache 下）
CACHE_DIR = Path(__file__).parent.parent / ".cache"


def set_cache_dir(path: str) -> None:
    """设置缓存目录路径。"""
    global CACHE_DIR
    CACHE_DIR = Path(path)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


# 确保缓存目录存在
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(ticker: str) -> Path:
    """返回某个 ticker 的本地缓存文件路径。"""
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    return CACHE_DIR / f"{safe_ticker}.pkl"


def load_cache(ticker: str) -> Optional[pd.DataFrame]:
    """读取本地缓存，若不存在或损坏则返回 None。"""
    path = cache_path(ticker)
    if not path.exists():
        return None
    try:
        df = pd.read_pickle(path)
        if df.empty or "adj_close" not in df.columns:
            return None
        df.index = pd.to_datetime(df.index).date
        return df.sort_index()
    except Exception:
        return None


def save_cache(ticker: str, df: pd.DataFrame) -> None:
    """把数据保存到本地缓存。"""
    path = cache_path(ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)


def download_from_yf(ticker: str, start: date, end: date) -> pd.DataFrame:
    """从 Yahoo Finance 下载数据并标准化。

    使用 auto_adjust=True 获取复权价格（已折算分红/拆股）。
    """
    import yfinance as yf

    df = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )

    if df.empty:
        raise ValueError(
            f"未获取到 {ticker} 在 {start} 至 {end} 之间的数据，"
            f"请检查 ticker 代码或日期范围，或检查网络连接。"
        )

    # 处理多级列名（yfinance 新版行为）
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 提取 Close 列（auto_adjust=True 时 Close 即复权收盘价）
    df = df[["Close"]].copy()
    df.columns = ["adj_close"]
    df.index = pd.to_datetime(df.index).date
    df = df.sort_index()
    df["adj_close"] = df["adj_close"].astype(float)
    return df


def fetch_data(
    ticker: str,
    start: date,
    end: date,
    verbose: bool = True,
) -> pd.DataFrame:
    """获取 Adjusted Close 数据，优先使用本地缓存。

    若缓存已覆盖请求区间则直接读取；
    否则从 Yahoo Finance 补充下载并更新缓存。

    Args:
        ticker: Yahoo Finance 代码（如 "510300.SS", "SPY", "2800.HK"）
        start: 起始日期
        end: 结束日期
        verbose: 是否打印进度信息

    Returns:
        包含 "adj_close" 列的 DataFrame，index 为 date 类型
    """
    cached = load_cache(ticker)

    if cached is not None and not cached.empty:
        cache_start, cache_end = cached.index[0], cached.index[-1]
        covers_start = cache_start <= start or (cache_start - start).days <= 7
        covers_end = cache_end >= end
        if covers_start and covers_end:
            if verbose:
                print(f"  [缓存] {ticker}: {cache_start} ~ {cache_end}")
            return cached.loc[start:end].copy()

    # 需要下载补充数据
    if cached is not None and not cached.empty:
        download_start = min(start, cached.index[0])
        download_end = max(end, cached.index[-1])
    else:
        download_start, download_end = start, end

    if verbose:
        print(f"  [下载] {ticker} ({download_start} ~ {download_end}) ...")

    df_new = download_from_yf(ticker, download_start, download_end)

    if cached is not None:
        df = pd.concat([cached, df_new])
        df = df[~df.index.duplicated(keep="last")]
        df = df.sort_index()
    else:
        df = df_new

    save_cache(ticker, df)
    if verbose:
        print(f"  [缓存] 已更新 {cache_path(ticker)} ({df.index[0]} ~ {df.index[-1]})")

    result = df.loc[start:end]
    if result.empty:
        raise ValueError(
            f"未获取到 {ticker} 在 {start} 至 {end} 之间的数据，"
            f"请检查日期范围。"
        )
    return result.copy()


def fetch_multiple(
    ticker_specs: List[Tuple[str, str]],
    start: date,
    end: date,
    verbose: bool = True,
) -> pd.DataFrame:
    """同时拉取多个标的的数据并合并为一个 DataFrame。

    Args:
        ticker_specs: [(ticker, label), ...] 列表
        start: 起始日期
        end: 结束日期
        verbose: 是否打印进度信息

    Returns:
        合并后的 DataFrame，每列名为 "{label}_adj_close"
    """
    combined = pd.DataFrame()

    for ticker, label in ticker_specs:
        if verbose:
            print(f"\n[{label}] 正在获取 {ticker} ...")

        df = fetch_data(ticker, start, end, verbose=verbose)
        col_name = f"{label}_adj_close"
        combined[col_name] = df["adj_close"]

    return combined


def to_csv(
    df: pd.DataFrame,
    output_path: str,
    include_date: bool = True,
) -> str:
    """将 DataFrame 保存为 CSV 文件。

    Args:
        df: 要保存的 DataFrame
        output_path: 输出路径
        include_date: 是否将 index（date）作为列写入

    Returns:
        保存的文件路径
    """
    out = df.copy()
    if include_date:
        out.index.name = "date"
        out = out.reset_index()

    out.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


# ── 常用标的预定义配置 ──────────────────────────────────────────
PREDEFINED_TICKERS: Dict[str, Dict] = {
    "csi300": {"ticker": "510300.SS", "name": "沪深300", "market": "CN"},
    "sp500": {"ticker": "SPY", "name": "标普500", "market": "US"},
    "nasdaq100": {"ticker": "513100.SS", "name": "纳斯达克100", "market": "CN"},
    "hsi": {"ticker": "2800.HK", "name": "恒生指数", "market": "HK"},
    "hstech": {"ticker": "3032.HK", "name": "恒生科技", "market": "HK"},
    "vxus": {"ticker": "VXUS", "name": "全球除美", "market": "US"},
    "gem50": {"ticker": "159949.SZ", "name": "创业板50", "market": "CN"},
    "star50": {"ticker": "588000.SS", "name": "科创50", "market": "CN"},
    "cninet": {"ticker": "513050.SS", "name": "中概互联", "market": "CN"},
    "nikkei225": {"ticker": "513000.SS", "name": "日经225", "market": "CN"},
    "dax30": {"ticker": "513030.SS", "name": "德国30", "market": "CN"},
    "gold": {"ticker": "518880.SS", "name": "黄金ETF", "market": "CN"},
    "govtbond30": {"ticker": "511090.SS", "name": "30年国债", "market": "CN"},
}


def resolve_predefined(name: str) -> Tuple[str, str]:
    """根据预定义名称获取 (ticker, label)。"""
    name = name.lower().strip()
    if name == "all":
        raise ValueError("'all' 不支持单标解析，请逐个指定")
    if name not in PREDEFINED_TICKERS:
        raise KeyError(
            f"未知预定义标的: '{name}'。可选: {', '.join(PREDEFINED_TICKERS.keys())}"
        )
    cfg = PREDEFINED_TICKERS[name]
    return cfg["ticker"], cfg["name"]
