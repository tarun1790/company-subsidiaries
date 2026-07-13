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

  // 1. Build nested tree hierarchy
  const treeData = useMemo(() => {
    const root: TreeNode = {
      id: parentName.toLowerCase(),
      name: parentName,
      children: []
    };

    const nodeMap: Record<string, TreeNode> = {
      [parentName.toLowerCase()]: root
    };

    // Initialize map with all verified subsidiaries
    subsidiaries.forEach((sub) => {
      const id = sub.name.toLowerCase();
      nodeMap[id] = {
        id,
        name: sub.name,
        item: sub,
        children: []
      };
    });

    // Populate children
    subsidiaries.forEach((sub) => {
      const id = sub.name.toLowerCase();
      const directParent = sub.parent || parentName;
      const parentId = directParent.toLowerCase();
      
      const parentNode = nodeMap[parentId] || root;
      parentNode.children.push(nodeMap[id]);
    });

    return root;
  }, [parentName, subsidiaries]);

  const toggleCollapse = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsedNodes((prev) => ({ ...prev, [id]: !prev[id] }));
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
          className={`relative z-10 flex flex-col min-w-[220px] max-w-[260px] rounded-xl border p-4 shadow-sm cursor-pointer transition-all ${
            isRoot 
              ? 'bg-slate-900 border-slate-800 text-white'
              : 'bg-white hover:border-brand-300 hover:shadow-md border-slate-200'
          }`}
        >
          {/* Card Header & Collapse Toggle */}
          <div className="flex items-start justify-between gap-2">
            <span className={`text-xs font-semibold uppercase tracking-wider ${isRoot ? 'text-brand-300' : 'text-slate-500'}`}>
              {isRoot ? 'Parent Group' : node.item?.relationship_type || 'Subsidiary'}
            </span>
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
          <span className="font-semibold text-sm tracking-tight mt-1.5 line-clamp-1">
            {node.name}
          </span>

          {/* Additional details */}
          {!isRoot && node.item && (
            <div className="mt-2.5 flex items-center justify-between border-t border-slate-100 pt-2 text-[11px] text-slate-500">
              <span className="truncate max-w-[120px] font-medium">{node.item.country || 'Global'}</span>
              <div className="flex items-center gap-1">
                {node.item.confidence >= 0.7 ? (
                  <CheckCircle2 className="h-3 w-3 text-brand-500" />
                ) : (
                  <AlertCircle className="h-3 w-3 text-amber-500" />
                )}
                <span className={`font-semibold ${node.item.confidence >= 0.7 ? 'text-brand-600' : 'text-amber-600'}`}>
                  {node.item.confidence * 100:.0f}%
                </span>
              </div>
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

  return (
    <div className="w-full overflow-auto bg-slate-50/50 p-8 rounded-xl border border-slate-100 min-h-[500px] flex justify-center items-start">
      <div className="inline-block">
        {renderNode(treeData)}
      </div>
    </div>
  );
};
