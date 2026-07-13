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

// ============================================================================
// HIGH-FIDELITY MOCK DATA FOR DEMO MODE
// ============================================================================
const MOCK_COMPANIES: Company[] = [
  {
    id: "mock-uuid-stripe",
    query_name: "Stripe",
    legal_name: "Stripe, Inc.",
    domain: "stripe.com",
    hq_country: "United States",
    created_at: new Date().toISOString()
  },
  {
    id: "mock-uuid-microsoft",
    query_name: "Microsoft",
    legal_name: "Microsoft Corporation",
    cik: "0000789019",
    ticker: "MSFT",
    domain: "microsoft.com",
    hq_country: "United States",
    created_at: new Date(Date.now() - 3600000 * 2).toISOString()
  },
  {
    id: "mock-uuid-amazon",
    query_name: "Amazon",
    legal_name: "Amazon.com, Inc.",
    cik: "0001018724",
    ticker: "AMZN",
    domain: "amazon.com",
    hq_country: "United States",
    created_at: new Date().toISOString()
  }
];

const MOCK_STRIPE_DETAILS: CompanyDetails = {
  company: MOCK_COMPANIES[0],
  subsidiaries: [
    {
      name: "Stripe Payments Europe Limited",
      legal_name: "Stripe Payments Europe Limited",
      country: "Ireland",
      ownership: "100%",
      parent: "Stripe, Inc.",
      relationship_type: "Subsidiary",
      registration_number: "IE513174",
      confidence: 1.0,
      notes: "Main European payment processing and operating subsidiary.",
      depth: 1,
      evidences: [
        { source_type: "Official Website", source_url: "https://stripe.com/legal", extracted_text: "Stripe Payments Europe, Limited is regulated by the Central Bank of Ireland." },
        { source_type: "Public Registry", source_url: "https://opencorporates.com", extracted_text: "Registered in Ireland, Company Number 513174." }
      ]
    },
    {
      name: "Stripe Japan KK",
      legal_name: "Stripe Japan Kabushiki Kaisha",
      country: "Japan",
      ownership: "100%",
      parent: "Stripe, Inc.",
      relationship_type: "Subsidiary",
      confidence: 0.85,
      notes: "Operating division managing Japanese payments and merchants.",
      depth: 1,
      evidences: [
        { source_type: "Official Website", source_url: "https://stripe.com/jp", extracted_text: "Stripe Japan KK manages local credit and bank transfer solutions." }
      ]
    },
    {
      name: "Stripe Payments UK Ltd",
      legal_name: "Stripe Payments UK Limited",
      country: "United Kingdom",
      ownership: "100%",
      parent: "Stripe Payments Europe Limited",
      relationship_type: "Subsidiary",
      registration_number: "08481771",
      confidence: 1.0,
      notes: "UK payment operations entity.",
      depth: 2,
      evidences: [
        { source_type: "Public Registry", source_url: "https://find-and-update.company-information.service.gov.uk", extracted_text: "Stripe Payments UK Ltd registered at Companies House UK." }
      ]
    }
  ],
  reports: {
    pdf: "#",
    excel: "#",
    csv: "#",
    json: "#"
  }
};

