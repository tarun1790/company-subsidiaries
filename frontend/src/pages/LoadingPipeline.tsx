import React, { useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, Circle, AlertCircle } from 'lucide-react';

interface LoadingPipelineProps {
  query: string;
  stageLogs: string[];
  currentStage: string;
  status: 'in_progress' | 'complete' | 'failed';
  liveSubsidiaries?: Array<{ name: string; legal_name?: string; country?: string; relationship_type?: string; confidence?: number; }>;
}

interface StepItem {
  id: string;
  label: string;
}

const PIPELINE_STEPS: StepItem[] = [
  { id: 'entity_resolution', label: 'Resolving Company Entity' },
  { id: 'sec_filings', label: 'Searching SEC EDGAR Filings' },
  { id: 'official_website', label: 'Crawling Official Websites' },
  { id: 'public_registry', label: 'Searching Public Registries' },
  { id: 'web_research', label: 'Running General Web Research' },
  { id: 'doc_extraction', label: 'Parsing PDF Documents' },
  { id: 'verification', label: 'Merging & Normalizing Evidence' },
  { id: 'corporate_hierarchy', label: 'Assembling Corporate Tree' },
  { id: 'report_agent', label: 'Rendering PDF & Data Reports' },
];

export const LoadingPipeline: React.FC<LoadingPipelineProps> = ({ query, stageLogs, currentStage, status, liveSubsidiaries = [] }) => {
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [stageLogs]);

  // Determine index of current stage to calculate progress bar width
  const currentStepIdx = PIPELINE_STEPS.findIndex((s) => s.id === currentStage);
  const progressPercent = Math.max(0, Math.min(100, ((currentStepIdx + 1) / PIPELINE_STEPS.length) * 100));

  const getStepStatusIcon = (stepId: string, idx: number) => {
    if (status === 'failed') return <AlertCircle className="h-5 w-5 text-red-500" />;
    
    if (currentStage === stepId) {
      return <Loader2 className="h-5 w-5 text-brand-600 animate-spin" />;
    }
    
    // Check if this step has already been passed
    const isCompleted = idx < currentStepIdx || status === 'complete';
    if (isCompleted) {
      return <CheckCircle2 className="h-5 w-5 text-brand-600 fill-brand-50" />;
    }
    
    return <Circle className="h-5 w-5 text-slate-300" />;
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
      
      {/* Title */}
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
          Audit In Progress: <span className="text-brand-700">{query}</span>
        </h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          Our multi-agent pipeline is querying SEC filers, local registries, and official portals. This may take up to a minute.
        </p>
      </div>

      {/* Progress Track */}
      <div className="mt-8 bg-white border border-slate-200/60 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-2">
          <span>PIPELINE ENGINE</span>
          <span>{Math.round(progressPercent)}% COMPLETE</span>
        </div>
        <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden">
          <div 
            className="h-full bg-brand-900 rounded-full transition-all duration-500"
            style={{ width: `${status === 'complete' ? 100 : progressPercent}%` }}
          />
        </div>
      </div>

      {/* Grid of Steps & Logs Console */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-5 gap-8">
        
        {/* Step Indicators */}
        <div className="md:col-span-2 space-y-4">
          <h3 className="text-sm font-semibold text-slate-800 tracking-wide uppercase mb-2 pl-1">
            Agent Stages
          </h3>
          <div className="space-y-3.5">
            {PIPELINE_STEPS.map((step, idx) => (
              <div key={step.id} className="flex items-center gap-3">
                {getStepStatusIcon(step.id, idx)}
                <span className={`text-sm font-medium transition-colors ${
                  currentStage === step.id 
                    ? 'text-brand-900 font-semibold' 
                    : idx < currentStepIdx || status === 'complete'
                      ? 'text-slate-700'
                      : 'text-slate-400'
                }`}>
                  {step.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Live Logs Console */}
        <div className="md:col-span-3 flex flex-col h-[380px] rounded-2xl border border-slate-900 bg-slate-950 text-emerald-400 p-5 font-mono text-xs shadow-xl">
          <div className="border-b border-slate-800 pb-2 mb-3 flex items-center justify-between text-[10px] text-slate-500 font-semibold tracking-wider">
            <span>PIPELINE LOGS CONSOLE</span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-brand-500 animate-ping" />
              LIVE STREAM
            </span>
          </div>
          
          <div className="flex-1 overflow-y-auto space-y-1.5 scrollbar-thin">
            {stageLogs.length === 0 ? (
              <div className="text-slate-500 italic">Initializing agent subprocess nodes...</div>
            ) : (
              stageLogs.map((log, index) => (
                <div key={index} className="leading-relaxed">
                  <span className="text-slate-500 select-none mr-2">&gt;</span>
                  {log}
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>

      </div>

      {/* Live Discovered Subsidiaries Real-Time Stream */}
      <div className="mt-8 bg-white border border-slate-200/80 rounded-2xl p-6 shadow-lg">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
              Live Subsidiary Tracking Stream
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Entities discovered and extracted in real-time as the agents query SEC filers and web sources
            </p>
          </div>
          <span className="px-3 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-semibold rounded-full">
            {liveSubsidiaries.length} Discovered
          </span>
        </div>

        {liveSubsidiaries.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-sm italic">
            Scanning public registries & SEC filings... Entities will populate here second-by-second.
          </div>
        ) : (
          <div className="max-h-64 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-3 pr-2 scrollbar-thin">
            {liveSubsidiaries.map((sub, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200/60 rounded-xl hover:border-brand-300 transition-all shadow-2xs">
                <div className="truncate pr-2">
                  <div className="text-sm font-semibold text-slate-800 truncate">{sub.name}</div>
                  <div className="text-xs text-slate-500 truncate">{sub.legal_name || sub.name}</div>
                </div>
                <div className="text-right shrink-0">
                  <span className="inline-block px-2 py-0.5 bg-blue-50 text-blue-700 text-[10px] font-semibold rounded-md border border-blue-100">
                    {sub.country || 'Global'}
                  </span>
                  <div className="text-[10px] text-slate-400 mt-1">{sub.relationship_type || 'Subsidiary'}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
};
