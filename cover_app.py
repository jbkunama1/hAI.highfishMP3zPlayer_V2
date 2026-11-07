"""Player, login, editors, mobile views, administration, MCP and Telegram."""
import metadata_app
from cover_service import register_mcp, install_web
from app_login import install_login
from library_tools import install_library
from telegram_runtime import start_bot
from admin_ui import install_admin
from view_modes import install_views


def main():
    original = metadata_app.build_mcp

    def extended(service, backend):
        server = original(service, backend)
        register_mcp(server, service)
        install_web(backend, service)
        install_login(backend)
        install_admin(backend)
        install_views(backend)
        lib = install_library(server, backend)
        start_bot(lib)
        return server

    metadata_app.build_mcp = extended
    metadata_app.main()


if __name__ == '__main__':
    main()
