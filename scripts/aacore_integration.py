#!/usr/bin/env python3
"""
AACORE Integration for WORKSPACE_OFERTAS
========================================
Cuando añades un lead manual → dispara auditoría, enriquecimiento y redacción.
Integra Haiku (auditoría) + Sonnet (redacción) + Hunter.io (contactos).
"""

import asyncio
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from typing import Optional

import anthropic


class AACorePipeline:
    """Pipeline completo: audit → enrich → write → notify."""

    def __init__(self):
        self.anthropic = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.hunter_key = os.environ.get("HUNTER_API_KEY", "")

    # ─── PHASE 1: AUDIT (Haiku) ──────────────────────────────────────────

    def fetch_homepage(self, domain: str, timeout: int = 8) -> str:
        """Descarga HTML de la homepage."""
        for protocol in ["https://", "http://"]:
            try:
                url = f"{protocol}{domain}" if not domain.startswith("http") else domain
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; WorkspaceBot/1.0)",
                        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                    },
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return response.read(15000).decode("utf-8", errors="replace")
            except Exception:
                continue
        return ""

    def html_to_text(self, html: str) -> str:
        """Convierte HTML a texto limpio."""
        cleaned = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = unescape(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()[:10000]

    def audit_with_haiku(self, empresa: str, domain: str, sector: str, html: str) -> dict:
        """Haiku audita la web."""
        if not html:
            return {
                "auditoria_score": 2,
                "prioridad": "baja",
                "auditoria_resumen": "No se pudo acceder a la web",
                "ecommerce_platform": None,
            }

        text = self.html_to_text(html)
        msg = self.anthropic.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system="""Eres auditor de presencia digital para empresas españolas.
Puntúa web de 0-10 basándote en:
1. CLARIDAD (0-2): ¿Se entiende qué hace en 5s?
2. MADUREZ (0-2): ¿Hay pruebas reales de trayectoria?
3. VISUAL (0-2): ¿Diseño moderno o anterior a 2018?
4. REDES (0-2): ¿Contenido con estrategia o abandonadas?
5. CONVERSIÓN (0-2): ¿CTA claro y formulario accesible?

Devuelve JSON:
{
  "auditoria_score": 7,
  "score_detalle": {"claridad": 1, "madurez": 2, "visual": 1, "redes": 2, "conversion": 1},
  "año_web_estimado": 2016,
  "ultimo_post_redes": "hace 2 años",
  "fortalezas": ["..."],
  "problemas": ["..."],
  "oportunidades": ["..."],
  "prioridad": "alta",
  "auditoria_resumen": "...",
  "ecommerce_platform": "prestashop"
}""",
            messages=[
                {
                    "role": "user",
                    "content": f"Empresa: {empresa}\nDominio: {domain}\nSector: {sector}\n\nHTML:\n{text}",
                }
            ],
        )
        try:
            return json.loads(msg.content[0].text)
        except Exception:
            return {
                "auditoria_score": 3,
                "prioridad": "media",
                "auditoria_resumen": "Auditoría incompleta",
            }

    # ─── PHASE 2: ENRICH (Hunter.io) ──────────────────────────────────────

    def find_email_hunter(self, domain: str, first_name: str = "", last_name: str = "") -> dict:
        """Busca email con Hunter.io."""
        if not self.hunter_key:
            return {"email": None, "confidence": 0}

        try:
            params = {
                "domain": domain,
                "api_key": self.hunter_key,
            }
            if first_name and last_name:
                params["first_name"] = first_name
                params["last_name"] = last_name
                url = "https://api.hunter.io/v2/email-finder"
            else:
                url = "https://api.hunter.io/v2/domain-search"
                params["limit"] = "5"

            query = urllib.parse.urlencode(params)
            request = urllib.request.Request(
                f"{url}?{query}",
                headers={"User-Agent": "WorkspaceBot/1.0"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())
                if "data" in data:
                    if isinstance(data["data"], dict):  # email-finder
                        return {
                            "email": data["data"].get("email"),
                            "confidence": data["data"].get("score", 0),
                        }
                    elif isinstance(data["data"], list):  # domain-search
                        if data["data"]:
                            return {
                                "email": data["data"][0].get("value"),
                                "confidence": 80,
                            }
        except Exception:
            pass
        return {"email": None, "confidence": 0}

    def enrich_contact(self, empresa: str, domain: str) -> dict:
        """Enriquece con contacto directo."""
        email_result = self.find_email_hunter(domain)
        return {
            "contacto_email": email_result.get("email"),
            "contacto_email_confianza": "verificado"
            if email_result.get("confidence", 0) > 70
            else "estimado",
            "enricher_status": "enriched",
        }

    # ─── PHASE 3: WRITE (Sonnet) ─────────────────────────────────────────

    def write_outreach_sonnet(
        self,
        empresa: str,
        domain: str,
        sector: str,
        auditoria_resumen: str,
        contacto_nombre: str = "",
        ruta: str = "ES_B2B",
    ) -> dict:
        """Sonnet redacta email + LinkedIn."""
        context = {
            "empresa": empresa,
            "domain": domain,
            "sector": sector,
            "auditoria_resumen": auditoria_resumen,
            "contacto_nombre": contacto_nombre,
        }

        msg = self.anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            system="""Eres redactor de outreach B2B para Aitor Sánchez Palacios,
freelance audiovisual y web en Manresa (España).

Sobre Aitor: vídeo corporativo, diseño web con IA, contenido digital.
Precio: 2.000-3.000€ proyecto | 600-1.200€/mes retainer.

TONO: Directo, sin relleno, 1 detalle real, CTA bajo compromiso.
Máx 5 frases email, 3 frases LinkedIn.

Devuelve JSON:
{
  "asunto_email": "...",
  "email_frio": "...",
  "mensaje_linkedin": "..."
}""",
            messages=[
                {
                    "role": "user",
                    "content": f"Genera outreach para:\n\n{json.dumps(context, ensure_ascii=False)}",
                }
            ],
        )
        try:
            return json.loads(msg.content[0].text)
        except Exception:
            return {
                "asunto_email": f"Renovar presencia digital de {empresa}",
                "email_frio": f"Hola, he visto {empresa} y puedo ayudarte a mejorar tu presencia online.",
                "mensaje_linkedin": f"Trabajo con empresas como {empresa} para modernizar su presencia digital.",
            }

    # ─── ORCHESTRATOR ────────────────────────────────────────────────────

    def process_lead(
        self,
        empresa: str,
        domain: str,
        sector: str = "general",
        contacto_nombre: str = "",
        ruta: str = "ES_B2B",
    ) -> dict:
        """Procesa un lead manual: auditoría → enriquecimiento → redacción."""

        # Fase 1: Audit
        html = self.fetch_homepage(domain)
        audit = self.audit_with_haiku(empresa, domain, sector, html)
        audit_score = audit.get("auditoria_score", 0)

        if audit_score < 4:
            return {
                "status": "low_score",
                "audit": audit,
                "message": f"Score muy bajo ({audit_score}/10). No se generará propuesta.",
            }

        # Fase 2: Enrich
        enrich = self.enrich_contact(empresa, domain)

        # Fase 3: Write
        outreach = self.write_outreach_sonnet(
            empresa, domain, sector, audit.get("auditoria_resumen", ""), contacto_nombre, ruta
        )

        return {
            "status": "success",
            "empresa": empresa,
            "domain": domain,
            "sector": sector,
            "auditoria_score": audit_score,
            "audit": audit,
            "contacto_email": enrich.get("contacto_email"),
            "asunto_email": outreach.get("asunto_email"),
            "email_frio": outreach.get("email_frio"),
            "mensaje_linkedin": outreach.get("mensaje_linkedin"),
        }


# ─── ASYNC WRAPPER (para integración con workspace_core) ────────────────

async def process_lead_async(
    empresa: str, domain: str, sector: str = "general", contacto_nombre: str = "", ruta: str = "ES_B2B"
) -> dict:
    """Wrapper async para usar en workspace_core."""
    pipeline = AACorePipeline()
    return pipeline.process_lead(empresa, domain, sector, contacto_nombre, ruta)


if __name__ == "__main__":
    # Test local
    import sys

    if len(sys.argv) > 1:
        domain = sys.argv[1]
        empresa = sys.argv[2] if len(sys.argv) > 2 else domain.split(".")[0].title()
        pipeline = AACorePipeline()
        result = pipeline.process_lead(empresa, domain)
        print(json.dumps(result, indent=2, ensure_ascii=False))
