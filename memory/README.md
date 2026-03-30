# Memory

Esta carpeta guarda conocimiento reutilizable y machine-readable.

Reglas:

- `offer_catalog.yaml`: catalogo vivo por ruta.
- `segment_rules.yaml`: routing, fit y umbrales.
- `operating_plan.yaml`: foco, gates y prioridad operativa.
- `objections.jsonl`: objeciones reales o seeds de objeciones probables.
- `outcomes.jsonl`: resultados reales o, al inicio, un sample marcado como tal.

En cuanto haya el primer caso documentado, `outcomes.jsonl` debe dejar de usar samples.
