"""Explicit MCP SDK Host/Origin allowlist; DNS-rebinding protection stays enabled."""
import ipaddress
import os
import re
from urllib.parse import urlsplit

NAME_RE=re.compile(r'^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*$')


def csv_values(name):
    return [v.strip() for v in os.getenv(name,'').split(',') if v.strip()]


def parse_host(value):
    if not value or any(c.isspace() for c in value): raise ValueError('Invalid allowed host')
    if value.startswith('['):
        match=re.fullmatch(r'\[([0-9A-Fa-f:.]+)\](?::(\d{1,5}|\*))?',value)
        if not match: raise ValueError('Invalid bracketed IPv6 host')
        try: ipaddress.IPv6Address(match.group(1))
        except ValueError as exc: raise ValueError('Invalid IPv6 address') from exc
        port=match.group(2)
    else:
        if value.count(':')>1: raise ValueError('IPv6 hosts must be bracketed')
        host,sep,suffix=value.partition(':')
        port=suffix if sep else None
        try: ipaddress.IPv4Address(host)
        except ValueError:
            if not NAME_RE.fullmatch(host): raise ValueError('Invalid hostname')
        if host=='*': raise ValueError('Wildcard host is forbidden')
    if port not in (None,'*') and not 1<=int(port)<=65535: raise ValueError('Port out of range')


def host_values():
    values=['localhost:*','127.0.0.1:*','mp3z:*','192.168.178.26:*']
    for value in csv_values('MCP_ALLOWED_HOSTS'):
        parse_host(value)
        if value not in values: values.append(value)
    return values


def origin_values():
    values=['http://192.168.178.26:8066']
    for value in csv_values('MCP_ALLOWED_ORIGINS'):
        p=urlsplit(value)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):
            raise ValueError('MCP_ALLOWED_ORIGINS must contain exact http(s) origins only')
        if value not in values: values.append(value)
    public=os.getenv('PUBLIC_URL','').strip()
    if public:
        p=urlsplit(public)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):
            raise ValueError('PUBLIC_URL must be an HTTPS origin without path/query/credentials')
        if public not in values: values.append(public)
    return values


def settings():
    from mcp.server.transport_security import TransportSecuritySettings
    return TransportSecuritySettings(enable_dns_rebinding_protection=True,
        allowed_hosts=host_values(),allowed_origins=origin_values())
