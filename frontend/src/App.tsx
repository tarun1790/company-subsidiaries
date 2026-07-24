import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Home } from './pages/Home';
import { LoadingPipeline } from './pages/LoadingPipeline';
import { Results } from './pages/Results';
import { HistoryPage } from './pages/History';
import { SettingsPage } from './pages/Settings';
import { DiscoveryTicker } from './components/DiscoveryTicker';
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
    let hasReceivedMessage = false;
    let watchdogTimer: any = null;
    
    const handleMessage = (msg: PipelineMessage) => {
      hasReceivedMessage = true;
      if (watchdogTimer) clearTimeout(watchdogTimer);
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
      if (watchdogTimer) clearTimeout(watchdogTimer);
      console.warn("WS Pipeline notice/error, switching to HTTP audit runner fallback: ", err);
      
      const stages = [
        { stage: 'entity_resolution', log: 'Resolving canonical company entity...' },
        { stage: 'sec_filings', log: 'Querying SEC EDGAR Exhibit 21 database...' },
        { stage: 'official_website', log: 'Crawling corporate domain & investor portals...' },
        { stage: 'public_registry', log: 'Searching statutory registries (GLEIF, OpenCorporates)...' },
        { stage: 'web_research', log: 'Running multi-engine web research for brands & acquisitions...' },
        { stage: 'doc_extraction', log: 'Parsing annual report PDF documents...' },
        { stage: 'verification', log: 'Fusing evidence & calculating dynamic confidence scores...' },
        { stage: 'corporate_hierarchy', log: 'Assembling corporate hierarchy tree...' },
        { stage: 'report_agent', log: 'Compiling audit reports...' }
      ];

      let stepIdx = 0;
      const progressInterval = setInterval(() => {
        if (stepIdx < stages.length) {
          const item = stages[stepIdx];
          setPipelineState((prev) => ({
            ...prev,
            currentStage: item.stage,
            stageLogs: [...prev.stageLogs, item.log]
          }));
          stepIdx++;
        }
      }, 1500);

      try {
        const details = await api.runPipelineHTTP(query);
        clearInterval(progressInterval);
        setPipelineState({
          query: details.company.legal_name || query,
          stageLogs: ["HTTP audit completed successfully. Rendering corporate intelligence graph..."],
          currentStage: "done",
          status: 'complete',
          results: details,
          liveSubsidiaries: []
        });
      } catch (httpErr: any) {
        clearInterval(progressInterval);
        console.error("HTTP Pipeline fallback failed: ", httpErr);
        setPipelineState((prev) => ({
          ...prev,
          stageLogs: [...prev.stageLogs, `Audit execution failed: ${httpErr.message}`],
          status: 'failed'
        }));
      }
    };

    const handleClose = () => {
      if (watchdogTimer) clearTimeout(watchdogTimer);
      console.log("WS Pipeline closed.");
    };

    try {
      ws = api.connectPipelineWS(query, handleMessage, handleError, handleClose);
      
      // Watchdog: If no message is received within 4 seconds, close WS & fallback to HTTP runner
      watchdogTimer = setTimeout(() => {
        if (!hasReceivedMessage) {
          console.warn("[App] WebSocket connection watchdog triggered (no response after 4s). Falling back to HTTP runner.");
          if (ws) {
            try { ws.close(); } catch (e) {}
          }
          handleError(new Error("WebSocket connection timeout (4s limit exceeded)"));
        }
      }, 4000);
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
      
      {/* Show live ticker if there are any subsidiaries */}
      {(pipelineState.liveSubsidiaries.length > 0 || (pipelineState.results && pipelineState.results.subsidiaries.length > 0)) && (
        <DiscoveryTicker 
          subsidiaries={
            pipelineState.status === 'complete' && pipelineState.results 
              ? pipelineState.results.subsidiaries 
              : pipelineState.liveSubsidiaries
          } 
        />
      )}

      <main className="flex-1">
        {renderContent()}
      </main>
    </div>
  );
};

export default App;
