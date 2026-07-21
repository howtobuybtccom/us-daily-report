import type { DailyData } from '@/types'
import { fmtUsd, fmtVol } from '@/hooks/useDailyData'
import { TrendingUp, TrendingDown, Sparkles, ExternalLink, Newspaper } from 'lucide-react'

const ChangeTag = ({ v }: { v: number }) => (
  <span className={`inline-flex items-center gap-1 font-mono font-semibold ${v >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
    {v >= 0 ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
    {v >= 0 ? '+' : ''}{v.toFixed(2)}%
  </span>
)

export default function TopVolume({ data }: { data: DailyData }) {
  return (
    <div className="space-y-8">
      {/* 榜单表格 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <span className="w-1 h-5 bg-amber-400 rounded-full" />
            成交额 Top 20 榜单
          </h2>
          <span className="text-xs text-slate-500">按当日成交额（价格 × 成交量）排序 · 股票池 {data.universe_size} 只</span>
        </div>
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/50">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-xs">
                <th className="px-4 py-3 text-left font-medium">#</th>
                <th className="px-4 py-3 text-left font-medium">代码 / 名称</th>
                <th className="px-4 py-3 text-right font-medium">最新价</th>
                <th className="px-4 py-3 text-right font-medium">涨跌幅</th>
                <th className="px-4 py-3 text-right font-medium">成交额</th>
                <th className="px-4 py-3 text-right font-medium">成交量</th>
                <th className="px-4 py-3 text-right font-medium">量比(20d)</th>
                <th className="px-4 py-3 text-center font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {data.top_volume.map((r) => (
                <tr key={r.ticker}
                    className={`border-b border-slate-800/60 transition-colors hover:bg-slate-800/40 ${r.is_new ? 'bg-amber-400/5' : ''}`}>
                  <td className="px-4 py-3 font-mono text-slate-400">{r.rank}</td>
                  <td className="px-4 py-3">
                    <div className="font-bold text-white">{r.ticker}</div>
                    <div className="text-xs text-slate-500 truncate max-w-[180px]">{r.name}</div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-200">${r.price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right"><ChangeTag v={r.change_pct} /></td>
                  <td className="px-4 py-3 text-right font-mono text-slate-200">{fmtUsd(r.dollar_volume)}</td>
                  <td className="px-4 py-3 text-right font-mono text-slate-400">{fmtVol(r.volume)}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    <span className={r.vol_ratio >= 1.5 ? 'text-amber-400 font-semibold' : 'text-slate-400'}>
                      {r.vol_ratio.toFixed(2)}x
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {r.is_new && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-400/15 text-amber-300 border border-amber-400/30">
                        <Sparkles className="w-3 h-3" />新进
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 新进个股分析 */}
      <div>
        <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-1">
          <span className="w-1 h-5 bg-emerald-400 rounded-full" />
          新进榜单个股分析
          <span className="text-sm font-normal text-slate-500">（{data.new_entrants.length} 只）</span>
        </h2>
        <p className="text-xs text-slate-500 mb-4">与上一交易日 Top 20 榜单对比，以下为今日首次进入榜单的个股及技术面总结</p>

        {data.new_entrants.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-slate-500">
            今日榜单与昨日完全一致，无新进个股
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {data.new_entrants.map((e) => (
              <div key={e.ticker} className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 hover:border-amber-400/40 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xl font-bold text-white">{e.ticker}</span>
                      <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-amber-400/15 text-amber-300">#{e.rank}</span>
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">{e.name}</div>
                  </div>
                  <ChangeTag v={e.change_pct} />
                </div>

                <div className="grid grid-cols-4 gap-2 mb-3 text-center">
                  {[
                    ['最新价', `$${e.price.toFixed(2)}`],
                    ['量比', `${e.vol_ratio.toFixed(2)}x`],
                    ['RSI', `${e.rsi}`],
                    ['52周位置', `${e.week52_position}%`],
                  ].map(([k, v]) => (
                    <div key={k} className="rounded-lg bg-slate-800/60 py-2">
                      <div className="text-[10px] text-slate-500">{k}</div>
                      <div className="text-sm font-mono font-semibold text-slate-200">{v}</div>
                    </div>
                  ))}
                </div>

                <p className="text-sm leading-relaxed text-slate-300 border-l-2 border-emerald-400/50 pl-3">{e.summary}</p>

                {e.news.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-800">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-2">
                      <Newspaper className="w-3.5 h-3.5" />相关资讯
                    </div>
                    {e.news.map((n, i) => (
                      <a key={i} href={n.link} target="_blank" rel="noreferrer"
                         className="flex items-start gap-1.5 text-xs text-sky-400 hover:text-sky-300 mb-1.5 leading-snug">
                        <ExternalLink className="w-3 h-3 mt-0.5 shrink-0" />{n.title}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
