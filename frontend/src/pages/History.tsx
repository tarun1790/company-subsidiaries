import React, { useEffect, useState } from 'react';
import { api, Company } from '../services/api';
import { Loader2, History, ChevronRight, Calendar, Building } from 'lucide-react';

interface HistoryPageProps {
  onSelectCompany: (id: string) => void;
}

export const HistoryPage: React.FC<HistoryPageProps> = ({ onSelectCompany }) => {
  const [history, setHistory] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadHistory() {
      try {
        setLoading(true);
        const data = await api.getHistory();
        setHistory(data);
      } catch (err: any) {
        setError('Failed to retrieve history logs.');
      } finally {
        setLoading(false);
      }
    }
    loadHistory();
  }, []);

  if (loading) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-2">
        <Loader2 className="h-8 w-8 text-brand-600 animate-spin" />
        <span className="text-sm font-medium text-slate-500">Loading audit history vault...</span>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8 space-y-8">
      
      {/* Title */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
          <History className="h-6 w-6 text-brand-600" />
          Audit Vault History
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Review and download previously compiled corporate hierarchy audits. Files are served directly from cache storage.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl bg-red-50 border border-red-100 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : history.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 p-12 text-center text-slate-400 font-medium">
          No corporate audits run yet. Return to Research to execute your first audit.
        </div>
      ) : (
        <div className="bg-white border border-slate-200/60 rounded-2xl overflow-hidden shadow-sm divide-y divide-slate-100">
          {history.map((comp) => (
            <div
              key={comp.id}
              onClick={() => onSelectCompany(comp.id)}
              className="flex items-center justify-between p-5 hover:bg-slate-50 cursor-pointer transition-colors"
            >
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-700 border border-brand-100 mt-0.5">
                  <Building className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-950 text-sm">
                    {comp.legal_name || comp.query_name}
                  </h4>
                  <span className="text-xs text-slate-500 font-medium mt-1 block">
                    Searched query: <span className="italic">"{comp.query_name}"</span>
                  </span>
                  
                  {/* Date details */}
                  <div className="mt-2.5 flex items-center gap-1.5 text-[10px] text-slate-400 font-semibold tracking-wide uppercase">
                    <Calendar className="h-3.5 w-3.5" />
                    {new Date(comp.created_at).toLocaleDateString(undefined, { 
                      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' 
                    })}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-xs text-slate-400 font-semibold group hover:text-brand-900 transition-colors">
                View Audit
                <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-brand-800" />
              </div>
            </div>
          ))}
        </div>
      )}

    </div>
  );
};
