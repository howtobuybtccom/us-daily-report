export interface TickerNews {
  title: string
  link: string
  publisher?: string
  published?: string
}

export interface TopVolumeItem {
  ticker: string
  name: string
  price: number
  change_pct: number
  volume: number
  dollar_volume: number
  vol_ratio: number
  rank: number
  is_new: boolean
}

export interface NewEntrant extends TopVolumeItem {
  rsi: number
  week52_position: number
  ret_20d: number
  summary: string
  news: TickerNews[]
}

export interface TrendPick {
  ticker: string
  name: string
  score: number
  price: number
  change_pct: number
  rsi: number
  ret_20d: number
  ret_60d: number
  reasons: string[]
}

export interface NewsItem {
  title: string
  link: string
  source: string
  published: string
  summary: string
}

export interface DailyData {
  generated_at: string
  trade_date: string
  universe_size: number
  top_volume: TopVolumeItem[]
  new_entrants: NewEntrant[]
  trend_picks: TrendPick[]
  news: NewsItem[]
  disclaimer: string
}
