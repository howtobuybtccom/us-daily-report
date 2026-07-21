# 美股选股策略工具

一个可部署在 GitHub Pages 上的美股每日选股工具，由 GitHub Actions 每天定时抓取数据并自动更新页面。**无需任何 API Key，无需服务器。**

## 功能板块

| 板块 | 内容 |
| --- | --- |
| 🔥 成交额 Top 20 | 按当日成交额（价格 × 成交量）排出前 20 只个股；与前一交易日榜单对比，标记并**深度分析新进榜单的个股**（技术面总结 + 相关新闻） |
| 📈 趋势选股 Top 10 | 多因子打分（均线多头排列、均线斜率、RSI、MACD、动量、量能），过滤低价/低流动性标的，推送最看好的 10 只 |
| 📰 财经资讯 | 聚合 MarketWatch / CNBC / WSJ / Yahoo Finance 当日重要美股新闻 |

## 架构

```
┌─────────────────────┐   cron (工作日 21:30 UTC)   ┌──────────────────┐
│  GitHub Actions      │ ─────────────────────────▶ │ fetch_data.py     │
│  daily-update.yml    │                            │ yfinance 行情     │
└─────────────────────┘                            │ RSS 财经资讯      │
         │ 提交 public/data/*.json                  └──────────────────┘
         ▼
┌─────────────────────┐   push 触发                 ┌──────────────────┐
│  GitHub Actions      │ ─────────────────────────▶ │ React + Vite 前端 │
│  deploy.yml          │   构建 dist/ 部署 Pages     │ 读取 latest.json  │
└─────────────────────┘                            └──────────────────┘
```

## 部署步骤（约 3 分钟）

1. **推送代码到 GitHub**
   ```bash
   git init && git add . && git commit -m "init"
   git remote add origin https://github.com/<你的用户名>/<仓库名>.git
   git push -u origin main
   ```

2. **开启 GitHub Pages**
   仓库页面 → `Settings` → `Pages` → `Source` 选择 **GitHub Actions**。

3. **手动跑一次数据管道**（首次需要数据）
   仓库页面 → `Actions` → `每日数据更新` → `Run workflow`。

4. **完成**
   数据提交后会自动触发部署，访问 `https://<你的用户名>.github.io/<仓库名>/`。
   之后每个工作日收盘后自动更新，无需任何操作。

> 定时任务说明：cron 为 `30 21 * * 1-5`（工作日 21:30 UTC），即美东收盘后约 30–90 分钟。
> GitHub 免费账户的定时任务可能有数分钟延迟，属正常现象。

## 本地开发

```bash
# 1. 生成数据（约 2-5 分钟，取决于网络）
pip install -r pipeline/requirements.txt
python pipeline/fetch_data.py

# 2. 启动前端
npm install
npm run dev
```

## 自定义策略

所有策略逻辑都在 `pipeline/fetch_data.py`，可直接修改：

- **股票池**：默认标普 500 全量；`FALLBACK_UNIVERSE` 为网络异常时的高流动性备选名单，也可以改成自己的观察清单
- **趋势打分**：`trend_score()` 函数内调整各因子权重（均线 / RSI / MACD / 动量 / 量能）
- **榜单规则**：`build_top_volume()` 中的 `[:20]` 改数量
- **资讯源**：`MARKET_FEEDS` 列表增删 RSS 源
- **更新时间**：`.github/workflows/daily-update.yml` 中的 cron 表达式

## 免责声明

本工具仅供学习研究，不构成投资建议。数据来自公开渠道（Yahoo Finance、各大媒体 RSS），可能存在延迟或错误。股市有风险，投资需谨慎。
