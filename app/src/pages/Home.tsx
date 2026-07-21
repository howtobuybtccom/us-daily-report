import { useState } from 'react'
import { useDailyData } from '@/hooks/useDailyData'
import TopVolume from '@/sections/TopVolume'
import TrendPicks from '@/sections/TrendPicks'
import MarketNews from '@/sections/MarketNews'
import { BarChart3, Flame, Newspaper, LineChart, RefreshCw, AlertTriangle } from 'lucide-react'

const TABS = [
  { key: 'volume', label: '成交额 Top 20', icon: Flame, desc: '每日量能榜单 · 新进个股分析' },
  { key: 'trend', label: '趋势选股 Top 10', icon: LineChart, desc: '多因子打分 · 最看好标的' },
  { key: 'news', label: '财经资讯', icon: Newspaper, desc: '当日重要美股新闻' },
] as const

type TabKey = (typeof TABS)[number]['key']

export default function Home() {
  const { data, error, loading } = useDailyData()
  const [tab, setTab] = useState<TabKey>(() => {
    const q = new URLSearchParams(window.location.search).get('tab')
    return TABS.some((t) => t.key === q) ? (q as TabKey) : 'volume'
  })

  const switchTab = (key: TabKey) => {
    setTab(key)
    const url = new URL(window.location.href)
    url.searchParams.set('tab', key)
    window.history.replaceState(null, '', url.toString())
  }

  return (
    <div className="min-h-screen bg-[#0a0e17] text-slate-200">
      {/* 头部 */}
      <header className="border-b border-slate-800/80 bg-[#0d1220]/90 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-slate-900" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-white tracking-wide">美股选股策略工具</h1>
                <p className="text-[11px] text-slate-500">US Stock Daily Strategy · GitHub Actions 每日自动更新</p>
              </div>
            </div>
            {data && (
              <div className="text-right">
                <div className="text-sm font-mono text-amber-300">{data.trade_date}</div>
                <div className="text-[11px] text-slate-500">更新于 {data.generated_at}</div>
              </div>
            )}
          </div>

          {/* 选项卡 */}
          <nav className="flex gap-2 mt-4 overflow-x-auto pb-1">
            {TABS.map(({ key, label, icon: Icon, desc }) => (
              <button key={key} onClick={() => switchTab(key)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border whitespace-nowrap transition-all
                  ${tab === key
                    ? 'bg-amber-400/10 border-amber-400/50 text-amber-300'
                    : 'bg-slate-900/50 border-slate-800 text-slate-400 hover:border-slate-600 hover:text-slate-200'}`}>
                <Icon className="w-4 h-4" />
                <span className="text-left">
                  <span className="block text-sm font-semibold">{label}</span>
                  <span className="block text-[10px] opacity-70">{desc}</span>
                </span>
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* 主体 */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 text-slate-500">
            <RefreshCw className="w-8 h-8 animate-spin mb-3" />
            正在加载数据…
          </div>
        )}
        {error && (
          <div className="flex flex-col items-center justify-center py-24 text-slate-500">
            <AlertTriangle className="w-8 h-8 mb-3 text-amber-400" />
            <p>数据加载失败：{error}</p>
            <p className="text-xs mt-2">请确认已运行数据管道（pipeline/fetch_data.py）生成 public/data/latest.json</p>
          </div>
        )}
        {data && (
          <>
            {tab === 'volume' && <TopVolume data={data} />}
            {tab === 'trend' && <TrendPicks data={data} />}
            {tab === 'news' && <MarketNews data={data} />}
          </>
        )}
      </main>

      {/* 页脚 */}
      <footer className="border-t border-slate-800/80 mt-8">
        <div className="max-w-6xl mx-auto px-4 py-5 text-xs text-slate-600 leading-relaxed">
          {data?.disclaimer ?? '本工具仅供学习研究，不构成投资建议。'}
          <span className="block mt-1">数据源：Yahoo Finance 行情 · MarketWatch / CNBC / WSJ RSS 资讯</span>

        </div>
      </footer>
    </div>
  )
}
