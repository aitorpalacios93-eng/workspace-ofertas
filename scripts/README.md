# Scripts

El directorio contiene dos capas:

- scripts de contrato de la V0 comercial
- runtime real del dashboard local y del worker automatico

Objetivo:

- Fijar inputs y outputs.
- Evitar construir automatizacion grande antes de tener casos reales.
- Dejar preparada la interfaz para la siguiente fase.

## Contratos V0

- `diagnostico_generico.py`
- `propuesta_modular.py`
- `acelerador_cierre.py`

Todos aceptan `--describe` para mostrar su contrato actual.

## Runtime del dashboard

- `workspace_state.py`: persistencia de prospects, jobs, eventos y mensajes.
- `workspace_notifications.py`: envio de avisos por Telegram.
- `workspace_core.py`: motor de routing, scoring, artefactos y respuesta automatica.
- `workspace_server.py`: servidor local con webapp y worker integrado.
