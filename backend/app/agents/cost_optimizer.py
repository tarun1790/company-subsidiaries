import re
import uuid
import time
from typing import List, Dict, Any, Tuple, Optional
from app.core.logging import logger
from app.schemas.entities import CandidateEntity

class CostOptimizer:
    """Tier 1 Rule-Based/NER Parsers with Zero-Drop Candidate Classification."""
    
    SUFFIX_PATTERN = r'\b(Inc|LLC|Ltd|Limited|Corp|Corporation|Co|Company|GmbH|AG|SA|BV|NV|SARL|Pty|Pvt|Private|PLC|Holdings|Group|S\.A\.P\.I\.|S\.R\.L\.|S\.A\.)\b'

    VALID_ENTITY_STATUSES = {
        "Confirmed", "Probable", "Unverified", "Conflicting", 
        "Historical", "Former", "Inactive", "Dissolved", "Excluded", "Unknown"
    }

    STOPWORDS = {
        "is", "was", "has", "have", "had", "its", "their", "our", "your", "today", 
        "ago", "latest", "news", "balance sheet", "last filed", "days ago", 
        "controlling stake", "e-commerce leader", "top startup", "get real-time", 
        "updates on", "read more", "filed on", "share capital", "financial year", 
        "annual report", "competitor", "competing", "market share", "held a", "holding a"
    }

    @classmethod
    def sanitize_and_clean_entity_name(cls, raw_name: str, parent_name: str) -> Optional[str]:
        """Cleans, trims, and validates entity names according to enterprise compliance rules."""
        if not raw_name:
            return None
            
        s = raw_name.strip()
        
        # 1. Handle concatenated prefix/suffix artifacts like 'Limited.Walmart Inc' or '00 Top Startup News... 7. Flipkart Private'
        if "..." in s:
            parts = s.split("...")
            s = parts[-1].strip()
        s = re.sub(r'^\d+\s*[\.\-\)]\s*', '', s) # Remove numbered list items '7. Flipkart' -> 'Flipkart'
        
        # If concatenated like 'Limited.Walmart Inc', split by period followed by capital letter
        sub_splits = re.split(r'(?<=\w\.)(?=[A-Z])', s)
        if len(sub_splits) > 1:
            valid_parts = [p.strip() for p in sub_splits if p.strip() and parent_name.lower().strip() not in p.lower()]
            s = valid_parts[0] if valid_parts else sub_splits[-1].strip()

        # 2. Trim leading/trailing punctuation and bullet points
        s = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', s).strip()
        
        # 3. Truncate trailing sentence fragments following legal suffixes
        # e.g., 'Flipkart Internet Private Limited is an Indian e-commerce company' -> 'Flipkart Internet Private Limited'
        suffix_match = re.search(r'\b(Private Limited|Pvt Ltd|Pte Ltd|Limited|Ltd|Inc|LLC|Corporation|Corp|PLC|GmbH|AG|SA|BV|NV|Holdings|Group)\b', s, re.IGNORECASE)
        if suffix_match:
            end_idx = suffix_match.end()
            trailing = s[end_idx:].strip()
            if trailing:
                trailing_words = trailing.lower().split()
                if any(w in {"is", "was", "has", "have", "had", "its", "their", "our", "an", "the", "a", "today", "ago", "latest", "news", "leader", "held", "filed"} for w in trailing_words):
                    s = s[:end_idx].strip()
                    
        # 4. Check for sentence stopword contamination
        s_lower = s.lower()
        if any(f" {sw} " in f" {s_lower} " for sw in cls.STOPWORDS):
            return None
            
        # 5. Reject if word count > 6 or too short
        words = s.split()
        if len(words) > 6 or len(s) < 3:
            return None
            
        # 6. Reject if it matches parent company name
        p_lower = parent_name.lower().strip()
        if s_lower == p_lower or s_lower == p_lower.replace("inc", "").replace("corp", "").strip():
            return None
            
        return s

    @classmethod
    def classify_entity_candidate(cls, raw_name: str, parent_name: str) -> CandidateEntity:
        cleaned = cls.sanitize_and_clean_entity_name(raw_name, parent_name)
        
        if not cleaned:
            return CandidateEntity(
                candidate_id=f"cand_{uuid.uuid4().hex[:8]}",
                raw_name=raw_name or "",
                status="Excluded",
                reason="Failed entity sanitization (sentence fragment, stopword, or parent match)",
                should_process_expensively=False
            )
            
        n_lower = cleaned.lower()
        if any(phrase in n_lower for phrase in cls.GENERIC_PHRASES) or n_lower.startswith(("as well as", "with the", "called ", "and listed", "cloud &", "consulting.", "structure chart")):
            return CandidateEntity(
                candidate_id=f"cand_{uuid.uuid4().hex[:8]}",
                raw_name=raw_name,
                normalized_name=cleaned,
                status="Excluded",
                reason="Generic phrase, not a legal entity",
                should_process_expensively=False
            )

        return CandidateEntity(
            candidate_id=f"cand_{uuid.uuid4().hex[:8]}",
            raw_name=raw_name,
            normalized_name=cleaned,
            status="Unknown",
            reason="Candidate retained for downstream verification",
            should_process_expensively=True
        )

    @classmethod
    def fast_extract_entities_from_text(cls, text: str, parent_name: str) -> Tuple[List[Dict[str, Any]], bool]:
        """Fast-path extraction using regex. Retains rejected candidates per Zero-Drop policy."""
        if not text or len(text.strip()) < 10:
            return [], False

        entities = []
        seen_names = set()

        pattern = re.compile(
            r'([A-Z0-9][A-Za-z0-9\&\,\.\-\s]{2,60}?\s+' + cls.SUFFIX_PATTERN + r')',
            re.IGNORECASE
        )
        
        matches = pattern.findall(text)
        for match in matches:
            raw_name = match[0] if isinstance(match, tuple) else match
            clean_name = re.sub(r'\s+', ' ', raw_name).strip()
            
            candidate = cls.classify_entity_candidate(clean_name, parent_name)
            
            clean_key = candidate.normalized_name.lower() if candidate.normalized_name else raw_name.lower()
            if clean_key not in seen_names:
                seen_names.add(clean_key)
                
                # Assign country based on cues
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
                    "candidate_id": candidate.candidate_id,
                    "name": clean_name,
                    "legal_name": clean_name,
                    "country": country,
                    "ownership": "Wholly-owned",
                    "parent": parent_name,
                    "relationship_type": "Direct Subsidiary",
                    "confidence": 0.88 if candidate.should_process_expensively else 0.0,
                    "status": candidate.status,
                    "reason": candidate.reason,
                    "should_process_expensively": candidate.should_process_expensively,
                    "evidences": [{
                        "source_type": "Cost-Optimized Regex Parser",
                        "extracted_text": clean_name
                    }],
                    "notes": candidate.reason
                })

        needs_llm = sum(1 for e in entities if e["should_process_expensively"]) == 0 and len(text) > 200
        logger.info(f"[CostOptimizer] Extracted {len(entities)} candidate entities via Fast Rule Engine. LLM Fallback Needed: {needs_llm}")
        return entities, needs_llm
