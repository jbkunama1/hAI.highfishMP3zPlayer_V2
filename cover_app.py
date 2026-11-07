"""Cover extension adapter for the existing metadata application."""
import metadata_app
from cover_service import register_mcp, install_web


def main():
    original = metadata_app.build_mcp

    def extended(service, backend):
        server = original(service, backend)
        register_mcp(server, service)
        install_web(backend, service)
        return server

    metadata_app.build_mcp = extended
    metadata_app.main()


if __name__ == '__main__':
    main()
