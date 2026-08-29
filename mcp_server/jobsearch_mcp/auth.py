"""Authentication for the HTTP transport.

Three modes, chosen with the ``MCP_AUTH`` environment variable:

``none``
    No authentication. This is the default **only** under the stdio transport,
    where the client launches the process directly and nothing is reachable
    over the network. Selecting it for an HTTP server that is not bound to
    localhost is refused outright - an unauthenticated job-search server on a
    public address hands your profile, contact details and application history
    to anyone who finds the URL.

``token``
    A shared bearer token you generate and paste into your client's config.
    This is the simple hosted option: no identity provider, no OAuth
    round-trip, works with any client that lets you set an ``Authorization``
    header.

``oauth``
    Full OAuth via Microsoft Entra ID. Clients discover it automatically and a
    browser window completes the login, so there is no token to paste - but it
    requires an Entra tenant and an app registration. Only worth it if you
    already have one, or if a client you use offers no header field.

Authentication is not authorization. Completing a login against your tenant
proves who someone is, not that they may read your CV and rewrite your profile.
``MCP_ALLOWED_EMAILS`` is therefore required in oauth mode and fails closed when
unset: without it every colleague in the tenant reaches the profile-write tools,
and a tenant of "common" or "organizations" would open them to any Microsoft
account that found the URL.
"""
from __future__ import annotations

import logging
import os
import secrets

log = logging.getLogger("jobsearch-mcp.auth")


class AuthConfigError(RuntimeError):
    """Raised when the requested auth mode cannot be configured safely."""


def _bound_to_localhost() -> bool:
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    return host in ("127.0.0.1", "localhost", "::1")


def mode() -> str:
    explicit = os.environ.get("MCP_AUTH")
    if explicit:
        return explicit.strip().lower()
    # stdio needs no auth; an HTTP server does unless it is loopback-only.
    if transport() == "stdio":
        return "none"
    return "none" if _bound_to_localhost() else "token"


def transport() -> str:
    return os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()


def _build_token_auth():
    """Static bearer token verification.

    The token is compared by FastMCP's own verifier; we only enforce that one
    exists and is not trivially guessable. Refusing a short token is deliberate:
    the whole security of this mode rests on it, and "changeme" in a copied
    example config is the realistic failure.
    """
    from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

    token = os.environ.get("MCP_TOKEN", "").strip()
    if not token:
        raise AuthConfigError(
            "MCP_AUTH=token requires MCP_TOKEN to be set.\n"
            f"Generate one with:  python -c \"import secrets;print(secrets.token_urlsafe(32))\"\n"
            f"Suggested value:    {secrets.token_urlsafe(32)}")
    if len(token) < 24:
        raise AuthConfigError(
            "MCP_TOKEN is too short to be a credential (need at least 24 "
            "characters). Generate one with: "
            "python -c \"import secrets;print(secrets.token_urlsafe(32))\"")
    log.info("auth: static bearer token")
    return StaticTokenVerifier(
        tokens={token: {"client_id": "jobsearch-client", "scopes": ["mcp-read"]}},
        required_scopes=["mcp-read"])


