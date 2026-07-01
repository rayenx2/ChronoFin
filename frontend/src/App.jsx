import { useState, useEffect, useCallback } from 'react'

const API = '/api/v1'
const AMBER = '#f59e0b'
const BG = '#0a0f1a'
const CARD = 'rgba(15,23,42,0.85)'
const BORDER = '1px solid rgba(251,191,36,0.12)'

const SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN', 'META', 'NVDA', 'BTC', 'ETH', 'EURUSD']
const STOCK_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN', 'META', 'NVDA']

function fmt(n, d = 2) {
  if (n == null || isNaN(n)) return '—'
  const abs = Math.abs(n)
  if (abs >= 10000) return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
  if (abs >= 100) return n.toFixed(2)
  return n.toFixed(d)
}

function SentimentBadge({ label, size = 'sm' }) {
  const map = {
    Bullish: ['#22c55e', '#14532d'],
    Bearish: ['#ef4444', '#7f1d1d'],
    Neutral: ['#94a3b8', '#1e293b'],
  }
  const [fg, bg] = map[label] || map.Neutral
  const pad = size === 'lg' ? '4px 14px' : '2px 10px'
  const fs = size === 'lg' ? 13 : 11
  return (
    <span style={{
      background: bg + '44', color: fg,
      border: `1px solid ${fg}33`, padding: pad,
      borderRadius: 99, fontSize: fs, fontWeight: 700,
    }}>
      {label}
    </span>
  )
}

function Spinner({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24"
      style={{ animation: 'spin 0.9s linear infinite', display: 'inline-block' }}>
      <circle cx="12" cy="12" r="9" stroke={AMBER} strokeWidth="2.5"
        fill="none" strokeDasharray="42" strokeDashoffset="15" />
    </svg>
  )
}

function LineChart({ bars, predicted, height = 120, color2 }) {
  if (!bars || bars.length < 2) {
    return (
      <div style={{ height, color: '#334155', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>
        No data
      </div>
    )
  }
  const closes = bars.map(b => b.close)
  const all = predicted != null ? [...closes, predicted] : closes
  const min = Math.min(...all); const max = Math.max(...all)
  const range = max - min || 1
  const W = 380; const H = height
  const sx = i => (i / (closes.length)) * (W - 20) + 10
  const sy = v => H - 8 - ((v - min) / range) * (H - 20)
  const pts = closes.map((c, i) => `${sx(i)},${sy(c)}`).join(' ')
  const up = closes.at(-1) >= closes[0]
  const lineColor = color2 || (up ? '#22c55e' : '#ef4444')
  const lastX = sx(closes.length - 1)
  const lastY = sy(closes.at(-1))
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id={`g${H}${lineColor}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.25" />
          <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${pts} ${lastX},${H} 10,${H}`} fill={`url(#g${H}${lineColor})`} />
      <polyline points={pts} fill="none" stroke={lineColor} strokeWidth="1.8" strokeLinejoin="round" />
      {predicted != null && (
        <>
          <line x1={lastX} y1={lastY} x2={W - 6} y2={sy(predicted)}
            stroke={predicted >= closes.at(-1) ? '#22c55e' : '#ef4444'}
            strokeWidth="1.5" strokeDasharray="5,4" />
          <circle cx={W - 6} cy={sy(predicted)} r="4"
            fill={predicted >= closes.at(-1) ? '#22c55e' : '#ef4444'} />
          <text x={W - 6} y={sy(predicted) - 8} fontSize="9"
            fill={predicted >= closes.at(-1) ? '#22c55e' : '#ef4444'} textAnchor="middle">
            ${fmt(predicted)}
          </text>
        </>
      )}
    </svg>
  )
}

function DualLineChart({ data, height = 180 }) {
  if (!data || data.length < 2) return null
  const actuals = data.map(d => d.actual)
  const preds = data.map(d => d.predicted)
  const all = [...actuals, ...preds]
  const min = Math.min(...all); const max = Math.max(...all); const range = max - min || 1
  const W = 500; const H = height
  const sx = i => (i / (data.length - 1)) * (W - 20) + 10
  const sy = v => H - 8 - ((v - min) / range) * (H - 20)
  const aPts = data.map((d, i) => `${sx(i)},${sy(d.actual)}`).join(' ')
  const pPts = data.map((d, i) => `${sx(i)},${sy(d.predicted)}`).join(' ')
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      <polyline points={aPts} fill="none" stroke="#60a5fa" strokeWidth="1.5" strokeLinejoin="round" />
      <polyline points={pPts} fill="none" stroke={AMBER} strokeWidth="1.5" strokeLinejoin="round" strokeDasharray="4,3" />
      <circle cx={sx(data.length - 1)} cy={sy(actuals.at(-1))} r="3" fill="#60a5fa" />
      <circle cx={sx(data.length - 1)} cy={sy(preds.at(-1))} r="3" fill={AMBER} />
    </svg>
  )
}

function EquityChart({ data, height = 100 }) {
  if (!data || data.length < 2) return null
  const vals = data.map(d => d.equity)
  const min = Math.min(...vals); const max = Math.max(...vals); const range = max - min || 0.01
  const W = 500; const H = height
  const sx = i => (i / (data.length - 1)) * (W - 20) + 10
  const sy = v => H - 4 - ((v - min) / range) * (H - 12)
  const pts = data.map((d, i) => `${sx(i)},${sy(d.equity)}`).join(' ')
  const lastX = sx(data.length - 1); const lastY = sy(vals.at(-1))
  const up = vals.at(-1) >= 1.0
  const color = up ? '#22c55e' : '#ef4444'
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="eqg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${pts} ${lastX},${H} 10,${H}`} fill="url(#eqg)" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
      <line x1="10" y1={sy(1.0)} x2={W - 10} y2={sy(1.0)}
        stroke="#334155" strokeWidth="1" strokeDasharray="4,4" />
    </svg>
  )
}

