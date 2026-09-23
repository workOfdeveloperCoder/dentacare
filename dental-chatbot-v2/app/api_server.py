from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.config import router as config_router
from app.config import API_URL, CORS_ORIGINS, DEFAULT_FLOW, FRONTEND_DIR
from app.db import ensure_schema
from app.site_config import public_config, write_site_config


ensure_schema()
write_site_config()

app = FastAPI(
    title="Site Chatbot API",
    description="JSON-driven decision-tree chatbot. Change flow.json to change the bot.",
    version="2.0.0",
)


allow_origins = CORS_ORIGINS or ["*"]
allow_all = allow_origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(chat_router)
app.include_router(config_router)

app.mount(
    "/frontend",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="frontend",
)


@app.get("/")
def root():
    return {
        "name": "Site Chatbot API",
        "status": "ok",
        "api_url": API_URL,
        "default_flow": DEFAULT_FLOW,
        "widget": f"{API_URL}/widget.js",
        "public_config": f"{API_URL}/public-config",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/public-config")
def get_public_config():
    """Expose URL/flow settings for website embeds (from .env)."""
    return JSONResponse(
        public_config(),
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/widget.js")
def widget_js():
    return FileResponse(
        FRONTEND_DIR / "js" / "chatbot.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/widget.css")
def widget_css():
    return FileResponse(
        FRONTEND_DIR / "css" / "chatbot.css",
        media_type="text/css",
        headers={"Cache-Control": "no-cache"},
    )
