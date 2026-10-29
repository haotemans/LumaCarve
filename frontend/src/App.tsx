import { useEffect, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Bell, Command, Database, HardDrive, History,
  House, Images, Layers3, Menu, Puzzle, Search, Settings2, Sparkles,
  WandSparkles, X,
} from 'lucide-react';
import { initialDatasets, initialOutputs } from './data/demo';
import type { Dataset, Notice, OutputImage, Page } from './types';
import {
  DashboardPage, HistoryPage, ModelsPage, PluginsPage, SettingsPage,
} from './pages/StudioPages';
import {
  TrainingPage,
} from './pages/OpticalStudio';
import ImageStudioPage from './pages/ImageStudioPage';
import GalleryPage from './pages/GalleryPage';
import DatasetsPage from './pages/DatasetsPage';

type NavEntry = { id: Page; label: string; icon: LucideIcon; subtitle?: string };

const primary: NavEntry[] = [
  { id: 'generate', label: '图像工作室', subtitle: 'CREATE & EDIT', icon: WandSparkles },
  { id: 'training', label: 'LoRA 训练', subtitle: 'CARVE', icon: Layers3 },
];

const secondary: NavEntry[] = [
  { id: 'dashboard', label: '监控仪表盘', icon: House },
  { id: 'gallery', label: '出图管理', icon: Images },
  { id: 'datasets', label: '数据集管理', icon: Database },
  { id: 'models', label: '模型管理', icon: HardDrive },
  { id: 'plugins', label: '插件管理', icon: Puzzle },
  { id: 'history', label: '任务历史', icon: History },
  { id: 'settings', label: '设置', icon: Settings2 },
];

