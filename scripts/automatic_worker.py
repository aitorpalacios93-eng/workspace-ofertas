#!/usr/bin/env python3
"""
MODO AUTOMÁTICO: Worker 24/7 descubre leads + procesa → avisa SOLO si feedback positivo.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

from aacore_integration import AACorePipeline
from workspace_notifications import TelegramNotifier


class AutomaticWorker:
    """Descubre leads automáticamente y procesa flujo completo."""

    def __init__(self):
        self.pipeline = AACorePipeline()
        self.telegram = TelegramNotifier()
        self.serpapi_key = os.environ.get("SERPAPI_KEY", "7697bccd691d52dd9386168e15134f983fada5e68d6d427a46a3d58e5d53afa8")

        # Queries para descubrir leads automáticamente
        self.discovery_queries = [
            'site:.es "desde 2010" OR "desde 2011" OR "desde 2012" tienda',
            'site:.es "fundada en 2009" OR "fundada en 2010" tienda online',
            'site:.es ferretería industrial online mayorista "años de experiencia"',
            'site:.es "material eléctrico" distribuidor online "desde 2"',
            'site:.es repuestos industriales online "años experiencia" España',
        ]

        self.processed_domains = set()
        self.feedback_cache = {}  # domain -> {"feedback": "positive/negative", "timestamp": "..."}

    def discover_leads(self) -> list[dict]:
        """Busca leads automáticamente con SerpAPI."""
        leads = []

        for query in self.discovery_queries:
            try:
                params = {
                    "q": query,
                    "api_key": self.serpapi_key,
                    "hl": "es",
                    "gl": "es",
                    "num": 5,
                    "engine": "google",
                }
                url = f"https://serpapi.com/search?{urllib.parse.urlencode(params)}"
                request = urllib.request.Request(url, headers={"User-Agent": "WorkspaceBot/1.0"})

                with urllib.request.urlopen(request, timeout=15) as response:
                    data = json.loads(response.read().decode())
                    for result in data.get("organic_results", [])[:3]:
                        domain = self._extract_domain(result.get("link", ""))
                        if domain and domain not in self.processed_domains:
                            leads.append({
                                "domain": domain,
                                "empresa": result.get("title", domain),
                                "sector": "industrial/comercial",
                            })
                            self.processed_domains.add(domain)
            except Exception:
                pass

            time.sleep(1)  # Respetar rate limit SerpAPI

        return leads

    def _extract_domain(self, url: str) -> str:
        """Extrae dominio limpio de una URL."""
        if not url:
            return ""
        url = url.replace("http://", "").replace("https://", "").split("/")[0].lower()
        return url if url.startswith(("www.", "")) else url

    def process_lead_with_feedback_gate(self, lead: dict) -> bool:
        """
        Procesa lead automático.
        Retorna True si hay feedback positivo (para notificar por Telegram).
        """
        domain = lead["domain"]

        # Saltar si ya tenemos feedback sobre este dominio
        if domain in self.feedback_cache:
            return False

        # Procesar con pipeline AACORE
        result = self.pipeline.process_lead(
            empresa=lead["empresa"],
            domain=domain,
            sector=lead.get("sector", "general"),
        )

        if result["status"] != "success":
            return False

        score = result.get("auditoria_score", 0)

        # SOLO notificar si:
        # 1. Score es bueno (>= 70)
        # 2. Tenemos email (para contactar)
        # 3. Propuesta está lista

        has_email = bool(result.get("contacto_email"))
        has_email_copy = bool(result.get("email_frio"))

        if score >= 70 and has_email and has_email_copy:
            # ✅ FEEDBACK POSITIVO: propuesta lista y contacto disponible
            self._notify_automatic_lead(result)
            self.feedback_cache[domain] = {
                "feedback": "positive",
                "timestamp": datetime.now().isoformat(),
            }
            return True

        return False

    def _notify_automatic_lead(self, result: dict) -> None:
        """Notifica que encontramos un lead automático con propuesta lista."""
        msg = f"""
🤖 LEAD AUTOMÁTICO LISTO

Empresa: {result['empresa']}
Dominio: {result['domain']}
Score: {result['auditoria_score']}/10

✅ Propuesta generada
✅ Email contacto disponible
✅ Listo para enviar

Entra en el dashboard para revisar y enviar.
        """
        self.telegram.send(msg)

    def run_once(self) -> dict:
        """Ejecuta un ciclo de descubrimiento + procesamiento."""
        leads = self.discover_leads()
        processed = 0
        positive_feedback = 0

        for lead in leads:
            try:
                if self.process_lead_with_feedback_gate(lead):
                    positive_feedback += 1
                processed += 1
            except Exception as e:
                print(f"Error procesando {lead['domain']}: {e}")

        return {
            "timestamp": datetime.now().isoformat(),
            "discovered": len(leads),
            "processed": processed,
            "positive_feedback": positive_feedback,
        }

    def run_continuous(self, interval_seconds: int = 300) -> None:
        """Corre continuamente (cada 5 min por defecto)."""
        print(f"Worker automático iniciado. Ciclo cada {interval_seconds}s")

        while True:
            try:
                result = self.run_once()
                print(f"[{result['timestamp']}] Descubiertos: {result['discovered']}, "
                      f"Procesados: {result['processed']}, "
                      f"Positivos: {result['positive_feedback']}")
            except Exception as e:
                print(f"Error en ciclo: {e}")

            time.sleep(interval_seconds)


if __name__ == "__main__":
    worker = AutomaticWorker()
    worker.run_continuous(interval_seconds=300)  # Cada 5 minutos
