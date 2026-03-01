"""Main FastAPI application."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import documentos

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="API Documentos Drive",
    description="API para subir documentos PDF a Google Drive desde base64.",
    version="1.0.0",
)

allowed_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documentos.router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return JSONResponse(
        content={
            "nombre": "API Documentos Drive",
            "version": "1.0.0",
            "descripcion": "API para subir documentos PDF a Google Drive desde base64.",
            "endpoints": {
                "subir_documento": "/documentos/subir",
                "docs": "/docs",
                "health": "/health",
            },
        }
    )


@app.get("/health")
async def health():
    """Health endpoint."""
    return JSONResponse(content={"status": "healthy", "environment": settings.ENVIRONMENT})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
