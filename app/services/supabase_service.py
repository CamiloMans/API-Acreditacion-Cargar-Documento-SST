"""Supabase service for persisting SST document metadata."""
import logging

from supabase import Client, create_client

from app.config import settings

logger = logging.getLogger(__name__)

TABLE_SST = "brg_acreditacion_persona_requerimiento_sst"
TABLE_PERSONA = "dim_core_persona"


class SupabaseError(Exception):
    """Base class for Supabase service errors."""


class SupabaseConfigError(SupabaseError):
    """Raised when Supabase configuration is missing."""


class SupabaseOperationError(SupabaseError):
    """Raised when a Supabase request fails."""


class SupabaseService:
    """Service for SST metadata updates in Supabase."""

    def __init__(self):
        self.client: Client | None = None
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        else:
            logger.warning(
                "Supabase credentials are not configured. "
                "Set SUPABASE_URL and SUPABASE_KEY to enable DB updates."
            )

    def _require_client(self) -> Client:
        if self.client is None:
            raise SupabaseConfigError(
                "Supabase no esta configurado (faltan SUPABASE_URL o SUPABASE_KEY)"
            )
        return self.client

    def actualizar_documento_sst(
        self,
        id_registro_sst: int,
        link: str,
        drive_pdf_id: str,
    ) -> bool:
        """Update link and drive file ID for a SST record."""
        client = self._require_client()
        payload = {
            "link": link,
            "drive_pdf_id": drive_pdf_id,
        }

        try:
            response = self._update_sst_by_column(client, "id", id_registro_sst, payload)
            if response.data and len(response.data) > 0:
                return True

            fallback_response = self._safe_update_sst_by_fallback_column(
                client,
                "id_registro_sst",
                id_registro_sst,
                payload,
            )
            if fallback_response is not None and fallback_response.data and len(fallback_response.data) > 0:
                return True

            return False
        except SupabaseError:
            raise
        except Exception as exc:
            raise SupabaseOperationError(
                "Error actualizando registro SST en Supabase"
            ) from exc

    def obtener_registro_sst(self, id_registro_sst: int) -> dict | None:
        """Get SST record by id with fallback to id_registro_sst."""
        client = self._require_client()
        try:
            response = (
                client.table(TABLE_SST)
                .select("id,drive_pdf_id,link")
                .eq("id", id_registro_sst)
                .limit(1)
                .execute()
            )
            if response.data and len(response.data) > 0:
                return response.data[0]

            fallback_response = self._safe_select_sst_by_fallback_column(
                client,
                "id_registro_sst",
                id_registro_sst,
            )
            if fallback_response.data and len(fallback_response.data) > 0:
                return fallback_response.data[0]

            return None
        except SupabaseError:
            raise
        except Exception as exc:
            raise SupabaseOperationError(
                "Error consultando registro SST en Supabase"
            ) from exc

    def limpiar_documento_sst(self, id_registro_sst: int) -> bool:
        """Clear drive_pdf_id and link in SST record."""
        client = self._require_client()
        payload = {
            "drive_pdf_id": None,
            "link": None,
        }
        try:
            response = self._update_sst_by_column(client, "id", id_registro_sst, payload)
            if response.data and len(response.data) > 0:
                return True

            fallback_response = self._safe_update_sst_by_fallback_column(
                client,
                "id_registro_sst",
                id_registro_sst,
                payload,
            )
            if fallback_response is not None and fallback_response.data and len(fallback_response.data) > 0:
                return True

            return False
        except SupabaseError:
            raise
        except Exception as exc:
            raise SupabaseOperationError(
                "Error limpiando documento SST en Supabase"
            ) from exc

    def _update_sst_by_column(self, client: Client, column: str, value: int, payload: dict):
        return (
            client.table(TABLE_SST)
            .update(payload)
            .eq(column, value)
            .execute()
        )

    def _safe_update_sst_by_fallback_column(
        self,
        client: Client,
        column: str,
        value: int,
        payload: dict,
    ):
        try:
            return self._update_sst_by_column(client, column, value, payload)
        except Exception as exc:
            logger.warning(
                "Fallback update por columna '%s' no disponible o fallo: %s",
                column,
                exc,
            )
            return None

    def _safe_select_sst_by_fallback_column(self, client: Client, column: str, value: int):
        try:
            return (
                client.table(TABLE_SST)
                .select("id,drive_pdf_id,link")
                .eq(column, value)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.warning(
                "Fallback select por columna '%s' no disponible o fallo: %s",
                column,
                exc,
            )
            class _EmptyResponse:
                data = []

            return _EmptyResponse()

    def _normalizar_rut(self, rut: str) -> str:
        return rut.replace(".", "").replace(" ", "").upper()

    def actualizar_sst_drive_folder_persona(
        self,
        rut_persona: str,
        folder_id: str,
    ) -> bool:
        """Update dim_core_persona.sst_drive_folder_id using person RUT."""
        client = self._require_client()
        payload = {"sst_drive_folder_id": folder_id}
        rut_raw = rut_persona.strip()
        rut_normalizado = self._normalizar_rut(rut_raw)
        rut_candidates = [rut_raw]
        if rut_normalizado != rut_raw:
            rut_candidates.append(rut_normalizado)

        try:
            for column in ("rut", "rut_persona"):
                for rut_value in rut_candidates:
                    try:
                        response = (
                            client.table(TABLE_PERSONA)
                            .update(payload)
                            .eq(column, rut_value)
                            .execute()
                        )
                    except Exception as exc:
                        logger.warning(
                            "Update dim_core_persona por columna '%s' fallo: %s",
                            column,
                            exc,
                        )
                        continue
                    if response.data and len(response.data) > 0:
                        return True
            return False
        except SupabaseError:
            raise
        except Exception as exc:
            raise SupabaseOperationError(
                "Error actualizando sst_drive_folder_id en dim_core_persona"
            ) from exc


supabase_service = SupabaseService()
