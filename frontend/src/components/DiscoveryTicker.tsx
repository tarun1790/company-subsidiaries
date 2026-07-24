import React, { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Subsidiary } from '../services/api';
import { Globe, Building2, Link } from 'lucide-react';

interface DiscoveryTickerProps {
  subsidiaries: Partial<Subsidiary>[];
}

export const DiscoveryTicker: React.FC<DiscoveryTickerProps> = ({ subsidiaries }) => {
  // We want to show the 5 most recently discovered entities, rotating.
  const [tickerItems, setTickerItems] = useState<Partial<Subsidiary>[]>([]);
  
  useEffect(() => {
    // Get up to the last 15, then we will CSS marquee them
    const recent = [...subsidiaries].filter(s => !!s.name).reverse().slice(0, 15);
    if (recent.length > 0) {
      // Duplicate them to create a seamless infinite scroll effect if there's enough room
      setTickerItems([...recent, ...recent]);
    } else {
      setTickerItems([]);
    }
  }, [subsidiaries]);

  if (tickerItems.length === 0) return null;

  return (
    <div className="w-full bg-slate-900 border-y border-slate-700 overflow-hidden py-2 relative flex items-center shadow-inner">
      <div className="absolute left-0 top-0 bottom-0 w-16 bg-gradient-to-r from-slate-900 to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-slate-900 to-transparent z-10 pointer-events-none" />
      
      <div className="flex shrink-0 items-center whitespace-nowrap overflow-hidden">
        <motion.div
          className="flex space-x-8 px-4"
          animate={{ x: [0, -1000] }}
          transition={{
            repeat: Infinity,
            repeatType: "loop",
            duration: 30,
            ease: "linear",
          }}
        >
          {tickerItems.map((sub, idx) => (
            <div key={`${sub.name}-${idx}`} className="flex items-center space-x-3 bg-slate-800/80 px-4 py-1.5 rounded-full border border-slate-700 shadow-sm">
              <span className="flex items-center space-x-1.5 text-xs font-semibold text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>NEW</span>
              </span>
              <span className="text-sm font-medium text-slate-200">
                {sub.name}
              </span>
              <span className="flex items-center space-x-1 text-xs text-slate-400 border-l border-slate-600 pl-3">
                <Globe className="w-3 h-3" />
                <span>{sub.country || 'Global'}</span>
              </span>
              <span className="flex items-center space-x-1 text-xs text-slate-400 border-l border-slate-600 pl-3">
                <Link className="w-3 h-3" />
                <span>{sub.relationship_type || 'Subsidiary'}</span>
              </span>
              <span className="text-xs font-mono text-emerald-400/90 border-l border-slate-600 pl-3">
                {((sub.confidence || 0) * 100).toFixed(0)}% Match
              </span>
            </div>
          ))}
        </motion.div>
      </div>
    </div>
  );
};
