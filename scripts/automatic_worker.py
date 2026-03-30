#!/usr/bin/env python3
"""
MODO AUTOMÁTICO: Worker 24/7 descubre leads por sector con rotación eficiente.

Cada ciclo ejecuta 2 queries sectoriales (de 37 totales), pide 3 resultados por query.
Rota entre sectores para cubrir todos en ~18 ciclos (~90 minutos).
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime


# 20 B2B + 17 B2C = 37 sectores con queries optimizadas
SECTOR_QUERIES = [
    # ─── B2B (20 sectores) ────────────────────────────────────────
    ("material eléctrico", 'site:.es "material eléctrico" distribuidor mayorista'),
    ("climatización", 'site:.es climatización fontanería calefacción distribuidor'),
    ("automatización industrial", 'site:.es automatización industrial sensórica control'),
    ("suministros industriales", 'site:.es suministros industriales MRO ferretería industrial'),
    ("materiales construcción", 'site:.es materiales construcción profesional distribuidor'),
    ("packaging", 'site:.es packaging envase embalaje industrial'),
    ("seguridad industrial", 'site:.es EPIs seguridad industrial vestuario técnico'),
    ("laboratorio", 'site:.es laboratorio instrumentación consumibles'),
    ("energías renovables", 'site:.es energías renovables autoconsumo profesional'),
    ("maquinaria industrial", 'site:.es maquinaria industrial recambio'),
    ("horeca", 'site:.es horeca frío comercial lavandería profesional'),
    ("producto sanitario", 'site:.es equipamiento clínico producto sanitario B2B'),
    ("agua y bombeo", 'site:.es bombeo tratamiento agua riego profesional'),
    ("telecom y redes", 'site:.es telecomunicaciones redes cableado seguridad electrónica'),
    ("agroinsumos", 'site:.es agroinsumos riego equipamiento agrícola'),
    ("recambio taller", 'site:.es recambios taller flotas equipamiento'),
    ("intralogística", 'site:.es intralogística almacenaje manutención'),
    ("química industrial", 'site:.es química industrial adhesivos lubricantes'),
    ("madera y carpintería", 'site:.es madera tablero herrajes carpintería profesional'),
    ("protección incendios", 'site:.es protección incendios seguridad técnica'),
    # ─── B2C (17 sectores) ────────────────────────────────────────
    ("clínicas estéticas", 'site:.es clínica estética medicina estética tratamientos'),
    ("hoteles boutique", 'site:.es hotel boutique alojamiento singular'),
    ("odontología", 'site:.es clínica dental implantes odontología'),
    ("inmobiliaria premium", 'site:.es inmobiliaria lujo obra nueva premium'),
    ("restauración", 'site:.es restaurante grupo gastronómico premium'),
    ("arquitectura", 'site:.es estudio arquitectura interiorismo'),
    ("reformas premium", 'site:.es reformas cocinas baños premium'),
    ("moda indie", 'site:.es moda joyería cosmética artesanal'),
    ("ecommerce nicho", 'site:.es tienda online especializada nicho'),
    ("formación privada", 'site:.es academia formación privada cursos'),
    ("coaches", 'site:.es coach consultor experto marca personal'),
    ("automoción premium", 'site:.es detailing wrapping automoción premium'),
    ("eventos bodas", 'site:.es bodas eventos espacios premium'),
    ("centros deportivos", 'site:.es centro deportivo boutique entrenamiento personal'),
    ("abogados", 'site:.es despacho abogados especializado'),
    ("asesorías", 'site:.es asesoría consultoría moderna digital'),
    ("psicología", 'site:.es psicología bienestar premium consulta'),
]

QUERIES_PER_CYCLE = 2
RESULTS_PER_QUERY = 3


class AutomaticWorker:
    """Descubre leads rotando por 37 sectores, 2 queries por ciclo."""

    def __init__(self):
        self.serpapi_key = os.environ.get("SERPAPI_KEY", "")
        self.query_index = 0
        self.processed_domains: set[str] = set()

    def discover_leads(self) -> list[dict]:
        """Ejecuta 2 queries sectoriales y devuelve leads descubiertos."""
        if not self.serpapi_key:
            print("[AutoDiscovery] No SERPAPI_KEY configured, skipping")
            return []

        leads = []
        total = len(SECTOR_QUERIES)
        start = self.query_index % total

        # Seleccionar 2 queries de la rotación
        batch_indices = [(start + i) % total for i in range(QUERIES_PER_CYCLE)]
        batch = [SECTOR_QUERIES[i] for i in batch_indices]
        self.query_index += QUERIES_PER_CYCLE

        for sector, query in batch:
            try:
                params = {
                    "q": query,
                    "api_key": self.serpapi_key,
                    "hl": "es",
                    "gl": "es",
                    "num": RESULTS_PER_QUERY,
                    "engine": "google",
                }
                url = f"https://serpapi.com/search?{urllib.parse.urlencode(params)}"
                request = urllib.request.Request(url, headers={"User-Agent": "WorkspaceBot/1.0"})

                with urllib.request.urlopen(request, timeout=15) as response:
                    data = json.loads(response.read().decode())
                    for result in data.get("organic_results", [])[:RESULTS_PER_QUERY]:
                        domain = self._extract_domain(result.get("link", ""))
                        if domain and domain not in self.processed_domains:
                            leads.append({
                                "domain": domain,
                                "empresa": result.get("title", domain),
                                "sector": sector,
                            })
                            self.processed_domains.add(domain)

                print(f"[AutoDiscovery] [{sector}] {len(data.get('organic_results', []))} results")
            except Exception as exc:
                print(f"[AutoDiscovery] [{sector}] Error: {exc}")

            time.sleep(1)  # Respetar rate limit SerpAPI

        return leads

    def _extract_domain(self, url: str) -> str:
        """Extrae dominio limpio de una URL."""
        if not url:
            return ""
        return url.replace("http://", "").replace("https://", "").split("/")[0].lower()


if __name__ == "__main__":
    worker = AutomaticWorker()
    print(f"Testing discovery with {len(SECTOR_QUERIES)} sector queries...")
    leads = worker.discover_leads()
    print(f"Discovered {len(leads)} leads:")
    for lead in leads:
        print(f"  [{lead['sector']}] {lead['empresa']} → {lead['domain']}")
