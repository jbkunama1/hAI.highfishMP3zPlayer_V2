"""Cover and dedicated app-login adapter for the metadata application."""
import metadata_app
from cover_service import register_mcp, install_web
from app_login import install_login


def main():
    original = metadata_app.build_mcp

    def extended(service, backend):
        server = original(service, backend)
        register_mcp(server, service)
        install_web(backend, service)
        install_login(backend)
        return server

    metadata_app.build_mcp = extended
    metadata_app.main()


if __name__ == '__main__':
    main()
