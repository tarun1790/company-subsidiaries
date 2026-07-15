import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Subsidiary } from '../services/api';
import { ChevronDown, ChevronRight, CheckCircle2, AlertCircle } from 'lucide-react';

interface TreeNode {
  id: string;
  name: string;
  item?: Subsidiary;
  children: TreeNode[];
}

interface CorporateTreeProps {
  parentName: string;
  subsidiaries: Subsidiary[];
  onSelectEntity: (entity: Subsidiary) => void;
}

export const CorporateTree: React.FC<CorporateTreeProps> = ({ parentName, subsidiaries, onSelectEntity }) => {
  const [collapsedNodes, setCollapsedNodes] = useState<Record<string, boolean>>({});

  // 1. Keep all discovered subsidiaries that have a name
  const verifiedSubs = useMemo(() => {
    return subsidiaries.filter((sub) => {
      return !!sub.name;
    });
  }, [subsidiaries]);

  // 2. Build nested tree hierarchy
  const treeData = useMemo(() => {
    const root: TreeNode = {
      id: parentName.toLowerCase(),
      name: parentName,
      children: []
    };

    const nodeMap: Record<string, TreeNode> = {
      [parentName.toLowerCase()]: root
    };

    // Initialize map with verified subsidiaries
    verifiedSubs.forEach((sub) => {
      const id = sub.name.toLowerCase().trim();
      nodeMap[id] = {
        id,
        name: sub.name,
        item: sub,
        children: []
      };
    });

    // Populate children
    verifiedSubs.forEach((sub) => {
      const id = sub.name.toLowerCase().trim();
      const directParent = sub.parent || parentName;
      const parentId = directParent.toLowerCase().trim();
      
      const parentNode = nodeMap[parentId] || root;
      parentNode.children.push(nodeMap[id]);
    });

    return root;
  }, [parentName, verifiedSubs]);

  const toggleCollapse = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsedNodes((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getConfidenceBadge = (confidence: number) => {
    const score = Math.round(confidence * 100);
    let emoji = "🔴";
    if (score >= 95) emoji = "🟢";
    else if (score >= 80) emoji = "🟢";
    else if (score >= 60) emoji = "🟡";
    else if (score >= 40) emoji = "🟠";
    return { emoji, score };
  };

  // Recursively render node cards and SVG paths
  const renderNode = (node: TreeNode, depth: number = 0): React.ReactNode => {
    const isCollapsed = collapsedNodes[node.id];
    const hasChildren = node.children.length > 0;
    const isRoot = !node.item;

    return (
      <div key={node.id} className="flex flex-col items-center">
        {/* Node Card */}
        <motion.div
          layout
          onClick={() => node.item && onSelectEntity(node.item)}
          className={`relative z-10 flex flex-col min-w-[240px] max-w-[280px] rounded-xl border p-4 shadow-sm cursor-pointer transition-all ${
            isRoot 
              ? 'bg-slate-900 border-slate-800 text-white'
              : 'bg-white hover:border-brand-300 hover:shadow-md border-slate-200'
          }`}
        >
          {/* Card Header & Collapse Toggle */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 overflow-hidden">
              <span className={`text-[10px] font-bold uppercase tracking-wider truncate ${isRoot ? 'text-brand-300' : 'text-slate-400'}`}>
                {isRoot ? 'Parent Group' : node.item?.relationship_type || 'Subsidiary'}
              </span>
              {!isRoot && node.item && (() => {
                const { emoji, score } = getConfidenceBadge(node.item.confidence);
                return (
                  <span className="text-[10px] font-bold shrink-0 bg-slate-50 border border-slate-100 rounded-full px-1.5 py-0.2 select-none text-slate-600">
                    {emoji} {score}%
                  </span>
                );
              })()}
            </div>
            {hasChildren && (
              <button 
                onClick={(e) => toggleCollapse(node.id, e)}
                className={`p-1 rounded-md transition-colors ${
                  isRoot ? 'hover:bg-slate-800 text-slate-400' : 'hover:bg-slate-100 text-slate-500'
                }`}
              >
                {isCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>
            )}
          </div>

          {/* Node Name */}
          <span className={`font-bold text-sm tracking-tight mt-1.5 ${isRoot ? 'text-white' : 'text-slate-900'}`}>
            {node.name}
          </span>

          {/* Additional details */}
          {!isRoot && node.item && (
            <div className="mt-2.5 space-y-1 border-t border-slate-100 pt-2.5 text-[11px] text-slate-600 font-medium">
              <div>
                <span className="text-slate-400">Legal Name:</span> {node.item.legal_name || node.item.name}
              </div>
              {node.item.ownership && (
                <div>
                  <span className="text-slate-400">Ownership:</span> {node.item.ownership}
                </div>
              )}
              <div>
                <span className="text-slate-400">Country:</span> {node.item.country || 'Global'}
              </div>
              <div>
                <span className="text-slate-400">Status:</span>{' '}
                <span className={`font-bold ${
                  node.item.confidence >= 0.95 ? 'text-emerald-700' :
                  node.item.confidence >= 0.80 ? 'text-emerald-600' :
                  node.item.confidence >= 0.60 ? 'text-amber-600' :
                  node.item.confidence >= 0.40 ? 'text-orange-600' : 'text-rose-600'
                }`}>
                  {node.item.confidence >= 0.95 ? 'Verified' :
                   node.item.confidence >= 0.80 ? 'High Confidence' :
                   node.item.confidence >= 0.60 ? 'Moderate Confidence' :
                   node.item.confidence >= 0.40 ? 'Low Confidence' : 'Unverified'}
                </span>
              </div>
              
              {/* Evidence trail checklist */}
              {node.item.evidences && node.item.evidences.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-100">
                  <div className="text-[9px] uppercase font-bold text-slate-400 tracking-wider mb-1">Evidence Trail</div>
                  <div className="space-y-0.5">
                    {Array.from(new Set(node.item.evidences.map(e => e.source_type))).map((srcType, sIdx) => (
                      <div key={sIdx} className="flex items-center gap-1 text-[10px] text-brand-700 font-semibold">
                        <CheckCircle2 className="h-3 w-3 text-brand-500" />
                        {srcType}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </motion.div>

        {/* Children Render block */}
        {hasChildren && !isCollapsed && (
          <div className="relative flex gap-8 pt-10 mt-2">
            {/* SVG Connecting lines */}
            <div className="absolute top-0 left-0 right-0 bottom-0 pointer-events-none z-0">
              <svg className="w-full h-full">
                {/* Vertical line coming down from parent card */}
                <line 
                  x1="50%" 
                  y1="0" 
                  x2="50%" 
                  y2="20" 
                  stroke="#cbd5e1" 
                  strokeWidth="1.5" 
                />
                {/* Horizontal bridging line */}
                <line 
                  x1={`${100 / (node.children.length * 2)}%`} 
                  y1="20" 
                  x2={`${100 - 100 / (node.children.length * 2)}%`} 
                  y2="20" 
                  stroke="#cbd5e1" 
                  strokeWidth="1.5" 
                />
              </svg>
            </div>
            
            {node.children.map((child, idx) => (
              <div key={child.id} className="relative flex flex-col items-center">
                {/* Connecting stem from bridges to child cards */}
                <div className="absolute -top-10 left-1/2 -translate-x-1/2 w-[1.5px] h-10 bg-slate-300 pointer-events-none z-0" />
                {renderNode(child, depth + 1)}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  if (verifiedSubs.length === 0) {
    if (subsidiaries.length > 0) {
      // Group all subsidiaries by confidence tiers
      const tiers = {
        verified: subsidiaries.filter(s => s.confidence >= 0.95),
        high: subsidiaries.filter(s => s.confidence >= 0.80 && s.confidence < 0.95),
        moderate: subsidiaries.filter(s => s.confidence >= 0.60 && s.confidence < 0.80),
        low: subsidiaries.filter(s => s.confidence >= 0.40 && s.confidence < 0.60),
        unverified: subsidiaries.filter(s => s.confidence < 0.40)
      };

      return (
        <div className="w-full bg-white border border-slate-200 rounded-2xl p-8 shadow-sm space-y-6 text-left">
          <div className="flex items-start gap-3 bg-amber-50/50 border border-amber-100 rounded-xl p-4">
            <AlertCircle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-bold text-amber-900">No entities reached the highest confidence tier (80%+)</h4>
              <p className="text-xs text-amber-700 mt-1 leading-relaxed">
                All crawled sources were analyzed, but no discovered relationships met the strict verification confidence threshold (80%+). 
                Below are all discovered candidates presented with their confidence scores and supporting evidence.
              </p>
            </div>
          </div>

          <div className="space-y-6">
            {(Object.keys(tiers) as Array<keyof typeof tiers>).map((tierKey) => {
              const tierList = tiers[tierKey];
              if (tierList.length === 0) return null;

              const tierNames = {
                verified: "Verified (95–100%)",
                high: "High Confidence (80–94%)",
                moderate: "Moderate Confidence (60–79%)",
                low: "Low Confidence (40–59%)",
                unverified: "Unverified (<40%)"
              };

              const tierColors = {
                verified: "text-emerald-700 bg-emerald-50 border-emerald-200",
                high: "text-blue-700 bg-blue-50 border-blue-200",
                moderate: "text-amber-700 bg-amber-50 border-amber-200",
                low: "text-orange-700 bg-orange-50 border-orange-200",
                unverified: "text-rose-700 bg-rose-50 border-rose-200"
              };

              return (
                <div key={tierKey} className="space-y-3">
                  <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${tierColors[tierKey]}`}>
                    {tierNames[tierKey]}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {tierList.map((sub, idx) => (
                      <div 
                        key={idx} 
                        onClick={() => onSelectEntity(sub)}
                        className="border border-slate-100 hover:border-slate-200 hover:shadow-sm rounded-xl p-4 cursor-pointer transition-all bg-slate-50/30 flex justify-between items-start gap-4"
                      >
                        <div className="space-y-1">
                          <div className="font-bold text-slate-800 text-sm">{sub.name} ({(sub.confidence * 100).toFixed(0)}%)</div>
                          <div className="text-xs text-slate-500 font-medium">Relationship: {sub.relationship_type || 'Subsidiary'}</div>
                          <div className="text-[10px] text-slate-400">Status: {sub.verification_status || 'Unverified'}</div>
                          {sub.reduced_confidence_reason && (
                            <div className="text-[10px] text-amber-600 bg-amber-50/50 rounded px-1.5 py-0.5 mt-1 border border-amber-100/40">
                              Reason: {sub.reduced_confidence_reason}
                            </div>
                          )}
                        </div>
                        <div className="shrink-0 flex flex-col items-end gap-1">
                          <span className="text-[10px] font-bold bg-slate-200/60 text-slate-600 rounded px-1.5 py-0.5">
                            {sub.source_count || sub.evidences?.length || 0} Sources
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    return (
      <div className="w-full flex flex-col items-center justify-center bg-white border border-slate-200 border-dashed rounded-2xl p-12 text-center text-slate-400 font-medium min-h-[300px]">
        <AlertCircle className="h-8 w-8 text-slate-300 mb-2 animate-bounce" />
        <span className="font-bold text-slate-700">No subsidiaries could be identified from any public sources.</span>
        <span className="text-xs text-slate-500 mt-1.5 max-w-md leading-relaxed">
          The structural discovery pipeline ran completely but found no candidates or entity relationships.
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-8 text-left">
      <div className="w-full overflow-auto bg-slate-50/50 p-8 rounded-xl border border-slate-100 min-h-[500px] flex justify-center items-start">
        <div className="inline-block">
          {renderNode(treeData)}
        </div>
      </div>

      {/* Render separate sections for lower confidence tiers underneath the main hierarchy */}
      {subsidiaries.some(s => s.confidence < 0.8) && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-sm">
          <div>
            <h4 className="font-bold text-slate-800 text-sm">Discovered Candidates & Auditor Tiers</h4>
            <p className="text-xs text-slate-500 mt-0.5">These discovered entities did not satisfy the strict hierarchy verification threshold (80%+) but are preserved for audit visibility.</p>
          </div>
          
          <div className="space-y-4">
            {([
              { key: "moderate", label: "Moderate Confidence (60-79%)", color: "text-amber-700 bg-amber-50 border-amber-200", filter: (s: Subsidiary) => s.confidence >= 0.6 && s.confidence < 0.8 },
              { key: "low", label: "Low Confidence (40-59%)", color: "text-orange-700 bg-orange-50 border-orange-200", filter: (s: Subsidiary) => s.confidence >= 0.4 && s.confidence < 0.6 },
              { key: "unverified", label: "Unverified (<40%)", color: "text-rose-700 bg-rose-50 border-rose-200", filter: (s: Subsidiary) => s.confidence < 0.4 }
            ]).map((tier) => {
              const tierList = subsidiaries.filter(tier.filter);
              if (tierList.length === 0) return null;
              
              return (
                <div key={tier.key} className="space-y-2">
                  <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${tier.color}`}>
                    {tier.label}
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {tierList.map((sub, idx) => (
                      <div 
                        key={idx}
                        onClick={() => onSelectEntity(sub)}
                        className="border border-slate-100 hover:border-slate-200 hover:shadow-sm rounded-xl p-4 cursor-pointer transition-all bg-slate-50/10 flex justify-between items-start gap-4"
                      >
                        <div className="space-y-1">
                          <div className="font-bold text-slate-800 text-sm">{sub.name} ({(sub.confidence * 100).toFixed(0)}%)</div>
                          <div className="text-xs text-slate-500 font-medium">Relationship: {sub.relationship_type || 'Subsidiary'}</div>
                          <div className="text-[10px] text-slate-400">Status: {sub.verification_status || 'Unverified'}</div>
                          {sub.reduced_confidence_reason && (
                            <div className="text-[10px] text-amber-600 bg-amber-50/50 rounded px-1.5 py-0.5 mt-1 border border-amber-100/40">
                              Reason: {sub.reduced_confidence_reason}
                            </div>
                          )}
                        </div>
                        <div className="shrink-0">
                          <span className="text-[10px] font-bold bg-slate-100 text-slate-500 rounded px-1.5 py-0.5">
                            {sub.source_count || sub.evidences?.length || 0} Sources
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
