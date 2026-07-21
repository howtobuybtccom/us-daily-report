import type { DailyData } from '@/types'
import { ExternalLink, Rss } from 'lucide-react'

const SOURCE_COLORS: Record<string, string> = {
  MarketWatch: 'bg-emerald-400/15 text-emerald-300 border-emerald-400/30',
  CNBC: 'bg-sky-400/15 text-sky-300 border-sky-400/30',
  'WSJ Markets': 'bg-violet-400/15 text-violet-300 border-violet-400/30',
  'Yahoo Finance': 'bg-fuchsia-400/15 text-fuchsia-300 border-fuchsia-400/30',
}

export default function MarketNews({ data }: { data: DailyData }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <span className="w-1 h-5 bg-fuchsia-400 rounded-full" />
          当日重要美股财经资讯
        </h2>
        <span className="text-xs text-slate-500">RSS 聚合 · MarketWatch / CNBC / WSJ</span>
      </div>
      <p className="text-xs text-slate-500 mb-4">点击标题跳转原文阅读</p>

      {data.news.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-slate-500">
          资讯源暂不可用，请稍后刷新
        </div>
      ) : (
        <div className="space-y-3">
          {data.news.map((n, i) => (
            <a key={i} href={n.link} target="_blank" rel="noreferrer"
               className="block rounded-xl border border-slate-800 bg-slate-900/50 p-4 hover:border-slate-600 hover:bg-slate-800/40 transition-colors group">
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold border ${SOURCE_COLORS[n.source] ?? 'bg-slate-700/40 text-slate-300 border-slate-600'}`}>
                  {n.source}
                </span>
                {n.published && <span className="text-[11px] text-slate-500 font-mono">{n.published}</span>}
                <Rss className="w-3 h-3 text-slate-600 ml-auto group-hover:text-slate-400" />
              </div>
              <div className="flex items-start gap-2">
                <h3 className="text-sm font-semibold text-slate-100 leading-snug group-hover:text-white flex-1">{n.title}</h3>
                <ExternalLink className="w-3.5 h-3.5 mt-0.5 shrink-0 text-slate-600 group-hover:text-sky-400" />
              </div>
              {n.summary && <p className="text-xs text-slate-500 mt-1.5 leading-relaxed line-clamp-2">{n.summary}</p>}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
