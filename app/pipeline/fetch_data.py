#!/usr/bin/env python3
"""
美股选股策略数据管道
=====================
每日由 GitHub Actions 运行（也可本地运行），生成三个板块的数据：

  板块一：成交额 Top 20 个股 + 新进榜单个股分析
  板块二：趋势上升选股 Top 10（多因子打分）
  板块三：当日重要美股财经资讯（RSS 聚合）

输出：
  public/data/latest.json          最新一期数据（前端读取）
  public/data/YYYY-MM-DD.json      按交易日归档

数据源：yfinance（行情）+ 公开 RSS（资讯），无需 API Key。
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from io import StringIO

import numpy as np
import pandas as pd
import requests

try:
    import yfinance as yf
except ImportError:
    sys.exit("请先安装 yfinance: pip install yfinance")

try:
    import feedparser
except ImportError:
    feedparser = None

ET = timezone(timedelta(hours=-4), name="ET")  # 美东夏令时；仅用于展示日期
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "data")

# ---------------------------------------------------------------------------
# 股票池：优先标普 500 全量，失败时回退到内置高流动性名单
# ---------------------------------------------------------------------------
SP500_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"

FALLBACK_UNIVERSE = [
    ("AAPL", "Apple Inc."), ("MSFT", "Microsoft"), ("NVDA", "NVIDIA"), ("AMZN", "Amazon"),
    ("GOOGL", "Alphabet A"), ("META", "Meta Platforms"), ("TSLA", "Tesla"), ("AVGO", "Broadcom"),
    ("AMD", "AMD"), ("PLTR", "Palantir"), ("SMCI", "Super Micro"), ("MU", "Micron"),
    ("INTC", "Intel"), ("QCOM", "Qualcomm"), ("ORCL", "Oracle"), ("CRM", "Salesforce"),
    ("NFLX", "Netflix"), ("COIN", "Coinbase"), ("MARA", "MARA Holdings"), ("HOOD", "Robinhood"),
    ("SOFI", "SoFi"), ("F", "Ford"), ("GM", "General Motors"), ("RIVN", "Rivian"),
    ("LCID", "Lucid Group"), ("NIO", "NIO"), ("XPEV", "XPeng"), ("BABA", "Alibaba"),
    ("PDD", "PDD Holdings"), ("JD", "JD.com"), ("JPM", "JPMorgan"), ("BAC", "Bank of America"),
    ("WFC", "Wells Fargo"), ("GS", "Goldman Sachs"), ("MS", "Morgan Stanley"), ("C", "Citigroup"),
    ("V", "Visa"), ("MA", "Mastercard"), ("PYPL", "PayPal"), ("XYZ", "Block"),
    ("XOM", "Exxon Mobil"), ("CVX", "Chevron"), ("OXY", "Occidental"), ("SLB", "Schlumberger"),
    ("PFE", "Pfizer"), ("MRNA", "Moderna"), ("JNJ", "Johnson & Johnson"), ("LLY", "Eli Lilly"),
    ("UNH", "UnitedHealth"), ("ABBV", "AbbVie"), ("DIS", "Disney"), ("WMT", "Walmart"),
    ("COST", "Costco"), ("KO", "Coca-Cola"), ("PEP", "PepsiCo"), ("MCD", "McDonald's"),
    ("NKE", "Nike"), ("BA", "Boeing"), ("UBER", "Uber"), ("LYFT", "Lyft"),
    ("ABNB", "Airbnb"), ("SHOP", "Shopify"), ("SNOW", "Snowflake"), ("CRWD", "CrowdStrike"),
    ("PANW", "Palo Alto Networks"), ("ARM", "Arm Holdings"), ("TSM", "TSMC"), ("ASML", "ASML"),
    ("DELL", "Dell"), ("HPQ", "HP Inc."), ("CSCO", "Cisco"), ("IBM", "IBM"),
    ("MSTR", "MicroStrategy"), ("RIOT", "Riot Platforms"), ("GME", "GameStop"), ("AMC", "AMC"),
    ("SNAP", "Snap"), ("PINS", "Pinterest"), ("RBLX", "Roblox"), ("DKNG", "DraftKings"),
    ("AAL", "American Airlines"), ("DAL", "Delta Air Lines"), ("UAL", "United Airlines"),
    ("CCL", "Carnival"), ("NCLH", "Norwegian Cruise"), ("T", "AT&T"), ("VZ", "Verizon"),
    ("TMUS", "T-Mobile"), ("SIRI", "Sirius XM"), ("PARA", "Paramount"), ("WBD", "Warner Bros."),
    ("ON", "ON Semiconductor"), ("TXN", "Texas Instruments"), ("ADI", "Analog Devices"),
    ("LRCX", "Lam Research"), ("AMAT", "Applied Materials"), ("KLAC", "KLA Corp"),
    ("MRVL", "Marvell"), ("SWKS", "Skyworks"), ("MPWR", "Monolithic Power"), ("ENPH", "Enphase"),
]


def load_universe() -> pd.DataFrame:
    """返回 DataFrame: columns=[Symbol, Name]，优先标普 500。"""
    try:
        r = requests.get(SP500_URL, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        df = df[["Symbol", "Name"]].dropna()
        # yfinance 用 "-" 代替 "."
        df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
        print(f"[universe] 标普500 成分股 {len(df)} 只")
        return df
    except Exception as e:
        print(f"[universe] 标普500 获取失败({e})，使用内置名单 {len(FALLBACK_UNIVERSE)} 只")
        return pd.DataFrame(FALLBACK_UNIVERSE, columns=["Symbol", "Name"])


# ---------------------------------------------------------------------------
# 技术指标
# ---------------------------------------------------------------------------
def rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    val = 100 - 100 / (1 + rs)
    return float(val.iloc[-1]) if not np.isnan(val.iloc[-1]) else 50.0


def macd_hist(close: pd.Series) -> float:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    return float((dif - dea).iloc[-1])


def compute_metrics(close: pd.Series, volume: pd.Series) -> dict | None:
    """单只个股的全部指标；数据不足返回 None。"""
    df = pd.DataFrame({"close": close, "volume": volume}).dropna()
    if len(df) < 60:
        return None
    c, v = df["close"], df["volume"]
    last, prev = float(c.iloc[-1]), float(c.iloc[-2])
    if last <= 0:
        return None

    ma20 = c.rolling(20).mean()
    ma50 = c.rolling(50).mean()
    ma200 = c.rolling(200).mean() if len(c) >= 200 else pd.Series([np.nan])

    dollar_vol = c * v
    hi52 = float(c.tail(252).max())
    lo52 = float(c.tail(252).min())

    m = {
        "price": round(last, 2),
        "change_pct": round((last / prev - 1) * 100, 2),
        "volume": int(v.iloc[-1]),
        "dollar_volume": float(dollar_vol.iloc[-1]),
        "dollar_volume_prev": float(dollar_vol.iloc[-2]),
        "avg_dollar_volume_20d": float(dollar_vol.tail(21).iloc[:-1].mean()),
        "rsi": round(rsi(c), 1),
        "macd_hist": round(macd_hist(c), 3),
        "ma20": float(ma20.iloc[-1]),
        "ma50": float(ma50.iloc[-1]),
        "ma200": float(ma200.iloc[-1]) if len(c) >= 200 and not np.isnan(ma200.iloc[-1]) else None,
        "ma20_slope": float(ma20.iloc[-1] / ma20.iloc[-6] - 1),  # 5日斜率
        "ret_20d": round((last / float(c.iloc[-21]) - 1) * 100, 2),
        "ret_60d": round((last / float(c.iloc[-61]) - 1) * 100, 2),
        "week52_position": round((last - lo52) / (hi52 - lo52) * 100, 1) if hi52 > lo52 else 50.0,
        "vol_ratio": float(v.iloc[-1] / v.tail(21).iloc[:-1].mean()) if v.tail(21).iloc[:-1].mean() > 0 else 1.0,
        "close_series": c,
    }
    return m


# ---------------------------------------------------------------------------
# 板块一：成交额 Top 20 + 新进分析
# ---------------------------------------------------------------------------
def build_top_volume(metrics: dict[str, dict], names: dict[str, str]) -> tuple[list[dict], list[dict]]:
    rows = []
    for t, m in metrics.items():
        rows.append({
            "ticker": t,
            "name": names.get(t, t),
            "price": m["price"],
            "change_pct": m["change_pct"],
            "volume": m["volume"],
            "dollar_volume": m["dollar_volume"],
            "dollar_volume_prev": m["dollar_volume_prev"],
            "vol_ratio": round(m["vol_ratio"], 2),
        })
    today = sorted(rows, key=lambda r: r["dollar_volume"], reverse=True)[:20]
    prev = sorted(rows, key=lambda r: r["dollar_volume_prev"], reverse=True)[:20]
    prev_set = {r["ticker"] for r in prev}

    for i, r in enumerate(today, 1):
        r["rank"] = i
        r["is_new"] = r["ticker"] not in prev_set

    new_entrants = []
    for r in today:
        if not r["is_new"]:
            continue
        m = metrics[r["ticker"]]
        new_entrants.append({**r, **analyze_new_entrant(r["ticker"], r, m, names)})
    return today, new_entrants


def analyze_new_entrant(ticker: str, row: dict, m: dict, names: dict) -> dict:
    """对新进 Top20 的个股做技术面总结 + 抓取个股相关新闻。"""
    name = names.get(ticker, ticker)
    above = [x for x, mv in [("20日", m["ma20"]), ("50日", m["ma50"]), ("200日", m["ma200"])]
             if mv is not None and m["price"] > mv]
    below = [x for x, mv in [("20日", m["ma20"]), ("50日", m["ma50"]), ("200日", m["ma200"])]
             if mv is not None and m["price"] <= mv]

    if m["rsi"] >= 75:
        rsi_txt = f"RSI {m['rsi']}，已进入超买区，短线追高风险较大"
    elif m["rsi"] >= 55:
        rsi_txt = f"RSI {m['rsi']}，处于强势区间"
    elif m["rsi"] >= 45:
        rsi_txt = f"RSI {m['rsi']}，动能中性"
    else:
        rsi_txt = f"RSI {m['rsi']}，动能偏弱，需警惕放量下跌"

    direction = "上涨" if row["change_pct"] >= 0 else "下跌"
    vol_txt = ("成交量显著放大，为 20 日均量的 "
               f"{row['vol_ratio']} 倍") if row["vol_ratio"] >= 1.5 else f"成交量约为 20 日均量的 {row['vol_ratio']} 倍"

    if above and not below:
        ma_txt = f"股价站上{('、').join(above)}均线，均线结构偏多"
    elif below and not above:
        ma_txt = f"股价位于{('、').join(below)}均线下方，趋势偏弱"
    else:
        ma_txt = (f"股价站上{('、').join(above)}均线" if above else "") + \
                 (f"，但仍在{('、').join(below)}均线下方" if below else "")

    pos = m["week52_position"]
    pos_txt = ("接近 52 周高位" if pos >= 80 else "处于 52 周区间低位" if pos <= 20 else "处于 52 周区间中部")

    summary = (
        f"{name}（{ticker}）今日以 {row['dollar_volume']/1e8:.0f} 亿美元成交额新进榜单第 {row['rank']} 名，"
        f"{direction} {abs(row['change_pct']):.2f}%。{vol_txt}。"
        f"技术面：{ma_txt}；{rsi_txt}；当前股价{pos_txt}（52周位置 {pos:.0f}%）。"
    )
    if row["change_pct"] >= 5:
        summary += "单日涨幅较大，注意利好兑现后的波动风险。"
    elif row["change_pct"] <= -5:
        summary += "单日放量大跌，建议先确认消息面是否有重大利空。"

    return {
        "rsi": m["rsi"],
        "week52_position": m["week52_position"],
        "ret_20d": m["ret_20d"],
        "summary": summary,
        "news": fetch_ticker_news(ticker),
    }


# ---------------------------------------------------------------------------
# 板块二：趋势上升选股 Top 10
# ---------------------------------------------------------------------------
def trend_score(m: dict) -> tuple[float, list[str]]:
    """多因子打分（满分 100），返回 (分数, 理由列表)。"""
    score, reasons = 0.0, []

    if m["price"] < 5 or m["avg_dollar_volume_20d"] < 1e8:
        return -1, []  # 流动性过滤

    if m["price"] > m["ma20"]:
        score += 12; reasons.append("股价位于 20 日均线上方")
    if m["ma20"] > m["ma50"]:
        score += 15; reasons.append("20 日均线上穿 50 日均线（多头排列）")
    if m["ma200"] is not None and m["ma50"] > m["ma200"]:
        score += 15; reasons.append("50 日均线位于 200 日均线上方（长期趋势向上）")
    if m["ma20_slope"] > 0:
        score += 13; reasons.append(f"20 日均线持续上行（5日斜率 {m['ma20_slope']*100:+.1f}%）")
    if 50 <= m["rsi"] <= 70:
        score += 15; reasons.append(f"RSI {m['rsi']}，强势且未超买")
    elif m["rsi"] > 70:
        score += 6; reasons.append(f"RSI {m['rsi']}，强势但接近超买")
    if m["macd_hist"] > 0:
        score += 10; reasons.append("MACD 柱状图为正，动能向上")
    if m["ret_60d"] > 10:
        score += 10; reasons.append(f"近 60 日涨幅 {m['ret_60d']:+.1f}%，中期动能强劲")
    elif m["ret_60d"] > 0:
        score += 5; reasons.append(f"近 60 日涨幅 {m['ret_60d']:+.1f}%")
    if m["ret_20d"] > 5:
        score += 5; reasons.append(f"近 20 日涨幅 {m['ret_20d']:+.1f}%")
    if m["vol_ratio"] >= 1.2:
        score += 5; reasons.append(f"量能配合（量比 {m['vol_ratio']:.1f}）")

    return score, reasons


def build_trend_picks(metrics: dict[str, dict], names: dict[str, str]) -> list[dict]:
    scored = []
    for t, m in metrics.items():
        s, reasons = trend_score(m)
        if s > 0:
            scored.append({
                "ticker": t, "name": names.get(t, t), "score": round(s, 1),
                "price": m["price"], "change_pct": m["change_pct"], "rsi": m["rsi"],
                "ret_20d": m["ret_20d"], "ret_60d": m["ret_60d"], "reasons": reasons,
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:10]


# ---------------------------------------------------------------------------
# 板块三：财经资讯 RSS 聚合
# ---------------------------------------------------------------------------
MARKET_FEEDS = [
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("CNBC", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
]


def _parse_feed(url: str, limit: int) -> list[dict]:
    if feedparser is None:
        return []
    try:
        d = feedparser.parse(url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        items = []
        for e in d.entries[:limit]:
            pub = ""
            if getattr(e, "published", None):
                try:
                    pub = parsedate_to_datetime(e.published).astimezone(ET).strftime("%m-%d %H:%M")
                except Exception:
                    pub = e.published[:16]
            summary = getattr(e, "summary", "") or ""
            # 去 HTML 标签
            summary = pd.Series([summary]).str.replace(r"<[^>]+>", "", regex=True).iloc[0][:150]
            items.append({"title": getattr(e, "title", "").strip(),
                          "link": getattr(e, "link", ""),
                          "published": pub, "summary": summary.strip()})
        return items
    except Exception as e:
        print(f"[news] 抓取失败 {url}: {e}")
        return []


def build_market_news(limit: int = 12) -> list[dict]:
    all_items = []
    for source, url in MARKET_FEEDS:
        for it in _parse_feed(url, 6):
            it["source"] = source
            all_items.append(it)
    # 去重（按标题前 40 字符）
    seen, out = set(), []
    for it in all_items:
        key = it["title"][:40].lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out[:limit]


def fetch_ticker_news(ticker: str, limit: int = 2) -> list[dict]:
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    items = _parse_feed(url, limit)
    for it in items:
        it.pop("summary", None)
        it["publisher"] = "Yahoo Finance"
    return items


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def load_metrics_from_csv(csv_dir: str, tickers: list[str], names: dict[str, str]) -> dict[str, dict]:
    """从本地 CSV 目录读取历史数据（离线/演示模式）。
    CSV 需包含 Date, Close, Volume 列（兼容插件导出的格式，可含中文名列 thsname_cn）。"""
    metrics: dict[str, dict] = {}
    for t in tickers:
        path = os.path.join(csv_dir, f"{t}.csv")
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path)
            close = pd.to_numeric(df["Close"], errors="coerce")
            volume = pd.to_numeric(df["Volume"], errors="coerce")
            m = compute_metrics(close, volume)
            if m:
                m["_last_date"] = str(df["Date"].iloc[-1])[:10]
                metrics[t] = m
                if "thsname_cn" in df.columns and df["thsname_cn"].dropna().size:
                    cn = str(df["thsname_cn"].dropna().iloc[0])
                    if cn and cn != "nan":
                        names[t] = cn
        except Exception as e:
            print(f"[csv] {t} 读取失败: {e}")
    return metrics


def main() -> None:
    t0 = time.time()
    csv_dir = None
    if "--csv-dir" in sys.argv:
        csv_dir = sys.argv[sys.argv.index("--csv-dir") + 1]

    universe = load_universe()
    tickers = universe["Symbol"].tolist()
    names = dict(zip(universe["Symbol"], universe["Name"]))

    if csv_dir:
        print(f"[csv] 离线模式：从 {csv_dir} 读取历史数据…")
        metrics = load_metrics_from_csv(csv_dir, tickers, names)
        print(f"[metrics] 有效股票 {len(metrics)} 只")
    else:
        print(f"[download] 下载 {len(tickers)} 只股票近 1 年日线数据…")
        metrics = {}
        pending = list(tickers)

        # 分批下载 + 失败重试（最多 3 轮），提高网络波动下的成功率
        for attempt in range(1, 4):
            if not pending:
                break
            failed = []
            batch_size = 50 if attempt == 1 else 15
            for i in range(0, len(pending), batch_size):
                batch = pending[i:i + batch_size]
                try:
                    data = yf.download(batch, period="1y", group_by="ticker",
                                       threads=True, auto_adjust=True, progress=False, timeout=30)
                except Exception as e:
                    print(f"[download] 批次异常({e})，稍后重试")
                    failed.extend(batch)
                    continue
                for t in batch:
                    try:
                        sub = data[t] if len(batch) > 1 else data
                        m = compute_metrics(sub["Close"], sub["Volume"])
                        if m:
                            metrics[t] = m
                        else:
                            failed.append(t)
                    except Exception:
                        failed.append(t)
            pending = failed
            print(f"[download] 第 {attempt} 轮完成：成功 {len(metrics)} 只，待重试 {len(pending)} 只")
            if pending and attempt < 3:
                time.sleep(5)

        print(f"[metrics] 有效股票 {len(metrics)} 只")

    if not metrics:
        sys.exit("没有取到任何行情数据，任务终止")

    # 交易日：优先取行情数据的最新日期，否则用当前美东日期
    dates = [m.pop("_last_date") for m in metrics.values() if "_last_date" in m]
    trade_date = max(dates) if dates else datetime.now(ET).strftime("%Y-%m-%d")

    top_volume, new_entrants = build_top_volume(metrics, names)
    trend_picks = build_trend_picks(metrics, names)
    news = build_market_news()

    result = {
        "generated_at": datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"),
        "trade_date": trade_date,
        "universe_size": len(metrics),
        "top_volume": top_volume,
        "new_entrants": new_entrants,
        "trend_picks": trend_picks,
        "news": news,
        "disclaimer": "本工具仅供学习研究，不构成投资建议。数据来源于公开渠道，可能存在延迟或错误。",
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    for fname in ("latest.json", f"{trade_date}.json"):
        with open(os.path.join(OUT_DIR, fname), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"[done] 数据已写入 {OUT_DIR}（{time.time()-t0:.0f}s）")


if __name__ == "__main__":
    main()
