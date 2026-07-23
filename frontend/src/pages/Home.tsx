import React, { useState } from 'react';
import { Search, Globe, ChevronRight, Award, Compass } from 'lucide-react';

interface HomeProps {
  onSearch: (query: string) => void;
  liveSubsidiaries?: Array<{ name: string; legal_name?: string; country?: string; relationship_type?: string; }>;
  isAuditing?: boolean;
}

export const Home: React.FC<HomeProps> = ({ onSearch, liveSubsidiaries = [], isAuditing = false }) => {
  const [query, setQuery] = useState('');

  // Get the latest 5 discovered subsidiaries
  const displaySubs = liveSubsidiaries.slice(-5).reverse();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 pt-16 pb-24 sm:px-6 lg:px-8">
      
      {/* Hero Header */}
      <div className="text-center space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 border border-brand-100 glow-green">
          <Compass className="h-6 w-6 text-brand-600 animate-pulse" />
        </div>
        <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight sm:text-5xl">
          Corporate Subsidiary Intelligence
        </h1>
        <p className="mx-auto max-w-xl text-base text-slate-500 leading-relaxed">
          Audit corporate hierarchies, verify subsidiaries across SEC filings and government databases, and compile instantly auditable intelligence maps.
        </p>
      </div>

      {/* Main Search Panel */}
      <div className="mt-12">
        <form onSubmit={handleSubmit} className="relative flex items-center">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter a company name, brand, branch, or domain"
            className="w-full rounded-2xl border border-slate-200 bg-white px-6 py-4.5 pr-36 shadow-md hover:border-brand-200 focus:border-brand-500 focus:outline-none transition-all text-base text-slate-800"
          />
          <button
            type="submit"
            className="absolute right-2.5 rounded-xl bg-brand-900 hover:bg-brand-950 px-5 py-2.5 text-sm font-semibold text-white transition-all flex items-center gap-1.5 shadow-sm"
          >
            <Search className="h-4 w-4" />
            Audit Entity
          </button>
        </form>
      </div>

      {/* Dynamic Live Subsidiary Discovery Feed (Replaces static feature cards) */}
      <div className="mt-16 bg-white border border-slate-200/80 rounded-2xl p-6 shadow-md">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <h3 className="text-base font-bold text-slate-900">
              {isAuditing ? "Live Audit Extraction Feed" : "Live Subsidiary Intelligence Stream"}
            </h3>
          </div>
          <span className="text-xs font-semibold text-brand-700 bg-brand-50 px-2.5 py-1 rounded-full border border-brand-100">
            Latest 5 Discovered Entities
          </span>
        </div>

        {displaySubs.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-sm italic">
            Enter a company name above to begin live hierarchy discovery. Discovered entities will stream here live.
          </div>
        ) : (
          <div className="space-y-3">
            {displaySubs.map((sub, idx) => (
              <div 
                key={idx} 
                className="flex items-center justify-between p-3.5 bg-slate-50/80 border border-slate-200/60 rounded-xl hover:border-brand-300 transition-all duration-300 shadow-2xs animate-fade-in"
              >
                <div className="flex items-center gap-3 truncate">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-800 text-xs font-bold">
                    #{idx + 1}
                  </div>
                  <div className="truncate">
                    <div className="text-sm font-bold text-slate-800 truncate">{sub.name}</div>
                    <div className="text-xs text-slate-500 truncate">{sub.legal_name || sub.name}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-semibold rounded-md border border-blue-100">
                    {sub.country || 'Global'}
                  </span>
                  <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-md border border-emerald-100">
                    {sub.relationship_type || 'Subsidiary'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
};
