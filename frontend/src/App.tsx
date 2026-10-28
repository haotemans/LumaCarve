import { useEffect, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Activity, Bell, Command, Database, GalleryHorizontal, HardDrive, History,
  House, Images, Layers3, Menu, Puzzle, Search, Settings2, Sparkles, WandSparkles, X, GitBranch,
} from 'lucide-react';
import { initialDatasets, initialOutputs, tasks } from './data/demo';
import type { Dataset, Notice, OutputImage, Page } from './types';
import { DashboardPage, GeneratePage, HistoryPage, ModelsPage, PluginsPage, SettingsPage, TrainingPage } from './pages/StudioPages';
import { GeneratePage as OpticalGenerate, TrainingPage as OpticalTraining, FlowPage } from './pages/OpticalStudio';
import GalleryPage from './pages/GalleryPage';
import DatasetsPage from './pages/DatasetsPage';

const navigation: { id: Page; label: string; icon: LucideIcon }[] = [
  { id: 'dashboard', label: '监控仪表盘', icon: House },
  { id: 'training', label: 'LoRA 训练', icon: Activity },
  { id: 'generate', label: '文生图', icon: WandSparkles },
  { id: 'flow', label: '图形流程', icon: GitBranch },
  { id: 'gallery', label: '出图管理', icon: Images },
  { id: 'datasets', label: '数据集管理', icon: Database },
  { id: 'models', label: '模型管理', icon: Layers3 },
  { id: 'plugins', label: '插件管理', icon: Puzzle },
  { id: 'history', label: '任务历史', icon: History },
  { id: 'settings', label: '设置', icon: Settings2 },
];

function parsePage(): Page {
  const current = window.location.hash.replace('#/', '').replace('#', '') as Page;
  return navigation.some((item) => item.id === current) ? current : 'generate';
}

