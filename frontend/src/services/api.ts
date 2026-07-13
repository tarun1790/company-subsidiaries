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

export interface CompanyDetails {
  company: Company;
  subsidiaries: Subsidiary[];
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
  reports?: {
    pdf?: string;
    excel?: string;
    csv?: string;
    json?: string;
  };
}

export const api = {
  async getHistory(): Promise<Company[]> {
    const res = await fetch('/api/companies/history');
    if (!res.ok) throw new Error('Failed to fetch history');
    return res.json();
  },

  async getCompanyDetails(id: string): Promise<CompanyDetails> {
    const res = await fetch(`/api/companies/${id}`);
    if (!res.ok) throw new Error('Failed to fetch details');
    return res.json();
  },

  connectPipelineWS(
    query: string,
    onMessage: (msg: PipelineMessage) => void,
    onError: (err: any) => void,
    onClose: () => void
  ): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // We target backend proxy port or local host depending on setup
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/companies/ws/pipeline/${encodeURIComponent(query)}`;
    
    logger_frontend("Connecting to WebSocket: " + wsUrl);
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
      onError(err);
    };

    ws.onclose = () => {
      onClose();
    };

    return ws;
  }
};

function logger_frontend(msg: string) {
  console.log("[api-service]", msg);
}
