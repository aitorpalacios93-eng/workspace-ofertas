# Setup Telegram Bot — Guía Paso a Paso

## Paso 1: Crear el Bot en Telegram

1. Abre Telegram y busca `@BotFather`
2. Envía: `/newbot`
3. Dale nombre: `Workspace Ofertas` (o lo que quieras)
4. Dale username: `workspace_ofertas_bot` (debe ser único, Telegram te dirá si no está disponible)
5. **BotFather te dará un TOKEN**: `123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi`

**Copia este token.**

---

## Paso 2: Obtener tu CHAT_ID

1. En Telegram, crea un grupo privado o usa un chat directo contigo
2. Añade tu nuevo bot al grupo o chatea con él
3. Envía cualquier mensaje al bot (ej: `/start`)
4. Abre esta URL en tu navegador (reemplaza `BOT_TOKEN`):

```
https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
```

Ejemplo:
```
https://api.telegram.org/bot123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi/getUpdates
```

5. Busca en el JSON que aparece: `"chat":{"id":`
6. **Ese número es tu CHAT_ID**. Cópialo.

---

## Paso 3: Guardar en .env

Copia `.env.example` a `.env`:

```bash
cp .env.example .env
```

Completa los campos Telegram:

```
WORKSPACE_TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi
WORKSPACE_TELEGRAM_CHAT_ID=987654321
```

---

## Paso 4: Verificar conexión

Arranca el servidor:

```bash
cd /Users/aitor/Downloads/WORKSPACE_OFERTAS
python3 scripts/workspace_server.py
```

Ve a `http://127.0.0.1:8787` y crea un prospect de prueba.

Si la integración funciona:
- ✅ Verás un mensaje en Telegram cuando se genere propuesta
- ✅ Los logs en terminal dirán `[TELEGRAM] Notification sent`

---

## Troubleshooting

**"Invalid token"**
→ Copia el token correctamente. Sin espacios, con el `:` incluido.

**"Chat not found"**
→ El chat_id no existe. Reintenta paso 2, cerciórate de que el bot está en el chat/grupo.

**"Permission denied"**
→ En Telegram Settings, comprueba que el bot tiene permisos de envío de mensajes.

---

## Qué recibirás por Telegram

El sistema enviará notificaciones SOLO de:
- ✅ Propuesta lista y score >= 70
- ✅ Email personalizado redactado
- ✅ Mensaje LinkedIn listo
- ✅ Error crítico que requiera acción

**NO** recibirás spam de cada prospect procesado. Solo lo relevante.
