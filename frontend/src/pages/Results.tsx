import React, { useState, useMemo } from 'react';
import { CompanyDetails, Subsidiary } from '../services/api';
import { CorporateTree } from '../components/CorporateTree';
import { EvidenceExplorer } from '../components/EvidenceExplorer';
import { 
  Building2, Globe, FileDown, TreeDeciduous, 
  ListOrdered, ShieldAlert, Award, ExternalLink, 
  MapPin, CheckCircle2, ChevronRight, HelpCircle
} from 'lucide-react';

interface ResultsProps {
  details: CompanyDetails;
  onNewSearch: () => void;
}

export const Results: React.FC<ResultsProps> = ({ details, onNewSearch }) => {
  const [activeTab, setActiveTab] = useState<'tree' | 'list' | 'evidence' | 'downloads'>('tree');
  const [selectedEntity, setSelectedEntity] = useState<Subsidiary | null>(null);
  
  // Search & Filters state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCountry, setSelectedCountry] = useState('All');

  const { company, subsidiaries, reports } = details;

  // Calculate unique countries for filter list
  const countries = useMemo(() => {
    const list = new Set<string>();
    subsidiaries.forEach(s => s.country && list.add(s.country));
    return ['All', ...Array.from(list)];
  }, [subsidiaries]);

  // Filtered subsidiaries list
  const filteredSubs = useMemo(() => {
    return subsidiaries.filter(sub => {
      const matchesSearch = sub.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            (sub.legal_name || '').toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCountry = selectedCountry === 'All' || sub.country === selectedCountry;
      return matchesSearch && matchesCountry;
    });
  }, [subsidiaries, searchQuery, selectedCountry]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
      
      {/* Header section with Metadata Cards */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white border border-slate-200/60 rounded-2xl p-6 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-900 text-white">
            <Building2 className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                {company.legal_name || company.query_name}
              </h2>
              {company.ticker && (
                <span className="rounded bg-brand-50 border border-brand-100 text-brand-700 px-2 py-0.5 text-xs font-semibold uppercase">
                  {company.ticker}
                </span>
              )}
            </div>
            
            {/* Sub-identifiers */}
            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 font-medium">
              {company.domain && (
                <span className="flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5" />
                  {company.domain}
                </span>
              )}
              {company.cik && (
                <span>CIK: {company.cik}</span>
              )}
              {company.hq_country && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  HQ: {company.hq_country}
                </span>
              )}
            </div>
          </div>
        </div>

        <button
          onClick={onNewSearch}
          className="rounded-xl border border-slate-200 hover:bg-slate-50 px-4.5 py-2.5 text-sm font-semibold text-slate-700 transition-all text-center"
        >
          New Audit
        </button>
      </div>

      {/* Tabs list */}
      <div className="border-b border-slate-200/80">
        <nav className="flex gap-6 -mb-px">
          <button
            onClick={() => setActiveTab('tree')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'tree'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <TreeDeciduous className="h-4 w-4" />
            Corporate Tree
          </button>
          
          <button
            onClick={() => setActiveTab('list')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'list'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <ListOrdered className="h-4 w-4" />
            Verified Subsidiaries ({subsidiaries.length})
          </button>
          
          <button
            onClick={() => setActiveTab('evidence')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'evidence'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <HelpCircle className="h-4 w-4" />
            Evidence Matrix
          </button>
          
          <button
            onClick={() => setActiveTab('downloads')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'downloads'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <FileDown className="h-4 w-4" />
            Report Vault
          </button>
        </nav>
      </div>

      {/* Dynamic Tab Body content */}
      <div className="min-h-[400px]">
        {activeTab === 'tree' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-bold text-slate-900">Corporate Hierarchy Tree</h3>
                <p className="text-xs text-slate-500 mt-0.5">Click any entity card to inspect detail attributes and audit evidence files.</p>
              </div>
            </div>
            <CorporateTree 
              parentName={company.legal_name || company.query_name}
              subsidiaries={subsidiaries}
              onSelectEntity={setSelectedEntity}
            />
          </div>
        )}

        {activeTab === 'list' && (
          <div className="space-y-6">
            {/* Filters panel */}
            <div className="flex flex-col sm:flex-row gap-4 bg-white border border-slate-100 rounded-xl p-4 shadow-sm">
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Filter entities by name..."
                className="flex-1 rounded-lg border border-slate-200 bg-slate-50/50 px-3.5 py-2 text-sm focus:border-brand-500 focus:outline-none focus:bg-white transition-all"
              />
              <select
                value={selectedCountry}
                onChange={e => setSelectedCountry(e.target.value)}
                className="rounded-lg border border-slate-200 bg-slate-50/50 px-3.5 py-2 text-sm focus:border-brand-500 focus:outline-none focus:bg-white transition-all min-w-[160px]"
              >
                {countries.map(c => (
                  <option key={c} value={c}>{c === 'All' ? 'All Countries' : c}</option>
                ))}
              </select>
            </div>

            {/* Entities Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4.5">
              {filteredSubs.map((sub, idx) => (
                <div 
                  key={idx}
                  onClick={() => setSelectedEntity(sub)}
                  className="group rounded-xl border border-slate-200 bg-white p-5 hover:border-brand-300 hover:shadow-md transition-all cursor-pointer flex flex-col justify-between"
                >
                  <div>
                    <div className="flex justify-between items-start gap-2">
                      <span className="text-[10px] font-semibold tracking-wider text-slate-500 uppercase">
                        {sub.relationship_type || 'Subsidiary'}
                      </span>
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                        sub.confidence >= 0.8 ? 'bg-brand-50 text-brand-700' : 'bg-amber-50 text-amber-700'
                      }`}>
                        {(sub.confidence * 100).toFixed(0)}% Match
                      </span>
                    </div>
                    <h4 className="font-bold text-sm text-slate-900 mt-2 tracking-tight group-hover:text-brand-900 transition-colors">
                      {sub.name}
                    </h4>
                  </div>

                  <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-[11px] text-slate-500 font-semibold">
                    <span className="truncate max-w-[150px]">{sub.country || 'Global'}</span>
                    <span className="flex items-center gap-0.5 text-brand-700 group-hover:gap-1 transition-all">
                      Audit Trail
                      <ChevronRight className="h-3 w-3" />
                    </span>
                  </div>
                </div>
              ))}

              {filteredSubs.length === 0 && (
                <div className="col-span-full text-center py-12 text-slate-400 font-medium">
                  No verified entities match your filters.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'evidence' && (
          <div className="space-y-4">
            <div>
              <h3 className="font-bold text-slate-900">Audit Evidence Matrix</h3>
              <p className="text-xs text-slate-500 mt-0.5">Comprehensive catalog showing verification data and text extracts from files.</p>
            </div>
            
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                    <th className="p-4 w-1/4">Entity Name</th>
                    <th className="p-4 w-1/6">Source Name</th>
                    <th className="p-4">Evidence Quote / Context snippet</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                  {subsidiaries.flatMap((sub, subIdx) => 
                    sub.evidences.map((ev, evIdx) => (
                      <tr 
                        key={`${subIdx}-${evIdx}`}
                        onClick={() => setSelectedEntity(sub)}
                        className="hover:bg-slate-50/50 cursor-pointer transition-colors"
                      >
                        <td className="p-4 font-semibold text-slate-900">{sub.name}</td>
                        <td className="p-4">
                          <span className="rounded bg-slate-100 border border-slate-200 px-2 py-0.5 font-semibold text-slate-600">
                            {ev.source_type}
                          </span>
                        </td>
                        <td className="p-4 text-slate-600 leading-relaxed italic">
                          "{ev.extracted_text || 'Verified via corporate filing registry indexing.'}"
                        </td>
                      </tr>
                    ))
                  )}
                  {subsidiaries.length === 0 && (
                    <tr>
                      <td colSpan={3} className="text-center py-8 text-slate-400 font-medium">
                        No evidence logs compiled.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'downloads' && (
          <div className="space-y-4 max-w-2xl">
            <div>
              <h3 className="font-bold text-slate-900">Compliance Downloads Vault</h3>
              <p className="text-xs text-slate-500 mt-0.5">Download generated audit packs in standardized formats.</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              
              {reports?.pdf && (
                <a
                  href={reports.pdf}
                  download
                  className="rounded-xl border border-slate-200 bg-white p-5 hover:border-brand-300 hover:shadow-md transition-all flex items-start gap-4"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50 text-red-600 border border-red-100">
                    <FileDown className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="font-bold text-sm text-slate-900 block">PDF Audit Report</span>
                    <span className="text-xs text-slate-500 block mt-0.5">Premium formatted document with cover, statistics, and tables.</span>
                  </div>
                </a>
              )}

              {reports?.excel && (
                <a
                  href={reports.excel}
                  download
                  className="rounded-xl border border-slate-200 bg-white p-5 hover:border-brand-300 hover:shadow-md transition-all flex items-start gap-4"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-100">
                    <FileDown className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="font-bold text-sm text-slate-900 block">Excel Spreadsheet</span>
                    <span className="text-xs text-slate-500 block mt-0.5">Data rows mapping ownership details, countries, and registration IDs.</span>
                  </div>
                </a>
              )}

              {reports?.csv && (
                <a
                  href={reports.csv}
                  download
                  className="rounded-xl border border-slate-200 bg-white p-5 hover:border-brand-300 hover:shadow-md transition-all flex items-start gap-4"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600 border border-brand-100">
                    <FileDown className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="font-bold text-sm text-slate-900 block">CSV File</span>
                    <span className="text-xs text-slate-500 block mt-0.5">Plain text comma-separated values structure.</span>
                  </div>
                </a>
              )}

              {reports?.json && (
                <a
                  href={reports.json}
                  download
                  className="rounded-xl border border-slate-200 bg-white p-5 hover:border-brand-300 hover:shadow-md transition-all flex items-start gap-4"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-50 text-slate-600 border border-slate-100">
                    <FileDown className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="font-bold text-sm text-slate-900 block">JSON Payload</span>
                    <span className="text-xs text-slate-500 block mt-0.5">Raw JSON data archive payload schema.</span>
                  </div>
                </a>
              )}

            </div>
          </div>
        )}
      </div>

      {/* Evidence Side Panel details drawer */}
      {selectedEntity && (
        <>
          <div 
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40" 
            onClick={() => setSelectedEntity(null)} 
          />
          <EvidenceExplorer 
            entity={selectedEntity} 
            onClose={() => setSelectedEntity(null)} 
          />
        </>
      )}

    </div>
  );
};
