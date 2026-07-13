import React from 'react';
import { Building2, History, Settings, FileText } from 'lucide-react';

interface NavbarProps {
  currentPage: 'search' | 'history' | 'settings';
  setCurrentPage: (page: 'search' | 'history' | 'settings') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentPage, setCurrentPage }) => {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        
        {/* Brand Logo */}
        <div 
          className="flex items-center gap-2.5 cursor-pointer"
          onClick={() => setCurrentPage('search')}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 border border-brand-100 glow-green">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <span className="font-semibold text-slate-900 tracking-tight block">Subsidiary Intel</span>
            <span className="text-[10px] text-slate-500 font-medium tracking-wide uppercase -mt-1 block">Enterprise Grade</span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1.5">
          <button
            onClick={() => setCurrentPage('search')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all ${
              currentPage === 'search'
                ? 'bg-brand-50 text-brand-700 border border-brand-100'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <Building2 className="h-4 w-4" />
            Research
          </button>
          
          <button
            onClick={() => setCurrentPage('history')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all ${
              currentPage === 'history'
                ? 'bg-brand-50 text-brand-700 border border-brand-100'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <History className="h-4 w-4" />
            Audit Vault
          </button>
          
          <button
            onClick={() => setCurrentPage('settings')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all ${
              currentPage === 'settings'
                ? 'bg-brand-50 text-brand-700 border border-brand-100'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <Settings className="h-4 w-4" />
            Settings
          </button>
        </nav>

      </div>
    </header>
  );
};
