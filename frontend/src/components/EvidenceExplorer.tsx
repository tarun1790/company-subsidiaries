import React from 'react';
import { Subsidiary } from '../services/api';
import { X, ExternalLink, ShieldCheck, CheckCircle2, AlertTriangle, FileText } from 'lucide-react';

interface EvidenceExplorerProps {
  entity: Subsidiary | null;
  onClose: () => void;
}

export const EvidenceExplorer: React.FC<EvidenceExplorerProps> = ({ entity, onClose }) => {
  if (!entity) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md border-l border-slate-200 bg-white shadow-2xl transition-all duration-300 sm:max-w-lg flex flex-col">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 p-5">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-brand-600">
            Entity Details
          </span>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight mt-0.5">
            {entity.name}
          </h2>
        </div>
        <button 
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-50 hover:text-slate-600 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Body Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        
        {/* Core Attributes Card */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 space-y-3.5">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-xs text-slate-500 font-medium block">Legal Corporate Name</span>
              <span className="font-semibold text-slate-900 block mt-0.5 truncate">{entity.legal_name || entity.name}</span>
            </div>
            <div>
              <span className="text-xs text-slate-500 font-medium block">HQ Jurisdiction</span>
              <span className="font-semibold text-slate-900 block mt-0.5">{entity.country || 'Global'}</span>
            </div>
            <div>
              <span className="text-xs text-slate-500 font-medium block">Ownership Share</span>
              <span className="font-semibold text-slate-900 block mt-0.5">{entity.ownership || '100%'}</span>
            </div>
            <div>
              <span className="text-xs text-slate-500 font-medium block">Registration No.</span>
              <span className="font-semibold text-slate-900 block mt-0.5 truncate">{entity.registration_number || 'N/A'}</span>
            </div>
          </div>
          
          <div className="border-t border-slate-200/60 pt-3">
            <span className="text-xs text-slate-500 font-medium block">Notes & Relationship Context</span>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">{entity.notes}</p>
          </div>
        </div>

        {/* Confidence Analytics */}
        <div>
          <h3 className="text-sm font-semibold text-slate-900 mb-3">Audit Confidence Analytics</h3>
          <div className="flex items-center gap-4 rounded-xl border border-slate-100 p-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-50 border border-brand-100">
              <ShieldCheck className="h-7 w-7 text-brand-600" />
            </div>
            <div className="flex-1">
              <div className="flex justify-between items-baseline">
                <span className="font-bold text-2xl text-slate-900">{(entity.confidence * 100).toFixed(0)}%</span>
                <span className={`text-xs font-semibold ${entity.confidence >= 0.7 ? 'text-brand-600' : 'text-amber-600'}`}>
                  {entity.confidence >= 0.8 ? 'Verified Ultimate' : entity.confidence >= 0.6 ? 'High Reliability' : 'Moderate Evidence'}
                </span>
              </div>
              {/* Progress track */}
              <div className="h-2 w-full bg-slate-100 rounded-full mt-2 overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all ${
                    entity.confidence >= 0.8 ? 'bg-brand-500' : entity.confidence >= 0.6 ? 'bg-emerald-400' : 'bg-amber-400'
                  }`}
                  style={{ width: `${entity.confidence * 100}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Conflict & Review LEDGER */}
        {entity.conflicts && entity.conflicts.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-rose-700 mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Conflict Detection Ledger
            </h3>
            <div className="rounded-xl border border-rose-200 bg-rose-50/50 p-4 space-y-4">
              <p className="text-xs text-rose-600 font-medium">Multiple authoritative sources conflict on the following data points:</p>
              
              <div className="space-y-3">
                {entity.conflicts.map((conflict, idx) => (
                  <div key={idx} className="bg-white border border-rose-100 rounded-lg p-3">
                    <span className="text-[10px] uppercase tracking-wider font-bold text-rose-500 block mb-2">{conflict.field}</span>
                    <div className="space-y-1.5">
                      {conflict.claims.map((claim, cIdx) => (
                        <div key={cIdx} className="flex justify-between text-xs items-center">
                          <span className="font-semibold text-slate-900">{claim.value}</span>
                          <span className="text-slate-500">{claim.source}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Evidence Matrix Logs */}
        <div>
          <h3 className="text-sm font-semibold text-slate-900 mb-3">Supporting Evidence Matrix ({entity.evidences.length})</h3>
          <div className="space-y-3.5">
            {entity.evidences.map((ev, idx) => (
              <div key={idx} className="rounded-xl border border-slate-200/80 p-4 space-y-3 hover:border-slate-300 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded bg-slate-50 border border-slate-100">
                      <FileText className="h-3.5 w-3.5 text-slate-500" />
                    </div>
                    <span className="text-xs font-semibold text-slate-900">{ev.source_type}</span>
                  </div>
                  {ev.source_url && ev.source_url.startsWith('http') && (
                    <a
                      href={ev.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-[11px] font-medium text-brand-600 hover:text-brand-700 transition-colors"
                    >
                      Source URL
                      <ExternalLink className="h-2.5 w-2.5" />
                    </a>
                  )}
                </div>
                {ev.extracted_text && (
                  <p className="text-xs text-slate-600 bg-slate-50/50 p-2.5 rounded-lg border border-slate-100 leading-relaxed italic">
                    "{ev.extracted_text}"
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
};
