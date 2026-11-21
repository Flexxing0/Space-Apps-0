"""Application Factory de EarthLens: interfaz y API en el mismo origen."""

from flask import Flask
from pathlib import Path

from api.errors import register_error_handlers
from api.routes import api
from services.api_service import EarthLensService
from services.providers.bulk import PowerBulkService
from services.providers.cache import DEFAULT_CACHE_DIR, JsonCache
from services.geography.cities import CATALOG_PATH
from services.science.analysis_service import AnalysisService
from web.routes import web
from services.science.fingerprint import FingerprintService
from services.science.radar import DEFAULT_ARTIFACT_NAME, RadarService
from services.science.scientific import ScientificService
from services.science.hydrology import HydrologyService
from api.scientific import scientific_api
from services.workspace.time_machine_service import TimeMachineService
from services.prediction.forecast_service import ForecastService
from services.workspace.workspace import WorkspaceService
from api.workspace import workspace_api
from services.weather.weather import WeatherService
from api.weather import weather_api
from api.predictions import predictions_api
from services.storage.persistence import Store
from services.storage.predictions import SQLitePredictions
from services.events.events import EventService
from api.events import events_api
from services.events.planning import PlanningService
from services.workspace.time_navigation import TimeNavigationService
import secrets


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        MAX_CONTENT_LENGTH=16384,
        CACHE_DIR=DEFAULT_CACHE_DIR,
        CATALOG_PATH=CATALOG_PATH,
        POWER_REQUEST_DELAY=1.0,
        POWER_CACHE_MAX_AGE_DAYS=None,
        RADAR_ARTIFACT_PATH=None,
        WEATHER_COMMERCIAL=False,
        DATABASE_PATH=None,
        PREDICTION_DATABASE_PATH=None,
        SECRET_KEY=secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )
    app.config.from_prefixed_env(prefix="EARTHLENS")
    if config is not None:
        app.config.update(config)
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY']=secrets.token_hex(32)
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    bulk = PowerBulkService(
        JsonCache(app.config["CACHE_DIR"]),
        catalog_path=app.config["CATALOG_PATH"],
        request_delay=app.config["POWER_REQUEST_DELAY"],
        max_age_days=app.config["POWER_CACHE_MAX_AGE_DAYS"],
    )
    app.extensions["earthlens_service"] = EarthLensService(bulk)
    app.extensions["earthlens_science"] = ScientificService(app.extensions["earthlens_service"])
    app.extensions["earthlens_hydrology"] = HydrologyService(Path(app.config["CACHE_DIR"]).parent / "science")
    app.extensions["earthlens_analysis"] = AnalysisService(app.extensions["earthlens_service"])
    app.extensions["earthlens_time_machine"] = TimeMachineService(app.extensions["earthlens_analysis"],app.extensions["earthlens_science"])
    app.extensions["earthlens_forecast"] = ForecastService(app.extensions["earthlens_time_machine"])
    app.extensions['earthlens_workspace'] = WorkspaceService(app.extensions['earthlens_service'], app.extensions['earthlens_science'], app.extensions['earthlens_analysis'])
    app.extensions['earthlens_weather'] = WeatherService(app.extensions['earthlens_service'], Path(app.config['CACHE_DIR']).parent/'weather', commercial=app.config['WEATHER_COMMERCIAL'])
    app.extensions['earthlens_store'] = Store(app.config['DATABASE_PATH'] or Path(app.config['CACHE_DIR']).parent.parent/'runtime'/'earthlens.sqlite3')
    prediction_path = app.config['PREDICTION_DATABASE_PATH'] or (
        Path(app.config['CACHE_DIR']).parent.parent / 'runtime' / 'predictions.sqlite3')
    app.extensions['earthlens_prediction_reader'] = SQLitePredictions(prediction_path)
    app.extensions['earthlens_events'] = EventService(app.extensions['earthlens_store'],app.extensions['earthlens_service'])
    app.extensions['earthlens_planning'] = PlanningService(app.extensions['earthlens_weather'])
    app.extensions['earthlens_navigation'] = TimeNavigationService(app.extensions['earthlens_workspace'],app.extensions['earthlens_weather'])
    app.extensions["earthlens_fingerprint"] = FingerprintService(app.extensions["earthlens_analysis"])
    radar_path = app.config["RADAR_ARTIFACT_PATH"] or Path(app.config["CACHE_DIR"]).parent / DEFAULT_ARTIFACT_NAME
    app.extensions["earthlens_radar"] = RadarService(app.extensions["earthlens_analysis"], radar_path)
    app.register_blueprint(api)
    app.register_blueprint(scientific_api)
    app.register_blueprint(workspace_api)
    app.register_blueprint(weather_api)
    app.register_blueprint(predictions_api)
    app.register_blueprint(events_api)
    @app.after_request
    def private_response_headers(response):
        from flask import request
        response.headers['X-Content-Type-Options']='nosniff'
        if request.path.startswith(('/api/session','/api/events','/api/notifications')):
            response.headers['Cache-Control']='no-store'
            response.vary.add('Cookie')
        return response
    app.register_blueprint(web)
    register_error_handlers(app)
    return app


# Entrada WSGI para la configuración Vercel recibida de main; sin consultas al importar.
app = create_app()

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
