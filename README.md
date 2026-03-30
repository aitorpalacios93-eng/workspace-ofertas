# Workspace de Ofertas

Workspace permanente para auditar prospectos, enrutar cada oportunidad a la ruta comercial correcta y generar propuestas high-ticket sin mezclar mensajes entre mercados.

## Dos vias de funcionamiento

### 1. WebApp operativa

Dashboard local para:

- visualizar prospects, jobs, eventos, mensajes y artefactos
- crear nuevas empresas por nombre, web o redes
- marcar una oportunidad como `Recomendacion` y/o forzar su ruta
- revisar el routing, fit score y documentos generados
- registrar mensajes entrantes y dejar que el worker prepare una respuesta

### 2. Worker automatico

Proceso en segundo plano que:

- descubre website si solo le das nombre
- analiza web y senales visibles
- asigna ruta (`ES_LOCAL`, `ES_B2B`, `US_HISPANIC`)
- calcula fit score
- mantiene el fit bruto, pero puede desbloquear propuesta si existe recomendacion manual
- escribe health check, propuesta, deck spec y pack de cierre cuando aplica
- genera borradores de respuesta para mensajes entrantes
- avisa por Telegram de eventos relevantes

## Doctrina operativa

- Un sistema interno, tres wrappers externos.
- No se vende por lineas de servicio. Se vende por momento de negocio.
- Cada prospecto ve una sola ruta comercial.
- Cada propuesta recomienda una oferta core y, como maximo, dos add-ons.
- El backend de automatizacion solo se ofrece despues de confianza o despues de vender el core.
- Si el fit score no da, el sistema genera diagnostico y quick wins, no una propuesta completa.
- La prioridad real de los proximos 60 dias es validar ventas y documentar casos, no automatizar de mas.

## Rutas activas

| Codigo | Mercado | Estado | Rol actual |
| --- | --- | --- | --- |
| `ES_B2B` | PYME consolidada B2B en Espana | Activa | Prioridad principal y tickets altos |
| `ES_LOCAL` | Negocio local premium y PYME pequena en Espana | Activa | Caja rapida y casos documentables |
| `US_HISPANIC` | Service businesses owner-led en USA con liderazgo hispano/latino | Playbook listo, prospeccion limitada | Upside alto, pero se activa de verdad tras el primer caso ES documentado |

## Prioridad de ejecucion

- `ES_B2B`: 50%
- `ES_LOCAL`: 40%
- `US_HISPANIC`: 10%

Regla practica:

- Si ya existe una propuesta B2B activa y viva, esa oportunidad tiene prioridad sobre nueva prospeccion USA.
- USA no se empuja de forma agresiva hasta tener al menos un caso ES documentado que sirva como prueba social operativa.

## Estructura

- `.tmp/`: artefactos temporales, auditorias, borradores y packs de cierre.
- `directivas/`: SOPs y reglas de negocio.
- `scripts/`: contratos y stubs Python 3.14 del flujo.
- `templates/`: plantillas de salida por ruta.
- `memory/`: catalogo, reglas de routing, prioridades y aprendizaje acumulado.

## Flujo V0

1. Intake del prospecto.
2. Diagnostico y recogida de evidencia.
3. Routing a `ES_B2B`, `ES_LOCAL` o `US_HISPANIC`.
4. Calculo de fit score.
5. Si el fit pasa el umbral, generacion de propuesta y deck spec.
6. Generacion de ROI, battlecard, discovery questions y follow-ups.
7. Registro de objeciones y outcomes en `memory/`.

## Uso de NotebookLM

NotebookLM queda como acelerador de research cuando hace falta contexto sectorial, comparativas o senales de mercado. No sustituye el fit gate ni justifica generar propuestas para prospectos flojos.

## Estado actual

Esta V0 deja preparado:

- El marco estrategico y operativo.
- El catalogo y pricing base por ruta.
- Las reglas de routing y de prioridad.
- Las plantillas de propuesta por segmento.
- Los contratos de los tres scripts principales.
- Un backend local con estado persistente.
- Una webapp ligera sin framework pesado.
- Un worker automatico para procesar cola y mensajes.

## Arranque local

Desde el directorio `WORKSPACE_OFERTAS`:

```bash
python3 scripts/workspace_server.py
```

La app queda disponible en `http://127.0.0.1:8787`.

Para arrancar sin worker automatico:

```bash
python3 scripts/workspace_server.py --without-worker
```

## Telegram

Si quieres avisos relevantes por Telegram, exporta estas variables antes de arrancar:

```bash
export WORKSPACE_TELEGRAM_BOT_TOKEN="<tu_bot_token>"
export WORKSPACE_TELEGRAM_CHAT_ID="<tu_chat_id>"
```

Con eso el sistema avisara cuando:

- una propuesta quede lista
- entre un mensaje nuevo
- se genere un borrador de respuesta
- ocurra un error relevante

## Recomendacion manual

Cuando una empresa entra por relacion previa, referido o criterio tuyo, puedes marcarla como `Recomendacion`.

Efecto:

- el fit score bruto se sigue calculando y se conserva tal cual
- la decision comercial puede pasar a modo `recommended_override`
- el sistema puede generar propuesta aunque el score bruto no llegue al umbral automatico
- opcionalmente puedes forzar tambien la ruta (`ES_LOCAL`, `ES_B2B`, `US_HISPANIC`)

Esto evita falsear el scoring, pero te deja mandar tu cuando una oportunidad conocida merece avanzar.

La automatizacion completa se implementa despues de capturar evidencia real de ventas y de uso.