const MOCK_MICROSOFT_DETAILS: CompanyDetails = {
  company: MOCK_COMPANIES[1],
  subsidiaries: [
    {
      name: "Microsoft Ireland Operations Limited",
      legal_name: "Microsoft Ireland Operations Limited",
      country: "Ireland",
      ownership: "100%",
      parent: "Microsoft Corporation",
      relationship_type: "Subsidiary",
      registration_number: "IE256796",
      confidence: 1.0,
      notes: "Core international licensing and logistics hub.",
      depth: 1,
      evidences: [
        { source_type: "SEC Filings", source_url: "https://sec.gov", extracted_text: "Microsoft Ireland Operations Limited listed in Exhibit 21 of 10-K filing." },
        { source_type: "Public Registry", source_url: "https://opencorporates.com", extracted_text: "Registered in Dublin, company number 256796." }
      ]
    },
    {
      name: "Xbox Game Studios",
      legal_name: "Xbox Game Studios LLC",
      country: "United States",
      ownership: "100%",
      parent: "Microsoft Corporation",
      relationship_type: "Brand",
      confidence: 0.9,
      notes: "Gaming division coordinating software and hardware releases.",
      depth: 1,
      evidences: [
        { source_type: "Official Website", source_url: "https://xbox.com", extracted_text: "Xbox Game Studios is a division of Microsoft Corp." }
      ]
    },
    {
      name: "GitHub, Inc.",
      legal_name: "GitHub, Incorporated",
      country: "United States",
      ownership: "100%",
      parent: "Microsoft Corporation",
      relationship_type: "Subsidiary",
      confidence: 1.0,
      notes: "Acquired developer community platform.",
      depth: 1,
      evidences: [
        { source_type: "Annual Report PDF", source_url: "https://microsoft.com", extracted_text: "GitHub operates as a wholly owned subsidiary of Microsoft." }
      ]
    }
  ],
  reports: {
    pdf: "#",
    excel: "#",
    csv: "#",
    json: "#"
  }
};

const MOCK_AMAZON_DETAILS: CompanyDetails = {
  company: MOCK_COMPANIES[2],
  subsidiaries: [
    {
      name: "Amazon Web Services, Inc.",
      legal_name: "Amazon Web Services, Inc.",
      country: "United States",
      ownership: "100%",
      parent: "Amazon.com, Inc.",
      relationship_type: "Subsidiary",
      confidence: 1.0,
      notes: "Cloud infrastructure and web operations branch.",
      depth: 1,
      evidences: [
        { source_type: "SEC Filings", source_url: "https://sec.gov", extracted_text: "Amazon Web Services, Inc. listed in Exhibit 21 of 10-K." },
        { source_type: "Official Website", source_url: "https://aws.amazon.com", extracted_text: "AWS is an Amazon.com company." }
      ]
    },
    {
      name: "Whole Foods Market, Inc.",
      legal_name: "Whole Foods Market, Inc.",
      country: "United States",
      ownership: "100%",
      parent: "Amazon.com, Inc.",
      relationship_type: "Subsidiary",
      confidence: 1.0,
      notes: "Acquired grocery store chain.",
      depth: 1,
      evidences: [
        { source_type: "Annual Report PDF", source_url: "https://amazon.com", extracted_text: "Whole Foods Market operates as a subsidiary of Amazon." }
      ]
    },
    {
      name: "Twitch Interactive, Inc.",
      legal_name: "Twitch Interactive, Incorporated",
      country: "United States",
      ownership: "100%",
      parent: "Amazon.com, Inc.",
      relationship_type: "Subsidiary",
      confidence: 0.95,
      notes: "Live video streaming service provider.",
      depth: 1,
      evidences: [
        { source_type: "Web Research", source_url: "https://wikipedia.org", extracted_text: "Twitch was acquired by Amazon for $970 million." }
      ]
    }
  ],
  reports: {
    pdf: "#",
    excel: "#",
    csv: "#",
    json: "#"
  }
};

const isGithubPages = () => {
  return window.location.hostname.includes('github.io');
};

