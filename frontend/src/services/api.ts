export interface Company {
  id: string;
  query_name: string;
  legal_name?: string;
  cik?: string;
  ticker?: string;
  domain?: string;
  hq_country?: string;
  metadata_fields?: Record<string, any>;
  created_at: string;
}

export interface Evidence {
  source_type: string;
  source_url?: string;
  extracted_text?: string;
  verified_at?: string;
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
  notes?: string;
  depth?: number;
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
  company_info?: Record<string, any>;
  subsidiaries?: Subsidiary[];
  knowledge_graph?: KnowledgeGraph;
  reports?: {
    pdf?: string;
    excel?: string;
    csv?: string;
    json?: string;
  };
}

const isGithubPages = () => {
  return window.location.hostname.includes('github.io');
};

const getBackendUrl = () => {
  const saved = localStorage.getItem('backend_url');
  if (saved) return saved;
  return isGithubPages() ? 'http://localhost:8000' : '';
};

export const api = {
  async getHistory(): Promise<Company[]> {
    try {
      const base = getBackendUrl();
      const res = await fetch(`${base}/api/companies/history`);
      if (!res.ok) throw new Error('API server returned an error');
      return await res.json();
    } catch (e) {
      console.error("[api-service] Failed to fetch search history:", e);
      throw e;
    }
  },

  async getCompanyDetails(id: string): Promise<CompanyDetails> {
    try {
      const base = getBackendUrl();
      const res = await fetch(`${base}/api/companies/${id}`);
      if (!res.ok) throw new Error('API server returned an error');
      return await res.json();
    } catch (e) {
      console.error(`[api-service] Failed to fetch company details for ID ${id}:`, e);
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
