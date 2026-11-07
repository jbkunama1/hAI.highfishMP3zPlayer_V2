# MCP DNS-Rebinding: LAN-IP Allowlist

Der MCP-SDK schuetzt Streamable HTTP gegen DNS-Rebinding. Der im Fehler genannte Host `192.168.178.26` ist in den Compose-Defaults explizit freigegeben (alle Ports); der Schutz bleibt aktiv. LAN-URL: `http://192.168.178.26:8066/agent/mcp`. Standard Browser-Origin: `http://192.168.178.26:8066`.

Aendern sich IP oder Port, in Portainer setzen:

```ini
MCP_ALLOWED_HOSTS=192.168.178.26:*
MCP_ALLOWED_ORIGINS=http://192.168.178.26:8066
```

Mehrere explizite Hostnamen/IPs kommasepariert; globaler Wildcard `*` ist verboten. Browser-Origins muessen genaue http(s)-Origins ohne Pfad, Query, Fragment oder Credentials sein. Eine gueltige HTTPS-PUBLIC_URL wird ebenfalls ergaenzt. Den `Authorization: Bearer <MCP_API_KEY>` Header weiter mitsenden.

Nach Image-Neubau und Stack-Update MCP-Verbindung trennen und Tools neu entdecken. Kein Deployment und kein echter Handshake auf dem Nutzerserver ausgefuehrt.
