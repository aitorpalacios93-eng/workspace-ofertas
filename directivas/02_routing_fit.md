# 02 Routing y Fit

## Objetivo

Decidir rapido si una oportunidad merece propuesta completa, que ruta le corresponde y con que intensidad hay que perseguirla.

## Seleccion de ruta

### `ES_LOCAL`

Se prioriza cuando aparecen varias de estas senales:

- Pais `ES`.
- Captacion geografica o local.
- Dependencia de llamadas, WhatsApp, reservas, Google Business o formulario simple.
- Necesidad clara de activacion rapida.

### `ES_B2B`

Se prioriza cuando aparecen varias de estas senales:

- Pais `ES`.
- Empresa con ventas B2B, distribucion, industria, servicios tecnicos o consultoria.
- Ciclo comercial mas largo o ticket medio-alto.
- Brecha entre capacidad real de la empresa y su presencia digital/comercial.

### `US_HISPANIC`

Se prioriza cuando aparecen varias de estas senales:

- Pais `US`.
- Negocio owner-led de servicios.
- Presencia en espanol, bilingue o con senales claras de liderazgo hispano.
- Fuerte dependencia de reviews, confianza y respuesta rapida.

## Hard stops

No se genera propuesta completa si pasa alguna de estas cosas:

- El prospecto cae fuera de ruta y no hay override manual.
- No hay evidencia minima del problema.
- El presupuesto o el tamano percibido queda muy por debajo del suelo de la ruta.
- En `US_HISPANIC`, el vertical cae en un segmento excluido en V1.

## Fit score v1

Puntuacion total: 100.

- `trust_gap`: 20
- `demand_signal`: 20
- `speed_to_value`: 20
- `commercial_urgency`: 15
- `delivery_fit`: 15
- `evidence_density`: 10

## Umbrales

- `0-39`: diagnostico y no propuesta.
- `40-64`: diagnostico, quick wins y propuesta solo con override manual.
- `65-79`: propuesta completa permitida.
- `80-100`: prioridad alta.

## Override manual

Se permite override si:

- Existe relacion previa.
- Hay propuesta viva o reunion ya abierta.
- Hay un motivo estrategico claro para entrar aunque el score sea imperfecto.

## Artefactos de salida del routing

1. `fit_score_<slug>.json`
2. `evidence_pack_<slug>.json`
3. `route_recommendation_<slug>.json`

## Regla de lenguaje y moneda

- `ES_LOCAL` y `ES_B2B`: espanol y `EUR`.
- `US_HISPANIC`: detectar idioma principal del prospecto y usar `USD`.
- Bilingue solo si el contexto comercial lo pide de verdad.
