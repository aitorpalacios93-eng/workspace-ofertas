#!/usr/bin/env python3
"""
MODO MANUAL: Cuando TÚ añades un lead → audita, enriquece, redacta propuesta completa.
"""

import json
import os
from aacore_integration import AACorePipeline
from workspace_notifications import TelegramNotifier


class ManualLeadProcessor:
    """Procesa leads manuales: auditoría completa + propuesta lista."""

    def __init__(self):
        self.pipeline = AACorePipeline()
        self.telegram = TelegramNotifier()

    def process(
        self,
        empresa: str,
        domain: str,
        sector: str = "general",
        contacto_nombre: str = "",
        ruta: str = "ES_B2B",
    ) -> dict:
        """
        Procesa un lead manual y genera propuesta completa.
        Retorna: {status, audit, enrichment, outreach, ready_to_send}
        """

        # Ejecutar pipeline AACORE
        result = self.pipeline.process_lead(empresa, domain, sector, contacto_nombre, ruta)

        if result["status"] != "success":
            return result

        # Extraer datos
        score = result.get("auditoria_score", 0)
        email = result.get("contacto_email", "")
        asunto = result.get("asunto_email", "")
        email_body = result.get("email_frio", "")
        linkedin_msg = result.get("mensaje_linkedin", "")

        # Formato para enviar
        propuesta_lista = {
            "empresa": empresa,
            "domain": domain,
            "sector": sector,
            "ruta": ruta,
            "score_auditoria": score,
            "contacto_email": email,
            "asunto_email": asunto,
            "email_frio": email_body,
            "mensaje_linkedin": linkedin_msg,
            "status": "listo_para_enviar",
            "audit_details": result.get("audit", {}),
        }

        # Notificar por Telegram que propuesta está lista
        self._notify_ready(propuesta_lista)

        return propuesta_lista

    def _notify_ready(self, propuesta: dict) -> None:
        """Notifica que propuesta está lista (siempre con leads manuales)."""
        msg = f"""
✅ PROPUESTA LISTA

Empresa: {propuesta['empresa']}
Score: {propuesta['score_auditoria']}/10
Email: {propuesta['contacto_email']}

Asunto: {propuesta['asunto_email'][:60]}...

Contacta y verifica que esté lista para enviar.
        """
        self.telegram.send(msg)


if __name__ == "__main__":
    # Test
    processor = ManualLeadProcessor()
    result = processor.process(
        empresa="Ferretería García SL",
        domain="ferreteria-garcia.es",
        sector="ferretería industrial",
        ruta="ES_B2B",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
