"""Flask application factory."""

from __future__ import annotations

import redis
import sentry_sdk
from flask_openapi3 import Info, OpenAPI
from sentry_sdk.integrations.flask import FlaskIntegration

from app.api.brands import brands_bp
from app.api.competitors import competitors_bp
from app.api.health import health_bp
from app.api.runs import runs_bp
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers, validation_error_callback
from app.core.logging import configure_logging, get_logger
from app.core.middleware import register_middleware
from app.db.base import init_engine, remove_session

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> OpenAPI:
    settings = settings or get_settings()

    configure_logging(settings.log_level)

    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, integrations=[FlaskIntegration()])

    info = Info(title="AI Visibility Platform API", version="0.1.0")
    app = OpenAPI(
        __name__,
        info=info,
        doc_prefix="/api/docs",
        validation_error_status=422,
        validation_error_callback=validation_error_callback,
    )
    app.config["SECRET_KEY"] = settings.secret_key

    init_engine(settings.database_url)
    app.extensions["redis"] = redis.Redis.from_url(settings.redis_url)

    register_middleware(app)
    register_error_handlers(app)

    app.register_api(brands_bp)
    app.register_api(competitors_bp)
    app.register_api(runs_bp)
    app.register_blueprint(health_bp)

    @app.teardown_appcontext
    def _remove_db_session(_exc: BaseException | None) -> None:
        remove_session()

    logger.info("app_created", flask_env=settings.flask_env)
    return app
