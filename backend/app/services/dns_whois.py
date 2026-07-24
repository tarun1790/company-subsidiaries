import asyncio
import httpx
import whois
import dns.resolver
from typing import Optional, Dict, Any, List
from app.core.logging import logger
from app.core.redis_cache import cache_manager

class DNSWhoisResolver:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_whois_info(self, domain: str) -> Dict[str, Any]:
        """Queries WHOIS records for a domain."""
        cache_key = f"whois:{domain}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        info = {
            "registrar": None,
            "org": None,
            "country": None,
            "creation_date": None,
            "emails": None
        }
        
        try:
            # Run in a separate thread since whois is synchronous and blocking
            w = await asyncio.to_thread(whois.whois, domain)
            
            # Extract attributes dynamically to prevent crashes on missing fields
            info["registrar"] = w.get("registrar")
            info["org"] = w.get("org") or w.get("name")
            info["country"] = w.get("country")
            
            dates = w.get("creation_date")
            if isinstance(dates, list):
                info["creation_date"] = str(dates[0])
            elif dates:
                info["creation_date"] = str(dates)
                
            emails = w.get("emails")
            if isinstance(emails, list):
                info["emails"] = ", ".join(emails)
            elif emails:
                info["emails"] = str(emails)
            
            await cache_manager.set_json(cache_key, info, expire=86400 * 7) # Cache for a week
        except Exception as e:
            logger.warning(f"WHOIS query failed for {domain}: {str(e)}")
            # Fallback to an empty dictionary structure
            
        return info

    async def get_dns_records(self, domain: str) -> Dict[str, List[str]]:
        """Queries DNS records (A, MX, TXT, NS) for a domain."""
        cache_key = f"dns:{domain}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        records = {"A": [], "MX": [], "TXT": [], "NS": []}
        loop = asyncio.get_event_loop()
        
        for r_type in records.keys():
            try:
                # Use default DNS resolver
                answers = await loop.run_in_executor(
                    None, 
                    lambda: dns.resolver.resolve(domain, r_type)
                )
                for rdata in answers:
                    if r_type == "MX":
                        records[r_type].append(str(rdata.exchange))
                    else:
                        records[r_type].append(str(rdata))
            except Exception:
                # Graceful pass for missing record types
                pass
                
        await cache_manager.set_json(cache_key, records, expire=86400 * 3) # Cache for 3 days
        return records

    async def get_cert_transparency_domains(self, domain: str) -> List[str]:
        """Queries crt.sh for certificate transparency logs related to the domain."""
        cache_key = f"cert_trans:{domain}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        domains = set()
        url = f"https://crt.sh/?q={domain}&output=json"
        
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                data = response.json()
                for entry in data:
                    common_name = entry.get("common_name", "")
                    name_value = entry.get("name_value", "")
                    
                    for name in [common_name, name_value]:
                        # Handle wildcard characters and split multi-name records
                        for part in name.split("\n"):
                            part = part.replace("*.", "").strip().lower()
                            if part and part.endswith(domain) and len(part) < 100:
                                domains.add(part)
                                
            resolved_domains = list(domains)
            await cache_manager.set_json(cache_key, resolved_domains, expire=86400 * 2) # Cache for 2 days
            return resolved_domains
        except Exception as e:
            logger.warning(f"Certificate Transparency lookup failed for {domain}: {str(e)}")
            return []

    async def get_ssl_cert_info(self, domain: str) -> Dict[str, Any]:
        """Inspects live SSL Certificate Subject Alternative Names (SANs) and Issuer via native Python ssl & socket."""
        cache_key = f"ssl_cert:{domain}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        info = {"san_domains": [], "issuer": None, "subject": None}
        try:
            import ssl
            import socket

            def _fetch_cert():
                ctx = ssl.create_default_context()
                ctx.check_hostname = True
                with socket.create_connection((domain, 443), timeout=5.0) as sock:
                    with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                        return ssock.getpeercert()

            cert = await asyncio.to_thread(_fetch_cert)
            if cert:
                san = cert.get("subjectAltName", ())
                info["san_domains"] = list(set([item[1].lower() for item in san if item[0] == "DNS"]))
                info["issuer"] = str(cert.get("issuer"))
                info["subject"] = str(cert.get("subject"))

            await cache_manager.set_json(cache_key, info, expire=86400 * 7)
        except Exception as e:
            logger.debug(f"Native SSL cert inspection failed for {domain}: {e}")

        return info

resolver = DNSWhoisResolver()
