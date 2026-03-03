# API Documentos Drive

API FastAPI para subir documentos PDF a Google Drive desde un payload base64.

## Resumen

La API expone un endpoint publico `POST /documentos/subir` que:

1. Recibe `id_registro_sst`, `documento_base64`, `nombre_documento`, `fecha_inicio`,
   `folder_id` (opcional), `nombre_persona`, `rut_persona`.
2. Valida que `nombre_documento` termine en `.pdf`.
3. Valida que `fecha_inicio` sea ISO parseable.
4. Limita el tamano del archivo a 200 MB.
5. Si envias `folder_id` y existe (y cuelga del root permitido), guarda el PDF ahi sin crear carpeta.
6. Si `folder_id` enviado no existe, crea carpeta con `nombre_persona` bajo el root permitido
   `1n8njw20WyC-uylqiMOZULj5tnDZjRjjA` y guarda ahi.
7. Si `folder_id` es null/vacio, usa flujo de carpeta bajo root permitido (resolver/crear por `nombre_persona`).
8. Genera nombre final: `YYYYMMDD_REQUERIMIENTO_NOMBRE_PERSONA.pdf`.
   - `REQUERIMIENTO` se genera desde `nombre_documento` (sin `.pdf`) en mayusculas.
   - `NOMBRE_PERSONA` se genera desde `nombre_persona`.
9. Si el nombre ya existe, crea sufijo incremental (`_1`, `_2`, ...).
10. Sube el PDF en la carpeta destino y devuelve metadatos + links de Drive.
11. Si el registro SST ya tiene `drive_pdf_id`, elimina ese archivo en Drive antes de subir el nuevo.
    - si eliminar devuelve 404, continua el flujo.
    - si eliminar falla por otro motivo, responde error y no sube el nuevo archivo.
12. Si falla la subida tras borrar el previo, limpia `drive_pdf_id` y `link` en SST (`null`).
13. Actualiza `dim_core_persona.sst_drive_folder_id` con el `folder_id` de destino usando `rut_persona`.
14. Actualiza en Supabase la tabla `brg_acreditacion_persona_requerimiento_sst`:
   - `link`: `https://drive.google.com/file/d/{file_id}/view?usp=drive_link`
   - `drive_pdf_id`: `{file_id}`
   filtrando por columna `id` usando el valor de `id_registro_sst`.

## Requisitos

- Python 3.11
- Variables de entorno:

```env
GOOGLE_CLIENT_SECRET_FILE=client_secret.json
GOOGLE_TOKEN_FILE=token.json
SUPABASE_URL=https://tu-project-id.supabase.co
SUPABASE_KEY=REEMPLAZAR_POR_SUPABASE_SERVICE_ROLE_KEY
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=https://myma-acreditacion.onrender.com,http://localhost:3000,http://127.0.0.1:3000
```

## Ejecutar local

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Endpoint principal

### `POST /documentos/subir`

#### Request

```json
{
  "id_registro_sst": 12345,
  "documento_base64": "JVBERi0xLjQKJ...",
  "nombre_documento": "Contrato SST.pdf",
  "fecha_inicio": "2026-03-01",
  "folder_id": null,
  "nombre_persona": "Juan Perez",
  "rut_persona": "12.345.678-9"
}
```

#### Response (ejemplo)

```json
{
  "ok": true,
  "id_registro_sst": 12345,
  "file_id": "1abcXYZ...",
  "file_name": "20260301_CONTRATO_SST_Juan_Perez.pdf",
  "folder_id": "1n8njw20WyC-uylqiMOZULj5tnDZjRjjA",
  "folder_id_destino": "1personaFolder...",
  "carpeta_persona_creada": true,
  "persona_actualizada": true,
  "link": "https://drive.google.com/file/d/1abcXYZ.../view?usp=drive_link",
  "db_actualizado": true,
  "web_view_link": "https://drive.google.com/file/d/1abcXYZ.../view",
  "web_content_link": "https://drive.google.com/uc?id=1abcXYZ...&export=download",
  "size_bytes": 182344,
  "created_time": "2026-03-01T14:08:07.000Z"
}
```

## Errores esperados

- `422`: base64 invalido, fecha invalida, nombre sin `.pdf` o `folder_id` invalido.
- `403`: `folder_id` fuera del arbol permitido o sin permisos.
- `404`: carpeta no existe/no accesible.
- `413`: archivo supera 200 MB.
- `502`: fallo al eliminar archivo previo en Drive.
- `502`: fallo en Google Drive API al subir.

## Estructura

```text
app/
  main.py
  config.py
  models.py
  routers/
    documentos.py
  services/
    drive_service.py
```