function pageFromHash(): Page {
  const name = window.location.hash.replace(/^#\/?/, '') as Page;
  if (name === 'flow') return 'generate';
  return [...primary, ...secondary].some(item => item.id === name) ? name : 'generate';
}

function PrismLogo() {
  return (
    <svg viewBox="0 0 32 32" width="25" height="25" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="lc-prism" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#6366f1" /><stop offset=".55" stopColor="#38bdf8" /><stop offset="1" stopColor="#ac89fb" />
        </linearGradient>
      </defs>
      <path d="m16 2 13 7.3v13.4L16 30 3 22.7V9.3L16 2Z" stroke="url(#lc-prism)" strokeWidth="2.2" strokeLinejoin="round"/>
      <path d="m3 9.3 13 7.3 13-7.3M16 16.6V30" stroke="#8090c7" strokeWidth="1.5" strokeLinejoin="round"/>
      <circle cx="16" cy="16.5" r="3" fill="#6366f1" stroke="white" strokeWidth="1.1"/>
    </svg>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [outputs, setOutputs] = useState<OutputImage[]>(initialOutputs);
  const [datasets, setDatasets] = useState<Dataset[]>(initialDatasets);
  const [focusedTask, setFocusedTask] = useState('');
  const [search, setSearch] = useState('');
  const [notice, setNotice] = useState<Notice | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const common = { notify };

  function notify(text: string, tone: Notice['tone'] = 'info') {
    setNotice({ id: Date.now(), text, tone });
  }

  useEffect(() => {
    function sync() { setPage(pageFromHash()); }
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);

  useEffect(() => {
    function keydown(event: KeyboardEvent) {
      const active = event.target instanceof HTMLElement ? event.target.tagName : '';
      if ((event.key === 'k' && (event.ctrlKey || event.metaKey)) || (event.key === '/' && !['TEXTAREA', 'INPUT'].includes(active))) {
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === 'Escape') {
        searchRef.current?.blur();
        setMobileOpen(false);
      }
    }
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  }, []);

  useEffect(() => {
    if (!notice) return;
    const handle = window.setTimeout(() => setNotice(null), 3800);
    return () => window.clearTimeout(handle);
  }, [notice]);

  function navigate(next: Page) {
    window.location.hash = '/' + next;
    setPage(next);
    setSearch('');
    setMobileOpen(false);
  }

  function navigateTask(id: string) {
    setFocusedTask(id);
    navigate('gallery');
  }

  const active = [...primary, ...secondary].find(item => item.id === page)!;
  const isLibrary = page === 'gallery' || page === 'datasets';

  return (
    <div className="lc-shell optical-theme">
      <div className="ambient-stage" aria-hidden="true">
        <span className="aura-blob blob-one" />
        <span className="aura-blob blob-two" />
        <span className="aura-blob blob-three" />
      </div>

      <div className="lc-workspace">
        <header className="lc-header" aria-label="LumaCarve 主工具栏">
          <button className="lc-brand" onClick={() => navigate('generate')} aria-label="LumaCarve 首页">
            <span className="lc-logo"><PrismLogo /></span>
            <span className="lc-brand-names"><strong>LumaCarve <em>琢影</em></strong><small>CREATIVE MODEL STUDIO</small></span>
          </button>

          <nav className="lc-primary-tabs" aria-label="主要工作模式">
            {primary.map(({id,label,subtitle,icon:Icon}) => (
              <button key={id} className={'lc-primary-tab '+(page===id?'is-active':'')} onClick={() => navigate(id)} aria-current={page===id?'page':undefined}>
                <Icon size={17} strokeWidth={1.85} />
                <span>{label}<small>{subtitle}</small></span>
              </button>
            ))}
          </nav>

          <div className="lc-header-actions">
            <span className="lc-gpu-indicator" title="未连接后端，暂无 GPU 遥测">
              <svg viewBox="0 0 36 36" width="28" height="28" aria-hidden="true">
                <circle cx="18" cy="18" r="14" stroke="#dee5f2" strokeWidth="3.5" fill="none" />
                <circle cx="18" cy="18" r="14" stroke="#aab7dd" strokeWidth="3.5" fill="none" strokeDasharray="6 84" transform="rotate(-90 18 18)"/>
              </svg>
              <span><strong>—</strong><small>GPU VRAM</small></span>
            </span>
            <button className="lc-icon-btn" aria-label="通知" title="通知" onClick={() => notify('暂无新通知')}><Bell size={18}/></button>
            <button className="lc-mobile-trigger" aria-label="切换资源导航" aria-expanded={mobileOpen} onClick={() => setMobileOpen(v => !v)}><Menu size={21}/></button>
          </div>
        </header>

        <div className={'lc-context-bar '+(mobileOpen?'lc-expanded':'')}>
          <nav className="lc-secondary-tabs" aria-label="资源与管理">
            {secondary.map(({id,label,icon:Icon}) => (
              <button key={id} className={'lc-secondary-tab '+(page===id?'is-active':'')} onClick={() => navigate(id)} aria-current={page===id?'page':undefined}>
                <Icon size={15} strokeWidth={1.8}/><span>{label}</span>
              </button>
            ))}
          </nav>
          <div className="lc-context-right">
            {isLibrary && <label className="lc-quick-search">
              <Search size={15}/>
              <input ref={searchRef} type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索素材..." aria-label="搜索素材"/>
              <kbd><Command size={10}/> K</kbd>
            </label>}
            {!isLibrary && <span className="lc-workspace-state"><span/> LOCAL STUDIO <b>UI PREVIEW</b></span>}
          </div>
        </div>

        <main className="lc-main" id="main-content">
          {page === 'dashboard' && <DashboardPage outputs={outputs} onNavigate={navigate} onNavigateTask={navigateTask}/>}
          {page === 'training' && <TrainingPage {...common} onNavigateTask={navigateTask}/>}
          {page === 'generate' && <ImageStudioPage {...common}/>}
          {page === 'gallery' && <GalleryPage outputs={outputs} setOutputs={setOutputs} search={search} focusedTask={focusedTask} onNavigate={navigate} {...common}/>}
          {page === 'datasets' && <DatasetsPage datasets={datasets} setDatasets={setDatasets} search={search} {...common}/>}
          {page === 'models' && <ModelsPage/>}
          {page === 'plugins' && <PluginsPage/>}
          {page === 'history' && <HistoryPage onNavigateTask={navigateTask}/>}
          {page === 'settings' && <SettingsPage {...common}/>}
        </main>

        <footer className="lc-footer">
          <span>LUMACARVE <span className="lc-foot-divider">/</span> 琢影</span>
          <span>{active.label} <span className="lc-foot-divider">·</span> LOCAL WORKSPACE</span>
          <span>UI DEMO — 未连接生成 / 编辑 / 训练引擎</span>
        </footer>
      </div>

      {notice && (
        <div role="status" className={'toast '+(notice.tone||'')} key={notice.id}>
          <Sparkles size={16}/><span>{notice.text}</span>
          <button aria-label="关闭提示" onClick={() => setNotice(null)}><X size={15}/></button>
        </div>
      )}
    </div>
  );
}

export type SharedProps = { notify: (message: string, tone?: Notice['tone']) => void };
export type OutputsSetter = Dispatch<SetStateAction<OutputImage[]>>;
