import { useMemo, useState, type ReactNode } from 'react'

type IconName =
  | 'activity' | 'bell' | 'book' | 'bot' | 'branch' | 'check' | 'chevron'
  | 'clock' | 'code' | 'copy' | 'database' | 'file' | 'folder' | 'github'
  | 'grid' | 'help' | 'lab' | 'menu' | 'play' | 'repo' | 'rocket' | 'search'
  | 'settings' | 'shield' | 'sparkles' | 'terminal' | 'x' | 'zap'

const iconPaths: Record<IconName, ReactNode> = {
  activity: <><path d="M3 12h4l2.2-6 4.1 12 2.2-6H21" /></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
  book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4H6.5A2.5 2.5 0 0 0 4 6.5z" /><path d="M4 6.5v13" /></>,
  bot: <><rect x="4" y="6" width="16" height="13" rx="3" /><path d="M9 11h.01M15 11h.01M9 15h6M12 6V3M10 3h4" /></>,
  branch: <><circle cx="6" cy="5" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="6" cy="19" r="2" /><path d="M6 7v10M8 10c5 0 3-4 8-4" /></>,
  check: <><path d="m5 12 4 4L19 6" /></>,
  chevron: <><path d="m9 18 6-6-6-6" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  code: <><path d="m8 9-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" /></>,
  copy: <><rect x="8" y="8" width="11" height="11" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>,
  file: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h4" /></>,
  folder: <><path d="M3 6h7l2 2h9v11H3z" /></>,
  github: <><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3.3-.4 6.8-1.6 6.8-7.4a5.8 5.8 0 0 0-1.5-4 5.4 5.4 0 0 0-.2-4S17.9-1.4 15 1.1a13.4 13.4 0 0 0-7 0C5.1-1.4 3.9-.9 3.9-.9a5.4 5.4 0 0 0-.2 4 5.8 5.8 0 0 0-1.5 4c0 5.8 3.5 7 6.8 7.4A4.8 4.8 0 0 0 8 18v4" /><path d="M8 19c-3 .9-3-1.5-4-2" /></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.8 9a2.4 2.4 0 1 1 3.7 2c-1.2.8-1.5 1.2-1.5 2M12 17h.01" /></>,
  lab: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3" /><path d="M7 15h10" /></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
  play: <><path d="m9 7 8 5-8 5z" /></>,
  repo: <><path d="M5 3h12a2 2 0 0 1 2 2v16H7a2 2 0 0 1-2-2z" /><path d="M9 7h6M5 17h14" /></>,
  rocket: <><path d="M14 5c3.5-3.5 6-2 6-2s1.5 2.5-2 6l-5 5-4-4z" /><path d="m9 10-4 1-2 3 6 1M13 14l1 6-3 2-1-5M6 18l-2 2" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
  shield: <><path d="M12 3 4 6v5c0 5 3.4 8.7 8 10 4.6-1.3 8-5 8-10V6z" /><path d="m9 12 2 2 4-5" /></>,
  sparkles: <><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2zM19 14l.7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7zM5 14l.7 2.3L8 17l-2.3.7L5 20l-.7-2.3L2 17l2.3-.7z" /></>,
  terminal: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="m7 9 3 3-3 3M13 15h4" /></>,
  x: <><path d="m6 6 12 12M18 6 6 18" /></>,
  zap: <><path d="M13 2 4 14h7l-1 8 9-12h-7z" /></>,
}

function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{iconPaths[name]}</svg>
}

function Button({ children, variant = 'default', icon, onClick, className = '' }: { children: ReactNode; variant?: 'default' | 'primary' | 'ghost' | 'danger'; icon?: IconName; onClick?: () => void; className?: string }) {
  return <button className={`button ${variant} ${className}`} onClick={onClick}>{icon && <Icon name={icon} size={15} />}{children}</button>
}

function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}><span className="badge-dot" />{children}</span>
}

const navGroups = [
  { label: 'CORE', items: [
    ['Overview', 'grid'], ['Repositories', 'repo'], ['Pull Requests', 'branch'], ['Live Playground', 'lab'],
  ]},
  { label: 'INSIGHTS', items: [
    ['Quality Analytics', 'activity'], ['LLM Cost & Tokens', 'database'], ['Benchmark & Eval', 'book'],
  ]},
  { label: 'ADMIN', items: [
    ['Rule Config', 'code'], ['Webhook Logs', 'terminal'], ['Settings', 'settings'],
  ]},
] as const

const recentPrs = [
  { id: '#101', title: 'feat(auth/payment): add database query and discount calculator', repo: 'vku-se/ecommerce-api', author: 'student_dev', status: 'Done', findings: [2, 4, 7], time: '2m ago' },
  { id: '#98', title: 'fix: prevent race condition in order processing', repo: 'vku-se/ecommerce-api', author: 'linhnguyen', status: 'Processing', findings: [0, 1, 3], time: '8m ago' },
  { id: '#342', title: 'refactor: migrate dashboard queries to server actions', repo: 'vku-se/web-portal', author: 'minhtran', status: 'Done', findings: [1, 2, 8], time: '22m ago' },
  { id: '#77', title: 'test: add integration suite for token refresh', repo: 'vku-se/auth-service', author: 'hoanganh', status: 'Failed', findings: [0, 0, 0], time: '1h ago' },
  { id: '#339', title: 'perf: cache organization permissions', repo: 'vku-se/web-portal', author: 'thao_le', status: 'Done', findings: [0, 1, 5], time: '3h ago' },
]