export const api = {
  async getHistory(): Promise<Company[]> {
    if (isGithubPages()) {
      return MOCK_COMPANIES;
    }
    try {
      const res = await fetch('/api/companies/history');
      if (!res.ok) throw new Error('API down');
      return await res.json();
    } catch {
      console.warn("API server unreachable. Loading mock history.");
      return MOCK_COMPANIES;
    }
  },

  async getCompanyDetails(id: string): Promise<CompanyDetails> {
    if (isGithubPages() || id.startsWith("mock-uuid")) {
      if (id === "mock-uuid-stripe") return MOCK_STRIPE_DETAILS;
      if (id === "mock-uuid-amazon") return MOCK_AMAZON_DETAILS;
      return MOCK_MICROSOFT_DETAILS;
    }
    try {
      const res = await fetch(`/api/companies/${id}`);
      if (!res.ok) throw new Error('API down');
      return await res.json();
    } catch {
      console.warn("API server unreachable. Loading mock details.");
      if (id.includes("stripe")) return MOCK_STRIPE_DETAILS;
      if (id.includes("amazon")) return MOCK_AMAZON_DETAILS;
      return MOCK_MICROSOFT_DETAILS;
    }
  },

  connectPipelineWS(
    query: string,
    onMessage: (msg: PipelineMessage) => void,
    onError: (err: any) => void,
    onClose: () => void
  ): WebSocket {
    // If running on GitHub Pages (static demo mode), simulate pipeline WS messages
    if (isGithubPages()) {
      console.log("[api-service] Simulating pipeline WebSocket for GitHub Pages...");
      simulatePipeline(query, onMessage);
      // Return a dummy websocket-like object so the app doesn't crash calling close()
      return { close: () => {} } as any;
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/api/companies/ws/pipeline/${encodeURIComponent(query)}`;
      
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
        // Trigger fallback simulation if local backend is down
        console.warn("WebSocket connection failed. Falling back to frontend simulation.");
        simulatePipeline(query, onMessage);
      };

      ws.onclose = () => {
        onClose();
      };

      return ws;
    } catch (e) {
      simulatePipeline(query, onMessage);
      return { close: () => {} } as any;
    }
  }
};

// Pipeline Simulators for GitHub Pages demo mode
function simulatePipeline(query: string, onMessage: (msg: PipelineMessage) => void) {
  const isStripe = query.toLowerCase().includes("stripe");
  const isAmazon = query.toLowerCase().includes("amazon");

  const resolvedName = isStripe ? "Stripe, Inc." : isAmazon ? "Amazon.com, Inc." : "Microsoft Corporation";
  const cik = isStripe ? "N/A" : isAmazon ? "0001018724" : "0000789019";
  const domain = isStripe ? "stripe.com" : isAmazon ? "amazon.com" : "microsoft.com";

  const steps = [
    { stage: "entity_resolution", log: `Resolving Company: '${query}'...` },
    { stage: "entity_resolution", log: `Resolved legal name: '${resolvedName}' (Confidence: 99%)` },
    { stage: "sec_filings", log: `Searching SEC EDGAR for CIK ${cik}...` },
    { stage: "sec_filings", log: "Found 10-K filing. Downloading Exhibit 21..." },
    { stage: "sec_filings", log: "Extracted subsidiaries from SEC Exhibit 21." },
    { stage: "official_website", log: `Crawling corporate links on ${domain}...` },
    { stage: "official_website", log: `Scraping page: https://${domain}/about...` },
    { stage: "public_registry", log: `Searching public registries for '${resolvedName}'...` },
    { stage: "web_research", log: "Running Web Research Agent (Wikipedia, SSL Certificates, Web Search)..." },
    { stage: "doc_extraction", log: "Parsing PDF Documents..." },
    { stage: "verification", log: "Merging & Normalizing Evidence..." },
    { stage: "corporate_hierarchy", log: "Assembling Corporate Tree..." },
    { stage: "report_agent", log: "Rendering PDF & Data Reports..." }
  ];

  let currentStep = 0;
  
  const interval = setInterval(() => {
    if (currentStep < steps.length) {
      onMessage({
        stage: steps[currentStep].stage,
        log: steps[currentStep].log,
        status: 'in_progress'
      });
      currentStep++;
    } else {
      clearInterval(interval);
      // Final message: return results
      const details = isStripe ? MOCK_STRIPE_DETAILS : isAmazon ? MOCK_AMAZON_DETAILS : MOCK_MICROSOFT_DETAILS;
      
      onMessage({
        stage: "done",
        log: "DEMO MODE: Results loaded from local data storage.",
        status: 'complete',
        company_id: isStripe ? "mock-uuid-stripe" : isAmazon ? "mock-uuid-amazon" : "mock-uuid-microsoft",
        company_info: details.company,
        subsidiaries: details.subsidiaries,
        reports: details.reports
      });
    }
  }, 1000); // 1s interval for snappy loading experience
}
