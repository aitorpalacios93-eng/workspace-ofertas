#!/usr/bin/env python3
"""Core engine for the workspace dashboard and automatic worker."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

from workspace_notifications import TelegramNotifier
from workspace_state import WorkspaceState, now_iso


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

LOCAL_SECTOR_HINTS = {
    "clinic",
    "clinica",
    "dental",
    "restaurant",
    "restaurante",
    "medspa",
    "med spa",
    "beauty",
    "salon",
    "peluqueria",
    "gimnasio",
    "gym",
    "estetica",
    "hotel",
    "school",
    "academia",
}

B2B_SECTOR_HINTS = {
    "industrial",
    "industry",
    "engineering",
    "ingenieria",
    "logistics",
    "logistica",
    "distribution",
    "distribucion",
    "consulting",
    "consultoria",
    "manufacturing",
    "fabricacion",
    "technical",
    "tecnico",
    "b2b",
}

US_EXCLUDED_V1 = {"legal", "real estate brokerage", "mortgage", "tax", "compliance"}

ROUTE_META = {
    "ES_LOCAL": {"currency": "EUR", "language": "es"},
    "ES_B2B": {"currency": "EUR", "language": "es"},
    "US_HISPANIC": {"currency": "USD", "language": "detect"},
}

OFFER_CATALOG = {
    "ES_LOCAL": {
        "entry": {
            "name": "Activacion Local",
            "price": "490EUR - 1200EUR",
            "promise": "Poner en marcha una maquina minima para generar mas llamadas, reservas o formularios.",
            "deliverables": [
                "Claridad de oferta y CTA principal",
                "Mejora rapida de landing, perfil o pagina clave",
                "Refuerzo de senales de confianza y seguimiento basico",
            ],
        },
        "core": {
            "name": "Sistema de Clientes",
            "price": "1500EUR - 4000EUR setup + 600EUR - 1500EUR/mes",
            "promise": "Convertir visibilidad actual en flujo comercial mas constante.",
            "deliverables": [
                "Oferta clara y mensaje comercial",
                "Landing o mejora web orientada a conversion",
                "Contenido y distribucion basica con seguimiento",
            ],
        },
        "addons": {
            "review_engine": "Review Engine",
            "creator_led_content": "Creator-led Content",
        },
    },
    "ES_B2B": {
        "entry": {
            "name": "Diagnostico Comercial Digital",
            "price": "1200EUR - 2500EUR",
            "promise": "Detectar la brecha comercial digital y priorizar quick wins accionables.",
            "deliverables": [
                "Diagnostico ejecutivo con evidencia",
                "Mapa de oportunidades y quick wins",
                "Preguntas clave para direccion comercial",
            ],
        },
        "core": {
            "name": "Sistema Comercial Digital",
            "price": "3500EUR - 9000EUR setup + 900EUR - 2500EUR/mes",
            "promise": "Pasar de presencia pasiva a sistema que da credibilidad y abre conversaciones.",
            "deliverables": [
                "Posicionamiento y mensaje comercial",
                "Upgrade de web o landing clave",
                "Activos de autoridad y estructura de seguimiento",
                "Plan de iteracion comercial",
            ],
        },
        "addons": {
            "authority_video": "Authority Video Asset",
            "follow_up_engine": "Follow-up Engine",
        },
    },
    "US_HISPANIC": {
        "entry": {
            "name": "Fast Trust Activation",
            "price": "$1000 - $2500",
            "promise": "Elevate trust and conversion fast without jumping into a large retainer.",
            "deliverables": [
                "Trust-gap audit and quick fixes",
                "Page or profile upgrade",
                "Review and response path improvements",
            ],
        },
        "core": {
            "name": "Client Acquisition System",
            "price": "$3000 - $8000 setup + $1500 - $4000/mo",
            "promise": "Turn trust, visibility and follow-up into booked calls and signed clients.",
            "deliverables": [
                "Offer and message clarity",
                "Landing or site conversion upgrade",
                "Trust assets and follow-up system",
            ],
        },
        "addons": {
            "review_engine": "Review and Response Engine",
            "creator_led_content": "Creator-led Content",
        },
    },
}


AACORE_B2B_PLAYBOOK = {
    "frontend_elevation": {
        "label": "Elevacion Web B2B",
        "name": "Elevacion Web B2B",
        "price": "760EUR - 1200EUR auditoria tecnica + 8000EUR - 12000EUR frontend",
        "promise": "Renovar la percepcion y la conversion del escaparate digital sin tocar el motor del negocio.",
        "deliverables": [
            "Auditoria tecnica corta para clasificar riesgo real",
            "Rediseño de home, categorias y fichas de alta conversion",
            "Refuerzo de trust signals, prueba social y CTA B2B",
            "Roadmap de implementacion con fases cerradas",
        ],
        "addons": ["Authority Video Asset", "Follow-up Engine"],
    },
    "authority_engine": {
        "label": "Motor de Autoridad B2B",
        "name": "Motor de Autoridad B2B",
        "price": "1450EUR - 4050EUR/mes",
        "promise": "Convertir el conocimiento tecnico de la empresa en contenido de autoridad que capture confianza y demanda.",
        "deliverables": [
            "Research sectorial y arquitectura editorial",
            "Sesiones guiadas de extraccion de conocimiento tecnico",
            "Edicion multi-formato con subtitulos, motion y adaptaciones",
            "Plan de distribucion y seguimiento de autoridad",
        ],
        "addons": ["Creator-led Content", "Follow-up Engine"],
    },
    "dual_system": {
        "label": "Sistema Dual: Autoridad B2B y Conversion",
        "name": "Sistema Dual: Autoridad B2B y Conversion",
        "price": "760EUR - 1200EUR auditoria + 8000EUR - 12000EUR frontend + 1450EUR - 4050EUR/mes contenido",
        "promise": "Activar a la vez la elevacion web y el motor de autoridad para capturar confianza, conversion y liderazgo.",
        "deliverables": [
            "Auditoria tecnica y plan de choque comercial",
            "Elevacion web orientada a conversion B2B",
            "Motor de contenido audiovisual tecnico recurrente",
            "Roadmap coordinado de 90 dias con doble palanca",
        ],
        "addons": ["Follow-up Engine", "Review Engine"],
    },
}


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "prospect"


def ensure_scheme(url: str) -> str:
    if not url:
        return url
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def fetch_text(url: str, timeout: int = 12) -> tuple[str, str | None]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = response.read(600000).decode("utf-8", errors="replace")
            return content, response.geturl()
    except (urllib.error.URLError, ValueError):
        return "", None


def html_to_text(html: str) -> str:
    cleaned = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def match_first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return unescape(match.group(1).strip()) if match else ""


def collect_matches(pattern: str, text: str, limit: int = 5) -> list[str]:
    return [
        unescape(item.strip())
        for item in re.findall(pattern, text, flags=re.IGNORECASE)[:limit]
        if item.strip()
    ]


def discover_website(company_name: str, country: str) -> tuple[str | None, list[str]]:
    if not company_name:
        return None, []

    query = company_name
    if country == "ES":
        query += " Espana sitio oficial"
    elif country == "US":
        query += " official website"
    else:
        query += " official website"

    search_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
        {"q": query}
    )
    html, _ = fetch_text(search_url, timeout=10)
    if not html:
        return None, []

    hrefs = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"', html, flags=re.IGNORECASE
    )
    candidates: list[str] = []
    for href in hrefs:
        parsed = urllib.parse.urlparse(href)
        final_url = href
        if "duckduckgo.com" in parsed.netloc:
            qs = urllib.parse.parse_qs(parsed.query)
            final_url = qs.get("uddg", [href])[0]
        final_url = urllib.parse.unquote(final_url)
        if any(
            domain in final_url
            for domain in [
                "linkedin.com",
                "instagram.com",
                "facebook.com",
                "youtube.com",
                "tiktok.com",
                "yelp.com",
            ]
        ):
            continue
        if final_url not in candidates:
            candidates.append(final_url)

    return (candidates[0] if candidates else None), candidates[:5]


def extract_site_signals(html: str) -> dict[str, Any]:
    text = html_to_text(html)
    lowered = text.lower()
    title = match_first(r"<title[^>]*>([^<]{1,180})</title>", html)
    meta_description = match_first(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']{1,250})', html
    )
    if not meta_description:
        meta_description = match_first(
            r'<meta[^>]*content=["\']([^"\']{1,250})["\'][^>]*name=["\']description["\']',
            html,
        )

    socials = {}
    for name, domain in {
        "linkedin": "linkedin.com",
        "instagram": "instagram.com",
        "facebook": "facebook.com",
        "youtube": "youtube.com",
        "tiktok": "tiktok.com",
    }.items():
        match = re.search(
            rf'https?://[^"\'\s>]*{re.escape(domain)}[^"\'\s<]*',
            html,
            flags=re.IGNORECASE,
        )
        if match:
            socials[name] = match.group(0)

    h1 = match_first(r"<h1[^>]*>([^<]{1,180})</h1>", html)
    h2s = collect_matches(r"<h2[^>]*>([^<]{1,180})</h2>", html, limit=5)
    cta_count = len(
        re.findall(
            r"book|call now|contact|request|demo|quote|reserv|whatsapp|schedule|get started|presupuesto|solicita|contacta",
            lowered,
        )
    )
    forms_count = len(re.findall(r"<form", html, flags=re.IGNORECASE))
    review_mentions = len(
        re.findall(
            r"review|testimonial|trustpilot|rese[ñn]a|opinion|google reviews", lowered
        )
    )
    whatsapp_present = "whatsapp" in lowered or "wa.me/" in lowered
    booking_present = any(
        term in lowered
        for term in ["book now", "schedule", "reserva", "reservar", "appointment"]
    )
    bilingual_signal = any(
        term in lowered
        for term in ["espanol", "spanish", "hablamos espanol", "se habla espanol"]
    )
    b2b_signal = any(
        term in lowered
        for term in [
            "distribuidor",
            "industrial",
            "engineering",
            "fabrication",
            "logistics",
            "solutions for businesses",
            "empresa",
            "empresas",
        ]
    )
    video_present = any(
        term in html.lower()
        for term in ["youtube.com/embed", "vimeo.com", "<video", "shorts"]
    )

    return {
        "title": title,
        "meta_description": meta_description,
        "h1": h1,
        "h2s": h2s,
        "text_sample": text[:1400],
        "socials_detected": socials,
        "cta_count": cta_count,
        "forms_count": forms_count,
        "review_mentions": review_mentions,
        "whatsapp_present": whatsapp_present,
        "booking_present": booking_present,
        "bilingual_signal": bilingual_signal,
        "b2b_signal": b2b_signal,
        "video_present": video_present,
        "word_count": len(text.split()),
    }


def detect_language(site_text: str, route: str | None = None) -> str:
    lowered = site_text.lower()
    spanish_hits = sum(
        lowered.count(token)
        for token in [
            " para ",
            " con ",
            " empresa ",
            " clientes ",
            " nosotros ",
            " reserv",
            " contacto",
            " presupuesto",
        ]
    )
    english_hits = sum(
        lowered.count(token)
        for token in [" the ", " and ", "book", "call now", "contact us", "services"]
    )
    if route in {"ES_LOCAL", "ES_B2B"}:
        return "es"
    if spanish_hits >= english_hits:
        return "es"
    return "en"


def choose_route(
    prospect: dict[str, Any],
    site_signals: dict[str, Any],
    discovered_website: str | None,
) -> tuple[str, list[str], bool]:
    country = prospect.get("country") or "UNKNOWN"
    sector = (prospect.get("sector") or "").lower()
    text = (
        (site_signals.get("title") or "")
        + " "
        + (site_signals.get("meta_description") or "")
        + " "
        + (site_signals.get("text_sample") or "")
    ).lower()
    reasons: list[str] = []
    excluded = False

    for blocked in US_EXCLUDED_V1:
        if blocked in sector or blocked in text:
            excluded = True

    local_hint = (
        any(term in sector for term in LOCAL_SECTOR_HINTS)
        or site_signals.get("booking_present")
        or site_signals.get("whatsapp_present")
    )
    b2b_hint = any(term in sector for term in B2B_SECTOR_HINTS) or site_signals.get(
        "b2b_signal"
    )

    if country == "US":
        reasons.append("Pais US detectado o indicado")
        if site_signals.get("bilingual_signal"):
            reasons.append("Senal bilingue o hispana detectada")
        if discovered_website:
            reasons.append("Website descubierto o confirmado")
        return "US_HISPANIC", reasons, excluded

    if country == "ES" or (discovered_website and discovered_website.endswith(".es")):
        if local_hint and not b2b_hint:
            reasons.append("Senales locales y de captacion rapida")
            return "ES_LOCAL", reasons, excluded
        reasons.append("Senales de empresa B2B o no-local clara")
        return "ES_B2B", reasons, excluded

    if local_hint:
        reasons.append(
            "Por defecto se asume ruta local por senales de reserva o WhatsApp"
        )
        return "ES_LOCAL", reasons, excluded

    reasons.append("Fallback a ruta B2B por falta de senales locales")
    return "ES_B2B", reasons, excluded


def fit_band(score: int) -> str:
    if score <= 39:
        return "no_proposal"
    if score <= 64:
        return "quickwins_only"
    if score <= 79:
        return "full_proposal"
    return "high_priority"


def calculate_fit(
    route: str, prospect: dict[str, Any], site_signals: dict[str, Any], excluded: bool
) -> dict[str, Any]:
    website_available = bool(
        prospect.get("website") or prospect.get("discovered_website")
    )
    trust_gap = 0
    if website_available:
        trust_gap += 6 if not site_signals.get("title") else 0
        trust_gap += 5 if not site_signals.get("meta_description") else 0
        trust_gap += 4 if site_signals.get("review_mentions", 0) == 0 else 0
        trust_gap += 5 if site_signals.get("cta_count", 0) == 0 else 0
    else:
        trust_gap = 8
    trust_gap = min(trust_gap, 20)

    demand_signal = 0
    demand_signal += 6 if site_signals.get("cta_count", 0) > 0 else 0
    demand_signal += 5 if site_signals.get("forms_count", 0) > 0 else 0
    demand_signal += 4 if site_signals.get("whatsapp_present") else 0
    demand_signal += (
        5
        if site_signals.get("socials_detected")
        or any(prospect.get("socials", {}).values())
        else 0
    )

    speed_to_value = 8 if route in {"ES_LOCAL", "US_HISPANIC"} else 5
    speed_to_value += 5 if website_available else 0
    speed_to_value += 4 if site_signals.get("cta_count", 0) <= 2 else 0
    speed_to_value += 3 if prospect.get("sector") else 0
    speed_to_value = min(speed_to_value, 20)

    commercial_urgency = 0
    commercial_urgency += 5 if trust_gap >= 8 else 0
    commercial_urgency += 5 if site_signals.get("word_count", 0) < 180 else 0
    commercial_urgency += 5 if not website_available else 0

    delivery_fit = 0
    delivery_fit += (
        6 if route == "ES_B2B" and (prospect.get("sector") or "").lower() else 0
    )
    delivery_fit += (
        8
        if route == "ES_LOCAL"
        and (
            site_signals.get("booking_present") or site_signals.get("whatsapp_present")
        )
        else 0
    )
    delivery_fit += (
        8 if route == "US_HISPANIC" and prospect.get("country") == "US" else 0
    )
    delivery_fit += (
        7
        if any(prospect.get("socials", {}).values())
        or site_signals.get("socials_detected")
        else 0
    )
    delivery_fit = min(delivery_fit, 15)

    evidence_density = 0
    evidence_density += 2 if prospect.get("company_name") else 0
    evidence_density += 2 if prospect.get("sector") else 0
    evidence_density += 2 if website_available else 0
    evidence_density += 2 if site_signals.get("title") else 0
    evidence_density += 2 if site_signals.get("text_sample") else 0

    parts = {
        "trust_gap": min(trust_gap, 20),
        "demand_signal": min(demand_signal, 20),
        "speed_to_value": min(speed_to_value, 20),
        "commercial_urgency": min(commercial_urgency, 15),
        "delivery_fit": min(delivery_fit, 15),
        "evidence_density": min(evidence_density, 10),
    }

    score = sum(parts.values())
    if excluded:
        score = min(score, 35)
    return {"score": score, "band": fit_band(score), "parts": parts}


def detect_b2b_strategic_angle(
    prospect: dict[str, Any], site_signals: dict[str, Any]
) -> dict[str, str]:
    sector = (prospect.get("sector") or "").lower()
    text = (
        (site_signals.get("title") or "")
        + " "
        + (site_signals.get("meta_description") or "")
        + " "
        + (site_signals.get("text_sample") or "")
    ).lower()

    technical_b2b = any(
        term in sector or term in text
        for term in [
            "industrial",
            "hvac",
            "refriger",
            "engineering",
            "distribution",
            "distrib",
            "technical",
            "tecnico",
            "spare parts",
            "repuestos",
            "manufact",
            "logistic",
        ]
    )

    web_gap = 0
    web_gap += 2 if not site_signals.get("title") else 0
    web_gap += 2 if not site_signals.get("meta_description") else 0
    web_gap += 2 if not site_signals.get("h1") else 0
    web_gap += 2 if site_signals.get("cta_count", 0) == 0 else 0
    web_gap += 1 if site_signals.get("review_mentions", 0) == 0 else 0
    web_gap += 1 if site_signals.get("forms_count", 0) == 0 else 0

    authority_gap = 0
    authority_gap += 2 if not site_signals.get("video_present") else 0
    authority_gap += (
        2
        if not site_signals.get("socials_detected") and not prospect.get("socials")
        else 0
    )
    authority_gap += 2 if site_signals.get("review_mentions", 0) == 0 else 0
    authority_gap += 2 if technical_b2b else 0
    authority_gap += 1 if site_signals.get("word_count", 0) < 250 else 0

    if technical_b2b and web_gap >= 6 and authority_gap >= 6:
        return {
            "code": "dual_system",
            "label": AACORE_B2B_PLAYBOOK["dual_system"]["label"],
            "reason": "Brecha simultanea de conversion web y ausencia de autoridad tecnica visible.",
        }
    if web_gap >= authority_gap:
        return {
            "code": "frontend_elevation",
            "label": AACORE_B2B_PLAYBOOK["frontend_elevation"]["label"],
            "reason": "La prioridad parece estar en elevar percepcion, UX y conversion del escaparate B2B.",
        }
    return {
        "code": "authority_engine",
        "label": AACORE_B2B_PLAYBOOK["authority_engine"]["label"],
        "reason": "La mayor oportunidad esta en convertir know-how tecnico en autoridad audiovisual recurrente.",
    }


def render_template(template_text: str, context: dict[str, str]) -> str:
    output = template_text
    for key, value in context.items():
        output = output.replace("{{" + key + "}}", value)
    return output


def safe_value(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


class WorkspaceEngine:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.templates_dir = workspace_root / "templates"
        self.tmp_dir = workspace_root / ".tmp"
        self.state = WorkspaceState(workspace_root)
        self.notifier = TelegramNotifier()
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def _artifact_dir(self, prospect_id: str) -> Path:
        path = self.tmp_dir / "prospects" / prospect_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_text(self, path: Path, content: str) -> None:
        path.write_text(content.strip() + "\n", encoding="utf-8")

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )

    def create_prospect(self, payload: dict[str, Any]) -> dict[str, Any]:
        socials = payload.get("socials") or {}
        clean_socials = {
            key: ensure_scheme(value.strip())
            for key, value in socials.items()
            if value and value.strip()
        }
        record = self.state.create_prospect(
            {
                "company_name": payload.get("company_name", ""),
                "website": ensure_scheme(payload.get("website", "").strip()),
                "country": payload.get("country", ""),
                "sector": payload.get("sector", ""),
                "notes": payload.get("notes", ""),
                "socials": clean_socials,
                "recommended": bool(payload.get("recommended")),
                "recommendation_note": payload.get("recommendation_note", ""),
                "route_override": payload.get("route_override")
                if payload.get("route_override") in ROUTE_META
                else None,
            }
        )
        recommendation_suffix = " [RECOMENDACION]" if record.get("recommended") else ""
        self.state.add_event(
            event_type="prospect_created",
            message=f"Nuevo prospecto en cola: {record['company_name'] or record['website'] or record['id']}{recommendation_suffix}",
            prospect_id=record["id"],
            telegram_relevant=bool(record.get("recommended")),
        )
        if record.get("recommended"):
            self._notify(
                f"WORKSPACE_OFERTAS\nNuevo prospecto recomendado: {record['company_name'] or record['website'] or record['id']}"
            )
        return record

    def update_prospect_controls(
        self, prospect_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        current = self.state.get_prospect(prospect_id)
        if not current:
            return None

        route_override = payload.get("route_override") or None
        if route_override not in ROUTE_META:
            route_override = None

        patch = {
            "recommended": bool(payload.get("recommended")),
            "recommendation_note": payload.get("recommendation_note", "").strip(),
            "route_override": route_override,
        }

        if payload.get("requeue"):
            patch.update(
                {
                    "status": "queued",
                    "proposal_ready": False,
                    "decision_mode": "manual_review_pending",
                }
            )

        updated = self.state.update_prospect(prospect_id, patch)
        if not updated:
            return None

        self.state.add_event(
            event_type="manual_controls_updated",
            message=f"Decision manual actualizada para {updated.get('company_name') or updated.get('website') or prospect_id}.",
            prospect_id=prospect_id,
            telegram_relevant=bool(updated.get("recommended")),
            data={
                "recommended": updated.get("recommended"),
                "route_override": updated.get("route_override"),
                "requeue": bool(payload.get("requeue")),
            },
        )
        return updated

    def add_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = self.state.add_message(payload)
        self.state.add_event(
            event_type="message_received",
            message="Mensaje entrante registrado para respuesta automatica.",
            prospect_id=message.get("prospect_id"),
            telegram_relevant=True,
        )
        self._notify("Nuevo mensaje entrante registrado en WORKSPACE_OFERTAS.")
        return message

    def _notify(self, text: str) -> None:
        self.notifier.send(text)

    def dashboard(self) -> dict[str, Any]:
        prospects = self.state.list_records("prospects")
        events = self.state.list_records("events")[:40]
        jobs = self.state.list_records("jobs")[:30]
        messages = self.state.list_records("messages")[:30]
        summary = {
            "total_prospects": len(prospects),
            "queued": sum(1 for item in prospects if item.get("status") == "queued"),
            "proposal_ready": sum(
                1 for item in prospects if item.get("proposal_ready")
            ),
            "outreach_ready": sum(
                1 for item in prospects if item.get("aacore_status") == "enriched"
            ),
            "recommended": sum(1 for item in prospects if item.get("recommended")),
            "needs_reply": sum(
                1
                for item in messages
                if item.get("direction") == "inbound" and item.get("status") == "new"
            ),
            "telegram_configured": self.notifier.configured,
        }
        return {
            "summary": summary,
            "prospects": prospects,
            "events": events,
            "jobs": jobs,
            "messages": messages,
            "settings": self.state.read_settings(),
        }

    def prospect_detail(self, prospect_id: str) -> dict[str, Any] | None:
        prospect = self.state.get_prospect(prospect_id)
        if not prospect:
            return None

        artifact_dir = self._artifact_dir(prospect_id)
        artifacts = []
        for path in sorted(artifact_dir.glob("*")):
            if path.is_file() and path.suffix in {".md", ".json"}:
                artifacts.append(
                    {"name": path.name, "content": path.read_text(encoding="utf-8")}
                )

        events = [
            event
            for event in self.state.list_records("events")
            if event.get("prospect_id") == prospect_id
        ][:30]
        messages = [
            item
            for item in self.state.list_records("messages")
            if item.get("prospect_id") == prospect_id
        ][:30]
        return {
            "prospect": prospect,
            "artifacts": artifacts,
            "events": events,
            "messages": messages,
        }

    def run_once(self) -> dict[str, Any]:
        pending_messages = self.state.list_pending_messages()
        if pending_messages:
            message = pending_messages[0]
            self._process_message(message)
            return {"processed": True, "kind": "message", "id": message["id"]}

        pending_prospects = self.state.list_pending_prospects()
        if pending_prospects:
            prospect = pending_prospects[0]
            self._process_prospect(prospect)
            return {"processed": True, "kind": "prospect", "id": prospect["id"]}

        return {"processed": False}

    def _process_prospect(self, prospect: dict[str, Any]) -> None:
        job = self.state.create_job("prospect_process", prospect_id=prospect["id"])
        prospect_id = prospect["id"]
        company_label = (
            prospect.get("company_name") or prospect.get("website") or prospect_id
        )
        self.state.update_prospect(prospect_id, {"status": "researching"})
        self.state.add_event(
            event_type="prospect_processing",
            message=f"Analizando {company_label}",
            prospect_id=prospect_id,
        )

        try:
            artifact_dir = self._artifact_dir(prospect_id)
            website = prospect.get("website") or ""
            discovered_candidates: list[str] = []
            if not website and prospect.get("company_name"):
                discovered_website, discovered_candidates = discover_website(
                    prospect["company_name"], prospect.get("country", "UNKNOWN")
                )
                if discovered_website:
                    website = ensure_scheme(discovered_website)
                    self.state.add_event(
                        event_type="website_discovered",
                        message=f"Website descubierto para {company_label}: {website}",
                        prospect_id=prospect_id,
                    )
                self.state.update_prospect(prospect_id, {"discovered_website": website})

            html = ""
            final_url = None
            if website:
                html, final_url = fetch_text(website)
            site_signals = (
                extract_site_signals(html)
                if html
                else {
                    "title": "",
                    "meta_description": "",
                    "h1": "",
                    "h2s": [],
                    "text_sample": "",
                    "socials_detected": {},
                    "cta_count": 0,
                    "forms_count": 0,
                    "review_mentions": 0,
                    "whatsapp_present": False,
                    "booking_present": False,
                    "bilingual_signal": False,
                    "b2b_signal": False,
                    "video_present": False,
                    "word_count": 0,
                }
            )

            merged_socials = dict(prospect.get("socials", {}))
            merged_socials.update(site_signals.get("socials_detected", {}))
            route, reasons, excluded = choose_route(
                prospect, site_signals, final_url or website
            )
            if prospect.get("route_override") in ROUTE_META:
                route = prospect["route_override"]
                reasons.insert(0, f"Ruta forzada manualmente a {route}")

            language = detect_language(site_signals.get("text_sample", ""), route)
            fit = calculate_fit(
                route,
                {**prospect, "discovered_website": final_url or website},
                site_signals,
                excluded,
            )
            currency = ROUTE_META[route]["currency"]
            strategic_angle = (
                detect_b2b_strategic_angle(prospect, site_signals)
                if route == "ES_B2B"
                else {"code": None, "label": None, "reason": ""}
            )
            manual_recommendation = bool(prospect.get("recommended"))
            approved_for_proposal = fit["score"] >= 65 or manual_recommendation
            decision_mode = (
                "recommended_override" if manual_recommendation else "automatic"
            )
            if manual_recommendation:
                reasons.insert(
                    0, "Entrada aprobada por recomendacion manual del usuario"
                )

            prospect_patch = {
                "status": "proposal_ready"
                if approved_for_proposal
                else "diagnosis_ready",
                "route": route,
                "fit_score": fit["score"],
                "fit_band": fit["band"],
                "fit_score_raw": fit["score"],
                "fit_band_raw": fit["band"],
                "language": language
                if ROUTE_META[route]["language"] == "detect"
                else ROUTE_META[route]["language"],
                "currency": currency,
                "website": prospect.get("website") or final_url or website,
                "discovered_website": final_url or website,
                "proposal_ready": approved_for_proposal,
                "decision_mode": decision_mode,
                "strategic_angle": strategic_angle.get("code"),
                "strategic_angle_label": strategic_angle.get("label"),
                "last_processed_at": now_iso(),
                "socials": merged_socials,
            }
            self.state.update_prospect(prospect_id, prospect_patch)

            health_check = self._build_health_check(
                {**prospect, **prospect_patch},
                route,
                fit,
                site_signals,
                reasons,
                final_url or website,
                excluded,
                strategic_angle,
                manual_recommendation,
            )
            evidence_pack = {
                "prospect_id": prospect_id,
                "company_name": prospect.get("company_name"),
                "route": route,
                "route_reasons": reasons,
                "excluded_v1_raw": excluded,
                "manual_recommendation": manual_recommendation,
                "website": final_url or website,
                "search_candidates": discovered_candidates,
                "socials": merged_socials,
                "site_signals": site_signals,
                "strategic_angle": strategic_angle,
            }
            fit_payload = {
                "prospect_id": prospect_id,
                "fit_score": fit["score"],
                "fit_band": fit["band"],
                "parts": fit["parts"],
                "manual_recommendation": manual_recommendation,
                "approved_for_proposal": approved_for_proposal,
            }
            route_payload = {
                "prospect_id": prospect_id,
                "recommended_route": route,
                "language": prospect_patch["language"],
                "currency": currency,
                "reasons": reasons,
                "excluded_v1_raw": excluded,
                "manual_recommendation": manual_recommendation,
                "strategic_angle": strategic_angle,
            }

            slug = slugify(prospect.get("company_name") or prospect_id)
            self._write_text(artifact_dir / f"health_check_{slug}.md", health_check)
            self._write_json(artifact_dir / f"evidence_pack_{slug}.json", evidence_pack)
            self._write_json(artifact_dir / f"fit_score_{slug}.json", fit_payload)
            self._write_json(
                artifact_dir / f"route_recommendation_{slug}.json", route_payload
            )

            if approved_for_proposal:
                proposal_bundle = self._build_proposal_bundle(
                    prospect={**prospect, **prospect_patch},
                    fit=fit,
                    site_signals=site_signals,
                )
                self._write_text(
                    artifact_dir / f"propuesta_{slug}.md", proposal_bundle["proposal"]
                )
                self._write_text(
                    artifact_dir / f"deck_spec_{slug}.md", proposal_bundle["deck_spec"]
                )
                self._write_text(
                    artifact_dir / f"executive_summary_{slug}.md",
                    proposal_bundle["summary"],
                )
                self._write_text(
                    artifact_dir / f"roi_{slug}.md", proposal_bundle["roi"]
                )
                self._write_text(
                    artifact_dir / f"battlecard_{slug}.md",
                    proposal_bundle["battlecard"],
                )
                self._write_text(
                    artifact_dir / f"discovery_questions_{slug}.md",
                    proposal_bundle["discovery_questions"],
                )
                self._write_text(
                    artifact_dir / f"followups_{slug}.md", proposal_bundle["followups"]
                )
                self.state.add_event(
                    event_type="proposal_ready",
                    message=f"Propuesta lista para {company_label} en ruta {route}."
                    + (
                        " Se activo por recomendacion manual."
                        if manual_recommendation and fit["score"] < 65
                        else ""
                    ),
                    prospect_id=prospect_id,
                    telegram_relevant=True,
                )
            else:
                self.state.add_event(
                    event_type="diagnosis_ready",
                    message=f"Diagnostico listo para {company_label}. Fit {fit['score']} ({fit['band']}).",
                    prospect_id=prospect_id,
                    telegram_relevant=fit["score"] <= 39,
                )
                if fit["score"] <= 39:
                    self._notify(
                        f"WORKSPACE_OFERTAS\nProspecto con fit bajo: {company_label}\nScore: {fit['score']}"
                    )

            # AACORE enrichment runs for ALL leads (Haiku audit always, Hunter+Sonnet gated)
            domain = self._extract_domain(final_url or website)
            sector = prospect.get("sector", "general")
            ruta = prospect.get("route", "ES_B2B")

            try:
                aacore_patch = self._run_aacore_enrichment(
                    prospect_id=prospect_id,
                    empresa=company_label,
                    domain=domain,
                    sector=sector,
                    html=html,
                    ruta=ruta,
                    force_full=manual_recommendation and approved_for_proposal,
                )
                if aacore_patch.get("aacore_status") in ("enriched", "audited"):
                    self.state.update_prospect(prospect_id, aacore_patch)

                    has_email = bool(aacore_patch.get("contacto_email"))
                    has_copy = bool(aacore_patch.get("email_frio"))
                    auditoria_score = aacore_patch.get("auditoria_score") or 0

                    should_notify = manual_recommendation or (
                        fit["score"] >= 70
                        and has_email
                        and has_copy
                        and auditoria_score >= 6
                    )

                    if should_notify:
                        notification = (
                            f"{'✅ LEAD MANUAL' if manual_recommendation else '🤖 LEAD AUTOMÁTICO'}\n"
                            f"Empresa: {company_label}\n"
                            f"Score web: {auditoria_score}/10 | Fit: {fit['score']}\n"
                            f"Email: {aacore_patch.get('contacto_email', 'N/A')}\n"
                            f"Asunto: {aacore_patch.get('asunto_email', '')[:60]}"
                        )
                        self._notify(notification)
                else:
                    self.state.update_prospect(prospect_id, aacore_patch)
                    if manual_recommendation:
                        self._notify(
                            f"WORKSPACE_OFERTAS\nPropuesta lista: {company_label}\nRuta: {route}\nFit: {fit['score']}"
                        )
            except Exception as exc:
                print(f"[AACORE] Error in enrichment: {exc}")
                if manual_recommendation:
                    self._notify(
                        f"WORKSPACE_OFERTAS\nPropuesta lista: {company_label}\nRuta: {route}\nFit: {fit['score']}"
                    )

            self.state.finish_job(
                job["id"],
                status="success",
                summary=f"Procesado {company_label} -> {route} ({fit['score']})",
            )
        except Exception as exc:  # noqa: BLE001
            self.state.update_prospect(
                prospect_id, {"status": "error", "proposal_ready": False}
            )
            self.state.add_event(
                event_type="processing_error",
                message=f"Error procesando {company_label}: {exc}",
                prospect_id=prospect_id,
                level="error",
                telegram_relevant=True,
            )
            self.state.finish_job(job["id"], status="error", error=str(exc))
            self._notify(f"WORKSPACE_OFERTAS\nError procesando {company_label}: {exc}")

    def _build_health_check(
        self,
        prospect: dict[str, Any],
        route: str,
        fit: dict[str, Any],
        site_signals: dict[str, Any],
        reasons: list[str],
        website: str | None,
        excluded: bool,
        strategic_angle: dict[str, str],
        manual_recommendation: bool,
    ) -> str:
        lines = [
            f"# Health Check - {safe_value(prospect.get('company_name') or website)}",
            "",
            f"- Route recomendada: `{route}`",
            f"- Fit score: `{fit['score']}` ({fit['band']})",
            f"- Website: `{safe_value(website)}`",
            f"- Excluido V1 (raw): `{excluded}`",
            f"- Recomendacion manual: `{manual_recommendation}`",
            f"- Decision mode: `{safe_value(prospect.get('decision_mode'), 'automatic')}`",
            "",
            "## Por que esta ruta",
        ]
        for reason in reasons:
            lines.append(f"- {reason}")
        if strategic_angle.get("label"):
            lines += [
                "",
                "## Angulo estrategico recomendado",
                f"- {strategic_angle['label']}",
                f"- Motivo: {strategic_angle.get('reason') or '-'}",
            ]
        lines += [
            "",
            "## Senales detectadas",
            f"- Title: {safe_value(site_signals.get('title'))}",
            f"- Meta description: {safe_value(site_signals.get('meta_description'))}",
            f"- H1: {safe_value(site_signals.get('h1'))}",
            f"- CTA count: {site_signals.get('cta_count', 0)}",
            f"- Forms count: {site_signals.get('forms_count', 0)}",
            f"- Review mentions: {site_signals.get('review_mentions', 0)}",
            f"- WhatsApp present: {site_signals.get('whatsapp_present', False)}",
            f"- Booking present: {site_signals.get('booking_present', False)}",
            f"- Video present: {site_signals.get('video_present', False)}",
            f"- Socials detectadas: {', '.join(site_signals.get('socials_detected', {}).keys()) or '-'}",
            "",
            "## Fit breakdown",
        ]
        for key, value in fit["parts"].items():
            lines.append(f"- {key}: {value}")
        lines += [
            "",
            "## Text sample",
            site_signals.get("text_sample") or "Sin muestra de texto.",
        ]
        return "\n".join(lines)

    def _recommend_offer(
        self,
        prospect: dict[str, Any],
        fit: dict[str, Any],
        site_signals: dict[str, Any],
    ) -> tuple[str, dict[str, Any], list[str]]:
        route = prospect["route"]
        if route == "ES_B2B":
            strategic_code = prospect.get("strategic_angle") or "frontend_elevation"
            offer = AACORE_B2B_PLAYBOOK.get(
                strategic_code, AACORE_B2B_PLAYBOOK["frontend_elevation"]
            )
            return "core", offer, offer.get("addons", [])[:2]

        route_catalog = OFFER_CATALOG[route]
        offer_stage = "entry"
        if route == "ES_B2B" and fit["score"] >= 70 and site_signals.get("text_sample"):
            offer_stage = "core"
        elif (
            route == "ES_LOCAL"
            and fit["score"] >= 75
            and (
                site_signals.get("cta_count", 0) > 0
                or site_signals.get("forms_count", 0) > 0
            )
        ):
            offer_stage = "core"
        elif route == "US_HISPANIC" and fit["score"] >= 72 and prospect.get("website"):
            offer_stage = "core"

        add_ons: list[str] = []
        if (
            route in {"ES_LOCAL", "US_HISPANIC"}
            and site_signals.get("review_mentions", 0) == 0
        ):
            add_ons.append(route_catalog["addons"]["review_engine"])
        if route == "ES_B2B" and site_signals.get("cta_count", 0) == 0:
            add_ons.append(route_catalog["addons"]["follow_up_engine"])
        if route in {"ES_LOCAL", "US_HISPANIC"} and (
            prospect.get("socials") or site_signals.get("socials_detected")
        ):
            add_ons.append(route_catalog["addons"]["creator_led_content"])

        return offer_stage, route_catalog[offer_stage], add_ons[:2]

    def _extract_domain(self, url: str) -> str:
        """Extract clean domain from URL."""
        if not url:
            return ""
        domain = url.replace("https://", "").replace("http://", "").split("/")[0].lower()
        return domain

    def _run_aacore_enrichment(
        self,
        prospect_id: str,
        empresa: str,
        domain: str,
        sector: str,
        html: str,
        contacto_nombre: str = "",
        ruta: str = "ES_B2B",
        force_full: bool = False,
    ) -> dict[str, Any]:
        """Call Haiku audit + Hunter enrichment + Sonnet outreach with phase gates.

        Phase gates (skipped when force_full=True, i.e. manual leads):
        - If Haiku score < 5 → STOP (no Hunter, no Sonnet)
        - If no email found → STOP (no Sonnet)
        This saves ~90% of Sonnet tokens on low-quality automatic leads.
        """
        try:
            from aacore_integration import AACorePipeline
            pipeline = AACorePipeline()

            # Phase 1: Haiku audit (~$0.001 — always runs)
            audit = pipeline.audit_with_haiku(empresa, domain, sector, html)
            score = audit.get("auditoria_score", 0)
            print(f"[AACORE] {domain} → Haiku score: {score}/10")

            result = {
                "auditoria_score": score,
                "auditoria_resumen": audit.get("auditoria_resumen"),
                "prioridad": audit.get("prioridad"),
                "contacto_email": None,
                "asunto_email": None,
                "email_frio": None,
                "mensaje_linkedin": None,
                "aacore_status": "audited",
            }

            # GATE 1: Skip Hunter + Sonnet if score too low (unless manual)
            if score < 5 and not force_full:
                print(f"[AACORE] {domain} → Score {score} < 5, skipping Hunter + Sonnet")
                return result

            # Phase 2: Hunter.io enrichment (free tier)
            enrich = pipeline.enrich_contact(empresa, domain)
            result["contacto_email"] = enrich.get("contacto_email")

            # GATE 2: Skip Sonnet if no email found (unless manual)
            if not result["contacto_email"] and not force_full:
                print(f"[AACORE] {domain} → No email found, skipping Sonnet")
                return result

            # Phase 3: Sonnet outreach (~$0.01-0.03 — only for qualified leads)
            outreach = pipeline.write_outreach_sonnet(
                empresa, domain, sector,
                audit.get("auditoria_resumen", ""),
                contacto_nombre, ruta,
            )
            result["asunto_email"] = outreach.get("asunto_email")
            result["email_frio"] = outreach.get("email_frio")
            result["mensaje_linkedin"] = outreach.get("mensaje_linkedin")
            result["aacore_status"] = "enriched"
            print(f"[AACORE] {domain} → Full enrichment complete")

            return result
        except Exception as exc:
            print(f"[AACORE] Error enriching {domain}: {exc}")
            return {"aacore_status": "error"}

    def _build_proposal_bundle(
        self,
        prospect: dict[str, Any],
        fit: dict[str, Any],
        site_signals: dict[str, Any],
    ) -> dict[str, str]:
        route = prospect["route"]
        offer_stage, offer, add_ons = self._recommend_offer(prospect, fit, site_signals)
        template_name = {
            "ES_LOCAL": "es_local.md",
            "ES_B2B": "es_b2b.md",
            "US_HISPANIC": "us_hispanic.md",
        }[route]
        template_text = (self.templates_dir / template_name).read_text(encoding="utf-8")

        context = {
            "company": safe_value(
                prospect.get("company_name") or prospect.get("website")
            ),
            "core_offer": offer["name"],
            "addons": ", ".join(add_ons) if add_ons else "Ninguno / None",
            "promise": offer["promise"],
            "deliverable_1": offer["deliverables"][0],
            "deliverable_2": offer["deliverables"][1],
            "deliverable_3": offer["deliverables"][2],
            "deliverable_4": offer["deliverables"][3]
            if len(offer["deliverables"]) > 3
            else "Seguimiento y priorizacion de quick wins",
            "expected_result": self._expected_result(
                route, fit["score"], site_signals, prospect.get("strategic_angle")
            ),
            "pricing": offer["price"],
            "next_step_1": "Revision interna del diagnostico y confirmacion de objetivo.",
            "next_step_2": "Ajuste final del alcance y calendario.",
            "next_step_3": "Inicio de ejecucion con primer quick win visible.",
        }

        proposal = render_template(template_text, context)
        deck_spec = self._build_deck_spec(prospect, offer, add_ons, fit)
        summary = self._build_summary(prospect, offer, add_ons, fit)
        roi = self._build_roi(prospect, offer, fit, site_signals)
        battlecard = self._build_battlecard(prospect, offer, add_ons, fit)
        discovery_questions = self._build_discovery_questions(prospect, route)
        followups = self._build_followups(prospect, route)

        return {
            "proposal": proposal,
            "deck_spec": deck_spec,
            "summary": summary,
            "roi": roi,
            "battlecard": battlecard,
            "discovery_questions": discovery_questions,
            "followups": followups,
        }

    def _expected_result(
        self,
        route: str,
        score: int,
        site_signals: dict[str, Any],
        strategic_angle: str | None = None,
    ) -> str:
        if route == "ES_LOCAL":
            return "Mas claridad de oferta, mejor conversion de visitas en contactos y una base medible para decidir el siguiente escalon."
        if route == "ES_B2B":
            if strategic_angle == "frontend_elevation":
                return "Escaparate digital mas solido, mejor percepcion de marca y menos friccion en conversion B2B."
            if strategic_angle == "authority_engine":
                return "Mas autoridad tecnica visible, mejor narrativa comercial y contenido reusable para ventas."
            return "Impacto combinado: mejor conversion web y mas autoridad tecnica para sostener el crecimiento comercial."
        return "Stronger trust signals, clearer conversion path and better follow-up from lead to booked call."

    def _build_deck_spec(
        self,
        prospect: dict[str, Any],
        offer: dict[str, Any],
        add_ons: list[str],
        fit: dict[str, Any],
    ) -> str:
        return "\n".join(
            [
                f"# Deck Spec - {safe_value(prospect.get('company_name'))}",
                "",
                "1. Contexto del negocio",
                "2. Coste de inaccion",
                f"3. Ruta recomendada: {prospect['route']}",
                f"4. Angulo estrategico: {safe_value(prospect.get('strategic_angle_label'))}",
                f"5. Oferta recomendada: {offer['name']}",
                f"6. Decision mode: {safe_value(prospect.get('decision_mode'))}",
                f"7. Add-ons opcionales: {', '.join(add_ons) if add_ons else 'Ninguno'}",
                f"8. Fit score: {fit['score']}",
                "9. Roadmap 30-90 dias",
                "10. Inversion y siguiente paso",
            ]
        )

    def _build_summary(
        self,
        prospect: dict[str, Any],
        offer: dict[str, Any],
        add_ons: list[str],
        fit: dict[str, Any],
    ) -> str:
        return "\n".join(
            [
                f"# Executive Summary - {safe_value(prospect.get('company_name'))}",
                "",
                f"- Route: {prospect['route']}",
                f"- Strategic angle: {safe_value(prospect.get('strategic_angle_label'))}",
                f"- Fit score: {fit['score']} ({fit['band']})",
                f"- Decision mode: {safe_value(prospect.get('decision_mode'))}",
                f"- Recommended offer: {offer['name']}",
                f"- Optional add-ons: {', '.join(add_ons) if add_ons else 'None'}",
                f"- Main promise: {offer['promise']}",
            ]
        )

    def _build_roi(
        self,
        prospect: dict[str, Any],
        offer: dict[str, Any],
        fit: dict[str, Any],
        site_signals: dict[str, Any],
    ) -> str:
        route = prospect["route"]
        lines = [f"# ROI - {safe_value(prospect.get('company_name'))}", ""]
        if route == "ES_LOCAL":
            lines += [
                "Escenario base:",
                "- Si la activacion mejora la tasa de contacto o reserva de forma visible, el negocio gana un canal mas predecible.",
                "- El retorno debe medirse en llamadas, formularios, reservas o conversaciones validas.",
            ]
        elif route == "ES_B2B":
            lines += [
                "Escenario base:",
                "- Si la empresa transmite mejor autoridad y clarifica su propuesta, reduce friccion comercial y mejora la calidad de las conversaciones.",
                "- El retorno debe medirse en oportunidades generadas, conversion web y velocidad del ciclo.",
            ]
            if prospect.get("strategic_angle") == "frontend_elevation":
                lines.append(
                    "- En este caso la palanca dominante es web/UX: mas confianza, menos fuga y mejor soporte a ventas."
                )
            elif prospect.get("strategic_angle") == "authority_engine":
                lines.append(
                    "- En este caso la palanca dominante es autoridad tecnica: contenido usable en captacion, ventas y seguimiento."
                )
        else:
            lines += [
                "Base scenario:",
                "- If trust signals and response speed improve, booked calls and close quality should improve too.",
                "- ROI should be tracked through response time, booked calls and show rate.",
            ]
        lines += [
            "",
            f"Oferta evaluada: {offer['name']}",
            f"Fit score actual: {fit['score']}",
        ]
        return "\n".join(lines)

    def _build_battlecard(
        self,
        prospect: dict[str, Any],
        offer: dict[str, Any],
        add_ons: list[str],
        fit: dict[str, Any],
    ) -> str:
        return "\n".join(
            [
                f"# Battlecard - {safe_value(prospect.get('company_name'))}",
                "",
                "## Objeciones probables",
                "- No necesito un proyecto grande ahora.",
                "- No veo claro el retorno.",
                "- Ya tenemos web o ya hacemos marketing.",
                "",
                "## Respuesta marco",
                f"- La recomendacion actual no es un catalogo. Es la siguiente mejor jugada: {offer['name']}.",
                "- El retorno se plantea como escenario defendible, no como promesa vacia.",
                "- Si ya existe algo, el objetivo es hacerlo convertir mejor, no rehacer por capricho.",
                "",
                "## Datos de apoyo",
                f"- Fit score: {fit['score']}",
                f"- Angulo estrategico: {safe_value(prospect.get('strategic_angle_label'))}",
                f"- Add-ons considerados: {', '.join(add_ons) if add_ons else 'Ninguno'}",
            ]
        )

    def _build_discovery_questions(self, prospect: dict[str, Any], route: str) -> str:
        base = [
            "# Discovery Questions",
            "",
            "1. Cual es hoy el cuello de botella real entre visibilidad y venta?",
            "2. Que pasa con un lead bueno desde que entra hasta que alguien responde?",
            "3. Que objetivo tendria sentido mover en 30-90 dias?",
        ]
        if route == "ES_B2B":
            base.append(
                "4. Que materiales usan hoy para sostener una venta compleja o tecnica?"
            )
        elif route == "US_HISPANIC":
            base.append(
                "4. How fast does the team respond to new calls, forms or messages today?"
            )
        else:
            base.append(
                "4. Que fuente actual trae mas llamadas o reservas, aunque este mal aprovechada?"
            )
        return "\n".join(base)

    def _build_followups(self, prospect: dict[str, Any], route: str) -> str:
        if route == "US_HISPANIC":
            return "\n".join(
                [
                    "# Follow-ups",
                    "",
                    "## Follow-up 1",
                    "Quick recap, one relevant insight, one CTA.",
                    "",
                    "## Follow-up 2",
                    "Reference trust gap or missed-call opportunity, softer CTA.",
                    "",
                    "## Follow-up 3",
                    "Ask for a clear yes/no and close the loop professionally.",
                ]
            )
        return "\n".join(
            [
                "# Follow-ups",
                "",
                "## Seguimiento 1",
                "Resumen breve de lo detectado y una llamada a la accion clara.",
                "",
                "## Seguimiento 2",
                "Aporta un insight nuevo y reduce la friccion para responder.",
                "",
                "## Seguimiento 3",
                "Pide una decision sencilla y cierra el hilo con seguridad.",
            ]
        )

    def _process_message(self, message: dict[str, Any]) -> None:
        job = self.state.create_job(
            "message_reply",
            prospect_id=message.get("prospect_id"),
            message_id=message["id"],
        )
        try:
            prospect = (
                self.state.get_prospect(message.get("prospect_id"))
                if message.get("prospect_id")
                else None
            )
            route = prospect.get("route") if prospect else None
            reply = self._build_reply_draft(message, prospect)
            self.state.update_message(
                message["id"], {"status": "draft_ready", "reply_draft": reply}
            )
            if prospect:
                self.state.update_prospect(prospect["id"], {"reply_ready": True})
            self.state.add_event(
                event_type="reply_draft_ready",
                message="Borrador de respuesta listo para revisar.",
                prospect_id=message.get("prospect_id"),
                telegram_relevant=True,
            )
            label = prospect.get("company_name") if prospect else "mensaje"
            self._notify(
                f"WORKSPACE_OFERTAS\nBorrador de respuesta listo para {label}.\nRuta: {route or 'sin ruta'}"
            )
            self.state.finish_job(
                job["id"], status="success", summary="Reply draft ready"
            )
        except Exception as exc:  # noqa: BLE001
            self.state.update_message(message["id"], {"status": "error"})
            self.state.add_event(
                event_type="reply_error",
                message=f"Error creando respuesta: {exc}",
                prospect_id=message.get("prospect_id"),
                level="error",
                telegram_relevant=True,
            )
            self.state.finish_job(job["id"], status="error", error=str(exc))

    def _build_reply_draft(
        self, message: dict[str, Any], prospect: dict[str, Any] | None
    ) -> str:
        content = message.get("content", "").strip()
        if not prospect:
            return "Gracias por tu mensaje. Estoy revisando el contexto y te comparto una respuesta mas concreta en cuanto termine de ordenar la informacion relevante."

        route = prospect.get("route") or "ES_B2B"
        if route == "US_HISPANIC":
            return (
                "Thanks for the message. I reviewed the current context and the next best step is to focus on the fastest trust and conversion fix first. "
                "If you want, I can send a tighter summary and the exact next step so we keep this simple."
            )
        if route == "ES_LOCAL":
            return (
                "Gracias por escribir. Lo que tiene mas sentido ahora es ir a la mejora mas rapida que mueva llamadas, reservas o formularios sin complicar el proyecto. "
                "Si quieres, te envio el siguiente paso exacto y lo dejamos aterrizado."
            )
        return (
            "Gracias por el mensaje. Revisando lo que hay hoy, la prioridad no es hacer mas ruido sino mejorar como se presenta y convierte la propuesta comercial. "
            "Si te encaja, te comparto el siguiente paso recomendado de forma muy concreta."
        )
