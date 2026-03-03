"""Router for PDF document uploads to Google Drive."""
import base64
import binascii
import logging

from fastapi import APIRouter, HTTPException, status

from app.models import SubirDocumentoRequest, SubirDocumentoResponse
from app.services.drive_service import (
    ALLOWED_ROOT_FOLDER_ID,
    DriveApiError,
    DriveDeleteError,
    DriveFileNotFoundError,
    DriveFolderOperationError,
    DriveInvalidFolderError,
    DrivePermissionError,
    DriveUploadError,
    drive_service,
)
from app.services.supabase_service import (
    SupabaseConfigError,
    SupabaseOperationError,
    supabase_service,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024

router = APIRouter(prefix="/documentos", tags=["documentos"])


def _decode_base64_document(documento_base64: str) -> bytes:
    """Decode base64 content, supporting optional data URI prefix."""
    data = documento_base64.strip()
    if "," in data and data.lower().startswith("data:"):
        data = data.split(",", 1)[1]

    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="documento_base64 no es valido",
        ) from exc


def _normalize_drive_pdf_id(value: object) -> str:
    """Normalize drive_pdf_id from DB to a safe string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


@router.post("/subir", response_model=SubirDocumentoResponse)
async def subir_documento(request: SubirDocumentoRequest):
    """Upload a PDF document to Google Drive."""
    file_bytes = _decode_base64_document(request.documento_base64)

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El documento excede el tamano maximo de {MAX_FILE_SIZE_BYTES} bytes",
        )

    try:
        base_folder_id = request.folder_id or ALLOWED_ROOT_FOLDER_ID

        if not drive_service.is_descendant_of_root(base_folder_id, ALLOWED_ROOT_FOLDER_ID):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="folder_id fuera de la carpeta permitida",
            )

        folder_id_destino, carpeta_persona_creada = drive_service.resolve_or_create_person_folder(
            base_folder_id=base_folder_id,
            nombre_persona=request.nombre_persona,
        )

        registro_sst = supabase_service.obtener_registro_sst(request.id_registro_sst)
        if not registro_sst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontro registro SST con id_registro_sst={request.id_registro_sst}",
            )

        drive_pdf_id_anterior = _normalize_drive_pdf_id(registro_sst.get("drive_pdf_id"))
        if drive_pdf_id_anterior:
            eliminado = drive_service.eliminar_archivo(drive_pdf_id_anterior)
            if eliminado:
                logger.info(
                    "Archivo previo eliminado id_registro_sst=%s drive_pdf_id_anterior=%s",
                    request.id_registro_sst,
                    drive_pdf_id_anterior,
                )
            else:
                logger.info(
                    "Archivo previo no existia (404), se continua id_registro_sst=%s drive_pdf_id_anterior=%s",
                    request.id_registro_sst,
                    drive_pdf_id_anterior,
                )

        candidate_name = drive_service.build_final_filename(
            request.fecha_inicio,
            request.nombre_documento,
            request.nombre_persona,
        )
        final_name = drive_service.resolve_non_colliding_name(folder_id_destino, candidate_name)

        try:
            uploaded = drive_service.upload_pdf_bytes(
                folder_id=folder_id_destino,
                final_name=final_name,
                file_bytes=file_bytes,
            )
        except DriveUploadError:
            # If previous file was removed and upload fails, clear DB references.
            if drive_pdf_id_anterior:
                try:
                    supabase_service.limpiar_documento_sst(request.id_registro_sst)
                    logger.warning(
                        "Subida fallida tras borrar previo; SST limpiado id_registro_sst=%s",
                        request.id_registro_sst,
                    )
                except SupabaseOperationError:
                    logger.exception(
                        "Subida fallida y no se pudo limpiar SST id_registro_sst=%s",
                        request.id_registro_sst,
                    )
            raise

        file_id = uploaded["id"]
        link = f"https://drive.google.com/file/d/{file_id}/view?usp=drive_link"
        logger.info(
            "Nuevo archivo subido id_registro_sst=%s drive_pdf_id_anterior=%s drive_pdf_id_nuevo=%s",
            request.id_registro_sst,
            drive_pdf_id_anterior or None,
            file_id,
        )

        actualizado = supabase_service.actualizar_documento_sst(
            id_registro_sst=request.id_registro_sst,
            link=link,
            drive_pdf_id=file_id,
        )
        if not actualizado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontro registro SST con id_registro_sst={request.id_registro_sst}",
            )

        persona_actualizada = supabase_service.actualizar_sst_drive_folder_persona(
            rut_persona=request.rut_persona,
            folder_id=folder_id_destino,
        )
        if not persona_actualizada:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontro persona con rut={request.rut_persona} en dim_core_persona",
            )

        return SubirDocumentoResponse(
            ok=True,
            id_registro_sst=request.id_registro_sst,
            file_id=file_id,
            file_name=uploaded["name"],
            folder_id=base_folder_id,
            folder_id_destino=folder_id_destino,
            carpeta_persona_creada=carpeta_persona_creada,
            persona_actualizada=True,
            link=link,
            db_actualizado=True,
            web_view_link=uploaded.get("webViewLink"),
            web_content_link=uploaded.get("webContentLink"),
            size_bytes=int(uploaded["size"]) if uploaded.get("size") is not None else None,
            created_time=uploaded.get("createdTime"),
        )
    except DriveFileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DriveInvalidFolderError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except DrivePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except DriveFolderOperationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except DriveDeleteError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except DriveUploadError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except SupabaseConfigError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except SupabaseOperationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except DriveApiError as exc:
        logger.exception("Drive API error while uploading document")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - safety net for unexpected runtime issues
        logger.exception(
            "Error no controlado en /documentos/subir id_registro_sst=%s",
            request.id_registro_sst,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar el documento",
        ) from exc