function Sidebar({ active, setActive, open, close }: { active: string; setActive: (v: string) => void; open: boolean; close: () => void }) {
  return <aside className={`sidebar ${open ? 'open' : ''}`}>
    <div className="brand">
      <div className="brand-mark"><Icon name="bot" size={20} /></div>
      <div><strong>ReviewBot</strong><span>VKU SE Platform</span></div>
      <button className="mobile-close" onClick={close}><Icon name="x" /></button>
    </div>
    <nav>
      {navGroups.map(group => <div className="nav-group" key={group.label}>
        <div className="nav-label">{group.label}</div>
        {group.items.map(([label, icon]) => <button key={label} className={`nav-item ${active === label ? 'active' : ''}`} onClick={() => { setActive(label); close() }}>
          <Icon name={icon as IconName} /><span>{label}</span>{label === 'Pull Requests' && <em>12</em>}
        </button>)}
      </div>)}
    </nav>
    <div className="sidebar-footer">
      <div className="org-card">
        <div className="avatar">VS</div>
        <div className="org-text"><strong>vku-se</strong><span><i /> GitHub synced</span></div>
        <Icon name="chevron" size={14} />
      </div>
    </div>
  </aside>
}

function Topbar({ active, menu }: { active: string; menu: () => void }) {
  return <header className="topbar">
    <button className="menu-button" onClick={menu}><Icon name="menu" /></button>
    <div className="crumb"><span>Workspace</span><Icon name="chevron" size={13} /><strong>{active}</strong></div>
    <div className="top-actions">
      <div className="global-search"><Icon name="search" size={15} /><span>Search anything...</span><kbd>⌘ K</kbd></div>
      <Badge tone="online">FastAPI & Redis Online</Badge>
      <button className="icon-button"><Icon name="help" /></button>
      <button className="icon-button notify"><Icon name="bell" /><span>3</span></button>
    </div>
  </header>
}

