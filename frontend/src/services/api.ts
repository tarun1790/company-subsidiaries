export interface Company {
  id: string;
  query_name: string;
  legal_name?: string;
  cik?: string;
  ticker?: string;
  domain?: string;
  hq_country?: string;
  original_query?: string;
  entity_classification?: string;
  confidence?: number;
  metadata_fields?: Record<string, any>;
  created_at: string;
}

export interface Evidence {
  source_type: string;
  source_url?: string;
  extracted_text?: string;
  verified_at?: string;
  source_tier?: number;
  extraction_confidence?: number;
}

export interface FieldConflict {
  field: string;
  claims: Array<{value: string, source: string}>;
}

export interface Subsidiary {
  name: string;
  legal_name?: string;
  country?: string;
  ownership?: string;
  parent?: string;
  relationship_type?: string;
  registration_number?: string;
  confidence: number;
  confidence_band?: string;
  verification_status?: string;
  reduced_confidence_reason?: string;
  source_count?: number;
  valid_from?: string;
  valid_to?: string;
  notes?: string;
  depth?: number;
  status?: 'Confirmed' | 'Probable' | 'Unverified' | 'Conflicting' | 'Historical' | 'Former' | 'Inactive' | 'Dissolved' | 'Excluded' | 'Unknown';
  requires_review?: boolean;
  conflicts?: FieldConflict[];
  evidences: Evidence[];
}

export interface KnowledgeGraphNode {
  id: string;
  label: string;
  type: string;
  country: string;
  confidence: number;
  evidences: Evidence[];
}

export interface KnowledgeGraphEdge {
  source: string;
  target: string;
  relationship: string;
  ownership: string;
  confidence: number;
  evidences: Evidence[];
}

export interface KnowledgeGraph {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
}

export interface CompanyDetails {
  company: Company;
  subsidiaries: Subsidiary[];
  knowledge_graph?: KnowledgeGraph;
  reports?: {
    pdf?: string;
    excel?: string;
    csv?: string;
    json?: string;
  };
}

export interface PipelineMessage {
  stage: string;
  log: string;
  status: 'in_progress' | 'complete' | 'failed';
  company_id?: string;
  company_info?: any;
  subsidiaries?: Subsidiary[];
  reports?: any;
  counts?: {
    subsidiaries: number;
    sec_results: number;
    website_results: number;
    search_results: number;
    discovered_documents: number;
  };
  live_subsidiaries?: Array<{
    name: string;
    legal_name?: string;
    country?: string;
    relationship_type?: string;
    confidence?: number;
  }>;
}

const isGithubPages = () => {
  return window.location.hostname.includes('github.io');
};

const ACTIVE_CLOUDFLARE_URL = 'https://every-bath-mercy-attend.trycloudflare.com';

const getBackendUrl = () => {
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isLocal) {
    return 'http://localhost:8000';
  }
  const saved = localStorage.getItem('backend_url');
  if (saved && (saved.includes('loca.lt') || saved.includes('trycloudflare.com'))) {
    localStorage.removeItem('backend_url');
  } else if (saved) {
    return saved;
  }
  if (isGithubPages()) {
    return ACTIVE_CLOUDFLARE_URL;
  }
  return ACTIVE_CLOUDFLARE_URL;
};

const defaultHeaders = {
  'bypass-tunnel-reminder': 'true'
};

export const api = {
  async getHistory(): Promise<Company[]> {
    try {
      const base = getBackendUrl();
      const res = await fetch(`${base}/api/companies/history`, { headers: defaultHeaders });
      if (!res.ok) throw new Error('API server returned an error');
      return await res.json();
    } catch (e) {
      console.error("[api-service] Failed to fetch search history:", e);
      throw e;
    }
  },

  async clearAllHistory(): Promise<{ message: string }> {
    try {
      const base = getBackendUrl();
      const res = await fetch(`${base}/api/companies/history/clear`, { method: 'DELETE', headers: defaultHeaders });
      if (!res.ok) throw new Error('Failed to clear audit history');
      return await res.json();
    } catch (e) {
      console.error("[api-service] Failed to clear audit history:", e);
      throw e;
    }
  },

  async deleteCompanyAudit(id: string): Promise<{ message: string }> {
    try {
      const base = getBackendUrl();
      const res = await fetch(`${base}/api/companies/${id}`, { method: 'DELETE', headers: defaultHeaders });
      if (!res.ok) throw new Error('Failed to delete company audit');
      return await res.json();
    } catch (e) {
      console.error(`[api-service] Failed to delete company audit for ID ${id}:`, e);
      throw e;
    }
  },

  async getCompanyDetails(id: string): Promise<CompanyDetails> {
    try {
      const base = getBackendUrl();
      const res = await fetch(`${base}/api/companies/${id}`, { headers: defaultHeaders });
      if (!res.ok) throw new Error('API server returned an error');
      return await res.json();
    } catch (e) {
      console.error(`[api-service] Failed to fetch company details for ID ${id}:`, e);
      throw e;
    }
  },

  async runPipelineHTTP(query: string): Promise<CompanyDetails> {
    try {
      const base = getBackendUrl();
      const res = await fetch(`${base}/api/companies/pipeline/${encodeURIComponent(query)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...defaultHeaders }
      });
      if (!res.ok) throw new Error('HTTP pipeline execution failed');
      return await res.json();
    } catch (e) {
      console.error(`[api-service] Failed HTTP pipeline run for query ${query}:`, e);
      throw e;
    }
  },

  connectPipelineWS(
    query: string,
    onMessage: (msg: PipelineMessage) => void,
    onError: (err: any) => void,
    onClose: () => void
  ): WebSocket {
    try {
      const base = getBackendUrl();
      let wsUrl = '';
      if (base) {
        // Map http:// or https:// to ws:// or wss://
        const wsBase = base.replace(/^http/, 'ws');
        wsUrl = `${wsBase}/api/companies/ws/pipeline/${encodeURIComponent(query)}`;
      } else {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        wsUrl = `${protocol}//${host}/api/companies/ws/pipeline/${encodeURIComponent(query)}`;
      }
      
      console.log(`[api-service] Connecting to pipeline websocket: ${wsUrl}`);
      const ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as PipelineMessage;
          onMessage(data);
        } catch (e) {
          onError(e);
        }
      };

      ws.onerror = (err) => {
        console.error("[api-service] WebSocket error encountered:", err);
        onError(err);
      };

      ws.onclose = () => {
        console.log("[api-service] WebSocket connection closed");
        onClose();
      };

      return ws;
    } catch (e) {
      console.error("[api-service] Failed to instantiate WebSocket connection:", e);
      onError(e);
      throw e;
    }
  }
};
