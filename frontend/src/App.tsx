import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Home } from './pages/Home';
import { LoadingPipeline } from './pages/LoadingPipeline';
import { Results } from './pages/Results';
import { HistoryPage } from './pages/History';
import { SettingsPage } from './pages/Settings';
import { api, CompanyDetails, PipelineMessage } from './services/api';

type Page = 'search' | 'history' | 'settings';

export const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<Page>('search');
  const [pipelineState, setPipelineState] = useState<{
    query: string;
    stageLogs: string[];
    currentStage: string;
    status: 'idle' | 'in_progress' | 'complete' | 'failed';
    results: CompanyDetails | null;
    liveSubsidiaries: Array<{ name: string; legal_name?: string; country?: string; relationship_type?: string; confidence?: number; }>;
  }>({
    query: '',
    stageLogs: [],
    currentStage: '',
    status: 'idle',
    results: null,
    liveSubsidiaries: []
  });

  const handleStartSearch = (query: string) => {
    // 1. Reset state and switch status to in_progress
    setPipelineState({
      query,
      stageLogs: ["Connecting to audit pipeline backend..."],
      currentStage: "entity_resolution",
      status: 'in_progress',
      results: null,
      liveSubsidiaries: []
    });
    setCurrentPage('search'); // Stay on search workspace page

    // 2. Connect to WebSocket pipeline stream
    let ws: WebSocket | null = null;
    
    const handleMessage = (msg: PipelineMessage) => {
      setPipelineState((prev) => {
        // Build running logs list
        const nextLogs = [...prev.stageLogs];
        if (msg.log && !nextLogs.includes(msg.log)) {
          nextLogs.push(msg.log);
        }

        const nextSubs = msg.live_subsidiaries && msg.live_subsidiaries.length > 0 ? msg.live_subsidiaries : prev.liveSubsidiaries;

        if (msg.status === 'complete' && msg.company_id) {
          const details: CompanyDetails = {
            company: {
              id: msg.company_id,
              query_name: query,
              legal_name: msg.company_info?.legal_name,
              domain: msg.company_info?.domain,
              ticker: msg.company_info?.ticker,
              cik: msg.company_info?.cik,
              hq_country: msg.company_info?.hq_country,
              metadata_fields: msg.company_info?.metadata_fields,
              created_at: new Date().toISOString()
            },
            subsidiaries: msg.subsidiaries || [],
            reports: msg.reports
          };
          
          return {
            ...prev,
            stageLogs: [...nextLogs, "Audit process completed successfully. Loading interface..."],
            currentStage: "done",
            status: 'complete',
            results: details,
            liveSubsidiaries: nextSubs
          };
        } else if (msg.status === 'failed') {
          return {
            ...prev,
            stageLogs: [...nextLogs, "Audit process failed. Please check backend logs."],
            status: 'failed',
            liveSubsidiaries: nextSubs
          };
        }

        let mappedStage = msg.stage;
        if (["document_discovery", "document_intelligence", "structured_entity_extraction"].includes(msg.stage)) {
            mappedStage = "doc_extraction";
        } else if (["evidence_fusion", "entity_normalization", "relationship_classification", "entity_verification", "conflict_resolution", "relationship_verification", "confidence_scoring"].includes(msg.stage)) {
            mappedStage = "verification";
        } else if (["knowledge_graph_builder", "graph_validation", "corporate_hierarchy"].includes(msg.stage)) {
            mappedStage = "corporate_hierarchy";
        } else if (["coverage_estimator", "discovery_strategy_engine", "loop_coordinator", "next_target_preparer"].includes(msg.stage)) {
            mappedStage = "corporate_hierarchy"; // Loop nodes
        }

        return {
          ...prev,
          stageLogs: nextLogs,
          currentStage: mappedStage,
          status: 'in_progress',
          liveSubsidiaries: nextSubs
        };
      });
    };

    const handleError = async (err: any) => {
      console.warn("WS Pipeline notice/error, switching to HTTP audit runner fallback: ", err);
      setPipelineState((prev) => ({
        ...prev,
        stageLogs: [...prev.stageLogs, "WebSocket closed. Executing synchronous HTTP pipeline fallback..."]
      }));
      try {
        const details = await api.runPipelineHTTP(query);
        setPipelineState({
          query: details.company.legal_name || query,
          stageLogs: ["HTTP pipeline audit completed successfully."],
          currentStage: "done",
          status: 'complete',
          results: details,
          liveSubsidiaries: []
        });
      } catch (httpErr: any) {
        console.error("HTTP Pipeline fallback failed: ", httpErr);
        setPipelineState((prev) => ({
          ...prev,
          stageLogs: [...prev.stageLogs, `Audit execution failed: ${httpErr.message}`],
          status: 'failed'
        }));
      }
    };

    const handleClose = () => {
      console.log("WS Pipeline closed.");
    };

    try {
      ws = api.connectPipelineWS(query, handleMessage, handleError, handleClose);
    } catch (err: any) {
      setPipelineState((prev) => ({
        ...prev,
        stageLogs: [...prev.stageLogs, `Fatal connection error: ${err.message}`],
        status: 'failed'
      }));
    }
  };

  const handleSelectHistoricalCompany = async (id: string) => {
    try {
      setPipelineState({
        query: "Loading...",
        stageLogs: ["Fetching historical records from storage vault..."],
        currentStage: "fetching",
        status: 'in_progress',
        results: null,
        liveSubsidiaries: []
      });
      setCurrentPage('search'); // switch back to main panel to display loading/results

      const data = await api.getCompanyDetails(id);
      
      setPipelineState({
        query: data.company.legal_name || data.company.query_name,
        stageLogs: ["Loaded cache successfully."],
        currentStage: "done",
        status: 'complete',
        results: data,
        liveSubsidiaries: []
      });
    } catch (err) {
      console.error("Error loading historical company details: ", err);
      setPipelineState((prev) => ({
        ...prev,
        stageLogs: [...prev.stageLogs, "Failed to retrieve historical record details."],
        status: 'failed'
      }));
    }
  };

  const handleNewSearch = () => {
    setPipelineState({
      query: '',
      stageLogs: [],
      currentStage: '',
      status: 'idle',
      results: null,
      liveSubsidiaries: []
    });
  };

  const renderContent = () => {
    if (currentPage === 'history') {
      return <HistoryPage onSelectCompany={handleSelectHistoricalCompany} />;
    }
    
    if (currentPage === 'settings') {
      return <SettingsPage />;
    }

    // Default 'search' workspace pages
    if (pipelineState.status === 'in_progress' || pipelineState.status === 'failed') {
      return (
        <LoadingPipeline
          query={pipelineState.query}
          stageLogs={pipelineState.stageLogs}
          currentStage={pipelineState.currentStage}
          status={pipelineState.status === 'failed' ? 'failed' : 'in_progress'}
          liveSubsidiaries={pipelineState.liveSubsidiaries}
        />
      );
    }

    if (pipelineState.status === 'complete' && pipelineState.results) {
      return (
        <Results
          details={pipelineState.results}
          onNewSearch={handleNewSearch}
        />
      );
    }

    return (
      <Home 
        onSearch={handleStartSearch} 
        liveSubsidiaries={pipelineState.liveSubsidiaries}
        isAuditing={false}
      />
    );
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-50/20">
      <Navbar currentPage={currentPage} setCurrentPage={setCurrentPage} />
      <main className="flex-1">
        {renderContent()}
      </main>
    </div>
  );
};

export default App;