function PageHeading({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="page-heading">
    <div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h1>{title}</h1><p>{description}</p></div>
    {actions && <div className="heading-actions">{actions}</div>}
  </div>
}

function MetricCard({ label, value, note, icon, trend, tone = '' }: { label: string; value: string; note: string; icon: IconName; trend?: string; tone?: string }) {
  return <div className="metric-card">
    <div className="metric-top"><span className={`metric-icon ${tone}`}><Icon name={icon} /></span>{trend && <Badge tone="success">{trend}</Badge>}</div>
    <span className="metric-label">{label}</span><strong className="metric-value">{value}</strong><span className="metric-note">{note}</span>
  </div>
}

function SeverityDonut() {
  return <div className="chart-card">
    <div className="card-heading"><div><h2>Severity breakdown</h2><p>All findings · Last 30 days</p></div><button className="more">•••</button></div>
    <div className="donut-layout">
      <div className="donut"><div><strong>3,891</strong><span>findings</span></div></div>
      <div className="legend">
        {[['Critical','142','critical'],['Major','820','major'],['Minor','1,674','minor'],['Info','1,255','info']].map(([l,v,t]) => <div key={l}><span><i className={t} />{l}</span><strong>{v}</strong></div>)}
      </div>
    </div>
  </div>
}

function DefectChart() {
  const weeks = [[32,26,18,12],[38,22,24,10],[26,34,20,16],[46,28,22,9],[40,38,26,12],[52,34,25,14],[58,42,32,16]]
  return <div className="chart-card wide">
    <div className="card-heading"><div><h2>Defect categories</h2><p>Findings by week</p></div><div className="tiny-legend"><span><i className="security" />Security</span><span><i className="bugs" />Bugs</span><span><i className="performance" />Performance</span></div></div>
    <div className="bars">
      {weeks.map((w, i) => <div className="bar-column" key={i}><div className="bar-stack">{w.map((h,j)=><i key={j} className={`bar b${j}`} style={{height:h}} />)}</div><span>W{i+1}</span></div>)}
    </div>
  </div>
}

function StatusBadge({ status }: { status: string }) {
  return <Badge tone={status === 'Done' ? 'success' : status === 'Processing' || status === 'Running' ? 'running' : status === 'Failed' ? 'critical' : 'neutral'}>{status}</Badge>
}

function PullRequestTable({ inspect }: { inspect: () => void }) {
  return <div className="table-card">
    <div className="card-heading table-heading"><div><h2>Recent pull requests</h2><p>Live reviews across connected repositories</p></div><div className="table-tools"><div className="mini-search"><Icon name="search" size={14} />Search PRs</div><Button variant="ghost">View all</Button></div></div>
    <div className="table-scroll"><table><thead><tr><th>Pull request</th><th>Repository</th><th>Status</th><th>Findings</th><th>Updated</th><th /></tr></thead>
      <tbody>{recentPrs.map((pr, i) => <tr key={pr.id}><td><div className="pr-title"><strong>{pr.id} {pr.title}</strong><span>by @{pr.author}</span></div></td><td><span className="repo-cell"><Icon name="repo" size={14} />{pr.repo}</span></td><td><StatusBadge status={pr.status} /></td><td><div className="finding-counts"><span className="critical">{pr.findings[0]}</span><span className="major">{pr.findings[1]}</span><span className="minor">{pr.findings[2]}</span></div></td><td className="muted">{pr.time}</td><td>{i === 0 ? <Button variant="ghost" onClick={inspect}>Inspect</Button> : <button className="row-menu">•••</button>}</td></tr>)}</tbody>
    </table></div>
    <div className="table-footer"><span>Showing 5 of 1,248 pull requests</span><div><Button variant="ghost">Previous</Button><Button variant="ghost">Next</Button></div></div>
  </div>
}

function Overview({ navigate }: { navigate: (v: string) => void }) {
  return <>
    <PageHeading eyebrow="COMMAND CENTER" title="Good morning, Vũ." description="ReviewBot analyzed 48 pull requests and found 126 issues this week." actions={<><Button variant="ghost" icon="book">Export report</Button><Button variant="primary" icon="branch" onClick={()=>navigate('Pull Requests')}>Review a PR</Button></>} />
    <div className="notice"><span className="notice-icon"><Icon name="sparkles" /></span><div><strong>ReviewBot is learning from your team</strong><p>87% of this week’s suggestions were marked helpful. Confidence calibration improved by 4.2%.</p></div><button>View model insights <Icon name="chevron" size={13} /></button></div>
    <div className="metrics-grid">
      <MetricCard label="TOTAL PRs ANALYZED" value="1,248" note="48 reviewed this week" icon="branch" trend="+12.4%" />
      <MetricCard label="VULNERABILITIES & BUGS" value="3,891" note="142 critical · 820 major" icon="shield" trend="+8.1%" tone="rose" />
      <MetricCard label="ACCUMULATED LLM COST" value="$14.82" note="1.9M tokens consumed" icon="database" trend="-3.2%" tone="indigo" />
      <MetricCard label="AVG. PROCESSING LATENCY" value="780 ms" note="p95 · 1.2 seconds" icon="zap" trend="-18.6%" tone="sky" />
    </div>
    <div className="charts-grid"><SeverityDonut /><DefectChart /></div>
    <PullRequestTable inspect={()=>navigate('Pull Requests')} />
  </>
}

const repos = [
  ['ecommerce-api','Core commerce APIs and order processing','Python','main','2m ago',true,12],
  ['web-portal','Customer and admin dashboard','TypeScript','production','14m ago',true,8],
  ['auth-service','OAuth, sessions and access policies','Go','main','1h ago',true,3],
  ['mobile-app','Cross-platform student marketplace','TypeScript','develop','3h ago',false,0],
  ['ml-experiments','Evaluation and prompt research','Python','main','1d ago',true,5],
  ['infrastructure','Terraform and deployment manifests','HCL','main','2d ago',false,0],
]

function Repositories() {
  const [wizard, setWizard] = useState(false)
  return <>
    <PageHeading eyebrow="WORKSPACE" title="Repositories" description="Manage connected codebases, branches, and automatic review policies." actions={<Button variant="primary" icon="github" onClick={()=>setWizard(true)}>Connect repository</Button>} />
    <div className="filter-row"><div className="mini-search large"><Icon name="search" />Search repositories...</div><Button variant="ghost">All languages <Icon name="chevron" size={12}/></Button><Button variant="ghost">Last activity <Icon name="chevron" size={12}/></Button></div>
    <div className="repo-grid">{repos.map(([name, desc, lang, branch, time, enabled, count]) => <div className="repo-card" key={String(name)}>
      <div className="repo-card-top"><span className="repo-icon"><Icon name="repo" /></span><label className="switch"><input type="checkbox" defaultChecked={Boolean(enabled)} /><span /></label></div>
      <h2>{String(name)}</h2><p>{String(desc)}</p>
      <div className="repo-meta"><Badge tone="neutral">{String(lang)}</Badge><span><Icon name="branch" size={13}/>{String(branch)}</span></div>
      <div className="repo-card-foot"><span><i className={enabled ? 'live' : ''}/>{enabled ? `${count} reviews this month` : 'Auto-review off'}</span><span>{String(time)}</span></div>
    </div>)}</div>
    {wizard && <Onboarding close={()=>setWizard(false)} />}
  </>
}

function Onboarding({ close }: { close: () => void }) {
  const [step, setStep] = useState(2)
  return <div className="modal-backdrop"><div className="wizard-modal">
    <div className="modal-header"><div><span className="eyebrow">GITHUB APP SETUP</span><h2>Connect your repositories</h2></div><button className="icon-button" onClick={close}><Icon name="x"/></button></div>
    <div className="steps">{['Connect GitHub','Select repositories','Review policy'].map((s,i)=><div className={step >= i+1 ? 'complete' : ''} key={s}><span>{step > i+1 ? <Icon name="check" size={13}/> : i+1}</span><strong>{s}</strong>{i<2&&<i/>}</div>)}</div>
    <div className="wizard-body"><div className="wizard-title"><h3>Select repositories</h3><p>Choose which repositories ReviewBot can access. You can change this later.</p></div>
      <div className="mini-search large"><Icon name="search"/>Search your organization...</div>
      <div className="select-list">{['ecommerce-api','web-portal','auth-service','mobile-app'].map((r,i)=><label key={r}><input type="checkbox" defaultChecked={i<2}/><span className="repo-icon small"><Icon name="repo" size={14}/></span><strong>vku-se / {r}</strong><Badge tone={i%2?'minor':'neutral'}>{i%2?'TypeScript':'Python'}</Badge></label>)}</div>
      <div className="permissions"><strong>Permission scopes</strong><div>{[['book','Read code','Analyze diffs'],['branch','Write PRs','Post reviews'],['check','Read checks','Track status']].map(([ic,t,d])=><span key={t}><Icon name={ic as IconName}/><i><b>{t}</b>{d}</i></span>)}</div></div>
    </div>
    <div className="modal-footer"><span>2 repositories selected</span><div><Button variant="ghost" onClick={close}>Cancel</Button><Button variant="primary" onClick={()=>step===3?close():setStep(3)}>{step===3?'Finish setup':'Continue'}<Icon name="chevron" size={13}/></Button></div></div>
  </div></div>
}

function PullRequests() {
  const [audit, setAudit] = useState(false)
  const [summary, setSummary] = useState(true)
  return <div className="pr-workspace">
    <div className="pr-context"><div><span className="eyebrow">PULL REQUEST #101</span><h1>feat(auth/payment): add database query and discount calculator</h1><div className="pr-sub"><span className="avatar tiny">SD</span><strong>@student_dev</strong><span>opened 18 minutes ago</span><Badge tone="success">Review complete</Badge></div></div><div className="pr-actions"><Button variant="ghost" icon="activity" onClick={()=>setAudit(true)}>View audit trace</Button><Button variant="primary" icon="github">Open in GitHub</Button></div></div>
    <div className="branch-strip"><span><Icon name="branch" size={14}/><code>main</code><span>←</span><code>feature/auth</code></span><span><Icon name="code" size={14}/>9f8e7d6</span><span><b>+124</b> <i>−38</i></span><span>5 files changed</span></div>
    <div className="review-grid">
      <aside className="file-tree"><div className="tree-title"><strong>CHANGED FILES</strong><span>5</span></div>
        <div className="tree-folder"><Icon name="chevron" size={12}/><Icon name="folder" size={14}/>src <Badge tone="critical">3</Badge></div>
        <button className="tree-file active"><Icon name="file" size={14}/><span>database.py<small>+28 −4</small></span><Badge tone="critical">2</Badge></button>
        <button className="tree-file"><Icon name="file" size={14}/><span>discount.py<small>+42 −8</small></span><Badge tone="major">1</Badge></button>
        <div className="tree-folder"><Icon name="chevron" size={12}/><Icon name="folder" size={14}/>tests</div>
        <button className="tree-file"><Icon name="file" size={14}/><span>test_discount.py<small>+38 −0</small></span></button>
        <button className="tree-file"><Icon name="file" size={14}/><span>config.py<small>+8 −2</small></span></button>
        <button className="tree-file"><Icon name="file" size={14}/><span>README.md<small>+8 −24</small></span></button>
        <div className="tree-stats"><strong>Review health</strong><div><span style={{width:'72%'}} /></div><p><b>3</b> issues in <b>2</b> files</p></div>
      </aside>
      <section className="review-main">
        <div className={`ai-summary ${summary?'':'collapsed'}`}><button className="summary-head" onClick={()=>setSummary(!summary)}><span className="ai-icon"><Icon name="sparkles"/></span><div><strong>AI pull request summary</strong><span>Generated by ReviewBot · Claude 3.5 Sonnet</span></div><Icon name="chevron"/></button>
          {summary&&<div className="summary-body"><div><span className="summary-label">GOAL</span><p>Add payment discount calculation and retrieve user records during checkout.</p><span className="summary-label">KEY CHANGES</span><ul><li>Introduces dynamic user lookup in <code>database.py</code></li><li>Adds tier-based discount calculation with three new test cases</li></ul></div><div className="risk-box"><span><Icon name="shield"/>POTENTIAL RISKS</span><p>User input is interpolated directly into a SQL query. Discount logic may divide by zero when quantity is empty.</p><strong>Recommended tests</strong><p>SQL injection payload · Empty cart · Concurrent checkout</p></div></div>}
        </div>
        <div className="diff-card">
          <div className="diff-header"><div><Icon name="file"/><strong>src/database.py</strong><span>+28 −4</span></div><div><Button variant="ghost">Unified</Button><button className="icon-button"><Icon name="settings"/></button></div></div>
          <div className="hunk">@@ -12,8 +12,16 @@ def get_user_by_email(email: str):</div>
          <CodeLine n={12} kind="normal" text="    connection = get_db_connection()" />
          <CodeLine n={13} kind="normal" text="    cursor = connection.cursor()" />
          <CodeLine n={14} kind="removed" text={'-   query = "SELECT * FROM users WHERE email = ?"'}/>
          <CodeLine n={15} kind="removed" text="-   cursor.execute(query, (email,))" />
          <CodeLine n={16} kind="added" text="+   # Build query from the submitted email" />
          <CodeLine n={17} kind="added" text={'+   query = f"SELECT * FROM users WHERE email = \'{email}\'"'}/>
          <CodeLine n={18} kind="added critical-line" text="+   cursor.execute(query)" />
          <InlineComment />
          <CodeLine n={19} kind="added" text="+   result = cursor.fetchone()" />
          <CodeLine n={20} kind="normal" text="    cursor.close()" />
          <CodeLine n={21} kind="normal" text="    return result" />
        </div>
      </section>
    </div>
    {audit&&<AuditModal close={()=>setAudit(false)}/>}
  </div>
}

function CodeLine({ n, text, kind }: { n: number; text: string; kind: string }) {
  return <div className={`code-line ${kind}`}><span className="old-num">{kind==='added'?'':n}</span><span className="new-num">{n}</span><code>{text}</code>{kind.includes('critical')&&<i/>}</div>
}

function InlineComment() {
  const [helpful, setHelpful] = useState(false)
  return <div className="inline-comment">
    <div className="comment-rail"><span><Icon name="bot" size={15}/></span></div>
    <div className="comment-card"><div className="comment-head"><div><Badge tone="critical">CRITICAL</Badge><Badge tone="neutral">SECURITY</Badge><span>Confidence: <strong>98%</strong></span></div><button className="more">•••</button></div>
      <h3>SQL Injection through unsanitized user input</h3>
      <p><strong>VI:</strong> Biến <code>email</code> được nối trực tiếp vào câu truy vấn SQL. Kẻ tấn công có thể chèn payload để đọc hoặc thay đổi dữ liệu.</p>
      <p><strong>EN:</strong> User-controlled input is interpolated into the query without parameterization, allowing arbitrary SQL execution.</p>
      <div className="evidence"><span>EVIDENCE</span><code>query = f"SELECT * FROM users WHERE email = '{'{email}'}'"</code></div>
      <div className="suggestion"><div><span><Icon name="sparkles" size={14}/>SUGGESTED CHANGE</span><Badge tone="success">Safe fix</Badge></div><pre><em>query = "SELECT * FROM users WHERE email = ?"</em>{'\n'}cursor.execute(query, (email,))</pre><div className="suggest-actions"><span>Parameterized query · CWE-89</span><div><Button variant="ghost" icon="copy">Copy</Button><Button variant="primary" icon="github">Apply to GitHub</Button></div></div></div>
      <div className="reaction-bar"><span>Was this helpful?</span><button className={helpful?'selected':''} onClick={()=>setHelpful(true)}>Yes, helpful</button><button>False positive</button><div className="reply"><span>Reply to ReviewBot...</span><Icon name="chevron" size={13}/></div></div>
    </div>
  </div>
}

function AuditModal({ close }: { close: () => void }) {
  const steps = [
    ['Webhook received','HMAC SHA-256 verified','12 ms','check'],
    ['File filter','package-lock.json ignored · 5 files accepted','8 ms','file'],
    ['Secrets scrubber','1 AWS access key redacted','31 ms','shield'],
    ['LLM chunking','2 context-aware chunks · 8,420 tokens','44 ms','code'],
    ['AI inference','Claude 3.5 Sonnet · 3 findings','642 ms','sparkles'],
    ['Postprocessing','Deduplicated · Confidence calibrated','27 ms','settings'],
    ['GitHub review posted','Review ID #182901 · 3 comments','16 ms','github'],
  ]
  return <div className="modal-backdrop"><div className="audit-modal"><div className="modal-header"><div><span className="eyebrow">EXECUTION TRACE</span><h2>Review audit timeline</h2><p>Request rb_exec_01J8K4M9 · Completed in 780 ms</p></div><button className="icon-button" onClick={close}><Icon name="x"/></button></div>
    <div className="audit-summary"><Badge tone="success">Completed</Badge><span>Started 10:42:18.201</span><span>7 stages</span><span>12,884 tokens</span><strong>$0.0082</strong></div>
    <div className="timeline">{steps.map(([t,d,ms,ic],i)=><div className="timeline-step" key={t}><div className="timeline-mark"><span><Icon name={ic as IconName}/></span>{i<steps.length-1&&<i/>}</div><div><strong>{t}</strong><p>{d}</p>{t==='Secrets scrubber'&&<code>AKIA••••••••••••Q7K2</code>}</div><time>{ms}</time></div>)}</div>
    <div className="modal-footer"><span><Icon name="shield" size={14}/> Immutable audit record · Retained 90 days</span><Button variant="primary" onClick={close}>Done</Button></div>
  </div></div>
}

function Playground() {
  const [running, setRunning] = useState(false)
  return <>
    <PageHeading eyebrow="SANDBOX" title="Live Review Playground" description="Test prompts and review behavior without opening a pull request." actions={<Badge tone="neutral">No data is saved</Badge>} />
    <div className="playground">
      <section className="play-panel"><div className="panel-heading"><div><span className="step-number">1</span><div><h2>Test input</h2><p>Configure a diff and prompt</p></div></div><Button variant="ghost">Reset</Button></div>
        <label className="field-label">PRESET</label><div className="preset-row">{['SQLi & Secrets','Division by Zero','Memory Leak'].map((p,i)=><button className={i===0?'active':''} key={p}>{p}</button>)}</div>
        <div className="editor-head"><span><Icon name="code" size={14}/>sample.py</span><Badge tone="neutral">Python</Badge></div>
        <pre className="code-editor"><span className="ln">1</span><span className="add">+ def find_user(email):</span>{'\n'}<span className="ln">2</span><span className="add">+     db = connect()</span>{'\n'}<span className="ln">3</span><span className="add">+     query = f"SELECT * FROM users</span>{'\n'}<span className="ln">4</span><span className="add">+       WHERE email = '{'{email}'}'"</span>{'\n'}<span className="ln">5</span><span className="add">+     return db.execute(query)</span>{'\n'}<span className="ln">6</span><span>  </span></pre>
        <label className="field-label">CUSTOM REVIEW INSTRUCTIONS <span>OPTIONAL</span></label><div className="prompt-field">Focus on security and explain findings in Vietnamese.<span>58 / 500</span></div>
        <Button variant="primary" icon={running?'activity':'rocket'} className="run-button" onClick={()=>{setRunning(true);setTimeout(()=>setRunning(false),900)}}>{running?'Reviewing code...':'Run AI Review'}<kbd>⌘ ↵</kbd></Button>
      </section>
      <section className="play-panel result-panel"><div className="panel-heading"><div><span className="step-number purple">2</span><div><h2>Review preview</h2><p>Exact GitHub output</p></div></div><Badge tone={running?'running':'success'}>{running?'Running':'Generated in 1.2s'}</Badge></div>
        <div className="preview-summary"><div><span className="ai-icon"><Icon name="sparkles"/></span><div><strong>Review summary</strong><p>1 critical security issue found across 5 added lines.</p></div></div><div className="preview-stats"><span><b>1</b> Critical</span><span><b>98%</b> Confidence</span><span><b>682</b> Tokens</span></div></div>
        <div className="github-preview"><div className="gh-head"><Icon name="github"/><strong>reviewbot-ai</strong><Badge tone="neutral">bot</Badge><span>commented just now</span></div><div className="gh-body"><Badge tone="critical">CRITICAL · SECURITY</Badge><h3>SQL Injection through unsanitized input</h3><p>Tham số <code>email</code> được đưa trực tiếp vào SQL query. Hãy sử dụng parameterized query để ngăn chặn SQL injection.</p><div className="suggestion compact"><span>SUGGESTED CHANGE</span><pre>query = "SELECT * FROM users WHERE email = ?"{'\n'}db.execute(query, (email,))</pre></div></div></div>
        <div className="preview-foot"><span><Icon name="check"/>Preview matches GitHub markdown rendering</span><Button variant="ghost" icon="copy">Copy markdown</Button></div>
      </section>
    </div>
  </>
}

function Benchmark() {
  const cases = [
    ['sql_injection_01.py','2','2','0','0','94.8','92.1','78.4'],
    ['race_condition_03.go','3','2','1','1','87.2','89.6','71.9'],
    ['xss_react_07.tsx','1','1','0','0','96.1','94.8','82.3'],
    ['memory_leak_02.cpp','2','2','0','0','91.4','93.0','85.6'],
    ['logic_error_12.py','4','3','1','1','88.9','86.2','76.8'],
  ]
  return <>
    <PageHeading eyebrow="RESEARCH LAB · SE GRADUATION" title="Benchmark & Evaluation" description="Reproducible model evaluation against the curated ground-truth dataset." actions={<><Button variant="ghost" icon="book">Methodology</Button><Button variant="primary" icon="play">Run evaluation</Button></>} />
    <div className="research-banner"><div><Icon name="lab" size={22}/><div><strong>Experiment RB-EVAL-2025-06</strong><p>eval/dataset/v2 · 250 samples · 1,842 labeled defects</p></div></div><span>Last run Jun 18, 2025 at 14:32</span></div>
    <div className="metrics-grid research"><MetricCard label="PRECISION" value="92.4%" note="±1.8% at 95% CI" icon="check" trend="+2.1%" /><MetricCard label="RECALL" value="88.7%" note="1,634 / 1,842 detected" icon="search" trend="+1.4%" tone="sky"/><MetricCard label="F1-SCORE" value="90.5%" note="Harmonic mean" icon="activity" trend="+1.8%" tone="indigo"/><MetricCard label="COST / 100 LOC" value="$0.003" note="Claude 3.5 Sonnet" icon="database" trend="-8.2%" /></div>
    <div className="table-card benchmark-table"><div className="card-heading table-heading"><div><h2>Ground-truth dataset matrix</h2><p>Model comparison on labeled test cases</p></div><Badge tone="neutral"><Icon name="folder" size={13}/> eval/dataset/</Badge></div>
      <div className="table-scroll"><table><thead><tr><th>Test case</th><th>Expected</th><th>Detected</th><th>FP</th><th>FN</th><th>Claude 3.5</th><th>GPT-4o</th><th>Llama 3</th></tr></thead><tbody>{cases.map(row=><tr key={row[0]}>{row.map((v,i)=><td key={i} className={i>4?'score':''}>{i===0?<span className="file-cell"><Icon name="file" size={14}/>{v}</span>:i>4?<><span className="scorebar"><i style={{width:`${v}%`}}/></span><strong>{v}%</strong></>:v}</td>)}</tr>)}</tbody></table></div>
      <div className="table-footer"><span>5 of 250 test cases · Dataset commit <code>e8c42a1</code></span><div><Button variant="ghost">Export CSV</Button><Button variant="ghost">View labels</Button></div></div>
    </div>
  </>
}

function RuleConfig() {
  const [confidence, setConfidence] = useState(82)
  return <>
    <PageHeading eyebrow="ADMINISTRATION" title="Review policy" description="Configure organization-wide review behavior. Changes sync to .reviewbot.yml." actions={<><Button variant="ghost">Discard</Button><Button variant="primary" icon="check">Save changes</Button></>} />
    <div className="settings-layout"><section className="settings-card"><div className="card-heading"><div><h2>Review behavior</h2><p>Control language, sensitivity, and output volume</p></div><Icon name="settings"/></div>
      <div className="form-row"><div><strong>Response language</strong><p>Language used for summaries and comments</p></div><div className="segmented"><button className="active">Vietnamese</button><button>English</button><button>Bilingual</button></div></div>
      <div className="form-row slider-row"><div><strong>Minimum confidence</strong><p>Only post findings above this threshold</p></div><strong className="range-value">0.{confidence}</strong><input type="range" min="60" max="95" value={confidence} onChange={e=>setConfidence(+e.target.value)}/><div className="range-labels"><span>0.60 More findings</span><span>0.95 Fewer false positives</span></div></div>
      <div className="form-row"><div><strong>Maximum comments per review</strong><p>Overflow findings appear in the summary</p></div><div className="number-field"><button>−</button><strong>15</strong><button>+</button></div></div>
      <div className="form-row tags-row"><div><strong>Ignored file patterns</strong><p>Glob patterns excluded from AI review</p></div><div className="tag-input"><span>**/package-lock.json <b>×</b></span><span>**/*.min.js <b>×</b></span><span>dist/** <b>×</b></span><em>Add pattern...</em></div></div>
    </section>
    <aside className="yaml-card"><div className="yaml-head"><span><Icon name="code"/>.reviewbot.yml</span><Badge tone="success">Valid</Badge></div><pre><span>version:</span> 1{'\n'}<span>language:</span> vi{'\n'}<span>min_confidence:</span> 0.{confidence}{'\n'}<span>max_comments:</span> 15{'\n'}<span>ignore:</span>{'\n'}  - "**/package-lock.json"{'\n'}  - "**/*.min.js"{'\n'}  - "dist/**"{'\n'}<span>rules:</span>{'\n'}  security: critical{'\n'}  performance: major</pre><div><Icon name="github"/>Synced with default branch</div></aside></div>
  </>
}

function WebhookLogs() {
  const logs=[['d_01J8K4M9','pull_request.opened','202 Valid','184','10:42:18'],['d_01J8K2P1','pull_request.synchronize','202 Valid','96','10:38:02'],['d_01J8JZX7','check_suite.completed','202 Valid','42','10:21:44'],['d_01J8JWF4','pull_request.opened','401 Invalid','8','09:58:11'],['d_01J8JQ29','installation.created','202 Valid','128','09:32:05']]
  return <>
    <PageHeading eyebrow="OBSERVABILITY" title="Webhook deliveries" description="Inspect GitHub events, signature verification, retries, and dead letters." actions={<Button variant="ghost" icon="activity">Live tail</Button>} />
    <div className="log-stats"><span><i className="green"/><b>99.98%</b> delivery success</span><span><Icon name="clock"/><b>92 ms</b> median latency</span><span><i className="rose"/><b>1</b> dead letter</span><Badge tone="online">Listening</Badge></div>
    <div className="table-card"><div className="card-heading table-heading"><div><h2>Recent deliveries</h2><p>Retained for 30 days</p></div><div className="table-tools"><div className="mini-search"><Icon name="search"/>Search delivery ID...</div><Button variant="ghost">All events</Button></div></div>
      <div className="table-scroll"><table><thead><tr><th>Delivery ID</th><th>Event</th><th>HMAC SHA-256</th><th>Latency</th><th>Received</th><th /></tr></thead><tbody>{logs.map((l,i)=><tr key={l[0]}><td><code>{l[0]}</code></td><td><Badge tone="neutral">{l[1]}</Badge></td><td><Badge tone={l[2].includes('202')?'success':'critical'}>{l[2]}</Badge></td><td>{l[3]} ms</td><td className="muted">{l[4]}</td><td><Button variant="ghost">{i===3?'Retry':'Inspect'}<Icon name="chevron" size={12}/></Button></td></tr>)}</tbody></table></div>
    </div>
    <div className="payload-preview"><div><span><Icon name="code"/>Payload preview · d_01J8JWF4</span><Badge tone="critical">Signature mismatch</Badge></div><pre>{'{'}{'\n'}  <b>"action"</b>: "opened",{'\n'}  <b>"number"</b>: 77,{'\n'}  <b>"repository"</b>: {'{'} <b>"full_name"</b>: "vku-se/auth-service" {'}'},{'\n'}  <b>"sender"</b>: {'{'} <b>"login"</b>: "unknown-client" {'}'}{'\n'}{'}'}</pre></div>
  </>
}

function Analytics({ type }: { type: 'quality'|'cost'|'settings' }) {
  const content = type==='quality'
    ? ['Quality analytics','Track defect escape rate, review acceptance, and engineering quality trends.','94.2%','Suggestion acceptance','−32%','Defect escape rate','4.2h','Review time saved']
    : type==='cost'
    ? ['LLM Cost & Tokens','Monitor model usage, token efficiency, and cost allocation by repository.','$14.82','Total spend','1.9M','Tokens processed','$0.012','Cost per PR']
    : ['Workspace settings','Manage organization identity, integrations, retention, and access controls.','12','Active members','6','Repositories','90d','Audit retention']
  return <><PageHeading eyebrow={type==='settings'?'ADMINISTRATION':'INSIGHTS'} title={content[0]} description={content[1]} actions={<Button variant="primary" icon={type==='settings'?'settings':'book'}>{type==='settings'?'Manage access':'Export report'}</Button>} />
    <div className="metrics-grid three">{[[content[2],content[3]], [content[4],content[5]], [content[6],content[7]]].map(([v,l],i)=><MetricCard key={l} label={l.toUpperCase()} value={v} note="Across the last 30 days" icon={i===0?'activity':i===1?'database':'clock'} trend={i===1?'+4.8%':'Healthy'} tone={i===1?'indigo':'sky'}/>)}</div>
    <div className="empty-chart"><div className="card-heading"><div><h2>{type==='cost'?'Daily token consumption':type==='settings'?'Workspace configuration':'Quality score trend'}</h2><p>Last 30 days · All repositories</p></div><Badge tone="success">Live data</Badge></div><div className="line-chart"><svg viewBox="0 0 800 220" preserveAspectRatio="none"><path className="area" d="M0 190 C80 150 90 170 160 130 S250 155 320 100 S420 130 480 75 S570 105 640 50 S730 65 800 22 L800 220 L0 220Z"/><path className="line" d="M0 190 C80 150 90 170 160 130 S250 155 320 100 S420 130 480 75 S570 105 640 50 S730 65 800 22"/></svg></div></div>
  </>
}

function App() {
  const [active, setActive] = useState('Overview')
  const [menuOpen, setMenuOpen] = useState(false)
  const view = useMemo(() => {
    if(active==='Overview') return <Overview navigate={setActive}/>
    if(active==='Repositories') return <Repositories/>
    if(active==='Pull Requests') return <PullRequests/>
    if(active==='Live Playground') return <Playground/>
    if(active==='Benchmark & Eval') return <Benchmark/>
    if(active==='Rule Config') return <RuleConfig/>
    if(active==='Webhook Logs') return <WebhookLogs/>
    if(active==='Quality Analytics') return <Analytics type="quality"/>
    if(active==='LLM Cost & Tokens') return <Analytics type="cost"/>
    return <Analytics type="settings"/>
  }, [active])
  return <div className="app-shell">
    <Sidebar active={active} setActive={setActive} open={menuOpen} close={()=>setMenuOpen(false)}/>
    {menuOpen&&<button className="sidebar-scrim" onClick={()=>setMenuOpen(false)}/>}
    <div className="app-main"><Topbar active={active} menu={()=>setMenuOpen(true)}/><main className={active==='Pull Requests'?'flush':''}>{view}</main></div>
  </div>
}

export default App