// ── Dashboard ──────────────────────────────────────────────────────────────────
function Dashboard({ health }) {
  const [rows, setRows] = useState([])
  const [charts, setCharts] = useState({})
  const [loading, setLoading] = useState(true)
  const [loadingSymbols, setLoadingSymbols] = useState(new Set())
  const [ts, setTs] = useState(null)
  const [error, setError] = useState(null)

  const loadPrediction = async (sym) => {
    setLoadingSymbols(prev => new Set([...prev, sym]))
    try {
      const r = await fetch(`${API}/predictions/${sym}`)
      if (!r.ok) throw new Error(`${r.status}`)
      const p = await r.json()
      setRows(prev => {
        const idx = prev.findIndex(x => x.symbol === sym)
        if (idx >= 0) { const n = [...prev]; n[idx] = p; return n }
        return [...prev, p]
      })
    } catch (e) {
      console.warn(`Prediction failed for ${sym}:`, e.message)
    } finally {
      setLoadingSymbols(prev => { const n = new Set(prev); n.delete(sym); return n })
    }
  }

  const loadChart = async (sym) => {
    try {
      const r = await fetch(`${API}/market/${sym}?days=30`)
      if (!r.ok) return
      const d = await r.json()
      setCharts(prev => ({ ...prev, [sym]: d }))
    } catch (e) {
      console.warn(`Chart failed for ${sym}:`, e.message)
    }
  }

  const fetchAll = useCallback(async () => {
    setLoading(true); setError(null); setRows([]); setCharts({})
    try {
      await Promise.all(SYMBOLS.slice(0, 6).map(loadPrediction))
      await Promise.all(SYMBOLS.slice(0, 4).map(loadChart))
      setTs(new Date().toLocaleTimeString())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  return (
    <div>
      {/* Status row */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 24 }}>
        {[
          { label: 'API', val: health?.status === 'ok' ? 'Online' : 'Offline', dot: health?.status === 'ok' },
          { label: 'Redis', val: health?.redis || '—', dot: health?.redis === 'ok' },
          { label: 'Model', val: 'XGBoost live', dot: true },
        ].map(s => (
          <div key={s.label} style={{ background: CARD, border: BORDER, borderRadius: 10, padding: '7px 14px', display: 'flex', alignItems: 'center', gap: 7, fontSize: 13 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.dot ? '#22c55e' : '#ef4444', display: 'inline-block' }} />
            <span style={{ color: '#64748b' }}>{s.label}:</span>
            <span style={{ color: '#94a3b8' }}>{s.val}</span>
          </div>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {ts && <span style={{ color: '#334155', fontSize: 12 }}>Updated {ts}</span>}
          <button onClick={fetchAll} disabled={loading} style={{
            background: AMBER + '20', border: `1px solid ${AMBER}40`, color: AMBER,
            borderRadius: 8, padding: '6px 14px', cursor: loading ? 'wait' : 'pointer', fontSize: 13,
          }}>
            {loading ? <Spinner size={14} /> : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: '#7f1d1d22', border: '1px solid #ef444440', borderRadius: 10, padding: 16, color: '#fca5a5', marginBottom: 20 }}>
          {error}
        </div>
      )}

      <h3 style={{ color: '#475569', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Live XGBoost Predictions, Yahoo Finance Data
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(270px,1fr))', gap: 14, marginBottom: 28 }}>
        {SYMBOLS.slice(0, 6).map(sym => {
          const p = rows.find(r => r.symbol === sym)
          const isLoading = loadingSymbols.has(sym)
          const change = p ? ((p.predicted_price - p.current_price) / p.current_price * 100) : 0
          const up = change >= 0
          return (
            <div key={sym} style={{ background: CARD, border: BORDER, borderRadius: 14, padding: 18, minHeight: 140 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ color: '#f1f5f9', fontWeight: 700, fontSize: 15 }}>{sym}</span>
                {isLoading && <Spinner size={16} />}
                {p && !isLoading && <SentimentBadge label={p.sentiment_label || 'Neutral'} />}
              </div>
              {isLoading && !p && (
                <div style={{ color: '#334155', fontSize: 12, paddingTop: 20, textAlign: 'center' }}>
                  Fetching live data...
                </div>
              )}
              {p && (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
                    <div>
                      <div style={{ color: '#475569', fontSize: 11 }}>Current</div>
                      <div style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 16 }}>${fmt(p.current_price)}</div>
                    </div>
                    <div>
                      <div style={{ color: '#475569', fontSize: 11 }}>Predicted</div>
                      <div style={{ color: up ? '#22c55e' : '#ef4444', fontWeight: 600, fontSize: 16 }}>${fmt(p.predicted_price)}</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ color: up ? '#22c55e' : '#ef4444', fontWeight: 700, fontSize: 13 }}>
                      {up ? '▲' : '▼'} {Math.abs(change).toFixed(2)}%
                    </span>
                    <span style={{ color: '#475569', fontSize: 11 }}>{p.prediction_date}</span>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#475569', marginBottom: 3 }}>
                      <span>Confidence</span>
                      <span>{(p.confidence_score * 100).toFixed(0)}%</span>
                    </div>
                    <div style={{ height: 3, background: '#1e293b', borderRadius: 2 }}>
                      <div style={{ height: 3, width: `${Math.min(p.confidence_score * 100, 100)}%`, background: AMBER, borderRadius: 2 }} />
                    </div>
                  </div>
                </>
              )}
            </div>
          )
        })}
      </div>

      {Object.keys(charts).length > 0 && (
        <>
          <h3 style={{ color: '#475569', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
            30-Day History, Live OHLCV
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(260px,1fr))', gap: 14 }}>
            {Object.entries(charts).map(([sym, d]) => {
              const pred = rows.find(r => r.symbol === sym)
              const last = d.data?.at(-1)
              return (
                <div key={sym} style={{ background: CARD, border: BORDER, borderRadius: 14, padding: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{sym}</span>
                    <span style={{ color: '#334155', fontSize: 12 }}>{d.count} bars</span>
                  </div>
                  <LineChart bars={d.data} predicted={pred?.predicted_price} height={80} />
                  {last && (
                    <div style={{ display: 'flex', gap: 12, marginTop: 8, fontSize: 11, color: '#475569' }}>
                      <span>RSI {last.rsi_14?.toFixed(1) || '—'}</span>
                      <span>Vol {(last.volume / 1e6).toFixed(1)}M</span>
                      {last.bb_upper && <span>BB {fmt(last.bb_lower)}–{fmt(last.bb_upper)}</span>}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

// ── Forecast ───────────────────────────────────────────────────────────────────
function Forecast() {
  const [sym, setSym] = useState('AAPL')
  const [pred, setPred] = useState(null)
  const [market, setMarket] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = useCallback(async (s) => {
    setLoading(true); setError(null); setPred(null); setMarket(null)
    try {
      const [fr, mr] = await Promise.all([
        fetch(`${API}/predictions/${s}?force_refresh=true`),
        fetch(`${API}/market/${s}?days=90`),
      ])
      if (!fr.ok) throw new Error((await fr.json()).detail || `Error ${fr.status}`)
      setPred(await fr.json())
      if (mr.ok) setMarket(await mr.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { run(sym) }, [sym, run])

  const change = pred ? ((pred.predicted_price - pred.current_price) / pred.current_price * 100) : 0
  const up = change >= 0

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 24 }}>
        {SYMBOLS.map(s => (
          <button key={s} onClick={() => { setSym(s); run(s) }} style={{
            background: sym === s ? AMBER + '22' : CARD,
            border: `1px solid ${sym === s ? AMBER + '60' : 'rgba(51,65,85,0.35)'}`,
            color: sym === s ? AMBER : '#64748b',
            borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13,
            fontWeight: sym === s ? 700 : 400,
          }}>{s}</button>
        ))}
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 80, color: '#475569' }}>
          <Spinner size={32} />
          <div style={{ marginTop: 14, fontSize: 14 }}>Training XGBoost on live {sym} data...</div>
        </div>
      )}

      {error && !loading && (
        <div style={{ background: '#7f1d1d22', border: '1px solid #ef444440', borderRadius: 12, padding: 20, color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {pred && !loading && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <div style={{ background: CARD, border: BORDER, borderRadius: 16, padding: 22 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h3 style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
                XGBoost Forecast, {pred.symbol}
              </h3>
              <SentimentBadge label={pred.sentiment_label || 'Neutral'} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
              {[
                { label: 'Current Price', val: `$${fmt(pred.current_price)}`, color: '#f1f5f9' },
                { label: 'Next-Day Forecast', val: `$${fmt(pred.predicted_price)}`, color: up ? '#22c55e' : '#ef4444' },
                { label: 'Expected Change', val: `${up ? '+' : ''}${change.toFixed(2)}%`, color: up ? '#22c55e' : '#ef4444' },
                { label: 'Confidence Score', val: `${(pred.confidence_score * 100).toFixed(1)}%`, color: AMBER },
              ].map(r => (
                <div key={r.label} style={{ background: '#0f172a', borderRadius: 10, padding: 14 }}>
                  <div style={{ color: '#475569', fontSize: 10, marginBottom: 4 }}>{r.label}</div>
                  <div style={{ color: r.color, fontWeight: 700, fontSize: 20 }}>{r.val}</div>
                </div>
              ))}
            </div>
            <div style={{ background: '#0f172a', borderRadius: 10, padding: 14, marginBottom: 10 }}>
              <div style={{ color: '#475569', fontSize: 10, marginBottom: 6 }}>95% Confidence Interval</div>
              <div style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: 13 }}>
                ${fmt(pred.confidence_lower)} — ${fmt(pred.confidence_upper)}
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div style={{ background: '#0f172a', borderRadius: 10, padding: 12 }}>
                <div style={{ color: '#475569', fontSize: 10, marginBottom: 4 }}>Model</div>
                <div style={{ color: '#94a3b8', fontSize: 12 }}>{pred.model_version}</div>
              </div>
              <div style={{ background: '#0f172a', borderRadius: 10, padding: 12 }}>
                <div style={{ color: '#475569', fontSize: 10, marginBottom: 4 }}>Prediction Date</div>
                <div style={{ color: '#94a3b8', fontSize: 12 }}>{pred.prediction_date}</div>
              </div>
            </div>
          </div>

          <div style={{ background: CARD, border: BORDER, borderRadius: 16, padding: 22 }}>
            <h3 style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 16 }}>
              90-Day Price History + Forecast
            </h3>
            {market ? (
              <>
                <LineChart bars={market.data} predicted={pred.predicted_price} height={160} />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, marginTop: 14 }}>
                  {[
                    { label: 'Bars', val: market.count },
                    { label: 'Latest RSI', val: market.data?.at(-1)?.rsi_14?.toFixed(1) || '—' },
                    { label: 'BB Upper', val: market.data?.at(-1)?.bb_upper ? `$${fmt(market.data.at(-1).bb_upper)}` : '—' },
                  ].map(r => (
                    <div key={r.label} style={{ background: '#0f172a', borderRadius: 8, padding: 10, textAlign: 'center' }}>
                      <div style={{ color: '#475569', fontSize: 10 }}>{r.label}</div>
                      <div style={{ color: '#94a3b8', fontWeight: 600, fontSize: 14 }}>{r.val}</div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ color: '#334155', textAlign: 'center', paddingTop: 60 }}>No chart data</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sentiment ──────────────────────────────────────────────────────────────────
function SentimentTab() {
  const [sym, setSym] = useState('AAPL')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = useCallback(async (s) => {
    setLoading(true); setError(null); setData(null)
    try {
      const r = await fetch(`${API}/sentiment/${s}`)
      if (!r.ok) throw new Error(`${r.status}`)
      setData(await r.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { run(sym) }, [sym, run])

  const scoreColor = s => s > 0.05 ? '#22c55e' : (s < -0.05 ? '#ef4444' : '#94a3b8')

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 24 }}>
        {SYMBOLS.map(s => (
          <button key={s} onClick={() => { setSym(s); run(s) }} style={{
            background: sym === s ? AMBER + '22' : CARD,
            border: `1px solid ${sym === s ? AMBER + '60' : 'rgba(51,65,85,0.35)'}`,
            color: sym === s ? AMBER : '#64748b',
            borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13,
            fontWeight: sym === s ? 700 : 400,
          }}>{s}</button>
        ))}
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spinner size={28} />
          <div style={{ color: '#475569', marginTop: 12, fontSize: 14 }}>Fetching {sym} news...</div>
        </div>
      )}

      {error && !loading && (
        <div style={{ background: '#7f1d1d22', border: '1px solid #ef444440', borderRadius: 12, padding: 20, color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* Aggregate card */}
          <div style={{ background: CARD, border: BORDER, borderRadius: 16, padding: 24, marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <div style={{ color: '#475569', fontSize: 12, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>
                  Aggregate Sentiment, {data.symbol}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <span style={{ fontSize: 36, fontWeight: 800, color: scoreColor(data.aggregate_score) }}>
                    {data.aggregate_score > 0 ? '+' : ''}{(data.aggregate_score * 100).toFixed(1)}
                  </span>
                  <SentimentBadge label={data.aggregate_label} size="lg" />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div style={{ background: '#0f172a', borderRadius: 10, padding: 14, textAlign: 'center' }}>
                  <div style={{ color: '#475569', fontSize: 10 }}>Articles</div>
                  <div style={{ color: '#f1f5f9', fontWeight: 700, fontSize: 22 }}>{data.article_count}</div>
                </div>
                <div style={{ background: '#0f172a', borderRadius: 10, padding: 14, textAlign: 'center' }}>
                  <div style={{ color: '#475569', fontSize: 10 }}>Source</div>
                  <div style={{ color: '#94a3b8', fontWeight: 600, fontSize: 13 }}>Yahoo Finance</div>
                </div>
              </div>
            </div>

            {/* Score bar */}
            <div style={{ marginTop: 18 }}>
              <div style={{ height: 6, background: '#1e293b', borderRadius: 3, position: 'relative', overflow: 'hidden' }}>
                <div style={{
                  position: 'absolute', left: '50%', height: '100%',
                  width: `${Math.abs(data.aggregate_score) * 50}%`,
                  marginLeft: data.aggregate_score >= 0 ? 0 : `-${Math.abs(data.aggregate_score) * 50}%`,
                  background: scoreColor(data.aggregate_score),
                  borderRadius: 3,
                }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#334155', marginTop: 4 }}>
                <span>Bearish −1.0</span>
                <span>Neutral 0.0</span>
                <span>Bullish +1.0</span>
              </div>
            </div>
          </div>

          {/* Article list */}
          {data.articles.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <h3 style={{ color: '#475569', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
                Recent Headlines
              </h3>
              {data.articles.map((a, i) => (
                <div key={i} style={{ background: CARD, border: BORDER, borderRadius: 12, padding: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <a href={a.url} target="_blank" rel="noopener noreferrer"
                      style={{ color: '#e2e8f0', fontSize: 14, fontWeight: 500, textDecoration: 'none', lineHeight: 1.5 }}>
                      {a.title}
                    </a>
                    <div style={{ color: '#475569', fontSize: 11, marginTop: 4 }}>{a.publisher}</div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                    <SentimentBadge label={a.sentiment_label} />
                    <span style={{ color: scoreColor(a.sentiment_score), fontSize: 12, fontFamily: 'monospace', fontWeight: 700 }}>
                      {a.sentiment_score > 0 ? '+' : ''}{a.sentiment_score.toFixed(3)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {data.articles.length === 0 && (
            <div style={{ textAlign: 'center', color: '#334155', padding: 40 }}>No news articles found for {data.symbol}</div>
          )}
        </>
      )}
    </div>
  )
}

// ── Backtest ───────────────────────────────────────────────────────────────────
function BacktestTab() {
  const [sym, setSym] = useState('AAPL')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = useCallback(async (s) => {
    setLoading(true); setError(null); setData(null)
    try {
      const r = await fetch(`${API}/backtest/${s}`)
      if (!r.ok) throw new Error(`${r.status}`)
      setData(await r.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { run(sym) }, [sym, run])

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 24 }}>
        {SYMBOLS.map(s => (
          <button key={s} onClick={() => { setSym(s); run(s) }} style={{
            background: sym === s ? AMBER + '22' : CARD,
            border: `1px solid ${sym === s ? AMBER + '60' : 'rgba(51,65,85,0.35)'}`,
            color: sym === s ? AMBER : '#64748b',
            borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13,
            fontWeight: sym === s ? 700 : 400,
          }}>{s}</button>
        ))}
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spinner size={32} />
          <div style={{ color: '#475569', marginTop: 14, fontSize: 14 }}>
            Running walk-forward backtest on {sym} (2 years of data)...
          </div>
        </div>
      )}

      {error && !loading && (
        <div style={{ background: '#7f1d1d22', border: '1px solid #ef444440', borderRadius: 12, padding: 20, color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* Key metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: 12, marginBottom: 20 }}>
            {[
              { label: 'Directional Accuracy', val: `${data.directional_accuracy}%`, good: data.directional_accuracy > 55, note: 'vs 50% random' },
              { label: 'Strategy Sharpe', val: data.strategy_sharpe.toFixed(3), good: data.strategy_sharpe > 0.5, note: '>1.0 is excellent' },
              { label: 'Buy & Hold Sharpe', val: data.buyhold_sharpe.toFixed(3), good: false, note: 'baseline' },
              { label: 'MAE vs Naive', val: `+${data.mae_vs_naive_pct}%`, good: data.mae_vs_naive_pct > 0, note: 'model beats naive' },
              { label: 'Model MAE', val: `$${fmt(data.mae)}`, good: true, note: `naive $${fmt(data.naive_mae)}` },
              { label: 'Final Equity', val: `${data.final_equity.toFixed(3)}x`, good: data.final_equity > 1, note: `${data.test_days} test days` },
            ].map(m => (
              <div key={m.label} style={{ background: CARD, border: BORDER, borderRadius: 12, padding: 16 }}>
                <div style={{ color: '#475569', fontSize: 10, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>{m.label}</div>
                <div style={{ color: m.good ? '#22c55e' : AMBER, fontWeight: 700, fontSize: 22, marginBottom: 4 }}>{m.val}</div>
                <div style={{ color: '#334155', fontSize: 11 }}>{m.note}</div>
              </div>
            ))}
          </div>

          {/* Methodology note */}
          <div style={{ background: '#0f172a', borderRadius: 10, padding: 14, marginBottom: 20, fontSize: 12, color: '#475569', lineHeight: 1.6 }}>
            <span style={{ color: AMBER, fontWeight: 600 }}>Walk-Forward Method: </span>
            Trained XGBoost on {data.train_days} days, tested on {data.test_days} unseen days.
            Strategy: go long when model predicts up, else hold cash. MAE {data.mae_vs_naive_pct > 0 ? `${data.mae_vs_naive_pct}% better` : 'worse'} than naive (predict today = tomorrow).
          </div>

          {/* Actual vs Predicted chart */}
          {data.chart && data.chart.length > 0 && (
            <div style={{ background: CARD, border: BORDER, borderRadius: 16, padding: 22, marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h3 style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
                  Actual vs Predicted, Test Period
                </h3>
                <div style={{ display: 'flex', gap: 16, fontSize: 11 }}>
                  <span><span style={{ color: '#60a5fa' }}>■</span> Actual</span>
                  <span><span style={{ color: AMBER }}>- -</span> Predicted</span>
                </div>
              </div>
              <DualLineChart data={data.chart} height={180} />
            </div>
          )}

          {/* Equity curve */}
          {data.chart && data.chart.length > 0 && (
            <div style={{ background: CARD, border: BORDER, borderRadius: 16, padding: 22 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h3 style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
                  Strategy Equity Curve
                </h3>
                <span style={{ color: data.final_equity >= 1 ? '#22c55e' : '#ef4444', fontWeight: 700, fontSize: 14 }}>
                  {data.final_equity >= 1 ? '+' : ''}{((data.final_equity - 1) * 100).toFixed(1)}% return
                </span>
              </div>
              <EquityChart data={data.chart} height={100} />
              <div style={{ color: '#334155', fontSize: 11, marginTop: 8 }}>
                Dashed line = break-even (1.0x). Starting capital = $1.00
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Efficient Frontier Chart ───────────────────────────────────────────────────
function FrontierChart({ data }) {
  const [hovered, setHovered] = useState(null)

  if (!data?.frontier?.length) return null

  const RF = 0.02
  const pts = data.frontier.map(p => ({
    ...p,
    sharpe: (p.ret / 100 - RF) / (p.vol / 100),
  }))

  const allVols = [...pts.map(p => p.vol), data.volatility, data.eq_volatility]
  const allRets = [...pts.map(p => p.ret), data.expected_return, data.eq_return]
  const minV = Math.min(...allVols) - 1
  const maxV = Math.max(...allVols) + 1
  const minR = Math.min(...allRets) - 3
  const maxR = Math.max(...allRets) + 3

  const W = 380, H = 260
  const PAD = { t: 14, r: 14, b: 38, l: 44 }
  const IW = W - PAD.l - PAD.r
  const IH = H - PAD.t - PAD.b

  const sx = v => PAD.l + ((v - minV) / (maxV - minV)) * IW
  const sy = r => PAD.t + IH - ((r - minR) / (maxR - minR)) * IH

  const maxSharpe = Math.max(...pts.map(p => p.sharpe))
  const minSharpe = Math.min(...pts.map(p => p.sharpe))

  // Color by Sharpe: low = blue, high = amber
  const sharpColor = (s) => {
    const t = Math.max(0, Math.min(1, (s - minSharpe) / (maxSharpe - minSharpe || 1)))
    const r = Math.round(59 + (245 - 59) * t)
    const g = Math.round(130 + (158 - 130) * t)
    const b = Math.round(246 + (11 - 246) * t)
    return `rgb(${r},${g},${b})`
  }

  const xTicks = 4, yTicks = 4
  const xStep = (maxV - minV) / xTicks
  const yStep = (maxR - minR) / yTicks

  const optX = sx(data.volatility), optY = sy(data.expected_return)
  const eqX = sx(data.eq_volatility), eqY = sy(data.eq_return)

  const downloadCSV = () => {
    const rows = [
      ['type','volatility_pct','return_pct','sharpe'],
      ...pts.map(p => ['sample', p.vol.toFixed(2), p.ret.toFixed(2), p.sharpe.toFixed(3)]),
      ['optimal', data.volatility.toFixed(2), data.expected_return.toFixed(2), data.sharpe.toFixed(3)],
      ['equal_weight', data.eq_volatility.toFixed(2), data.eq_return.toFixed(2), data.eq_sharpe.toFixed(3)],
    ]
    const csv = rows.map(r => r.join(',')).join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    a.download = `chronofin_frontier_${data.days_used}d.csv`
    a.click()
  }

  return (
    <div style={{ background: CARD, border: BORDER, borderRadius: 16, padding: 22 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <h3 style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
          Efficient Frontier
        </h3>
        <button onClick={downloadCSV} style={{
          background: 'rgba(30,41,59,0.6)', border: '1px solid rgba(51,65,85,0.5)',
          color: '#64748b', borderRadius: 6, padding: '3px 10px', cursor: 'pointer', fontSize: 11,
        }}>↓ CSV</button>
      </div>
      <div style={{ color: '#334155', fontSize: 11, marginBottom: 12, lineHeight: 1.5 }}>
        Each dot = one portfolio. <span style={{ color: '#60a5fa' }}>Blue</span> = low Sharpe,{' '}
        <span style={{ color: AMBER }}>amber</span> = high Sharpe. Top-left = best (high return, low risk).
      </div>

      {/* Tooltip */}
      {hovered && (
        <div style={{
          background: '#0f172a', border: `1px solid ${AMBER}40`, borderRadius: 8,
          padding: '8px 12px', fontSize: 11, marginBottom: 10, display: 'flex', gap: 20,
        }}>
          <span style={{ color: '#475569' }}>Volatility: <span style={{ color: '#f87171', fontWeight: 700 }}>{hovered.vol.toFixed(1)}%</span></span>
          <span style={{ color: '#475569' }}>Return: <span style={{ color: '#22c55e', fontWeight: 700 }}>{hovered.ret.toFixed(1)}%</span></span>
          <span style={{ color: '#475569' }}>Sharpe: <span style={{ color: AMBER, fontWeight: 700 }}>{hovered.sharpe.toFixed(2)}</span></span>
        </div>
      )}

      <svg
        width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', cursor: 'crosshair' }}
        onMouseLeave={() => setHovered(null)}
        onMouseMove={e => {
          const rect = e.currentTarget.getBoundingClientRect()
          const mx = (e.clientX - rect.left) / rect.width * W
          const my = (e.clientY - rect.top) / rect.height * H
          let best = null, bestD = 999
          pts.forEach(p => {
            const d = Math.hypot(sx(p.vol) - mx, sy(p.ret) - my)
            if (d < bestD) { bestD = d; best = p }
          })
          if (bestD < 16) setHovered(best); else setHovered(null)
        }}
      >
        {/* Grid lines */}
        {Array.from({ length: yTicks + 1 }, (_, i) => {
          const r = minR + i * yStep
          return <line key={i} x1={PAD.l} y1={sy(r)} x2={W - PAD.r} y2={sy(r)}
            stroke="rgba(30,41,59,0.8)" strokeWidth="1" strokeDasharray="3,3" />
        })}
        {Array.from({ length: xTicks + 1 }, (_, i) => {
          const v = minV + i * xStep
          return <line key={i} x1={sx(v)} y1={PAD.t} x2={sx(v)} y2={H - PAD.b}
            stroke="rgba(30,41,59,0.8)" strokeWidth="1" strokeDasharray="3,3" />
        })}

        {/* Axis labels */}
        {Array.from({ length: yTicks + 1 }, (_, i) => {
          const r = minR + i * yStep
          return <text key={i} x={PAD.l - 6} y={sy(r) + 4} fontSize="9" fill="#334155"
            textAnchor="end">{r.toFixed(0)}%</text>
        })}
        {Array.from({ length: xTicks + 1 }, (_, i) => {
          const v = minV + i * xStep
          return <text key={i} x={sx(v)} y={H - PAD.b + 14} fontSize="9" fill="#334155"
            textAnchor="middle">{v.toFixed(0)}%</text>
        })}

        {/* Axis titles */}
        <text x={PAD.l + IW / 2} y={H - 4} fontSize="9" fill="#475569" textAnchor="middle">
          Volatility (Risk) →
        </text>
        <text x={10} y={PAD.t + IH / 2} fontSize="9" fill="#475569" textAnchor="middle"
          transform={`rotate(-90, 10, ${PAD.t + IH / 2})`}>
          Return →
        </text>

        {/* Frontier dots */}
        {pts.map((p, i) => (
          <circle key={i} cx={sx(p.vol)} cy={sy(p.ret)} r={hovered === p ? 5 : 2.5}
            fill={sharpColor(p.sharpe)} fillOpacity={hovered === p ? 1 : 0.55}
            style={{ transition: 'r 0.1s' }}
          />
        ))}

        {/* Equal-weight baseline */}
        <circle cx={eqX} cy={eqY} r="6" fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="3,2" />
        <text x={eqX + 9} y={eqY + 4} fontSize="9" fill="#94a3b8">Equal-weight</text>

        {/* Optimal portfolio star */}
        <circle cx={optX} cy={optY} r="8" fill={AMBER} stroke="#0f172a" strokeWidth="2" />
        <text x={optX} y={optY + 4} fontSize="10" fill="#0f172a" textAnchor="middle" fontWeight="bold">★</text>
        <text x={optX + 12} y={optY - 8} fontSize="9" fill={AMBER} fontWeight="bold">Max Sharpe</text>
      </svg>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: 11, color: '#475569', flexWrap: 'wrap' }}>
        <span><span style={{ color: '#3b82f6' }}>●</span> Low Sharpe portfolio</span>
        <span><span style={{ color: AMBER }}>●</span> High Sharpe portfolio</span>
        <span><span style={{ color: AMBER }}>★</span> Optimal (max Sharpe)</span>
        <span><span style={{ color: '#94a3b8' }}>○</span> Equal-weight baseline</span>
      </div>
    </div>
  )
}

// ── Portfolio ──────────────────────────────────────────────────────────────────
function PortfolioTab() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [days, setDays] = useState(252)

  const run = useCallback(async (d, refresh = false) => {
    setLoading(true); setError(null); setData(null)
    try {
      const url = `${API}/portfolio/optimize?days=${d}${refresh ? '&force_refresh=true' : ''}`
      const r = await fetch(url)
      if (!r.ok) throw new Error(`${r.status}`)
      setData(await r.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { run(days) }, [])

  const COLORS = ['#f59e0b', '#60a5fa', '#34d399', '#f87171', '#a78bfa', '#fb923c', '#38bdf8']

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 24 }}>
        {[60, 126, 252, 504].map(d => (
          <button key={d} onClick={() => { setDays(d); run(d) }} style={{
            background: days === d ? AMBER + '22' : CARD,
            border: `1px solid ${days === d ? AMBER + '60' : 'rgba(51,65,85,0.35)'}`,
            color: days === d ? AMBER : '#64748b',
            borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13,
            fontWeight: days === d ? 700 : 400,
          }}>{d === 60 ? '3M' : d === 126 ? '6M' : d === 252 ? '1Y' : '2Y'}</button>
        ))}
        <span style={{ color: '#334155', fontSize: 12 }}>historical window</span>
        <button onClick={() => run(days, true)} disabled={loading} style={{
          marginLeft: 'auto', background: AMBER + '20', border: `1px solid ${AMBER}40`,
          color: AMBER, borderRadius: 8, padding: '6px 14px', cursor: loading ? 'wait' : 'pointer', fontSize: 13,
        }}>
          {loading ? <Spinner size={14} /> : 'Reoptimize'}
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spinner size={32} />
          <div style={{ color: '#475569', marginTop: 14, fontSize: 14 }}>
            Running 10,000 Monte Carlo portfolios on {days}-day returns...
          </div>
        </div>
      )}

      {error && !loading && (
        <div style={{ background: '#7f1d1d22', border: '1px solid #ef444440', borderRadius: 12, padding: 20, color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* Summary metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: 12, marginBottom: 24 }}>
            {[
              { label: 'Optimized Sharpe', val: data.sharpe.toFixed(3), color: AMBER },
              { label: 'Equal-Weight Sharpe', val: data.eq_sharpe.toFixed(3), color: '#94a3b8' },
              { label: 'Sharpe Improvement', val: `+${data.sharpe_improvement}%`, color: '#22c55e' },
              { label: 'Expected Return', val: `${data.expected_return}%`, color: '#60a5fa' },
              { label: 'Volatility', val: `${data.volatility}%`, color: '#f87171' },
              { label: 'History Used', val: `${data.days_used}d`, color: '#94a3b8' },
            ].map(m => (
              <div key={m.label} style={{ background: CARD, border: BORDER, borderRadius: 12, padding: 16 }}>
                <div style={{ color: '#475569', fontSize: 10, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>{m.label}</div>
                <div style={{ color: m.color, fontWeight: 700, fontSize: 22 }}>{m.val}</div>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Optimal weights */}
            <div style={{ background: CARD, border: BORDER, borderRadius: 16, padding: 22 }}>
              <h3 style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 18 }}>
                Max-Sharpe Allocation
              </h3>
              {data.symbols.map((s, i) => {
                const w = data.weights[i]
                return (
                  <div key={s} style={{ marginBottom: 14 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                      <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: 13 }}>{s}</span>
                      <span style={{ color: COLORS[i % COLORS.length], fontWeight: 700, fontSize: 14 }}>
                        {(w * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div style={{ height: 6, background: '#1e293b', borderRadius: 3 }}>
                      <div style={{
                        height: 6, width: `${w * 100}%`, borderRadius: 3,
                        background: COLORS[i % COLORS.length],
                        transition: 'width 0.6s ease',
                      }} />
                    </div>
                  </div>
                )
              })}

              <div style={{ marginTop: 20, padding: 12, background: '#0f172a', borderRadius: 10, fontSize: 12, color: '#475569', lineHeight: 1.6 }}>
                <span style={{ color: AMBER, fontWeight: 600 }}>Method: </span>
                Markowitz mean-variance optimization. 10,000 Monte Carlo weight vectors sampled, max-Sharpe selected.
                Risk-free rate: 2% (EU 10Y Bund).
              </div>
            </div>

            {/* Efficient frontier scatter */}
            <FrontierChart data={data} />
          </div>
        </>
      )}
    </div>
  )
}

// ── About ──────────────────────────────────────────────────────────────────────
function About({ health }) {
  return (
    <div style={{ maxWidth: 720 }}>
      <p style={{ color: '#94a3b8', lineHeight: 1.7, marginBottom: 22 }}>
        ChronoFin is a production-grade financial ML pipeline. It fetches live OHLCV data from Yahoo Finance,
        engineers 16 technical features (RSI, MACD, Bollinger Bands, ATR, SMA, returns), trains an XGBoost model
        per symbol, and forecasts next-day closing prices. News sentiment via VADER, walk-forward backtesting,
        and Markowitz portfolio optimization are computed on real historical data.
      </p>

      <div style={{ background: CARD, border: BORDER, borderRadius: 14, padding: 20, marginBottom: 18 }}>
        <h3 style={{ color: AMBER, fontSize: 14, marginBottom: 14 }}>API Endpoints</h3>
        {[
          ['GET', '/health', 'API + Redis status'],
          ['GET', '/api/v1/predictions/{symbol}', 'Live XGBoost forecast + confidence interval'],
          ['GET', '/api/v1/market/{symbol}?days=90', 'Live OHLCV + RSI/MACD/BB indicators'],
          ['GET', '/api/v1/sentiment/{symbol}', 'News headlines + VADER sentiment scores'],
          ['GET', '/api/v1/backtest/{symbol}', 'Walk-forward backtest: Sharpe, dir. accuracy, equity curve'],
          ['GET', '/api/v1/portfolio/optimize?days=252', 'Markowitz max-Sharpe allocation'],
          ['GET', '/metrics', 'Prometheus metrics'],
          ['GET', '/docs', 'Swagger UI'],
        ].map(([m, p, d]) => (
          <div key={p} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '7px 0', borderBottom: '1px solid rgba(30,41,59,0.8)' }}>
            <span style={{ background: '#1d4ed822', color: '#93c5fd', border: '1px solid #1d4ed840', padding: '1px 7px', borderRadius: 4, fontSize: 10, fontFamily: 'monospace', minWidth: 34, textAlign: 'center' }}>{m}</span>
            <code style={{ color: AMBER, fontSize: 12, flex: 1 }}>{p}</code>
            <span style={{ color: '#475569', fontSize: 12 }}>{d}</span>
          </div>
        ))}
      </div>

      <div style={{ background: CARD, border: BORDER, borderRadius: 14, padding: 20, marginBottom: 18 }}>
        <h3 style={{ color: AMBER, fontSize: 14, marginBottom: 14 }}>Infrastructure</h3>
        {[
          ['React UI', 'http://localhost:3012', 'This dashboard'],
          ['FastAPI', 'http://localhost:8000/docs', 'Swagger docs'],
          ['Prometheus', 'http://localhost:9090', 'Metrics scraper'],
          ['Grafana', 'http://localhost:3002', 'admin / admin'],
        ].map(([l, u, d]) => (
          <div key={l} style={{ display: 'flex', gap: 12, padding: '7px 0', borderBottom: '1px solid rgba(30,41,59,0.6)', alignItems: 'center' }}>
            <span style={{ color: AMBER, minWidth: 100, fontSize: 13, fontWeight: 600 }}>{l}</span>
            <a href={u} target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', fontSize: 12, flex: 1 }}>{u}</a>
            <span style={{ color: '#475569', fontSize: 12 }}>{d}</span>
          </div>
        ))}
      </div>

      <div style={{ background: CARD, border: BORDER, borderRadius: 14, padding: 20, marginBottom: 18 }}>
        <h3 style={{ color: AMBER, fontSize: 14, marginBottom: 12 }}>Stack</h3>
        {[
          ['ML', 'XGBoost · VADER Sentiment · scikit-learn'],
          ['Data', 'Yahoo Finance (yfinance) · Redis cache · PostgreSQL'],
          ['Portfolio', 'Markowitz mean-variance · Monte Carlo (10k portfolios)'],
          ['MLOps', 'MLflow · MinIO · Airflow 2.8'],
          ['Observability', 'Prometheus · Grafana'],
          ['API', 'FastAPI · Pydantic v2 · Python 3.11'],
          ['Frontend', 'React 18 · Vite · nginx'],
        ].map(([l, t]) => (
          <div key={l} style={{ display: 'flex', gap: 12, padding: '7px 0', borderBottom: '1px solid rgba(30,41,59,0.6)' }}>
            <span style={{ color: AMBER, minWidth: 100, fontSize: 13, fontWeight: 600 }}>{l}</span>
            <span style={{ color: '#94a3b8', fontSize: 13 }}>{t}</span>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 18, color: '#334155', fontSize: 13 }}>
        Built by{' '}
        <a href="https://github.com/Hamilas" style={{ color: AMBER }}>Rayen Lassoued</a>
        {' · '}
        <a href="https://www.linkedin.com/in/lassoued-rayen/" style={{ color: AMBER }}>LinkedIn</a>
      </div>
    </div>
  )
}

// ── App shell ──────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'forecast',  label: 'Forecast' },
  { id: 'sentiment', label: 'Sentiment' },
  { id: 'backtest',  label: 'Backtest' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'about',     label: 'About' },
]

const VALID_TABS = new Set(['dashboard','forecast','sentiment','backtest','portfolio','about'])

function getHashTab() {
  const h = window.location.hash.replace('#/', '').split('?')[0]
  return VALID_TABS.has(h) ? h : 'dashboard'
}

export default function App() {
  const [tab, setTab] = useState(getHashTab)
  const [health, setHealth] = useState(null)

  // Sync tab → URL hash
  const navigate = (id) => {
    window.location.hash = '/' + id
    setTab(id)
  }

  // Handle browser back/forward
  useEffect(() => {
    const onHash = () => setTab(getHashTab())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    const ping = () =>
      fetch('/health').then(r => r.ok ? r.json() : null).then(setHealth).catch(() => null)
    ping()
    const t = setInterval(ping, 30000)
    return () => clearInterval(t)
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: BG, color: '#f1f5f9', fontFamily: "'Inter',sans-serif" }}>
      <style>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        a { text-decoration: none; }
        button { font-family: inherit; }
        @keyframes spin { to { transform: rotate(360deg); } }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0a0f1a; }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
      `}</style>
      <div style={{ height: 2, background: AMBER }} />

      <header style={{
        background: 'rgba(10,15,26,0.96)', backdropFilter: 'blur(12px)',
        borderBottom: BORDER, padding: '0 32px',
        position: 'sticky', top: 0, zIndex: 100,
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', alignItems: 'center', height: 58, gap: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <svg width="26" height="26" viewBox="0 0 26 26">
              <rect width="26" height="26" rx="6" fill={AMBER + '22'} />
              <polyline points="3,19 9,11 15,15 23,5" stroke={AMBER} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="23" cy="5" r="2.2" fill={AMBER} />
            </svg>
            <span style={{ fontWeight: 800, fontSize: 17, color: '#f1f5f9' }}>
              Chrono<span style={{ color: AMBER }}>Fin</span>
            </span>
          </div>

          <nav style={{ display: 'flex', gap: 2 }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => navigate(t.id)} style={{
                background: tab === t.id ? AMBER + '15' : 'transparent',
                border: 'none', color: tab === t.id ? AMBER : '#475569',
                borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13,
                fontWeight: tab === t.id ? 600 : 400,
                borderBottom: tab === t.id ? `2px solid ${AMBER}` : '2px solid transparent',
              }}>{t.label}</button>
            ))}
          </nav>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: health?.status === 'ok' ? '#22c55e' : '#ef4444' }} />
            <span style={{ color: '#334155', fontSize: 12 }}>
              {health?.status === 'ok' ? 'Live' : 'Connecting...'}
            </span>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 32px' }}>
        {tab === 'dashboard' && <Dashboard health={health} />}
        {tab === 'forecast'  && <Forecast />}
        {tab === 'sentiment' && <SentimentTab />}
        {tab === 'backtest'  && <BacktestTab />}
        {tab === 'portfolio' && <PortfolioTab />}
        {tab === 'about'     && <About health={health} />}
      </main>
    </div>
  )
}
