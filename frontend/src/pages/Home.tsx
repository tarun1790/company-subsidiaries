import React, { useState } from 'react';
import { Search, Globe, ChevronRight, Award, Compass } from 'lucide-react';

interface HomeProps {
  onSearch: (query: string) => void;
}

export const Home: React.FC<HomeProps> = ({ onSearch }) => {
  const [query, setQuery] = useState('');

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

      {/* Core Platform Pillars (Value props) */}
      <div className="mt-20 grid grid-cols-1 gap-6 sm:grid-cols-3">
        
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 space-y-2 hover:shadow-sm transition-shadow">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600 border border-brand-100">
            <Search className="h-5 w-5" />
          </div>
          <h3 className="font-semibold text-sm text-slate-900">Multi-source Verification</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Automatically aggregates reports across SEC filings, official site crawls, OpenCorporates registries, and SSL certificate logs.
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/60 bg-white p-5 space-y-2 hover:shadow-sm transition-shadow">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600 border border-brand-100">
            <Globe className="h-5 w-5" />
          </div>
          <h3 className="font-semibold text-sm text-slate-900">Traceable Evidence Matrix</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Every discovered subsidiary is anchored by a confidence score and verifiable textual extracts mapping back to source URLs.
          </p>
        </div>

        <div className="rounded-xl border border-slate-200/60 bg-white p-5 space-y-2 hover:shadow-sm transition-shadow">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600 border border-brand-100">
            <ChevronRight className="h-5 w-5" />
          </div>
          <h3 className="font-semibold text-sm text-slate-900">Automated Hierarchies</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Extracts complex parent-subsidiary-brand layers, assembling interactive trees and premium compliance-grade PDF downloads.
          </p>
        </div>

      </div>

    </div>
  );
};
