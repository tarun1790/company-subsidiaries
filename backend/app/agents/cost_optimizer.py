import re
from typing import List, Dict, Any, Tuple
from app.core.logging import logger

class CostOptimizer:
    """Cost Optimization Layer: Routes entity extraction tasks through Tier 0 Regex,
    Tier 1 Rule-Based/NER Parsers, and only invokes Tier 2 LLM when necessary."""
    
    # Common corporate legal suffixes
    SUFFIX_PATTERN = r'\b(Inc|LLC|Ltd|Limited|Corp|Corporation|Co|Company|GmbH|AG|SA|BV|NV|SARL|Pty|Pvt|Private|PLC|Holdings|Group|S\.A\.P\.I\.|S\.R\.L\.|S\.A\.)\b'

    @classmethod
    def fast_extract_entities_from_text(cls, text: str, parent_name: str) -> Tuple[List[Dict[str, Any]], bool]:
        """Fast-path Tier 0 & Tier 1 extraction using regex pattern matching and structural cues.
        Returns: (extracted_entities, needs_llm_fallback)"""
        if not text or len(text.strip()) < 10:
            return [], False

        entities = []
        seen_names = set()

        # 1. Regex Pattern for Named Legal Entities with Suffixes
        pattern = re.compile(
            r'([A-Z0-9][A-Za-z0-9\&\,\.\-\s]{2,60}?\s+' + cls.SUFFIX_PATTERN + r')',
            re.IGNORECASE
        )
        
        matches = pattern.findall(text)
        for match in matches:
            raw_name = match[0] if isinstance(match, tuple) else match
            clean_name = re.sub(r'\s+', ' ', raw_name).strip()
            
            # Filter parent self-collisions or short noise
            if clean_name.lower() == parent_name.lower() or len(clean_name) < 4:
                continue

            clean_key = clean_name.lower()
            if clean_key not in seen_names:
                seen_names.add(clean_key)
                
                # Infer basic relationship and country cues
                country = "Global"
                if any(k in clean_key for k in ["uk", "united kingdom", "ireland", "gmbh", "germany", "france", "india", "china", "japan", "australia"]):
                    if "gmbh" in clean_key or "germany" in clean_key:
                        country = "Germany"
                    elif "ireland" in clean_key:
                        country = "Ireland"
                    elif "india" in clean_key:
                        country = "India"
                    elif "china" in clean_key:
                        country = "China"

                entities.append({
                    "name": clean_name,
                    "legal_name": clean_name,
                    "country": country,
                    "ownership": "Wholly-owned",
                    "parent": parent_name,
                    "relationship_type": "Direct Subsidiary",
                    "confidence": 0.88,
                    "evidences": [{
                        "source_type": "Cost-Optimized Regex Parser",
                        "extracted_text": clean_name
                    }],
                    "notes": "Extracted via Fast Tier 1 Cost Optimization Parser."
                })

        # If regex extracted clear candidates, skip expensive LLM generation
        needs_llm = len(entities) == 0 and len(text) > 200
        logger.info(f"[CostOptimizer] Extracted {len(entities)} entities via Fast Rule Engine. LLM Fallback Needed: {needs_llm}")
        return entities, needs_llm