export default function App() {
  const [page, setPage] = useState<Page>(parsePage);
  const [outputs, setOutputs] = useState<OutputImage[]>(initialOutputs);
  const [datasets, setDatasets] = useState<Dataset[]>(initialDatasets);
  const [focusedTask, setFocusedTask] = useState<string>('');
  const [search, setSearch] = useState('');
  const [notice, setNotice] = useState<Notice | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  function notify(text: string, tone: Notice['tone'] = 'info') {
    setNotice({ id: Date.now(), text, tone });
  }

  useEffect(() => {
    function syncHash() { setPage(parsePage()); }
    window.addEventListener('hashchange', syncHash);
    return () => window.removeEventListener('hashchange', syncHash);
  }, []);

  useEffect(() => {
    function shortcuts(event: KeyboardEvent) {
      if ((event.key === 'k' && (event.metaKey || event.ctrlKey)) || (event.key === '/' && !['TEXTAREA', 'INPUT'].includes((event.target as HTMLElement)?.tagName || ''))) {
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === 'Escape') searchRef.current?.blur();
    }
    window.addEventListener('keydown', shortcuts);
    return () => window.removeEventListener('keydown', shortcuts);
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 3500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function navigate(next: Page) {
    window.location.hash = '/' + next;
    setPage(next);
    setMenuOpen(false);
    setSearch('');
  }

  function navigateTask(id: string) {
    setFocusedTask(id);
    navigate('gallery');
  }

  const current = navigation.find((item) => item.id === page)!;
  const common = { notify };

  return (
    <div className="app-shell optical-theme"><div className="ambient-stage" aria-hidden="true"><span className="aura-blob blob-one"/><span className="aura-blob blob-two"/><span className="aura-blob blob-three"/></div>
      <aside className={'nav-rail ' + (menuOpen ? 'nav-open' : '')} aria-label="主导航">
        <button className="brand-mark" type="button" onClick={() => navigate('dashboard')} title="LumaCarve · 琢影" aria-label="返回仪表盘">
          <svg viewBox="0 0 54 52" aria-hidden="true" width="39" height="39">
            <defs><linearGradient id="luma-logo" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#6ce1ff"/><stop offset=".55" stopColor="#667dfb"/><stop offset="1" stopColor="#9d65f5"/></linearGradient></defs>
            <path d="M21 3 3 40 18 49 35 15Z" fill="url(#luma-logo)"/>
            <path d="M35 15 18 49 44 49 51 34Z" fill="#5f70e9"/>
            <path d="M28 24 18 49 35 43Z" fill="#b5cfff" opacity=".8"/>
          </svg>
        </button>
        <div className="nav-divider" />
        <div className="nav-list">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" className={'nav-icon ' + (page === id ? 'active' : '')} onClick={() => navigate(id)} aria-label={label} title={label} aria-current={page === id ? 'page' : undefined}>
              <Icon size={20} strokeWidth={1.8} />
              <span className="nav-mobile-label">{label}</span>
            </button>
          ))}
        </div>
        <div className="nav-footer">
          <div className="nav-divider" />
          <button className="nav-icon" title="工作空间" aria-label="工作空间" onClick={() => navigate('settings')}><HardDrive size={20} strokeWidth={1.8}/></button>
        </div>
      </aside>

      {menuOpen && <button className="mobile-scrim" aria-label="关闭导航" onClick={() => setMenuOpen(false)} />}

      <div className="app-body">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" aria-label="打开导航菜单" onClick={() => setMenuOpen(!menuOpen)}><Menu size={20}/></button>
            <div className="breadcrumb"><span>LUMACARVE</span><span className="breadcrumb-sep">/</span><b>{current.label}</b></div>
            <span className="topbar-version">GLASS STUDIO · UI</span>
          </div>
          <div className="topbar-right">
            <label className="global-search">
              <Search size={16}/>
              <input ref={searchRef} type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索内容..." aria-label="搜索当前页面"/>
              <kbd><Command size={11}/> K</kbd>
            </label>
            <button className="icon-button topbar-notify" aria-label="通知" title="通知" onClick={() => notify('暂无新通知')}><Bell size={18}/><i/></button>
            <span className="status-chip"><span className="status-dot"/>UI PREVIEW</span>
            <div className="avatar" title="本地工作空间">L</div>
          </div>
        </header>
        <main className="main-scroll" id="main-content">
          <div className="content-inner">
            {page === 'dashboard' && <DashboardPage outputs={outputs} onNavigate={navigate} onNavigateTask={navigateTask} />}
            {page === 'training' && <OpticalTraining {...common} onNavigateTask={navigateTask} />}
            {page === 'generate' && <OpticalGenerate {...common} />}
            {page === 'flow' && <FlowPage {...common} />}
            {page === 'gallery' && <GalleryPage outputs={outputs} setOutputs={setOutputs} search={search} focusedTask={focusedTask} onNavigate={navigate} {...common} />}
            {page === 'datasets' && <DatasetsPage datasets={datasets} setDatasets={setDatasets} search={search} {...common} />}
            {page === 'models' && <ModelsPage />}
            {page === 'plugins' && <PluginsPage />}
            {page === 'history' && <HistoryPage onNavigateTask={navigateTask} />}
            {page === 'settings' && <SettingsPage {...common} />}
          </div>
          <footer className="app-footer"><span>LUMACARVE / 琢影</span><span>Designed for WebUI &amp; Desktop</span><span className="footer-note">前端演示数据 · 未连接训练引擎</span></footer>
        </main>
      </div>
      {notice && (
        <div role="status" className={'toast ' + (notice.tone || '')} key={notice.id}>
          <Sparkles size={17} />
          <span>{notice.text}</span>
          <button aria-label="关闭提示" onClick={() => setNotice(null)}><X size={15}/></button>
        </div>
      )}
    </div>
  );
}

export type SharedProps = { notify: (message: string, tone?: Notice['tone']) => void };
export type OutputsSetter = Dispatch<SetStateAction<OutputImage[]>>;
