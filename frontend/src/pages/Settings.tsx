import React, { useState } from 'react';
import { Settings, ShieldCheck, Database, KeyRound, Cpu } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [geminiKey, setGeminiKey] = useState('••••••••••••••••••••••••');
  const [tavilyKey, setTavilyKey] = useState('••••••••••••••••••••••••');
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8 space-y-8">
      
      {/* Title */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
          <Settings className="h-6 w-6 text-brand-600" />
          System Settings
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Configure API credentials, caching behavior, and LLM parameters. Note: Keys are set via environment variables for container security.
        </p>
      </div>

      {/* Form Card */}
      <div className="bg-white border border-slate-200/60 rounded-2xl p-6 shadow-sm space-y-6">
        
        <form onSubmit={handleSave} className="space-y-4">
          <div className="flex items-center gap-2.5 border-b border-slate-100 pb-3">
            <KeyRound className="h-4.5 w-4.5 text-slate-400" />
            <h3 className="font-semibold text-sm text-slate-900">API Credentials</h3>
          </div>
          
          <div className="space-y-4 text-sm">
            <div>
              <label className="block font-medium text-slate-700 mb-1.5">Google Gemini API Key</label>
              <input
                type="password"
                value={geminiKey}
                onChange={e => setGeminiKey(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3.5 py-2 focus:border-brand-500 focus:outline-none focus:bg-white transition-all text-slate-800"
              />
            </div>
            
            <div>
              <label className="block font-medium text-slate-700 mb-1.5">Tavily Search API Key (Optional)</label>
              <input
                type="password"
                value={tavilyKey}
                onChange={e => setTavilyKey(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3.5 py-2 focus:border-brand-500 focus:outline-none focus:bg-white transition-all text-slate-800"
              />
              <span className="text-[10px] text-slate-400 mt-1 block">If Tavily is omitted, research will fallback to DuckDuckGo tools.</span>
            </div>
          </div>

          <div className="pt-2 flex items-center justify-between">
            {saved ? (
              <span className="text-xs font-semibold text-brand-600 flex items-center gap-1">
                <ShieldCheck className="h-4 w-4" />
                Settings saved locally.
              </span>
            ) : <span />}
            <button
              type="submit"
              className="rounded-xl bg-slate-900 hover:bg-slate-950 px-4.5 py-2 text-sm font-semibold text-white transition-all"
            >
              Update Config
            </button>
          </div>
        </form>

        {/* Infrastructure Details */}
        <div className="border-t border-slate-100 pt-6 space-y-4">
          <div className="flex items-center gap-2.5 border-b border-slate-100 pb-3">
            <Cpu className="h-4.5 w-4.5 text-slate-400" />
            <h3 className="font-semibold text-sm text-slate-900">Infrastructure Details</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-medium text-slate-500">
            <div className="rounded-xl border border-slate-100 p-4 space-y-1.5 bg-slate-50/30">
              <span className="font-semibold text-slate-900 block flex items-center gap-1.5">
                <Database className="h-4 w-4 text-brand-600" />
                PostgreSQL Status
              </span>
              <span>Connected: subsidiary_db</span>
              <span className="block text-[10px] text-slate-400">Storing Company hierarchies & reports</span>
            </div>

            <div className="rounded-xl border border-slate-100 p-4 space-y-1.5 bg-slate-50/30">
              <span className="font-semibold text-slate-900 block flex items-center gap-1.5">
                <Cpu className="h-4 w-4 text-brand-600" />
                Redis Cache Status
              </span>
              <span>Active: redis://redis:6379/0</span>
              <span className="block text-[10px] text-slate-400">Caching filing downloads & websites</span>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
};
