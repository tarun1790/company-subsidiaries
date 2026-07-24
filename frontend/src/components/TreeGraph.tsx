import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';
import { Subsidiary } from '../services/api';

interface TreeGraphProps {
  parentName: string;
  subsidiaries: Subsidiary[];
}

export const TreeGraph: React.FC<TreeGraphProps> = ({ parentName, subsidiaries }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'base',
      themeVariables: {
        primaryColor: '#f8fafc',
        primaryTextColor: '#0f172a',
        primaryBorderColor: '#cbd5e1',
        lineColor: '#94a3b8',
        secondaryColor: '#f1f5f9',
        tertiaryColor: '#e2e8f0',
      },
      flowchart: {
        curve: 'basis',
        nodeSpacing: 50,
        rankSpacing: 50,
        padding: 15
      }
    });
    
    // Generate graph definition
    let graphDefinition = 'graph TD\n';
    
    // Sanitize ID function
    const sanitizeId = (str: string) => {
      return (str || '').replace(/[^a-zA-Z0-9]/g, '') || 'node' + Math.random().toString(36).substr(2, 9);
    };

    const rootId = sanitizeId(parentName);
    graphDefinition += `    ${rootId}["${parentName.replace(/"/g, '')}"]\n`;
    graphDefinition += `    style ${rootId} fill:#cbd5e1,stroke:#64748b,stroke-width:2px,color:#0f172a\n`;
    
    const addedNodes = new Set<string>();
    addedNodes.add(rootId);
    
    const validSubs = subsidiaries.filter(s => !!s.name);
    
    validSubs.forEach(sub => {
      const subId = sanitizeId(sub.name);
      const parentNodeId = sub.parent ? sanitizeId(sub.parent) : rootId;
      
      if (!addedNodes.has(subId)) {
        // Different styling based on status or confidence
        let fill = '#f8fafc';
        let stroke = '#cbd5e1';
        
        if (sub.status === 'Confirmed' || sub.confidence >= 0.85) {
          fill = '#ecfdf5'; // emerald-50
          stroke = '#34d399'; // emerald-400
        } else if (sub.status === 'Probable' || (sub.confidence >= 0.6 && sub.confidence < 0.85)) {
          fill = '#fffbeb'; // amber-50
          stroke = '#fbbf24'; // amber-400
        } else if (sub.status === 'Conflicting') {
          fill = '#fef2f2'; // red-50
          stroke = '#f87171'; // red-400
        }
        
        graphDefinition += `    ${subId}["${sub.name.replace(/"/g, '')}"]\n`;
        graphDefinition += `    style ${subId} fill:${fill},stroke:${stroke},stroke-width:1px,color:#0f172a\n`;
        addedNodes.add(subId);
      }
      
      const relLabel = sub.ownership && sub.ownership !== 'Not Publicly Disclosed' ? `|"${sub.ownership}"|` : '';
      graphDefinition += `    ${parentNodeId} -->${relLabel} ${subId}\n`;
    });

    const renderMermaid = async () => {
      if (containerRef.current) {
        try {
          const id = `mermaid-svg-${Date.now()}`;
          const { svg } = await mermaid.render(id, graphDefinition);
          containerRef.current.innerHTML = svg;
        } catch (error) {
          console.error("Mermaid parsing error", error);
        }
      }
    };

    if (validSubs.length > 0) {
      renderMermaid();
    } else {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    }
  }, [parentName, subsidiaries]);

  if (subsidiaries.length === 0) {
    return (
      <div className="w-full h-64 flex items-center justify-center bg-slate-50 border border-slate-200 rounded-lg">
        <div className="text-slate-400 font-medium">Awaiting hierarchy data...</div>
      </div>
    );
  }

  return (
    <div className="w-full bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
      <div className="p-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
        <h3 className="text-sm font-semibold text-slate-700">Corporate Hierarchy Map</h3>
        <div className="flex gap-4 text-xs font-medium">
          <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-full bg-emerald-100 border border-emerald-400"></div> Confirmed</div>
          <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-full bg-amber-100 border border-amber-400"></div> Probable</div>
        </div>
      </div>
      <div className="p-6 overflow-auto max-h-[700px] w-full min-h-[400px]">
        <div ref={containerRef} className="flex justify-center items-center min-w-max" />
      </div>
    </div>
  );
};