def _build_oauth_auth():
    """Microsoft Entra ID OAuth.

    Durable OAuth state: dynamic client registrations and encrypted tokens
    persist to a directory, and the JWT signing key is stable, so a restart does
    not wipe the registry and break connected clients with "Client Not
    Registered".
    """
    try:
        from fastmcp.server.auth.providers.azure import AzureProvider
        from key_value.aio.stores.filetree import FileTreeStore
    except ImportError as exc:
        raise AuthConfigError(
            "MCP_AUTH=oauth needs the optional OAuth dependencies. Install "
            "them with:  pip install 'jobsearch-mcp[oauth]'") from exc

    missing = [k for k in ("AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
                           "AZURE_TENANT_ID", "MCP_BASE_URL",
                           "MCP_JWT_SIGNING_KEY") if not os.environ.get(k)]
    if missing:
        raise AuthConfigError(
            "MCP_AUTH=oauth requires these environment variables: "
            + ", ".join(missing))

    # Fail closed. A login proves identity, not entitlement: without this list
    # anyone who can authenticate against the tenant reaches every tool,
    # including the ones that rewrite the profile a CV is drafted from.
    if not allowed_identities():
        raise AuthConfigError(
            "MCP_AUTH=oauth requires MCP_ALLOWED_EMAILS: a comma-separated "
            "list of the accounts allowed to use this server.\n"
            "Signing in only proves who someone is. Without this list, every "
            "account that can authenticate against your tenant can read your "
            "profile and rewrite it.\n"
            "Example:  MCP_ALLOWED_EMAILS=you@example.com")

    tenant = os.environ["AZURE_TENANT_ID"].strip().lower()
    if tenant in ("common", "organizations", "consumers"):
        raise AuthConfigError(
            f"AZURE_TENANT_ID={tenant!r} is a multi-tenant endpoint: it lets "
            "any Microsoft account complete the login, not just yours. Set it "
            "to your specific tenant GUID instead.")

    # Registration is open (dynamic client registration), so the redirect target
    # is the real control: an authorization code is only ever delivered to one of
    # these. Without it any caller could register https://attacker.example/cb and
    # have a code for this server sent there.
    allowed = ["http://localhost:*", "http://localhost:*/*",
               "http://127.0.0.1:*", "http://127.0.0.1:*/*"]
    extra = os.environ.get("MCP_ALLOWED_REDIRECT_URIS", "")
    allowed += [u.strip() for u in extra.split(",") if u.strip()]

    log.info("auth: Entra OAuth")
    return AzureProvider(
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
        tenant_id=os.environ["AZURE_TENANT_ID"],
        base_url=os.environ["MCP_BASE_URL"],
        required_scopes=["mcp-read"],
        redirect_path="/auth/callback",
        client_storage=FileTreeStore(
            data_directory=os.environ.get(
                "MCP_OAUTH_STORE",
                os.path.join(os.environ.get("JOBSEARCH_STATE_DIR", "."),
                             "oauth-store"))),
        jwt_signing_key=os.environ["MCP_JWT_SIGNING_KEY"],
        # The built-in consent screen is disabled deliberately. Its CSRF token is
        # single-use and some browsers replay the form POST milliseconds later:
        # the first submit returns 302 and the replay returns 403, so the error
        # page is what renders and the flow dies. It guards against a malicious
        # client being silently approved, which is exactly what the redirect
        # allowlist above prevents - and Entra still authenticates every login.
        require_authorization_consent=False,
    )


def allowed_identities() -> set[str]:
    """Accounts permitted to use this server, lowercased.

    Empty means "not configured". Callers in oauth mode treat that as fatal
    rather than as "allow everyone".
    """
    raw = os.environ.get("MCP_ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def identity_of(token) -> str | None:
    """Best-effort email or subject for an authenticated caller.

    Providers differ in which claim carries the address, so several are tried in
    turn. Returning None means the token carried no recognizable identity, which
    the middleware treats as a denial rather than guessing.
    """
    claims = {}
    for attr in ("claims", "token_claims", "payload"):
        value = getattr(token, attr, None)
        if isinstance(value, dict):
            claims = value
            break
    for key in ("email", "preferred_username", "upn", "unique_name", "sub"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def build():
    """Return a FastMCP auth provider, or None for no authentication."""
    m = mode()
    if m == "none":
        if transport() != "stdio" and not _bound_to_localhost():
            raise AuthConfigError(
                "Refusing to start: MCP_AUTH=none with MCP_TRANSPORT=http bound "
                f"to {os.environ.get('MCP_HOST')}. An unauthenticated job-search "
                "server on a non-loopback address exposes your profile and "
                "application history to anyone who finds it.\n"
                "Either set MCP_HOST=127.0.0.1 (and reach it through an SSH "
                "tunnel or reverse proxy), or set MCP_AUTH=token.")
        log.info("auth: none (%s transport)", transport())
        return None
    if m == "token":
        return _build_token_auth()
    if m in ("oauth", "entra", "azure"):
        return _build_oauth_auth()
    raise AuthConfigError(
        f"Unknown MCP_AUTH value {m!r}. Valid values: none, token, oauth.")
