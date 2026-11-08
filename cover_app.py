"""Player, login, editors, mobile views, administration, MCP and Telegram."""
import metadata_app
from cover_service import register_mcp, install_web
from app_login import install_login
from library_tools import install_library
from telegram_runtime import start_bot
from admin_ui import install_admin
from view_modes import install_views
from mcp_security import settings as mcp_security_settings
from storage_config import configure_storage
from playlist_integration import install_playlists, enable_telegram_playlists
from ai_playlist import install_ai
from ai_catalog import install_catalog
from ai_studio import install_studio, enable_telegram_studio


def main():
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).with_name('.env'))
    configure_storage()
    original = metadata_app.build_mcp

    def extended(service, backend):
        server = original(service, backend)
        register_mcp(server, service)
        install_web(backend, service)
        install_login(backend)
        install_admin(backend)
        install_views(backend)
        lib = install_library(server, backend)
        install_playlists(server, lib)
        install_ai(lib)
        install_catalog(lib)
        install_studio(server, lib)
        enable_telegram_playlists()
        enable_telegram_studio()
        start_bot(lib)
        return server

    metadata_app.build_mcp = extended
    metadata_app.mcp_transport_security = mcp_security_settings
    metadata_app.main()


if __name__ == '__main__':
    main()
