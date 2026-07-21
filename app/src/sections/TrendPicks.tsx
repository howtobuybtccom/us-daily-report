import type { DailyData } from '@/types'
import { TrendingUp, TrendingDown, CheckCircle2, Medal } from 'lucide-react'

export default function TrendPicks({ data }: { data: DailyData }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <span className="w-1 h-5 bg-sky-400 rounded-full" />
          趋势上升 · 最看好 10 只
        </h2>
        <span className="text-xs text-slate-500">多因子打分 · 满分 100</span>
      </div>
      <p className="text-xs text-slate-500 mb-4">
        选股条件：多头排列（股价 &gt; MA20 &gt; MA50）· 均线上行 · RSI 强势未超买 · MACD 动能向上 · 量能配合；已过滤低价股与低流动性标的
      </p>

      {data.trend_picks.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-slate-500">
          今日无满足条件的趋势个股
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.trend_picks.map((p, i) => (
            <div key={p.ticker} className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 hover:border-sky-400/40 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm
                    ${i === 0 ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40'
                    : i < 3 ? 'bg-slate-400/15 text-slate-300 border border-slate-500/40'
                    : 'bg-slate-800 text-slate-400 border border-slate-700'}`}>
                    {i === 0 ? <Medal className="w-4 h-4" /> : i + 1}
                  </div>
                  <div>
                    <div className="text-lg font-bold text-white">{p.ticker}</div>
                    <div className="text-xs text-slate-500">{p.name}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-slate-200">${p.price.toFixed(2)}</div>
                  <span className={`inline-flex items-center gap-1 text-xs font-mono font-semibold ${p.change_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {p.change_pct >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {p.change_pct >= 0 ? '+' : ''}{p.change_pct.toFixed(2)}%
                  </span>
                </div>
              </div>

              {/* 评分条 */}
              <div className="mb-3">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-500">趋势评分</span>
                  <span className="font-mono font-bold text-sky-300">{p.score.toFixed(0)} / 100</span>
                </div>
                <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all"
                       style={{ width: `${Math.min(p.score, 100)}%` }} />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 mb-3 text-center">
                {[
                  ['RSI', `${p.rsi}`],
                  ['20日涨幅', `${p.ret_20d >= 0 ? '+' : ''}${p.ret_20d}%`],
                  ['60日涨幅', `${p.ret_60d >= 0 ? '+' : ''}${p.ret_60d}%`],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-slate-800/60 py-1.5">
                    <div className="text-[10px] text-slate-500">{k}</div>
                    <div className="text-sm font-mono font-semibold text-slate-200">{v}</div>
                  </div>
                ))}
              </div>

              <ul className="space-y-1">
                {p.reasons.map((r, j) => (
                  <li key={j} className="flex items-start gap-1.5 text-xs text-slate-300">
                    <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0 text-emerald-400" />{r}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
