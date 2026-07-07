#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
美股量化日报 v1.0(选股 + 成交榜监控 合并版)
================================================
每日收盘后输出两段式日报,数据只下载一次:

【第一段】多因子选股 TOP N
  - 12-1 动量(40%) + 距52周高点(25%) + 低波动(20%) + 量能放大(15%)
  - 硬过滤:价 > MA50 > MA200 多头排列、股价≥$5、日均成交额≥$500万

【第二段】成交榜 TOP50 监控
  - 🆕 新进榜:今日进前50,此前20个交易日均未上榜
  - 👀 守榜观察:入榜后第2~4天仍在榜
  - ⭐ 重点提醒:连续5个交易日守住前50(第5天触发,只报一次)

依赖: pip install yfinance pandas numpy lxml requests
用法:
  python daily_report.py                # 控制台输出
  python daily_report.py --push        # 推送微信/钉钉
  python daily_report.py --top 10      # 选股只出前10

推送环境变量(二选一或都配):
  SERVERCHAN_KEY    Server酱 SendKey -> 微信
  DINGTALK_WEBHOOK  钉钉群机器人 Webhook
"""

import argparse
import os
import sys
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    sys.exit("请先安装依赖: pip install yfinance pandas numpy lxml requests")

# ============================================================
# 参数区
# ============================================================
CONFIG = {
    # ---- 选股 ----
    "TOP_N": 20,              # 选股数量
    "LOOKBACK_YEARS": 2,      # 下载年数(动量需 ~13个月,2年足够)
    "MOM_WINDOW": 252,        # 12个月动量窗口
    "MOM_SKIP": 21,           # 剔除最近1个月
    "VOL_WINDOW": 60,         # 波动率窗口
    "VOLUME_SHORT": 20,
    "VOLUME_LONG": 120,
    "MIN_PRICE": 5.0,
    "MIN_DOLLAR_VOL": 5e6,
    "WEIGHTS": {
        "momentum": 0.40,
        "low_vol": 0.20,
        "high_52w": 0.25,
        "volume_surge": 0.15,
    },
    # ---- 成交榜监控 ----
    "TOP_K": 50,              # 榜单深度
    "PERSIST_DAYS": 5,        # 连续守榜天数 -> 重点提醒
    "LOOKBACK_OUT": 20,       # 入榜前多少个交易日不在榜才算"新进"
    "BY_DOLLAR": True,        # True=成交额排名, False=股数
}


# ============================================================
# 数据层(只下载一次,两段共用)
# ============================================================
FALLBACK_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    "BRK-B", "JPM", "V", "UNH", "XOM", "LLY", "MA", "HD", "COST",
    "PG", "JNJ", "ABBV", "NFLX", "CRM", "AMD", "ORCL", "ADBE",
    "WMT", "MRK", "KO", "PEP", "TMO", "BAC", "CSCO", "ACN", "MCD",
    "LIN", "INTU", "QCOM", "TXN", "CAT", "GE", "AMAT", "ISRG",
    "NOW", "UBER", "BKNG", "PLTR", "SPOT", "PANW", "ANET", "MU",
    "COIN", "MSTR", "HOOD", "SMCI", "ARM", "DELL", "VRT", "CEG",
]


def get_universe() -> list[str]:
    """Wikipedia 抓 S&P 500;GitHub Actions IP 常被 403,带 UA 请求,
    失败则降级到内置票池,保证日报照常产出"""
    import io
    import requests
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/125.0 Safari/537.36")}
    try:
        html = requests.get(url, headers=headers, timeout=20)
        html.raise_for_status()
        tables = pd.read_html(io.StringIO(html.text))
        tickers = [t.replace(".", "-") for t in tables[0]["Symbol"].tolist()]
        if len(tickers) < 400:
            raise ValueError(f"解析结果异常,仅 {len(tickers)} 只")
        print(f"[数据] S&P 500 成分股 {len(tickers)} 只")
        return tickers
    except Exception as e:
        print(f"[警告] Wikipedia 票池获取失败({e}),"
              f"降级到内置票池 {len(FALLBACK_TICKERS)} 只")
        return FALLBACK_TICKERS


def download(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = (datetime.now()
             - timedelta(days=365 * CONFIG["LOOKBACK_YEARS"] + 30)
             ).strftime("%Y-%m-%d")
    print(f"[数据] 下载 {len(tickers)} 只股票 {start} 至今日线 ...")
    raw = yf.download(tickers, start=start, auto_adjust=True,
                      progress=False, threads=True)
    if raw is None or raw.empty:
        sys.exit("[错误] yfinance 返回空数据,大概率是 Yahoo 对当前 IP 限流,"
                 "稍后重跑或参阅日志")
    close = raw["Close"].dropna(axis=1, how="all")
    volume = raw["Volume"].reindex(columns=close.columns)
    if close.empty:
        sys.exit("[错误] 全部标的下载失败(Yahoo 限流),稍后重跑")
    print(f"[数据] 有效标的 {len(close.columns)} 只,"
          f"交易日 {len(close)} 天,最新 {close.index[-1].date()}")
    return close, volume


# ============================================================
# 第一段:多因子选股
# ============================================================
def zscore(s: pd.Series) -> pd.Series:
    z = (s - s.mean()) / (s.std() + 1e-12)
    return z.clip(-3, 3)


def run_screener(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    c = CONFIG
    need = c["MOM_WINDOW"] + c["MOM_SKIP"]
    px = close.loc[:, close.notna().sum() >= need + 20]
    vol = volume[px.columns]
    if px.empty:
        return pd.DataFrame()

    last = px.iloc[-1]
    ma50 = px.rolling(50).mean().iloc[-1]
    ma200 = px.rolling(200).mean().iloc[-1]
    dollar_vol = (px.iloc[-20:] * vol.iloc[-20:]).mean()
    mask = ((last > ma50) & (ma50 > ma200)
            & (last >= c["MIN_PRICE"])
            & (dollar_vol >= c["MIN_DOLLAR_VOL"]))
    u = mask[mask].index
    if len(u) < 5:
        return pd.DataFrame()

    mom = px[u].iloc[-c["MOM_SKIP"] - 1] / \
          px[u].iloc[-c["MOM_WINDOW"] - c["MOM_SKIP"]] - 1
    ret = px[u].pct_change().iloc[-c["VOL_WINDOW"]:]
    volat = ret.std() * np.sqrt(252)
    prox = last[u] / px[u].iloc[-252:].max()
    vsurge = (vol[u].iloc[-c["VOLUME_SHORT"]:].mean()
              / (vol[u].iloc[-c["VOLUME_LONG"]:].mean() + 1e-9)
              ).replace([np.inf, -np.inf], np.nan)

    df = pd.DataFrame({"momentum": mom, "volatility": volat,
                       "high_52w": prox, "volume_surge": vsurge}).dropna()
    w = c["WEIGHTS"]
    df["score"] = (w["momentum"] * zscore(df["momentum"])
                   + w["low_vol"] * zscore(-df["volatility"])
                   + w["high_52w"] * zscore(df["high_52w"])
                   + w["volume_surge"] * zscore(df["volume_surge"]))
    return df.sort_values("score", ascending=False).head(c["TOP_N"])


# ============================================================
# 第二段:成交榜 TOP50 监控
# ============================================================
def run_monitor(close: pd.DataFrame, volume: pd.DataFrame) -> dict:
    c = CONFIG
    k, p, lb = c["TOP_K"], c["PERSIST_DAYS"], c["LOOKBACK_OUT"]

    metric = close * volume if c["BY_DOLLAR"] else volume.astype(float)
    member = metric.rank(axis=1, ascending=False, method="min") <= k

    n = len(member)
    if n < lb + p + 1:
        return {}

    in_today = member.iloc[-1]

    # 新进榜:今天在榜,前 lb 天全不在榜
    new_today = in_today & ~member.iloc[n - 1 - lb: n - 1].any()

    # 重点提醒:连续 p 天在榜,入榜前 lb 天全不在榜
    alert_5d = (member.iloc[n - p: n].all()
                & ~member.iloc[n - p - lb: n - p].any())

    # 守榜观察:第 2 ~ p-1 天
    watching = {}
    for d in range(2, p):
        hit = (member.iloc[n - d: n].all()
               & ~member.iloc[n - d - lb: n - d].any()
               & ~alert_5d)
        for t in member.columns[hit]:
            watching[t] = d

    rank_today = metric.iloc[-1].rank(ascending=False, method="min")
    chg = close.iloc[-1] / close.iloc[-2] - 1

    def rows(tickers):
        out = []
        for t in sorted(tickers, key=lambda x: rank_today[x]):
            v = metric.iloc[-1][t]
            vtxt = f"${v/1e9:.2f}B" if c["BY_DOLLAR"] else f"{v/1e6:.1f}M股"
            out.append(f"  {t:<6} 第{int(rank_today[t]):>2}名  "
                       f"{chg[t]:+.2%}  {vtxt}  ${close.iloc[-1][t]:.2f}")
        return out

    return {
        "alert_5d": rows(member.columns[alert_5d]),
        "new_today": rows(member.columns[new_today]),
        "watching": [f"  {t:<6} 已连续{d}日在榜,当前第{int(rank_today[t])}名"
                     for t, d in sorted(watching.items(),
                                        key=lambda x: -x[1])],
    }


# ============================================================
# 渲染与推送
# ============================================================
def render(picks: pd.DataFrame, mon: dict, asof) -> str:
    c = CONFIG
    L = [f"📈 美股量化日报 | {asof}", "=" * 36]

    # ---- 第一段:选股 ----
    L.append(f"\n【一】多因子选股 TOP {len(picks)}")
    L.append("(动量40/距高点25/低波20/量能15,多头排列过滤)")
    if picks.empty:
        L.append("  今日无符合条件标的")
    else:
        for i, (t, r) in enumerate(picks.iterrows(), 1):
            L.append(f"  {i:>2}. {t:<6} 分{r['score']:+.2f}  "
                     f"动量{r['momentum']:+.0%}  "
                     f"距高{r['high_52w']:.0%}  "
                     f"量比{r['volume_surge']:.2f}x")

    # ---- 第二段:成交榜 ----
    L.append(f"\n【二】成交榜TOP{c['TOP_K']}监控"
             f"({'成交额' if c['BY_DOLLAR'] else '股数'}排名)")
    if not mon:
        L.append("  数据不足,跳过")
    else:
        if mon["alert_5d"]:
            L.append(f"\n⭐⭐ 重点提醒:连续{c['PERSIST_DAYS']}日守住前"
                     f"{c['TOP_K']}(资金持续性确认)")
            L += mon["alert_5d"]
        if mon["new_today"]:
            L.append(f"\n🆕 今日新进前{c['TOP_K']}"
                     f"(此前{c['LOOKBACK_OUT']}日未上榜)")
            L += mon["new_today"]
        if mon["watching"]:
            L.append("\n👀 守榜观察中(未满5日)")
            L += mon["watching"]
        if not (mon["alert_5d"] or mon["new_today"] or mon["watching"]):
            L.append("  今日无新进榜/守榜信号")

    L.append("\n" + "=" * 36)
    L.append("仅供研究参考,不构成投资建议")
    return "\n".join(L)


def push(text: str):
    import requests
    key = os.environ.get("SERVERCHAN_KEY")
    ding = os.environ.get("DINGTALK_WEBHOOK")
    title = text.splitlines()[0]
    if key:
        try:
            r = requests.post(f"https://sctapi.ftqq.com/{key}.send",
                              data={"title": title,
                                    "desp": f"```\n{text}\n```"},
                              timeout=10)
            print(f"[推送] Server酱 HTTP {r.status_code}")
        except Exception as e:
            print(f"[推送] Server酱失败: {e}")
    if ding:
        try:
            r = requests.post(ding, json={"msgtype": "text",
                                          "text": {"content": text}},
                              timeout=10)
            print(f"[推送] 钉钉 HTTP {r.status_code}")
        except Exception as e:
            print(f"[推送] 钉钉失败: {e}")
    if not key and not ding:
        print("[推送] 未配置 SERVERCHAN_KEY / DINGTALK_WEBHOOK,跳过")


# ============================================================
# 主流程
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=CONFIG["TOP_N"],
                    help="选股数量")
    ap.add_argument("--by-shares", action="store_true",
                    help="成交榜按股数而非成交额排名")
    ap.add_argument("--push", action="store_true", help="推送微信/钉钉")
    ap.add_argument("--tickers", type=str, default="",
                    help="自定义票池,逗号分隔;默认 S&P 500")
    args = ap.parse_args()

    CONFIG["TOP_N"] = args.top
    CONFIG["BY_DOLLAR"] = not args.by_shares

    tickers = ([t.strip().upper() for t in args.tickers.split(",")
                if t.strip()] if args.tickers else get_universe())

    close, volume = download(tickers)      # 只下载一次
    picks = run_screener(close, volume)    # 第一段
    mon = run_monitor(close, volume)       # 第二段

    text = render(picks, mon, close.index[-1].date())
    print("\n" + text)
    if args.push:
        push(text)


if __name__ == "__main__":
    main()
