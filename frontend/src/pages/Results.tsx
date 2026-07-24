import React, { useState, useMemo } from 'react';
import { CompanyDetails, Subsidiary, getBackendUrl } from '../services/api';
import { CorporateTree } from '../components/CorporateTree';
import { TreeGraph } from '../components/TreeGraph';
import { EvidenceExplorer } from '../components/EvidenceExplorer';
import { 
  Building2, Globe, FileDown, TreeDeciduous, 
  ListOrdered, ShieldAlert, Award, ExternalLink, 
  MapPin, CheckCircle2, ChevronRight, HelpCircle, Compass,
  GitBranch, Network
} from 'lucide-react';

interface ResultsProps {
  details: CompanyDetails;
  onNewSearch: () => void;
}

export const Results: React.FC<ResultsProps> = ({ details, onNewSearch }) => {
  const [activeTab, setActiveTab] = useState<'tree' | 'graph' | 'subsidiaries' | 'brands' | 'acquisitions' | 'units' | 'parents' | 'candidates' | 'evidence' | 'downloads'>('tree');
  const [selectedEntity, setSelectedEntity] = useState<Subsidiary | null>(null);
  
  // Search & Filters state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCountry, setSelectedCountry] = useState('All');

  const { company, subsidiaries, reports } = details;

  // Categorize entities based on V3 status
  const categorizedEntities = useMemo(() => {
    const verified: Subsidiary[] = [];
    const probable: Subsidiary[] = [];
    const unverified: Subsidiary[] = [];
    const conflicting: Subsidiary[] = [];
    const excluded: Subsidiary[] = [];

    subsidiaries.forEach(sub => {
      const status = sub.status || 'Unknown';
      if (status === 'Confirmed') verified.push(sub);
      else if (status === 'Probable') probable.push(sub);
      else if (status === 'Unverified') unverified.push(sub);
      else if (status === 'Conflicting' || sub.requires_review) conflicting.push(sub);
      else if (status === 'Excluded' || status === 'Dissolved' || status === 'Inactive') excluded.push(sub);
      else probable.push(sub); // Fallback
    });

    return { verified, probable, unverified, conflicting, excluded };
  }, [subsidiaries]);

  // Determine active dataset based on selected tab
  const activeList = useMemo(() => {
    if (activeTab === 'subsidiaries') return categorizedEntities.verified;
    if (activeTab === 'brands') return categorizedEntities.probable;
    if (activeTab === 'acquisitions') return categorizedEntities.unverified;
    if (activeTab === 'units') return categorizedEntities.conflicting;
    if (activeTab === 'parents') return categorizedEntities.excluded;
    if (activeTab === 'candidates') return subsidiaries; // All Entities
    return [];
  }, [activeTab, categorizedEntities, subsidiaries]);

  // Calculate unique countries for filter list
  const countries = useMemo(() => {
    const list = new Set<string>();
    activeList.forEach(s => s.country && list.add(s.country));
    return ['All', ...Array.from(list)];
  }, [activeList]);

  // Filtered subsidiaries list
  const filteredSubs = useMemo(() => {
    return activeList.filter(sub => {
      const matchesSearch = sub.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            (sub.legal_name || '').toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCountry = selectedCountry === 'All' || sub.country === selectedCountry;
      return matchesSearch && matchesCountry;
    });
  }, [activeList, searchQuery, selectedCountry]);

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

        <div className="flex items-center gap-3">
          {reports?.pdf && (
            <a 
              href={`${getBackendUrl()}${reports.pdf}`} 
              target="_blank" 
              rel="noreferrer"
              className="flex items-center gap-2 rounded-xl bg-slate-900 hover:bg-slate-800 px-4 py-2 text-sm font-semibold text-white transition-all shadow-sm"
            >
              <FileDown className="h-4 w-4" /> PDF Report
            </a>
          )}
          {reports?.excel && (
            <a 
              href={`${getBackendUrl()}${reports.excel}`} 
              target="_blank" 
              rel="noreferrer"
              className="flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition-all shadow-sm"
            >
              <FileDown className="h-4 w-4" /> Excel
            </a>
          )}
          <button
            onClick={onNewSearch}
            className="rounded-xl border border-slate-200 hover:bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700 transition-all"
          >
            New Audit
          </button>
        </div>
      </div>

      {/* Tabs list */}
      <div className="border-b border-slate-200/80 overflow-x-auto whitespace-nowrap">
        <nav className="flex gap-6 -mb-px px-2">
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
            onClick={() => setActiveTab('graph')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'graph'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <Network className="h-4 w-4 text-brand-600" />
            Graph ({details.knowledge_graph?.edges.length || 0})
          </button>
          
          <button
            onClick={() => setActiveTab('subsidiaries')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'subsidiaries'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            Confirmed ({categorizedEntities.verified.length})
          </button>

          <button
            onClick={() => setActiveTab('brands')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'brands'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <Compass className="h-4 w-4 text-brand-500" />
            Probable ({categorizedEntities.probable.length})
          </button>

          <button
            onClick={() => setActiveTab('acquisitions')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'acquisitions'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <HelpCircle className="h-4 w-4 text-amber-500" />
            Unverified ({categorizedEntities.unverified.length})
          </button>

          <button
            onClick={() => setActiveTab('units')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'units'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <ShieldAlert className="h-4 w-4 text-rose-500" />
            Requires Review ({categorizedEntities.conflicting.length})
          </button>

          <button
            onClick={() => setActiveTab('parents')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'parents'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <Building2 className="h-4 w-4 text-slate-400" />
            Excluded/Historical ({categorizedEntities.excluded.length})
          </button>

          <button
            onClick={() => setActiveTab('candidates')}
            className={`pb-4 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'candidates'
                ? 'border-brand-900 text-brand-950'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <ListOrdered className="h-4 w-4" />
            All Entities ({subsidiaries.length})
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
            
            <div className="pt-6">
              <TreeGraph
                parentName={company.legal_name || company.query_name}
                subsidiaries={subsidiaries}
              />
            </div>
          </div>
        )}

        {activeTab === 'graph' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <div>
                <h3 className="font-bold text-slate-900">Knowledge Graph Relational Edges</h3>
                <p className="text-xs text-slate-500 mt-0.5">Directed edges connecting corporate entities with complete evidence matrices.</p>
              </div>
              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm divide-y divide-slate-100">
                {details.knowledge_graph?.edges.map((edge, idx) => (
                  <div 
                    key={idx}
                    onClick={() => {
                      const matchingSub = subsidiaries.find(s => s.name.toLowerCase().trim() === edge.target.toLowerCase().trim());
                      if (matchingSub) setSelectedEntity(matchingSub);
                    }}
                    className="p-4 hover:bg-slate-50 cursor-pointer transition-colors flex items-center justify-between gap-4"
                  >
                    <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold text-slate-700">
                      <span className="rounded bg-slate-900 text-white px-2 py-0.5">{edge.source}</span>
                      <span className="text-brand-600 font-bold text-[10px]">── [{edge.relationship} ({edge.ownership})] ──►</span>
                      <span className="rounded bg-brand-50 border border-brand-200 text-brand-800 px-2 py-0.5">{edge.target}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                        edge.confidence >= 0.8 ? 'bg-brand-50 text-brand-700 border border-brand-100' : 'bg-amber-50 text-amber-700 border border-amber-100'
                      }`}>
                        {(edge.confidence * 100).toFixed(0)}% Match
                      </span>
                    </div>
                  </div>
                ))}
                {(!details.knowledge_graph?.edges || details.knowledge_graph.edges.length === 0) && (
                  <div className="text-center py-12 text-slate-400 font-medium">
                    No relational edges loaded in the Knowledge Graph.
                  </div>
                )}
              </div>
            </div>
            
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 shadow-sm space-y-4 h-fit">
              <h4 className="font-bold text-slate-900 border-b border-slate-200 pb-2 flex items-center gap-2 text-sm">
                <Building2 className="h-4 w-4 text-brand-600" />
                Knowledge Graph Inspector
              </h4>
              
              {selectedEntity ? (
                <div className="space-y-4 pt-1">
                  <div>
                    <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 block">Canonical Name</span>
                    <span className="font-bold text-xs text-slate-900 block mt-0.5">{selectedEntity.name}</span>
                  </div>
                  {selectedEntity.legal_name && (
                    <div>
                      <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 block">Official Legal Name</span>
                      <span className="font-medium text-xs text-slate-700 block mt-0.5">{selectedEntity.legal_name}</span>
                    </div>
                  )}
                  <div>
                    <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 block">Relationship Type & Ownership</span>
                    <span className="font-semibold text-xs text-slate-700 block mt-0.5">{selectedEntity.relationship_type} ({selectedEntity.ownership})</span>
                  </div>
                  <div>
                    <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 block">HQ Jurisdiction</span>
                    <span className="font-medium text-xs text-slate-700 block mt-0.5">{selectedEntity.country}</span>
                  </div>
                  <div>
                    <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 block">Confidence Score</span>
                    <span className="font-bold text-xs text-brand-700 block mt-0.5">{(selectedEntity.confidence * 100).toFixed(0)}% Confidence Match</span>
                  </div>
                  <div>
                    <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Citations & References</span>
                    <div className="space-y-2">
                      {selectedEntity.evidences.map((ev, eIdx) => (
                        <div key={eIdx} className="bg-white border border-slate-200 rounded-lg p-3 text-[11px] leading-relaxed shadow-sm">
                          <span className="font-bold text-brand-700 uppercase tracking-wider block text-[9px] mb-1">{ev.source_type}</span>
                          <p className="text-slate-600 italic">"{ev.extracted_text || 'Verified via official filing registry indexing.'}"</p>
                          {ev.source_url && (
                            <a 
                              href={ev.source_url} 
                              target="_blank" 
                              rel="noreferrer" 
                              className="text-brand-600 font-bold hover:underline inline-flex items-center gap-0.5 mt-1 text-[10px]"
                            >
                              Open Source Link <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic text-center py-6">Select a relational edge to inspect details.</p>
              )}
            </div>
          </div>
        )}

        {['subsidiaries', 'brands', 'acquisitions', 'units', 'parents', 'candidates'].includes(activeTab) && (
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
              {filteredSubs.map((sub, idx) => {
                const isConflict = sub.status === 'Conflicting' || sub.requires_review;
                
                return (
                  <div 
                    key={idx}
                    onClick={() => setSelectedEntity(sub)}
                    className={`group rounded-xl border bg-white p-5 hover:shadow-md transition-all cursor-pointer flex flex-col justify-between ${
                      isConflict ? 'border-rose-300 shadow-[0_0_10px_rgba(244,63,94,0.1)] hover:border-rose-400' : 'border-slate-200 hover:border-brand-300'
                    }`}
                  >
                    <div>
                      <div className="flex justify-between items-start gap-2">
                        <span className="text-[10px] font-semibold tracking-wider text-slate-500 uppercase">
                          {sub.relationship_type || 'Subsidiary'}
                        </span>
                        
                        <div className="flex gap-1">
                          {isConflict && (
                            <span className="text-xs font-semibold px-2 py-0.5 rounded border bg-rose-50 text-rose-700 border-rose-100 flex items-center gap-1">
                              <ShieldAlert className="h-3 w-3" />
                              Review
                            </span>
                          )}
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${
                            sub.confidence >= 0.95 ? 'bg-emerald-50 text-emerald-700 border-emerald-100' :
                            sub.confidence >= 0.80 ? 'bg-emerald-50/50 text-emerald-600 border-emerald-100/50' :
                            sub.confidence >= 0.60 ? 'bg-amber-50 text-amber-700 border-amber-100' :
                            sub.confidence >= 0.40 ? 'bg-orange-50 text-orange-700 border-orange-100' :
                            'bg-rose-50 text-rose-700 border-rose-100'
                          }`}>
                            {sub.confidence >= 0.95 ? '🟢 ' :
                             sub.confidence >= 0.80 ? '🟢 ' :
                             sub.confidence >= 0.60 ? '🟡 ' :
                             sub.confidence >= 0.40 ? '🟠 ' : '🔴 '}
                            {(sub.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                      
                      <h4 className="font-bold text-sm text-slate-900 mt-2 tracking-tight group-hover:text-brand-900 transition-colors">
                        {sub.name}
                      </h4>
                      
                      {isConflict && sub.conflicts && sub.conflicts.length > 0 && (
                        <div className="mt-2 text-[10px] bg-rose-50/50 rounded-lg p-2 border border-rose-100/50">
                          <span className="font-bold text-rose-700 block mb-1">Conflicting Fields:</span>
                          {sub.conflicts.map((c, cIdx) => (
                            <div key={cIdx} className="text-rose-600/80 mb-1 last:mb-0">
                              <span className="font-semibold uppercase text-[9px] tracking-wider">{c.field}:</span> {c.claims.length} variants found
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-[11px] text-slate-500 font-semibold">
                      <span className="truncate max-w-[150px]">{sub.country || 'Global'}</span>
                      <span className="flex items-center gap-0.5 text-brand-700 group-hover:gap-1 transition-all">
                        Audit Trail
                        <ChevronRight className="h-3 w-3" />
                      </span>
                    </div>
                  </div>
                );
              })}

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
