# google-multi — MCP server para varias cuentas Google

Servidor MCP local (Python + FastMCP, transporte stdio) que da a Claude acceso **simultáneo** a varias cuentas Google — hoy `personal` y `work` — para Gmail, Calendar, Drive y Tasks. Los conectores nativos de Claude solo admiten una cuenta Google a la vez; este servidor elimina esa limitación.

Cada herramienta recibe un parámetro `account` con el nombre de la cuenta definido en [config.json](config.json).

---

## Requisitos

- Windows con Python 3.12 (`winget install Python.Python.3.12`; evitar el alias de Microsoft Store)
- Un proyecto de Google Cloud con estas APIs habilitadas: Gmail, Google Calendar, Google Drive, Tasks
- Credencial OAuth 2.0 de tipo **Aplicación de escritorio**, con las cuentas a usar agregadas como usuarios autorizados

## Instalación

```powershell
cd C:\Users\ag87r\projects\gmail-mcp
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

1. Descargar el JSON de la credencial OAuth de Google Cloud y guardarlo como `credentials\client_secret.json`.
2. Definir las cuentas en `config.json` (ver abajo).
3. Autenticar todas las cuentas de una vez (abre el navegador por cada cuenta):

   ```powershell
   .venv\Scripts\python fix_display_name.py
   ```

   Los tokens quedan en `credentials\tokens\<cuenta>.json` y se renuevan solos. Si no se ejecuta este paso, el flujo OAuth se lanza la primera vez que se usa una herramienta de esa cuenta.

## Configuración de cuentas

```json
{
  "accounts": {
    "personal": {
      "email": "usuario@gmail.com",
      "display_name": "Nombre Apellido",
      "description": "Cuenta personal",
      "browser": "default"
    },
    "work": {
      "email": "usuario@empresa.com",
      "display_name": "Apellido, Nombre",
      "description": "Cuenta de trabajo",
      "browser": "chrome"
    }
  },
  "credentials_dir": "./credentials"
}
```

| Campo | Uso |
|-------|-----|
| clave (`personal`, `work`) | Valor que se pasa como `account` en cada herramienta; también es el nombre del archivo de token |
| `email` | Dirección de la cuenta; se usa en el header `From` |
| `display_name` | Nombre de respaldo si Gmail no devuelve uno en *Enviar como* |
| `browser` | Navegador para el login OAuth: `default`, `chrome` o `brave`. Útil cuando cada cuenta tiene sesión iniciada en un navegador distinto. Las rutas están en `_BROWSER_PATHS` de [auth.py](auth.py) |

Para añadir una cuenta basta con agregar una entrada nueva y autenticarla.

## Registro en Claude

**Claude Code:**

```powershell
claude mcp add google-multi --scope user -- C:\Users\ag87r\projects\gmail-mcp\.venv\Scripts\python.exe C:\Users\ag87r\projects\gmail-mcp\server.py
```

**Claude Desktop** — en `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "google-multi": {
      "command": "C:\\Users\\ag87r\\projects\\gmail-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\ag87r\\projects\\gmail-mcp\\server.py"]
    }
  }
}
```

Después de cambiar la configuración o el código, cerrar Claude Desktop desde la bandeja del sistema (clic derecho → **Quit**); cerrar la ventana deja vivo el proceso anterior.

## Herramientas (28)

| Servicio | Herramientas |
|----------|--------------|
| Cuentas | `list_accounts` |
| Gmail | `gmail_search`, `gmail_read`, `gmail_read_thread`, `gmail_send`, `gmail_create_draft`, `gmail_list_drafts`, `gmail_delete_draft`, `gmail_list_labels`, `gmail_archive`, `gmail_mark_read` |
| Calendar | `calendar_list_events`, `calendar_create_event`, `calendar_update_event`, `calendar_delete_event` |
| Drive | `drive_search`, `drive_read`, `drive_list_recent`, `drive_create_file`, `drive_update_file_content`, `drive_create_folder`, `drive_find_or_create_folder`, `drive_trash_file` |
| Tasks | `tasks_list_tasklists`, `tasks_list`, `tasks_create`, `tasks_update`, `tasks_complete` |

Detalles a tener en cuenta:

- **Envío de correo:** `gmail_send` y `gmail_create_draft` agregan automáticamente la firma HTML configurada en Gmail (*Enviar como*) y aceptan adjuntos como rutas locales completas de Windows.
- **Borrado protegido:** `gmail_delete_draft` (permanente) y `drive_trash_file` (a la papelera) no hacen nada a menos que reciban `confirm=true`, para obligar a pedir aprobación explícita al usuario.
- **Formatos de fecha:** Calendar usa ISO 8601 con zona (`2026-05-15T10:00:00-05:00`); Tasks usa RFC 3339 (`2026-05-20T00:00:00.000Z`); el rango de `calendar_list_events` usa `YYYY-MM-DD`.
- **Google Meet:** `calendar_create_event` con `add_meet=true` genera el enlace.
- **Lectura en Drive:** `drive_read` devuelve Google Docs como texto, Sheets como CSV y archivos `text/*` tal cual; los binarios solo devuelven un aviso.
- **Crear en Drive:** `drive_create_file` con `target_mime_type='application/vnd.google-apps.document'` crea un Google Doc editable; con `text/markdown` o `text/plain` crea el archivo sin conversión.

Ejemplos de peticiones a Claude:

```
Busca los correos no leídos de esta semana en mi cuenta de trabajo
Crea un evento mañana a las 3pm en mi calendario personal con enlace de Meet
Lista mis tareas pendientes en las dos cuentas
```

## Permisos OAuth

Definidos en `SCOPES` de [auth.py](auth.py):

`gmail.modify`, `gmail.send`, `calendar`, `drive.readonly`, `drive.file`, `tasks`

Si se agrega un scope nuevo, [auth.py](auth.py) detecta que el token guardado no lo incluye, lo borra y vuelve a pedir consentimiento en el navegador. Un token revocado o vencido (`invalid_grant`) se maneja igual. Esto incluye el caso en que Google revoca el token mientras el access token local aún parece vigente: la renovación que hace la librería dentro de la llamada a la API pasa por `_ReauthCredentials.refresh()`, que relanza el login y reintenta la petición.

## Estructura

```
gmail-mcp/
├── server.py              # Entry point FastMCP; declara las herramientas
├── auth.py                # OAuth por cuenta, selección de navegador, scopes
├── config.json            # Cuentas
├── tools/                 # Lógica por servicio: gmail, calendar, drive, tasks
├── credentials/
│   ├── client_secret.json # Credencial OAuth (no versionar)
│   └── tokens/            # Tokens por cuenta (no versionar)
├── fix_display_name.py    # Autentica todas las cuentas de config.json
└── RESUMEN-CONVERSACION.md  # Historia de la implementación y problemas resueltos
```

`credentials/client_secret.json` y `credentials/tokens/` están en `.gitignore`; no deben compartirse.

## Solución de problemas

| Síntoma | Causa / solución |
|---------|------------------|
| Las herramientas no aparecen en Claude Desktop | El proceso sigue vivo en la bandeja; salir con **Quit** y volver a abrir |
| El login OAuth abre el navegador equivocado | Revisar `browser` en `config.json` y que la ruta del ejecutable en `_BROWSER_PATHS` exista |
| Error de token o `invalid_scope` | Borrar `credentials\tokens\<cuenta>.json` y volver a autenticar |
| Tildes ilegibles en el nombre del remitente | Configurar el nombre en Gmail → Ajustes → Cuentas → *Enviar como*, sin acentos |
| `python` abre Microsoft Store | Instalar Python con `winget` y desactivar los alias de ejecución de la Store |

Más contexto sobre cada problema en [RESUMEN-CONVERSACION.md](RESUMEN-CONVERSACION.md).
