from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import Settings
from app.db import init_db, make_engine, make_session_factory
from app.inference import build_inference
from app.routers import health, ingest, inspect, notebooks, retrieve
from app.vault import bind_list_chunks, bind_retrieve, mount_study_logic


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.files_dir.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.db_path)
    init_db(engine)
    inference = build_inference(settings)

    app = FastAPI(
        title="Notbook Study API",
        description=(
            "S0 local vault: notebooks, ingest (PDF / markdown / paste / image OCR), "
            "inspectable chunks, retrieve with citation ids, and an inference adapter."
        ),
        version=__version__,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.SessionLocal = make_session_factory(engine)
    app.state.inference = inference
    app.state.retrieve = bind_retrieve(app)
    app.state.list_chunks = bind_list_chunks(app)

    app.include_router(health.router)
    app.include_router(notebooks.router)
    app.include_router(ingest.router)
    app.include_router(retrieve.router)
    app.include_router(inspect.router)
    mount_study_logic(app)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": "notbook-study-api",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    # Study-logic routes (mounted via install_study_logic):
    #   POST /api/v1/notebooks/{id}/topics/propose
    #   POST /api/v1/notebooks/{id}/topics/confirm
    #   GET  /api/v1/notebooks/{id}/topics
    #   POST /api/v1/notebooks/{id}/quizzes
    #   POST /api/v1/quizzes/{id}/attempts
    #   GET  /api/v1/notebooks/{id}/scoreboard
    #   GET|POST /api/v1/notebooks/{id}/chats/orchestrator
    #   GET  /api/v1/notebooks/{id}/chats
    #   GET  /api/v1/notebooks/{id}/spawn-offer
    #   POST /api/v1/notebooks/{id}/chats/specialists
    #   POST /api/v1/chats/{id}/messages
    #   POST /api/v1/chats/{id}/close
    #   GET  /api/v1/notebooks/{id}/handoffs

    return app


app = create_app()
