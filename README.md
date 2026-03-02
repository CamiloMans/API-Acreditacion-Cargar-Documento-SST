# API Documentos Drive

API FastAPI para subir documentos PDF a Google Drive desde un payload base64.

## Resumen

La API expone un endpoint publico `POST /documentos/subir` que:

1. Recibe `id_registro_sst`, `documento_base64`, `nombre_documento`, `fecha_inicio`,
   `folder_id` (opcional), `nombre_persona`, `rut_persona`.
2. Valida que `nombre_documento` termine en `.pdf`.
3. Valida que `fecha_inicio` sea ISO parseable.
4. Limita el tamano del archivo a 200 MB.
5. Si `folder_id` es null/vacio, usa la carpeta root permitida como base.
6. Valida que la carpeta base cuelgue de la carpeta permitida:
   `1n8njw20WyC-uylqiMOZULj5tnDZjRjjA`.
7. Genera nombre final: `YYYYMMDD_nombredocumento.pdf`.
8. Si el nombre ya existe, crea sufijo incremental (`_1`, `_2`, ...).
9. Busca carpeta de persona por nombre bajo la carpeta base.
10. Si no existe, crea carpeta con `nombre_persona`.
11. Sube el PDF dentro de la carpeta de persona y devuelve metadatos + links de Drive.
12. Actualiza `dim_core_persona.sst_drive_folder_id` con el `folder_id` de destino usando `rut_persona`.
13. Actualiza en Supabase la tabla `brg_acreditacion_persona_requerimiento_sst`:
   - `link`: `https://drive.google.com/file/d/{file_id}/view?usp=drive_link`
   - `drive_pdf_id`: `{file_id}`
   por `id_registro_sst`.

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
  "file_name": "20260301_contrato_sst.pdf",
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
