# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import os

from azure.identity import AzureCliCredential, ManagedIdentityCredential
from azure.storage.blob.aio import BlobServiceClient
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Mount

from bots import AssistantBot, MagenticBot
from bots.access_control_middleware import AccessControlMiddleware
from bots.show_typing_middleware import ShowTypingMiddleware
from config import DefaultConfig, load_agent_config, setup_app_insights_logging, setup_logging
from data_models.app_context import AppContext
from data_models.data_access import create_data_access
from mcp_app import create_fast_mcp_app
from routes.api.chats import chats_routes
from routes.api.messages import messages_routes
from routes.api.time import time_routes
from routes.api.user import user_routes
from routes.patient_data.patient_data_routes import patient_data_routes
from routes.views.patient_data_answer_routes import patient_data_answer_source_routes
from routes.views.patient_timeline_routes import patient_timeline_entry_source_routes

load_dotenv(".env")

# Setup default logging and minimum log level severity for your environment that you want to consume
log_level = logging.INFO
setup_logging(log_level=log_level)

# Load Azure Credential
credential = None
if os.getenv("WEBSITE_SITE_NAME") is not None:
    try:
        credential = ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID"))
    except Exception as e:
        logger.warning(f"ManagedIdentityCredential unavailable: {e}")
else:
    try:
        credential = AzureCliCredential()
    except Exception:
        credential = None

# Setup Application Insights logging
if credential:
    setup_app_insights_logging(credential=credential, log_level=log_level)


def create_app_context() -> AppContext:
    '''Create the application context for commonly used objects in the application.'''

    # Load agent configuration
    scenario = os.getenv("SCENARIO", "default")
    agent_config = load_agent_config(scenario)

    # Setup data access
    blob_endpoint = os.getenv("APP_BLOB_STORAGE_ENDPOINT")
    blob_service_client = None
    if blob_endpoint and blob_endpoint.lower() not in ("local", "none", "") and credential:
        try:
            blob_service_client = BlobServiceClient(
                account_url=blob_endpoint,
                credential=credential,
            )
        except Exception as e:
            logger.warning(f"Could not connect to Blob Storage: {e}. Falling back to local data access.")

    data_access = create_data_access(blob_service_client, credential)

    return AppContext(
        all_agent_configs=agent_config,
        blob_service_client=blob_service_client,
        credential=credential,
        data_access=data_access,
    )


def create_app(
    bots: dict,
    app_context: AppContext,
) -> FastAPI:
    app = FastAPI()
    app.include_router(messages_routes(adapters, bots))
    app.include_router(chats_routes(app_context))
    app.include_router(user_routes())
    app.include_router(patient_data_routes(app_context.blob_service_client))
    app.include_router(patient_data_answer_source_routes(app_context.data_access))
    app.include_router(patient_timeline_entry_source_routes(app_context.data_access))
    app.include_router(time_routes())

    # Serve static files from the React build directory or democlient/build
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    democlient_build_path = os.path.join(repo_root, "democlient", "build")
    static_files_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

    client_dir = None
    if os.path.exists(os.path.join(democlient_build_path, "index.html")):
        client_dir = democlient_build_path
    elif os.path.exists(os.path.join(static_files_path, "static", "index.html")):
        client_dir = os.path.join(static_files_path, "static")
    elif os.path.exists(os.path.join(static_files_path, "index.html")):
        client_dir = static_files_path

    if client_dir:
        assets_path = os.path.join(client_dir, "assets")
        if os.path.exists(assets_path):
            app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

        static_sub = os.path.join(client_dir, "static")
        if os.path.exists(static_sub):
            app.mount("/static", StaticFiles(directory=static_sub), name="static")

        # Add a route for the root URL to serve index.html
        @app.get("/")
        async def serve_root():
            index_path = os.path.join(client_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {"detail": "React app not built yet"}

        # Add a catch-all route to serve index.html for client-side routing
        @app.get("/{full_path:path}")
        async def serve_react_app(full_path: str):
            index_path = os.path.join(client_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {"detail": "React app not built yet"}

    return app


app_context = create_app_context()

# Create Teams specific objects
adapters = {
    agent["name"]: CloudAdapter(ConfigurationBotFrameworkAuthentication(
        DefaultConfig(botId=agent["bot_id"]))).use(ShowTypingMiddleware()).use(AccessControlMiddleware())
    for agent in app_context.all_agent_configs
}
bot_config = {
    "adapters": adapters,
    "app_context": app_context,
    "turn_contexts": {}
}
bots = {
    agent["name"]: AssistantBot(agent, **bot_config) if agent["name"] != "magentic"
    else MagenticBot(agent, **bot_config)
    for agent in app_context.all_agent_configs
}

teams_app = create_app(bots, app_context)
fast_mcp_app, lifespan = create_fast_mcp_app(app_context)

app = Starlette(
    routes=[
        Mount('/mcp', app=fast_mcp_app),
        Mount('/', teams_app),
    ], lifespan=lifespan)
