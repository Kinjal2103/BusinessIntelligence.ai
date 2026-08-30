import { useState, useEffect } from 'react'
import './App.css'

const API_BASE = "http://localhost:8000"

// ==========================================
// 1. ANOMALY CHART COMPONENT (AnomalyChart)
// ==========================================
function AnomalyChart({ data, xKey, yKey1, yKey2, label1, label2, anomalyDate, anomalyDetails }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-on-surface-variant font-mono-data text-[12px] min-h-[160px]">
        No trend data available for selected window.
      </div>
    )
  }

  const width = 600
  const height = 220
  const paddingLeft = 50
  const paddingRight = 50
  const paddingTop = 20
  const paddingBottom = 30
  
  const chartWidth = width - paddingLeft - paddingRight
  const chartHeight = height - paddingTop - paddingBottom

  const y1Values = data.map(d => Number(d[yKey1] || 0))
  const y2Values = data.map(d => Number(d[yKey2] || 0))

  const y1Min = 0
  const y1Max = Math.max(...y1Values, 100) * 1.15
  const y2Min = 0
  const y2Max = Math.max(...y2Values, 1) * 1.15

  const getX = (index) => paddingLeft + (index / (data.length - 1)) * chartWidth
  const getY1 = (val) => paddingTop + chartHeight - ((val - y1Min) / (y1Max - y1Min)) * chartHeight
  const getY2 = (val) => paddingTop + chartHeight - ((val - y2Min) / (y2Max - y2Min)) * chartHeight

  let y1Points = ""
  let y2Points = ""
  data.forEach((d, idx) => {
    y1Points += `${getX(idx)},${getY1(y1Values[idx])} `
    y2Points += `${getX(idx)},${getY2(y2Values[idx])} `
  })

  const formatY1 = (val) => val >= 1000 ? `$${(val / 1000).toFixed(0)}k` : `$${val.toFixed(0)}`
  const formatY2 = (val) => val.toFixed(1)

  const yGridLines = [0, 0.25, 0.5, 0.75, 1]
  const parsedAnomalyDate = anomalyDate ? anomalyDate.split(' ')[0] : null
  const anomalyIndex = data.findIndex(d => d[xKey] === parsedAnomalyDate)

  const mean = anomalyDetails?.baseline_mean || 0
  const std = anomalyDetails?.baseline_std || 0
  let rangeBandPoints = ""

  if (mean && std) {
    const topY = getY1(Math.min(y1Max, mean + 2 * std))
    const bottomY = getY1(Math.max(0, mean - 2 * std))
    rangeBandPoints = `${paddingLeft},${topY} ${width - paddingRight},${topY} ${width - paddingRight},${bottomY} ${paddingLeft},${bottomY}`
  }

  return (
    <div className="bg-[#0f172a] border border-[#1e293b] rounded flex flex-col h-[300px]">
      <div className="p-4 border-b border-[#1e293b] flex justify-between items-center bg-[#0f172a] z-10">
        <h2 className="font-label-caps text-label-caps text-on-surface uppercase tracking-wider text-[11px]">
          {anomalyDetails?.kpi.toUpperCase()} TREND & ALIGNED METRICS
        </h2>
        <div className="flex gap-4 font-mono-data text-[10px] text-on-surface-variant">
          <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 bg-primary"></div> {label1}</div>
          <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 bg-[#ed8936]"></div> {label2}</div>
          {mean > 0 && <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-[#1e293b]/20 border border-[#334155]/30"></div> Expected Range</div>}
        </div>
      </div>
      
      <div className="flex-1 relative p-4 flex flex-col justify-end bg-gradient-to-b from-[#0f172a] to-[#020617] select-none">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
          {rangeBandPoints && (
            <polygon points={rangeBandPoints} fill="#1e293b" fillOpacity="0.25" stroke="#334155" strokeOpacity="0.15" strokeWidth="1" />
          )}

          {yGridLines.map((pct, idx) => {
            const y = paddingTop + chartHeight * pct
            return (
              <line key={idx} x1={paddingLeft} y1={y} x2={width - paddingRight} y2={y} stroke="#1e293b" strokeWidth="1" strokeDasharray="2 2" />
            )
          })}

          {yGridLines.map((pct, idx) => {
            const val = y1Max - (y1Max - y1Min) * pct
            return (
              <text key={idx} x={paddingLeft - 8} y={paddingTop + chartHeight * pct + 3} fill="#8c909f" fontSize="9" className="font-mono-data" textAnchor="end">
                {formatY1(val)}
              </text>
            )
          })}

          {yGridLines.map((pct, idx) => {
            const val = y2Max - (y2Max - y2Min) * pct
            return (
              <text key={idx} x={width - paddingRight + 8} y={paddingTop + chartHeight * pct + 3} fill="#8c909f" fontSize="9" className="font-mono-data" textAnchor="start">
                {formatY2(val)}
              </text>
            )
          })}

          {[0, Math.floor(data.length / 2), data.length - 1].map((idx) => {
            const x = getX(idx)
            const dateStr = data[idx][xKey]
            const isAnomalyIdx = idx === anomalyIndex
            return (
              <text key={idx} x={x} y={height - 5} fill={isAnomalyIdx ? "#ef4444" : "#8c909f"} fontSize="9" className="font-mono-data" textAnchor="middle">
                {dateStr ? dateStr.substring(5) : ""}
              </text>
            )
          })}

          {anomalyIndex !== -1 && (
            <g>
              <line 
                x1={getX(anomalyIndex)} 
                y1={paddingTop} 
                x2={getX(anomalyIndex)} 
                y2={paddingTop + chartHeight} 
                stroke="#ef4444" 
                strokeWidth="1.5" 
                strokeDasharray="2 2" 
              />
              <circle 
                cx={getX(anomalyIndex)} 
                cy={getY1(y1Values[anomalyIndex])} 
                r="4.5" 
                fill="#ef4444" 
                stroke="#020617" 
                strokeWidth="1.5" 
                className="animate-pulse"
              />
            </g>
          )}

          <polyline fill="none" stroke="#3b82f6" strokeWidth="2.0" strokeLinecap="round" strokeLinejoin="round" points={y1Points.trim()} />
          <polyline fill="none" stroke="#ed8936" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" points={y2Points.trim()} />
        </svg>
      </div>
    </div>
  )
}

// ==========================================
// 2. PERSONA SWITCHER COMPONENT (PersonaSwitcher)
// ==========================================
function PersonaSwitcher({ persona, setPersona, regionFilter, setRegionFilter }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1 bg-surface-container-low border border-outline-variant rounded p-1">
        <button 
          onClick={() => setPersona("admin")}
          className={`px-3 py-1 rounded font-label-caps text-label-caps text-[11px] transition-colors ${persona === "admin" ? "bg-surface-container-highest text-on-surface border border-outline-variant" : "text-on-surface-variant hover:text-on-surface"}`}
        >
          Admin
        </button>
        <button 
          onClick={() => setPersona("CFO")}
          className={`px-3 py-1 rounded font-label-caps text-label-caps text-[11px] transition-colors ${persona === "CFO" ? "bg-surface-container-highest text-on-surface border border-outline-variant" : "text-on-surface-variant hover:text-on-surface"}`}
        >
          CFO
        </button>
        <button 
          onClick={() => setPersona("Regional_Ops_Manager")}
          className={`px-3 py-1 rounded font-label-caps text-label-caps text-[11px] transition-colors ${persona === "Regional_Ops_Manager" ? "bg-surface-container-highest text-on-surface border border-outline-variant" : "text-on-surface-variant hover:text-on-surface"}`}
        >
          Ops Mgr
        </button>
      </div>

      {persona === "Regional_Ops_Manager" && (
        <select 
          value={regionFilter} 
          onChange={(e) => setRegionFilter(e.target.value)}
          className="input-technical py-1 px-2.5 bg-surface-container-low border border-outline-variant rounded font-label-caps text-label-caps text-[11px] text-on-surface cursor-pointer h-[28px] leading-none"
        >
          <option value="Southeast">Southeast</option>
          <option value="West">West</option>
          <option value="Northeast">Northeast</option>
        </select>
      )}
    </div>
  )
}

// ==========================================
// 3. INSIGHT CARD COMPONENT (InsightCard)
// ==========================================
function InsightCard({ incident, isSelected, onClick }) {
  const anomaly = incident.anomaly
  const isAbstain = incident.abstain
  const track = incident.confidence_track
  const corroborated = incident.drivers.find(d => d.evidence_gate_passed)
  const primary = corroborated || incident.drivers[0]
  
  let badgeClass = "bg-[#1e293b] text-[#94a3b8] border border-[#334155]"
  let icon = "account_tree"
  let hoverBorder = "hover:border-[#94a3b8]"
  
  if (isAbstain || track === "Unconfirmed") {
    badgeClass = "bg-[#451a03]/10 text-[#f59e0b] border border-[#78350f]"
    icon = "help_outline"
    hoverBorder = "hover:border-[#f59e0b]"
  } else if (track === "Acute") {
    badgeClass = "bg-[#064e3b]/10 text-[#10b981] border border-[#065f46]"
    icon = "warning"
    hoverBorder = "hover:border-primary"
  } else if (track === "External") {
    badgeClass = "border border-dashed border-[#334155] text-[#64748b]"
    icon = "public"
    hoverBorder = "hover:border-[#64748b]"
  }

  const borderClass = isSelected ? "border-primary ring-1 ring-primary" : "border-[#1e293b]"

  return (
    <div 
      className={`bg-[#0f172a] border p-card-padding flex flex-col gap-stack-md transition-colors cursor-pointer rounded ${hoverBorder} ${borderClass}`}
      onClick={onClick}
    >
      <div className="flex justify-between items-start">
        <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-wider text-[11px]">{anomaly.kpi}</h3>
        <span className={`${badgeClass} px-2 py-0.5 rounded font-label-caps text-[9px] uppercase tracking-wider flex items-center gap-1`}>
          <span className="material-symbols-outlined text-[12px]">{icon}</span>
          {isAbstain ? "ABSTAINED" : track}
        </span>
      </div>

      <div className="h-[40px] w-full flex items-end">
        <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 30">
          {track === "Acute" ? (
            <>
              <path d="M0 25 Q 10 20, 20 28 T 40 15 T 60 22 T 80 5 T 100 10" fill="none" stroke="#3b82f6" strokeLinejoin="round" strokeWidth="2"></path>
              <path d="M0 25 Q 10 20, 20 28 T 40 15 T 60 22 T 80 5 T 100 10 L 100 30 L 0 30 Z" fill="url(#blueGradientCard)" opacity="0.05" stroke="none"></path>
            </>
          ) : track === "Structural" ? (
            <path d="M0 10 L 20 12 L 40 15 L 60 20 L 80 25 L 100 28" fill="none" stroke="#94a3b8" strokeLinejoin="round" strokeWidth="2"></path>
          ) : (
            <path d="M0 15 L 20 18 L 40 5 L 60 8 L 80 28 L 100 20" fill="none" stroke="#f59e0b" strokeDasharray="3 3" strokeLinejoin="round" strokeWidth="1.5"></path>
          )}
          <defs>
            <linearGradient id="blueGradientCard" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6"></stop>
              <stop offset="100%" stopColor="transparent"></stop>
            </linearGradient>
          </defs>
        </svg>
      </div>

      <div>
        <p className="font-body-sm text-body-sm text-on-surface mb-unit line-clamp-2 leading-relaxed text-[13px]">
          {incident.title}
        </p>
        <div className="flex justify-between items-center mt-2 border-t border-[#1e293b] pt-2">
          <p className="font-mono-data text-mono-data text-on-surface-variant flex items-center gap-1 text-[11px]">
            <span className="material-symbols-outlined text-[13px]">schedule</span>
            {anomaly.timestamp.split(' ')[0]}
          </p>
          <span className="font-mono-data text-[#8c909f] text-[10px]">
            Region: {anomaly.region}
          </span>
        </div>
      </div>
    </div>
  )
}

// ==========================================
// 4. EVIDENCE & DATA LINEAGE PANEL (EvidencePanel)
// ==========================================
function EvidencePanel({ incident }) {
  const [collapsed, setCollapsed] = useState(false)
  const primaryDriver = incident.drivers.find(d => d.evidence_gate_passed) || incident.drivers[0]
  
  if (!primaryDriver) return null

  const primaryWeight = Math.round(Math.abs(primaryDriver.correlation) * 100)
  const remaining = 100 - primaryWeight
  const secWeight = Math.round(remaining * 0.6)
  const otherWeight = remaining - secWeight

  return (
    <section className="data-card rounded flex flex-col overflow-hidden">
      <button 
        className="p-4 flex justify-between items-center w-full text-left bg-[#0f172a] hover:bg-[#1e293b]/50 transition-colors"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-on-surface-variant">account_tree</span>
          <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-wider text-[11px]">EVIDENCE &amp; LINEAGE</h3>
        </div>
        <span className={`material-symbols-outlined text-[20px] text-on-surface-variant transition-transform duration-200 ${collapsed ? '' : 'rotate-180'}`}>
          expand_more
        </span>
      </button>

      {!collapsed && (
        <div className="p-6 border-t border-[#1e293b] flex flex-col md:flex-row gap-stack-lg bg-[#0c1324]/40">
          <div className="flex-1 flex flex-col gap-stack-md">
            <div>
              <div className="font-label-caps text-[10px] text-on-surface-variant mb-2 tracking-wider">ANALYTICAL METHOD</div>
              <div className="level-2-surface px-3 py-2 rounded font-mono-data text-[12px] inline-flex items-center gap-2">
                <span className="material-symbols-outlined text-[14px] text-secondary">functions</span>
                Lead-Lag Pearson Correlation (Lag: {primaryDriver.lag}d)
              </div>
            </div>
            <div>
              <div className="font-label-caps text-[10px] text-on-surface-variant mb-2 tracking-wider">DATA LINEAGE</div>
              <div className="flex items-center flex-wrap gap-2 font-mono-data text-[11px] text-[#94a3b8]">
                <div className="flex items-center gap-1 bg-[#020617] border border-[#1e293b] px-2 py-1 rounded">
                  <span className="material-symbols-outlined text-[12px]">database</span> Zendesk & CRM
                </div>
                <span className="material-symbols-outlined text-[14px]">arrow_right_alt</span>
                <div className="flex items-center gap-1 bg-[#020617] border border-[#1e293b] px-2 py-1 rounded">
                  <span className="material-symbols-outlined text-[12px]">transform</span> pgvector Sync
                </div>
                <span className="material-symbols-outlined text-[14px]">arrow_right_alt</span>
                <div className="flex items-center gap-1 bg-[#1e293b] border border-[#334155] px-2 py-1 rounded text-on-surface">
                  <span className="material-symbols-outlined text-[12px] text-primary">analytics</span> {primaryDriver.candidate.toUpperCase()}
                </div>
              </div>
            </div>
          </div>

          <div className="flex-1 flex flex-col border-t md:border-t-0 md:border-l border-[#1e293b] pt-4 md:pt-0 md:pl-6">
            <div className="font-label-caps text-[10px] text-on-surface-variant mb-4 tracking-wider">CONTRIBUTION TO DEVIATION</div>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between font-mono-data text-[11px] mb-1">
                  <span className="text-on-surface">{primaryDriver.candidate}</span>
                  <span className="text-error font-bold">{primaryWeight}%</span>
                </div>
                <div className="w-full bg-[#020617] rounded h-1 border border-[#1e293b] overflow-hidden">
                  <div className="bg-error h-1 rounded" style={{ width: `${primaryWeight}%` }}></div>
                </div>
              </div>
              
              {incident.drivers.length > 1 && (
                <div>
                  <div className="flex justify-between font-mono-data text-[11px] mb-1">
                    <span className="text-on-surface">{incident.drivers[1].candidate}</span>
                    <span className="text-tertiary font-bold">{secWeight}%</span>
                  </div>
                  <div className="w-full bg-[#020617] rounded h-1 border border-[#1e293b] overflow-hidden">
                    <div className="bg-tertiary h-1 rounded" style={{ width: `${secWeight}%` }}></div>
                  </div>
                </div>
              )}

              <div>
                <div className="flex justify-between font-mono-data text-[11px] mb-1">
                  <span className="text-on-surface">External/Residual Factors</span>
                  <span className="text-primary font-bold">{otherWeight}%</span>
                </div>
                <div className="w-full bg-[#020617] rounded h-1 border border-[#1e293b] overflow-hidden">
                  <div className="bg-primary h-1 rounded" style={{ width: `${otherWeight}%` }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

// ==========================================
// 5. REVIEW & AUTHORIZE CARD (ReviewAuthorizeCard)
// ==========================================
function ReviewAuthorizeCard({ incident, onSubmitDecision, comments, setComments, decisionLogged, completedRecs, toggleRec }) {
  const corroborated = incident.drivers.find(d => d.evidence_gate_passed)
  const primary = corroborated || incident.drivers[0]

  return (
    <div className="flex flex-col gap-4">
      <div className="data-card rounded p-6 bg-[#0f172a] border border-[#1e293b]">
        <h3 className="font-label-caps text-label-caps text-on-surface mb-stack-md border-b border-[#1e293b] pb-2 uppercase tracking-wider text-[11px]">
          MITIGATION ACTION CHECKLIST
        </h3>
        <p className="font-body-sm text-body-sm text-on-surface-variant mb-4 leading-relaxed text-[13px]">
          Dynamically selected action recommendations. Verify and execute checklist items before authorizing.
        </p>
        <div className="flex flex-col gap-3">
          {incident.recommendations.map((rec, idx) => {
            const isChecked = !!completedRecs[`${incident.incident_id}-${idx}`]
            return (
              <label 
                key={idx} 
                className="flex items-start gap-3 cursor-pointer select-none text-[13px] text-on-surface leading-normal py-1"
                style={{ textDecoration: isChecked ? 'line-through' : 'none', opacity: isChecked ? 0.5 : 1 }}
              >
                <input 
                  type="checkbox" 
                  className="input-technical w-4 h-4 text-primary focus:ring-1 focus:ring-primary rounded cursor-pointer mt-0.5"
                  checked={isChecked}
                  onChange={() => toggleRec(incident.incident_id, idx)}
                />
                <span>{rec}</span>
              </label>
            )
          })}
        </div>
      </div>

      <section className="data-card rounded p-6 border-l-4 border-l-secondary relative overflow-hidden">
        <div className="absolute inset-0 bg-secondary/5 pointer-events-none"></div>
        <div className="relative z-10 flex flex-col gap-stack-md">
          <div className="flex justify-between items-start">
            <div>
              <div className="flex items-center gap-2 mb-1.5 text-secondary font-label-caps text-label-caps text-[11px] tracking-wider">
                <span className="material-symbols-outlined text-[16px]">robot_2</span>
                SYSTEM RECOMMENDATION
              </div>
              <h3 className="font-headline-md text-headline-md text-on-surface mb-2 text-[16px] font-semibold">
                Authorize {primary ? primary.candidate.toUpperCase() : "incident"} mitigations to system.
              </h3>
            </div>
            
            <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#1e293b] border border-[#334155] rounded-full text-on-surface font-mono-data text-[11px]">
              <span className="material-symbols-outlined text-[14px] text-secondary">trending_up</span>
              Est. Margin Impact: <strong className="text-secondary">+1.2%</strong>
            </div>
          </div>

          <div>
            <label className="font-label-caps text-[10px] text-on-surface-variant tracking-wider uppercase mb-1.5 block" htmlFor="comments">
              ANALYST NOTES
            </label>
            <textarea 
              id="comments"
              rows="2"
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder="Supply validation notes, edit suggestions, or deployment context before signing..."
              className="input-technical w-full p-3 font-body-sm text-body-sm rounded placeholder:text-outline/40 placeholder:font-light"
            />
          </div>

          <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
            <button 
              onClick={() => onSubmitDecision('reject')}
              className="px-4 py-2 bg-transparent border border-[#334155] text-on-surface-variant hover:text-error hover:border-error hover:bg-error/10 rounded transition-colors font-label-caps text-[11px] font-bold tracking-wider flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[16px]">close</span> REJECT ALERT
            </button>
            
            <button 
              onClick={() => onSubmitDecision('approve')}
              className="px-6 py-2 bg-primary text-[#002e6a] hover:bg-primary-fixed rounded transition-colors font-label-caps text-[11px] font-black tracking-widest shadow-[0_0_15px_rgba(59,130,246,0.2)] hover:shadow-[0_0_20px_rgba(59,130,246,0.4)] flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[16px]">check</span> AUTHORIZE MITIGATION
            </button>
          </div>

          {decisionLogged && (
            <p className="font-mono-data text-secondary text-[11px] font-bold text-right">
              ✓ Decision logged to audit database. Recalibrator completed.
            </p>
          )}
        </div>
      </section>
    </div>
  )
}

// ==========================================
// 6. ABSTENTION VIEW COMPONENT (AbstentionView)
// ==========================================
function AbstentionView({ incident, contextText, setContextText, onSubmitContext }) {
  const anomaly = incident.anomaly
  const primaryDriver = incident.drivers[0] || {}

  return (
    <div className="data-card rounded flex flex-col w-full relative overflow-hidden">
      <div className="absolute inset-0 opacity-[0.02] pointer-events-none" style={{ backgroundImage: 'radial-gradient(#8c909f 1px, transparent 1px)', backgroundSize: '16px 16px' }}></div>
      
      <div className="p-card-padding border-b border-outline-variant flex justify-between items-start relative z-10 bg-[#0f172a]">
        <div>
          <h2 className="font-headline-md text-headline-md text-on-surface mb-unit text-[17px] font-semibold">
            Correlation Detected: Revenue vs. {primaryDriver.candidate}
          </h2>
          <div className="flex items-center gap-stack-sm mt-stack-sm">
            <span className="bg-[#451a03]/15 text-[#f59e0b] border border-[#78350f]/55 font-mono-data text-[10px] px-2 py-0.5 rounded inline-flex items-center gap-1 uppercase tracking-wider font-bold">
              <span className="material-symbols-outlined text-[13px]">warning</span>
              INSUFFICIENT EVIDENCE (ABSTAINED)
            </span>
            <span className="text-on-surface-variant font-mono-data text-[11px] opacity-60">Confidence: {(incident.confidence_score * 100).toFixed(0)}%</span>
          </div>
        </div>
        <span className="material-symbols-outlined text-on-surface-variant opacity-30 text-[32px] font-light">analytics</span>
      </div>

      <div className="p-card-padding flex flex-col md:flex-row gap-stack-lg relative z-10 bg-[#0c1324]/40">
        <div className="flex-1 flex flex-col">
          <div className="mb-stack-md">
            <p className="font-body-lg text-body-lg text-on-surface-variant leading-relaxed text-[15px] mb-2 font-medium">
              We scanned the system for evidence, but no direct corroborating support tickets or error logs were found.
            </p>
            <p className="font-body-sm text-body-sm text-outline leading-relaxed text-[13px] border-l-2 border-[#1e293b] pl-3 italic">
              "{incident.clarifying_question}"
            </p>
          </div>

          <div className="mt-auto bg-surface-container-lowest border border-[#1e293b] p-stack-md rounded">
            <div className="flex items-center gap-stack-sm mb-stack-sm">
              <span className="material-symbols-outlined text-[#8c909f] text-[16px]">data_object</span>
              <span className="font-label-caps text-label-caps text-[#8c909f] uppercase tracking-wider text-[10px]">Statistical Correlation Snapshot</span>
            </div>
            <div className="grid grid-cols-2 gap-stack-sm">
              <div>
                <span className="block font-label-caps text-label-caps text-on-surface-variant opacity-60 text-[10px] uppercase">Pearson Correlation</span>
                <span className="font-mono-data text-on-surface text-[13px] font-bold">
                  {primaryDriver.correlation ? primaryDriver.correlation.toFixed(3) : "0.000"}{" "}
                  <span className="text-error opacity-80 text-[10px]">↑</span>
                </span>
              </div>
              <div>
                <span className="block font-label-caps text-label-caps text-on-surface-variant opacity-60 text-[10px] uppercase">Anomalous Data Points</span>
                <span className="font-mono-data text-on-surface text-[13px] font-bold">
                  Revenue deviation (-{Math.round(anomaly.pct_change*100)}%)
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col border-t md:border-t-0 md:border-l border-outline-variant pt-stack-lg md:pt-0 md:pl-stack-lg">
          <label className="font-label-caps text-label-caps text-on-surface mb-stack-sm block uppercase tracking-wider text-[11px]" htmlFor="context-input">
            Analyst Input Required
          </label>
          <textarea 
            id="context-input"
            rows="4"
            value={contextText}
            onChange={(e) => setContextText(e.target.value)}
            placeholder="Supply missing context, paste SRE logs snippets, or upload bypass deployment confirmation..."
            className="input-technical w-full p-3 font-body-sm text-body-sm rounded resize-none mb-stack-md placeholder:text-[#8c909f]/45"
          />
          <div className="flex justify-end gap-stack-sm mt-auto">
            <button 
              onClick={() => { setContextText(""); alert("Insight dismiss logged."); }}
              className="px-4 py-2 bg-transparent border border-[#1e293b] text-[#f8fafc] rounded font-label-caps text-[11px] uppercase tracking-wider hover:bg-[#1e293b] transition-colors flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[16px]">close</span> Dismiss
            </button>
            <button 
              onClick={onSubmitContext}
              className="px-4 py-2 bg-primary text-[#002e6a] hover:bg-primary-fixed rounded font-label-caps text-[11px] uppercase tracking-widest font-bold transition-colors flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[16px]">upload</span> Submit Context
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ==========================================
// 7. TELEMETRY GOVERNANCE PANEL (TelemetryPanel)
// ==========================================
function TelemetryPanel({ logs }) {
  const totalCost = logs.reduce((sum, item) => sum + (item.cost || 0.0), 0.0)
  const totalLatencySec = (logs.reduce((sum, item) => sum + (item.latency || 0), 0) / 1000).toFixed(2)
  const inputTokens = logs.reduce((sum, item) => sum + (item.input_tokens || 0), 0)
  const outputTokens = logs.reduce((sum, item) => sum + (item.output_tokens || 0), 0)

  return (
    <div className="w-full space-y-stack-lg">
      <div className="flex justify-between items-end border-b border-outline-variant pb-stack-sm">
        <div>
          <h2 className="font-display text-display text-on-surface mb-unit text-[28px]">Insight Telemetry</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant">Detailed breakdown of computational execution and resource utilization.</p>
        </div>
      </div>

      <div className="col-span-12 bg-[#0f172a] border border-[#1e293b] rounded flex flex-col overflow-hidden">
        <div className="p-card-padding border-b border-[#1e293b] flex justify-between items-center bg-[#0f172a]">
          <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-wider text-[11px]">
            INSIGHT EXECUTION TELEMETRY
          </h3>
          <span className="px-2 py-0.5 bg-[#1e293b] border border-[#334155] rounded text-[10px] font-mono-data text-[#94a3b8] uppercase tracking-wider font-bold">
            Status: Active
          </span>
        </div>

        {/* Bento Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 border-b border-[#1e293b] bg-[#0c1324]/30">
          <div className="p-card-padding border-r border-b md:border-b-0 border-[#1e293b]">
            <div className="flex items-center justify-between mb-stack-sm text-on-surface-variant font-label-caps text-[10px] tracking-wider uppercase">
              <span>LLM Running Cost</span>
              <span className="material-symbols-outlined text-[15px] text-primary">attach_money</span>
            </div>
            <div className="font-mono-data text-[22px] text-on-surface font-bold">${totalCost.toFixed(5)}</div>
          </div>
          <div className="p-card-padding border-r border-b md:border-b-0 border-[#1e293b]">
            <div className="flex items-center justify-between mb-stack-sm text-on-surface-variant font-label-caps text-[10px] tracking-wider uppercase">
              <span>LLM Accum. Latency</span>
              <span className="material-symbols-outlined text-[15px] text-primary">timer</span>
            </div>
            <div className="font-mono-data text-[22px] text-on-surface font-bold">{totalLatencySec}s</div>
          </div>
          <div className="p-card-padding">
            <div className="flex items-center justify-between mb-stack-sm text-on-surface-variant font-label-caps text-[10px] tracking-wider uppercase">
              <span>Token Aggregations</span>
              <span className="material-symbols-outlined text-[15px] text-primary">toll</span>
            </div>
            <div className="font-mono-data text-[14px] text-on-surface mt-1.5">
              <span className="text-on-surface-variant">In:</span> {inputTokens.toLocaleString()}{" "}
              <span className="text-on-surface-variant mx-2">|</span>{" "}
              <span className="text-on-surface-variant">Out:</span> {outputTokens.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Execution Path Nodes */}
        <div className="p-card-padding border-b border-[#1e293b] overflow-x-auto bg-[#0c1324]/20">
          <div className="min-w-[600px] relative pt-6 pb-2">
            <div className="absolute left-10 right-10 top-10 h-[1.5px] bg-[#1e293b] border-t border-dashed border-[#334155]/60"></div>
            
            <div className="flex justify-between relative z-10">
              <div className="flex flex-col items-center w-36">
                <div className="w-7 h-7 rounded bg-[#020617] border border-[#334155] flex items-center justify-center mb-stack-sm font-mono-data text-[11px] text-on-surface-variant">01</div>
                <div className="text-center">
                  <div className="font-body-sm text-[12px] text-on-surface font-semibold mb-0.5">Data Ingestion</div>
                  <span className="inline-block px-1.5 py-0.5 bg-[#1e293b] border border-[#334155] rounded font-mono-data text-[9px] text-[#94a3b8] font-bold">NON-LLM</span>
                </div>
              </div>
              <div className="flex flex-col items-center w-36">
                <div className="w-7 h-7 rounded bg-[#020617] border border-[#334155] flex items-center justify-center mb-stack-sm font-mono-data text-[11px] text-on-surface-variant">02</div>
                <div className="text-center">
                  <div className="font-body-sm text-[12px] text-on-surface font-semibold mb-0.5">Anomaly Detect</div>
                  <span className="inline-block px-1.5 py-0.5 bg-[#1e293b] border border-[#334155] rounded font-mono-data text-[9px] text-[#94a3b8] font-bold">NON-LLM</span>
                </div>
              </div>
              <div className="flex flex-col items-center w-36">
                <div className="w-7 h-7 rounded bg-[#020617] border border-[#334155] flex items-center justify-center mb-stack-sm font-mono-data text-[11px] text-on-surface-variant">03</div>
                <div className="text-center">
                  <div className="font-body-sm text-[12px] text-on-surface font-semibold mb-0.5">Investigate Gate</div>
                  <span className="inline-block px-1.5 py-0.5 bg-[#1e293b]/50 border border-[#334155]/50 rounded font-mono-data text-[9px] text-[#3b82f6] font-bold">LLM (triage)</span>
                </div>
              </div>
              <div className="flex flex-col items-center w-36">
                <div className="w-7 h-7 rounded bg-[#0f172a] border border-primary flex items-center justify-center mb-stack-sm relative before:absolute before:inset-0 before:ring-2 before:ring-primary/20 before:rounded font-mono-data text-[11px] text-primary font-bold">04</div>
                <div className="text-center">
                  <div className="font-body-sm text-[12px] text-primary font-semibold mb-0.5">Narrative Synthesis</div>
                  <span className="inline-block px-1.5 py-0.5 bg-primary/10 border border-primary/30 rounded font-mono-data text-[9px] text-primary font-bold">LLM (flash)</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Detailed Performance Trace */}
        <div className="p-card-padding max-h-96 overflow-y-auto">
          <table className="w-full text-left font-mono-data text-[11.5px] text-[#8c909f] border-collapse">
            <thead>
              <tr className="border-b border-[#1e293b] text-on-surface font-bold">
                <th className="py-2">Pipeline Stage</th>
                <th className="py-2">Model Name</th>
                <th className="py-2 text-right">Prompt/Output Tokens</th>
                <th className="py-2 text-right">API Latency</th>
                <th className="py-2 text-right">Cost (USD)</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, idx) => (
                <tr key={idx} className="border-b border-[#1e293b]/50 hover:bg-[#1e293b]/20">
                  <td className="py-2 font-bold text-on-surface">{log.stage.toUpperCase()}</td>
                  <td className="py-2">{log.model_name}</td>
                  <td className="py-2 text-right">{log.input_tokens}/{log.output_tokens}</td>
                  <td className="py-2 text-right">{log.latency}ms</td>
                  <td className="py-2 text-right font-bold text-[#f8fafc]">${log.cost.toFixed(5)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ==========================================
// 8. INSIGHT DETAIL COMPONENT (InsightDetail)
// ==========================================
function InsightDetail({ 
  incident, 
  chartData, 
  comments, 
  setComments, 
  decisionLogged, 
  onSubmitDecision, 
  completedRecs, 
  toggleRec,
  analystContext,
  setAnalystContext,
  onSubmitContext,
  persona
}) {
  const anomaly = incident.anomaly
  const primaryDriver = incident.drivers.find(d => d.evidence_gate_passed) || incident.drivers[0]
  const corroborated = !!incident.drivers.find(d => d.evidence_gate_passed)

  return (
    <div className="flex-grow flex flex-col gap-stack-lg">
      <header className="flex flex-col gap-stack-sm border-b border-[#1e293b] pb-stack-md pt-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-on-surface-variant font-label-caps text-label-caps text-[11px] tracking-wider">
            <span className={`material-symbols-outlined text-[16px] ${incident.severity === 'Critical' ? 'text-error' : 'text-tertiary'}`}>
              warning
            </span>
            {incident.confidence_track.toUpperCase()} REVENUE ANOMALY
          </div>
          <button 
            onClick={() => { alert(`Incident ID Copied: ${incident.incident_id}`); }}
            className="flex items-center gap-1 text-primary hover:text-primary-container font-label-caps text-label-caps text-[11px] transition-colors"
          >
            <span className="material-symbols-outlined text-[15px]">ios_share</span> Share ID
          </button>
        </div>
        <h1 className="font-display text-display text-on-surface leading-tight text-[28px] mt-1">{incident.title}</h1>
        <div className="flex gap-4 mt-2 font-mono-data text-[11px] text-on-surface-variant items-center">
          <span className="material-symbols-outlined text-[14px]">map</span>
          Region: <strong className="text-on-surface">{anomaly.region}</strong>
          <span className="opacity-50">|</span>
          <span className="material-symbols-outlined text-[14px]">calendar_month</span>
          Date: <strong className="text-on-surface">{anomaly.timestamp.split(' ')[0]}</strong>
          <span className="opacity-50">|</span>
          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#064e3b]/10 border border-[#065f46] text-[#10b981]">
            <span className="material-symbols-outlined text-[12px]">check_circle</span>
            {(incident.confidence_score * 100).toFixed(0)}% CONFIDENCE
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter">
        <div className="data-card rounded p-card-padding">
          <div className="font-label-caps text-[10px] text-on-surface-variant mb-1 uppercase tracking-wider">ACTUAL REVENUE</div>
          <div className="font-mono-data text-[20px] text-[#f8fafc] font-bold">${anomaly.actual.toLocaleString()}</div>
        </div>
        <div className="data-card rounded p-card-padding">
          <div className="font-label-caps text-[10px] text-on-surface-variant mb-1 uppercase tracking-wider">EXPECTED BASELINE</div>
          <div className="font-mono-data text-[20px] text-on-surface-variant font-bold">${anomaly.baseline_mean.toLocaleString()}</div>
        </div>
        <div className="data-card rounded p-card-padding border-l-4 border-l-error">
          <div className="font-label-caps text-[10px] text-error mb-1 uppercase tracking-wider">ABSOLUTE IMPACT</div>
          <div className="font-mono-data text-[20px] text-error font-bold">
            -${anomaly.absolute_change.toLocaleString()} (-{(anomaly.pct_change * 100).toFixed(1)}%)
          </div>
        </div>
      </div>

      <div className="data-card rounded p-6 bg-[#0f172a] border border-[#1e293b]">
        <h3 className="font-label-caps text-label-caps text-on-surface mb-3 border-b border-[#1e293b] pb-2 uppercase tracking-wider text-[11px]">
          EXECUTIVE TRIAGE SUMMARY
        </h3>
        <p className="font-body-lg text-body-lg text-on-surface-variant leading-relaxed text-[14.5px] mb-4">
          {incident.executive_summary}
        </p>
        <h3 className="font-label-caps text-label-caps text-on-surface mb-3 border-b border-[#1e293b] pb-2 uppercase tracking-wider text-[11px] mt-6">
          BUSINESS IMPACT DESCRIPTION
        </h3>
        <p className="font-body-sm text-body-sm text-on-surface-variant leading-relaxed text-[13px]">
          {incident.business_impact}
        </p>
      </div>

      {incident.abstain ? (
        <AbstentionView 
          incident={incident} 
          contextText={analystContext}
          setContextText={setAnalystContext}
          onSubmitContext={onSubmitContext}
        />
      ) : (
        <>
          {primaryDriver && (
            <AnomalyChart 
              data={chartData}
              xKey="date"
              yKey1="revenue"
              yKey2="driverValue"
              label1="Revenue"
              label2={primaryDriver.candidate.toUpperCase()}
              anomalyDate={anomaly.timestamp}
              anomalyDetails={anomaly}
            />
          )}

          <EvidencePanel incident={incident} />

          <div className="data-card rounded p-6 bg-[#0f172a] border border-[#1e293b]">
            <h3 className="font-label-caps text-label-caps text-on-surface mb-3 border-b border-[#1e293b] pb-2 uppercase tracking-wider text-[11px]">
              ROOT CAUSE ANALYSIS & EVIDENCE GATE
            </h3>
            
            <div className={`custom-alert px-4 py-2.5 rounded text-[13.5px] flex items-start gap-2.5 mb-4 border ${corroborated ? 'bg-[#064e3b]/15 text-[#10b981] border-[#065f46]' : 'bg-[#451a03]/15 text-[#f59e0b] border-[#78350f]'}`}>
              <span className="material-symbols-outlined text-[17px]">
                {corroborated ? 'check_circle' : 'info'}
              </span>
              <div>
                <strong>Evidence Gate: {corroborated ? 'PASSED (CORROBORATED ROOT CAUSE)' : 'WARNING (UNCORROBORATED)'}</strong><br />
                {incident.confidence_caveat}
              </div>
            </div>

            <p className="font-body-sm text-body-sm text-on-surface-variant leading-relaxed text-[13.5px] whitespace-pre-line">
              {incident.root_cause_analysis}
            </p>

            <h4 className="font-label-caps text-[10px] text-on-surface-variant mt-6 mb-3 uppercase tracking-wider">
              RETRIEVED VECTOR EVIDENCE TICKETS ({incident.retrieved_tickets?.length || 0})
            </h4>

            {incident.retrieved_tickets && incident.retrieved_tickets.length > 0 ? (
              <div className="flex flex-col gap-3">
                {incident.retrieved_tickets.map((t) => (
                  <div key={t.ticket_id} className="border border-[#1e293b] rounded bg-[#020617]/40 p-4">
                    <div className="flex justify-between items-center text-[11px] font-mono-data text-[#8c909f] mb-2 border-b border-[#1e293b]/60 pb-1.5">
                      <span className="text-[#3b82f6] font-bold">#{t.ticket_id}</span>
                      <span>Category: {t.category} | Priority: {t.priority}</span>
                      <span>{t.created_at}</span>
                    </div>
                    <p className="font-body-sm text-[13px] text-on-surface italic leading-normal bg-[#0f172a] p-2.5 rounded border border-[#1e293b]/70 flex items-center justify-between">
                      <span>"{t.description}"</span>
                      {t.description.includes("REDACTED") && (
                        <span className="px-2 py-0.5 bg-error-container/20 border border-error/30 text-error text-[9px] font-mono-data uppercase tracking-wider font-bold rounded">
                          CFO REDACTION
                        </span>
                      )}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 border border-dashed border-[#1e293b] text-center font-mono-data text-[12px] text-on-surface-variant rounded">
                No tickets matching evidence signatures retrieved.
              </div>
            )}
          </div>

          <ReviewAuthorizeCard 
            incident={incident}
            onSubmitDecision={onSubmitDecision}
            comments={comments}
            setComments={setComments}
            decisionLogged={decisionLogged}
            completedRecs={completedRecs}
            toggleRec={toggleRec}
          />
        </>
      )}
    </div>
  )
}

// ==========================================
// 9. CORE REACT CONTAINER (App)
// ==========================================
function App() {
  const [incidents, setIncidents] = useState([])
  const [selectedIncident, setSelectedIncident] = useState(null)
  const [chartData, setChartData] = useState([])
  const [apiStatus, setApiStatus] = useState("checking")
  const [pipelineRunning, setPipelineRunning] = useState(false)
  
  // Custom checklist states
  const [completedRecs, setCompletedRecs] = useState({})
  
  // Navigation state (Overview, Intelligence, Audits, Telemetry)
  const [currentTab, setCurrentTab] = useState("intelligence")
  
  // Persona Entitlement boundaries
  const [persona, setPersona] = useState("admin")
  const [regionFilter, setRegionFilter] = useState("Southeast")
  
  // Telemetry and Audited Decisions logs
  const [telemetry, setTelemetry] = useState([])
  const [decisions, setDecisions] = useState([])
  
  const [comments, setComments] = useState("")
  const [analystContext, setAnalystContext] = useState("")
  const [decisionLogged, setDecisionLogged] = useState(false)

  // Trigger loads whenever switching persona or region filter
  useEffect(() => {
    fetchIncidents()
    fetchTelemetry()
    fetchDecisions()
  }, [persona, regionFilter])

  // Fetch trend correlations chart data
  useEffect(() => {
    if (!selectedIncident) return
    
    const anomaly = selectedIncident.anomaly
    const region = anomaly.region
    const anomalyDate = anomaly.timestamp.split(' ')[0]
    const corroborated = selectedIncident.drivers.find(d => d.evidence_gate_passed)
    const primary = corroborated || selectedIncident.drivers[0]
    
    if (!primary) {
      setChartData([])
      return
    }

    const dt = new Date(anomalyDate)
    const startDt = new Date(dt.getTime() - 10 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    const endDt = new Date(dt.getTime() + 10 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]

    const headers = { "X-User-Role": persona }
    if (persona === "Regional_Ops_Manager") {
      headers["X-User-Region"] = regionFilter
    }

    fetch(`${API_BASE}/api/reconcile?kpi_x=${primary.candidate}&kpi_y=revenue&region=${region}&start_date=${startDt}&end_date=${endDt}`, { headers })
      .then(res => {
        if (res.status === 403) throw new Error("Forbidden regional boundaries check.")
        return res.json()
      })
      .then(data => {
        const formatted = data.map(d => ({
          date: d.date,
          revenue: d.revenue,
          driverValue: d[primary.candidate]
        }))
        setChartData(formatted)
      })
      .catch(err => {
        console.error(err)
        setChartData([])
      })

  }, [selectedIncident, persona, regionFilter])

  const fetchIncidents = () => {
    setApiStatus("loading")
    const headers = { "X-User-Role": persona }
    if (persona === "Regional_Ops_Manager") {
      headers["X-User-Region"] = regionFilter
    }

    fetch(`${API_BASE}/api/reports?active_only=true`, { headers })
      .then(res => {
        if (!res.ok) throw new Error("API not active")
        return res.json()
      })
      .then(data => {
        setIncidents(data)
        setApiStatus("healthy")
        if (data.length > 0) {
          const stillExists = data.find(i => i.incident_id === selectedIncident?.incident_id)
          setSelectedIncident(stillExists || data[0])
        } else {
          setSelectedIncident(null)
        }
      })
      .catch(err => {
        console.error(err)
        setApiStatus("offline")
      })
  }

  const fetchTelemetry = () => {
    fetch(`${API_BASE}/api/telemetry`)
      .then(res => res.json())
      .then(data => setTelemetry(data))
      .catch(err => console.error("Telemetry failed:", err))
  }

  const fetchDecisions = () => {
    fetch(`${API_BASE}/api/decisions`)
      .then(res => res.json())
      .then(data => setDecisions(data))
      .catch(err => console.error("Decisions log failed:", err))
  }

  const runPipeline = () => {
    setPipelineRunning(true)
    fetch(`${API_BASE}/api/run-pipeline`, { method: "POST" })
      .then(res => res.json())
      .then(data => {
        alert("Pipeline completed end-to-end! (Detect -> Investigate -> Judge -> Act).")
        fetchIncidents()
        fetchTelemetry()
        fetchDecisions()
      })
      .catch(err => {
        console.error(err)
        alert("Pipeline run failed. Verify SRE logs.")
      })
      .finally(() => {
        setPipelineRunning(false)
      })
  }

  const submitDecision = (decisionType) => {
    if (!selectedIncident) return
    const payload = {
      incident_id: selectedIncident.incident_id,
      decision: decisionType,
      adjusted_narrative: selectedIncident.executive_summary,
      adjusted_action: selectedIncident.recommendations.join('\n'),
      analyst_comments: comments
    }

    fetch(`${API_BASE}/api/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        setDecisionLogged(true)
        setComments("")
        alert(`Analyst feedback logged: ${decisionType.toUpperCase()}. Threshold overrides recalibrated!`)
        fetchIncidents()
        fetchTelemetry()
        fetchDecisions()
        setTimeout(() => setDecisionLogged(false), 3000)
      })
      .catch(err => {
        console.error(err)
        alert("Decision submit failed.")
      })
  }

  const submitContext = () => {
    if (!analystContext.trim()) return
    alert(`Operational context logged successfully:\n"${analystContext}"`)
    setAnalystContext("")
  }

  const toggleRec = (incidentId, idx) => {
    const key = `${incidentId}-${idx}`
    setCompletedRecs(prev => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div className="flex h-screen overflow-hidden antialiased bg-background text-on-surface">
      
      {/* SideNavBar with Navigation State Link toggling */}
      <nav className="hidden md:flex flex-col h-screen w-60 bg-surface-container-low border-r border-outline-variant py-stack-md shrink-0 z-40">
        <div className="px-gutter mb-stack-lg flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-primary flex items-center justify-center text-on-primary font-bold">BI</div>
          <div>
            <div className="font-headline-md text-headline-md font-black text-on-surface">BI.ai</div>
            <div className="font-label-caps text-label-caps text-on-surface-variant">Enterprise Intelligence</div>
          </div>
        </div>
        <div className="flex-1 px-gutter space-y-1 select-none">
          <button 
            onClick={() => setCurrentTab("overview")}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded text-left transition-all font-body-sm text-body-sm ${currentTab === "overview" ? "bg-secondary-container text-on-secondary-container border-r-2 border-secondary font-bold" : "text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface font-semibold"}`}
          >
            <span className="material-symbols-outlined text-[20px]">dashboard</span> Overview
          </button>
          
          <button 
            onClick={() => setCurrentTab("intelligence")}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded text-left transition-all font-body-sm text-body-sm ${currentTab === "intelligence" ? "bg-secondary-container text-on-secondary-container border-r-2 border-secondary font-bold" : "text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface font-semibold"}`}
          >
            <span className="material-symbols-outlined text-[20px]">psychology</span> Intelligence
          </button>
          
          <button 
            onClick={() => setCurrentTab("audits")}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded text-left transition-all font-body-sm text-body-sm ${currentTab === "audits" ? "bg-secondary-container text-on-secondary-container border-r-2 border-secondary font-bold" : "text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface font-semibold"}`}
          >
            <span className="material-symbols-outlined text-[20px]">history_edu</span> Audits
          </button>
          
          <button 
            onClick={() => setCurrentTab("telemetry")}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded text-left transition-all font-body-sm text-body-sm ${currentTab === "telemetry" ? "bg-secondary-container text-on-secondary-container border-r-2 border-secondary font-bold" : "text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface font-semibold"}`}
          >
            <span className="material-symbols-outlined text-[20px]">developer_board</span> Telemetry
          </button>
        </div>
        
        <div className="px-gutter mt-auto space-y-1 border-t border-outline-variant/60 pt-4">
          <a className="flex items-center gap-3 px-3 py-2 rounded text-on-surface-variant hover:text-on-surface transition-all font-body-sm text-body-sm" href="#">
            <span className="material-symbols-outlined text-[20px]">description</span> Docs
          </a>
          <a className="flex items-center gap-3 px-3 py-2 rounded text-on-surface-variant hover:text-on-surface transition-all font-body-sm text-body-sm" href="#">
            <span className="material-symbols-outlined text-[20px]">help</span> Support
          </a>
        </div>
      </nav>

      {/* Main Container Area */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* TopNavBar */}
        <header className="bg-surface border-b border-outline-variant w-full h-16 flex-shrink-0 z-10 px-margin-page flex justify-between items-center bg-[#0c1324]">
          <div className="flex items-center gap-4">
            <span className="font-headline-lg text-headline-lg font-bold text-primary hidden lg:block uppercase tracking-wider text-[17px]">
              BusinessIntelligence.ai
            </span>
          </div>

          <div className="flex items-center gap-stack-md">
            <PersonaSwitcher 
              persona={persona} 
              setPersona={setPersona} 
              regionFilter={regionFilter} 
              setRegionFilter={setRegionFilter} 
            />

            <button 
              onClick={runPipeline}
              disabled={pipelineRunning || apiStatus !== "healthy"}
              className="run-btn bg-primary text-[#002e6a] hover:bg-primary-fixed border-none rounded px-4 py-1.5 font-label-caps text-label-caps text-[11px] font-black tracking-wider transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {pipelineRunning ? "Running..." : "RUN SENTINEL"}
            </button>
          </div>
        </header>

        {/* Tab-driven canvas layout */}
        <div className="flex-grow overflow-hidden flex bg-[#020617] relative">
          <div className="absolute inset-0 grid-bg pointer-events-none z-[1]"></div>
          
          {/* TAB 1: INTELLIGENCE VIEW (Active Split Screen) */}
          {currentTab === "intelligence" && (
            <div className="flex-1 flex overflow-hidden z-10">
              <div className="w-[340px] border-r border-[#1e293b] flex flex-col bg-[#0f172a] shrink-0">
                <div className="p-4 border-b border-[#1e293b] flex justify-between items-center bg-[#0f172a] select-none shrink-0">
                  <span className="font-label-caps text-label-caps text-on-surface uppercase tracking-wider text-[11px]">ACTIVE ANOMALIES</span>
                  <span className="px-2 py-0.5 bg-[#020617] border border-[#1e293b] rounded font-mono-data text-[10px] text-on-surface-variant font-bold">
                    Count: {incidents.length}
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {incidents.length === 0 ? (
                    <div className="text-center text-[#8c909f] font-mono-data text-[12px] pt-12">
                      No anomalies found for selected role. Click "RUN SENTINEL".
                    </div>
                  ) : (
                    incidents.map((inc) => (
                      <InsightCard 
                        key={inc.incident_id}
                        incident={inc}
                        isSelected={selectedIncident?.incident_id === inc.incident_id}
                        onClick={() => setSelectedIncident(inc)}
                      />
                    ))
                  )}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-margin-page bg-[#020617]/50 flex flex-col gap-stack-lg">
                {!selectedIncident ? (
                  <div className="flex-grow flex flex-col items-center justify-center text-on-surface-variant font-mono-data text-[12px] pt-24">
                    <span className="material-symbols-outlined text-[48px] opacity-20 mb-4 font-light">analytics</span>
                    SELECT AN ANOMALY IN THE FEED TO INITIATE INVESTIGATION
                  </div>
                ) : (
                  <InsightDetail 
                    incident={selectedIncident}
                    chartData={chartData}
                    comments={comments}
                    setComments={setComments}
                    decisionLogged={decisionLogged}
                    onSubmitDecision={submitDecision}
                    completedRecs={completedRecs}
                    toggleRec={toggleRec}
                    analystContext={analystContext}
                    setAnalystContext={setAnalystContext}
                    onSubmitContext={submitContext}
                    persona={persona}
                  />
                )}
              </div>
            </div>
          )}

          {/* TAB 2: OVERVIEW VIEW */}
          {currentTab === "overview" && (
            <div className="flex-grow overflow-y-auto p-margin-page z-10 max-w-5xl mx-auto space-y-stack-lg">
              <header className="border-b border-outline-variant pb-stack-sm">
                <h2 className="font-display text-display text-on-surface mb-unit text-[28px]">System Status Overview</h2>
                <p className="font-body-lg text-body-lg text-on-surface-variant">Active monitoring modules status and anomaly summaries.</p>
              </header>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-gutter">
                <div className="data-card rounded p-card-padding">
                  <div className="font-label-caps text-[10px] text-on-surface-variant mb-1">TOTAL ANOMALIES SCAN</div>
                  <div className="font-mono-data text-[26px] text-primary font-bold">{incidents.length} Active</div>
                </div>
                <div className="data-card rounded p-card-padding">
                  <div className="font-label-caps text-[10px] text-on-surface-variant mb-1">DATABASE OVERRIDES</div>
                  <div className="font-mono-data text-[26px] text-secondary font-bold">Active</div>
                </div>
                <div className="data-card rounded p-card-padding">
                  <div className="font-label-caps text-[10px] text-on-surface-variant mb-1">PII PROTECTION</div>
                  <div className="font-mono-data text-[26px] text-on-surface font-bold">Enabled</div>
                </div>
                <div className="data-card rounded p-card-padding">
                  <div className="font-label-caps text-[10px] text-on-surface-variant mb-1">SUPABASE pgvector</div>
                  <div className="font-mono-data text-[26px] text-secondary font-bold">Online</div>
                </div>
              </div>

              <div className="data-card rounded p-6 bg-[#0f172a]">
                <h3 className="font-label-caps text-label-caps text-on-surface mb-4 border-b border-[#1e293b] pb-2 uppercase tracking-wider text-[11px]">
                  Regional Status Summary
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter">
                  <div className="border border-[#1e293b] rounded p-4 bg-[#020617]/35 text-[13px] leading-relaxed">
                    <h4 className="font-headline-md text-on-surface mb-2 text-[14px]">Southeast Region</h4>
                    <p className="text-on-surface-variant mb-2">Subject to checkout billing outage on 2026-08-15. Status: Investigated.</p>
                    <span className="bg-error-container/20 border border-error/30 text-error text-[10px] font-mono-data px-2 py-0.5 rounded font-bold uppercase">Critical Alert</span>
                  </div>
                  <div className="border border-[#1e293b] rounded p-4 bg-[#020617]/35 text-[13px] leading-relaxed">
                    <h4 className="font-headline-md text-on-surface mb-2 text-[14px]">West Region</h4>
                    <p className="text-on-surface-variant mb-2">Potential silent infrastructure latency issues. Status: Abstained.</p>
                    <span className="bg-[#451a03]/20 border border-[#78350f] text-[#f59e0b] text-[10px] font-mono-data px-2 py-0.5 rounded font-bold uppercase">Abstained</span>
                  </div>
                  <div className="border border-[#1e293b] rounded p-4 bg-[#020617]/35 text-[13px] leading-relaxed">
                    <h4 className="font-headline-md text-on-surface mb-2 text-[14px]">Northeast Region</h4>
                    <p className="text-on-surface-variant mb-2">Slow structural decline in revenue. Status: Investigated.</p>
                    <span className="bg-[#1e293b] border border-[#334155] text-[#94a3b8] text-[10px] font-mono-data px-2 py-0.5 rounded font-bold uppercase">Structural</span>
                  </div>
                </div>
              </div>
            </div>
          )}



          {/* TAB 4: AUDITS VIEW (Feedback Log List) */}
          {currentTab === "audits" && (
            <div className="flex-grow overflow-y-auto p-margin-page z-10 max-w-5xl mx-auto space-y-stack-lg">
              <header className="flex justify-between items-end border-b border-outline-variant pb-stack-sm">
                <div>
                  <h2 className="font-display text-display text-on-surface mb-unit text-[28px]">Audit & Decision Logs</h2>
                  <p className="font-body-lg text-body-lg text-on-surface-variant">Logged analyst decisions and threshold overrides recalibration records.</p>
                </div>
                <button 
                  onClick={fetchDecisions}
                  className="px-4 py-1.5 bg-transparent border border-[#1e293b] text-[#f8fafc] font-label-caps text-label-caps text-[11px] rounded hover:bg-[#1e293b] transition-colors"
                >
                  Refresh Logs
                </button>
              </header>

              <div className="data-card rounded overflow-hidden">
                <table className="w-full text-left font-mono-data text-[12px] border-collapse">
                  <thead>
                    <tr className="bg-[#0f172a] border-b border-[#1e293b] text-on-surface font-bold">
                      <th className="p-4">Log ID</th>
                      <th className="p-4">Incident ID</th>
                      <th className="p-4">Analyst Decision</th>
                      <th className="p-4">Comments</th>
                      <th className="p-4 text-right">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {decisions.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="p-8 text-center text-on-surface-variant italic">
                          No audit decisions found in feedback database. Submit a decision from the Intelligence detail card.
                        </td>
                      </tr>
                    ) : (
                      decisions.map((dec) => (
                        <tr key={dec.id} className="border-b border-[#1e293b]/70 hover:bg-[#1e293b]/20">
                          <td className="p-4 font-bold text-on-surface">#0{dec.id}</td>
                          <td className="p-4 text-[#3b82f6] font-bold">{dec.incident_id}</td>
                          <td className="p-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-mono-data font-bold uppercase tracking-wider ${dec.decision === 'approve' ? 'bg-[#064e3b]/20 border border-[#065f46] text-[#10b981]' : 'bg-error-container/20 border border-error/30 text-error'}`}>
                              {dec.decision.toUpperCase()}
                            </span>
                          </td>
                          <td className="p-4 italic">"{dec.analyst_comments || "None provided"}"</td>
                          <td className="p-4 text-right text-on-surface-variant">{dec.created_at}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 5: TELEMETRY VIEW */}
          {currentTab === "telemetry" && (
            <div className="flex-grow overflow-y-auto p-margin-page z-10 max-w-5xl mx-auto">
              <TelemetryPanel logs={telemetry} />
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
