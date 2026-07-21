import React, { useEffect, useState } from 'react';
import { api, Company } from '../services/api';
import { Loader2, History, ChevronRight, Calendar, Building, Trash2, AlertTriangle } from 'lucide-react';

interface HistoryPageProps {
  onSelectCompany: (id: string) => void;
}

export const HistoryPage: React.FC<HistoryPageProps> = ({ onSelectCompany }) => {
  const [history, setHistory] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

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

  async function handleClearAll() {
    if (!window.confirm("Are you sure you want to delete all corporate audit history? This will clear all cached records so re-entering company names starts fresh from scratch.")) {
      return;
    }
    try {
      setClearing(true);
      await api.clearAllHistory();
      setHistory([]);
      localStorage.removeItem('cached_company_id');
    } catch (err: any) {
      alert("Failed to clear history: " + err.message);
    } finally {
      setClearing(false);
    }
  }

  async function handleDeleteCompany(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    if (!window.confirm("Delete this company audit record to start fresh from scratch?")) {
      return;
    }
    try {
      setDeletingId(id);
      await api.deleteCompanyAudit(id);
      setHistory(prev => prev.filter(c => c.id !== id));
    } catch (err: any) {
      alert("Failed to delete record: " + err.message);
    } finally {
      setDeletingId(null);
    }
  }

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
      
      {/* Title & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <History className="h-6 w-6 text-brand-600" />
            Audit Vault History
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Review, download, or clear previously compiled corporate hierarchy audits.
          </p>
        </div>

        {history.length > 0 && (
          <button
            onClick={handleClearAll}
            disabled={clearing}
            className="flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 text-red-700 hover:bg-red-100 hover:border-red-300 px-4 py-2 text-xs font-bold transition-all w-fit disabled:opacity-50"
          >
            {clearing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Trash2 className="h-3.5 w-3.5" />
            )}
            Clear All Audit History
          </button>
        )}
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
              className="flex items-center justify-between p-5 hover:bg-slate-50 cursor-pointer transition-colors group"
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

              <div className="flex items-center gap-3">
                <button
                  onClick={(e) => handleDeleteCompany(e, comp.id)}
                  disabled={deletingId === comp.id}
                  title="Delete this audit to run fresh from scratch"
                  className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
                >
                  {deletingId === comp.id ? (
                    <Loader2 className="h-4 w-4 animate-spin text-red-600" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </button>
                <div className="flex items-center gap-1.5 text-xs text-slate-400 font-semibold group-hover:text-brand-900 transition-colors">
                  View Audit
                  <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-brand-800" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

    </div>
  );
};
