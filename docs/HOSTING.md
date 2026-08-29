# Hosting the server

**You do not need this.** The Quick Start in the main README runs the server on
your own computer, which is what most people want. Read on only if you want to:

- reach your job search from your phone
- share one server between several devices
- keep it running while your laptop is closed

Hosting means the server is reachable over a network, so it has to be
authenticated. It holds your CV, contact details and application history.

---

## Option A: SSH tunnel (simplest, most private)

If you already have a Linux box or VPS you can SSH into, this needs no
authentication setup, no domain and no certificates. The server stays bound to
localhost on the remote machine, and SSH does the rest.

On the server:

```bash
git clone https://github.com/treymorgan/jobsearch-apply-mcp.git
cd jobsearch-apply-mcp
pip install -e .
cp jobsearch.config.example.json jobsearch.config.json   # then edit it
MCP_TRANSPORT=http MCP_HOST=127.0.0.1 jobsearch-mcp
```

On Windows PowerShell, set the variables first:

```powershell
$env:MCP_TRANSPORT="http"; $env:MCP_HOST="127.0.0.1"; jobsearch-mcp
```

On your laptop:

```bash
ssh -N -L 8791:127.0.0.1:8791 user@your-server
```

Then point your MCP client at `http://127.0.0.1:8791/mcp`.

This does not work from a phone, which is the trade-off.

---

## Option B: Shared token (recommended for phone access)

A single secret you generate and paste into your client's settings. No identity
provider, no OAuth, works with any client that lets you set a header.

### 1. Generate a token

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep it somewhere safe. Anyone with it can read your profile.

### 2. Run the server

```bash
cd mcp_server
cp .env.example .env
```

Edit `.env`:

```
MCP_AUTH=token
MCP_TOKEN=<the token you just generated>
```

Then:

```bash
mkdir -p data profile config
cp ../jobsearch.config.json config/
docker compose up -d --build
```

Or without Docker:

```bash
MCP_TRANSPORT=http MCP_HOST=127.0.0.1 MCP_AUTH=token MCP_TOKEN=<token> jobsearch-mcp
```

PowerShell:

```powershell
$env:MCP_TRANSPORT="http"; $env:MCP_AUTH="token"; $env:MCP_TOKEN="<token>"; jobsearch-mcp
```

### 3. Put HTTPS in front of it

The compose file binds to `127.0.0.1` on purpose, so nothing is exposed yet.
Publish it with whichever of these you already run:

- **Caddy or nginx** as a reverse proxy with a TLS certificate
- **Cloudflare Tunnel**, if the host has no public IP. Create the tunnel in the
  Cloudflare dashboard pointing at `http://localhost:8791`, put the token in
  `.env` as `CF_TUNNEL_TOKEN`, and start with:

  ```bash
  docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d
  ```

  A tunnel is transport, not authentication. Keep `MCP_AUTH=token` set.

> **Do not** expose the port directly without TLS. A bearer token sent over
> plain HTTP is readable by anything on the network path.

### 4. Connect a client

```json
{
  "mcpServers": {
    "jobsearch": {
      "type": "http",
      "url": "https://jobs.example.com/mcp",
      "headers": { "Authorization": "Bearer YOUR-TOKEN-HERE" }
    }
  }
}
```

---

## Option C: Microsoft Entra ID sign-in

Only worth it if you already have an Entra tenant, or if a client you use
offers no way to set a header. Clients discover the login automatically and a
browser window completes it, so there is no token to paste.

```bash
pip install -e ".[oauth]"
```

Register an application in Entra ID with redirect URI
`https://your-domain/auth/callback`, then set in `.env`:

```
MCP_AUTH=oauth
MCP_BASE_URL=https://your-domain
MCP_JWT_SIGNING_KEY=<any long random string, kept stable>
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_TENANT_ID=<your specific tenant GUID>
MCP_ALLOWED_EMAILS=you@example.com
```

> **`MCP_ALLOWED_EMAILS` is required, and the server refuses to start without
> it.** Signing in proves *who* someone is, not that they may use your server.
> Without this list, every account that can authenticate against your tenant
> reaches every tool, including the ones that rewrite the profile your CVs are
> drafted from. List only the accounts that should have access, comma-separated.

> **`AZURE_TENANT_ID` must be a specific tenant GUID.** The values `common`,
> `organizations` and `consumers` are multi-tenant endpoints: any Microsoft
> account in the world can complete a login against them. The server rejects
> those three outright.

Also restrict the app registration itself, in the Azure portal under
**Enterprise applications → your app → Properties**: set *Assignment required*
to **Yes**, then grant only your own account under **Users and groups**. That
enforces the same rule at the identity provider, so a misconfigured environment
variable is not the only thing standing between a stranger and your profile.

Clients then need only the URL:

```json
{
  "mcpServers": {
    "jobsearch": { "type": "http", "url": "https://your-domain/mcp" }
  }
}
```

Notes learned the hard way:

- Keep `MCP_JWT_SIGNING_KEY` stable, or every client must sign in again after a
  restart. Registrations persist to `/data/oauth-store` for the same reason.
- Registration is open (dynamic client registration), so the redirect allowlist
  is the real control. Localhost is allowed by default; add anything else via
  `MCP_ALLOWED_REDIRECT_URIS` (comma-separated).
- Putting an identity-aware proxy such as Cloudflare Access in front of an MCP
  server does not work. It answers every request with a redirect to a login
  page, including the discovery documents a client must read *before* it can
  authenticate, so the client can never complete the flow.

---

## Authentication modes

Set with `MCP_AUTH`:

| Mode | Use when |
|---|---|
| `none` | Local desktop use over stdio, or an HTTP server bound to localhost behind an SSH tunnel. |
| `token` | Hosted. One shared secret. The usual choice. |
| `oauth` | Hosted, and you already have an Entra tenant. |

The server **refuses to start** with `MCP_AUTH=none` when it is listening on a
non-localhost address, and tells you how to fix it. That is intentional: an
unauthenticated job-search server on a public address hands your profile to
anyone who finds the URL.

---

## Deploying with the script

`mcp_server/deploy.sh` automates a Docker deployment over SSH:

```bash
./mcp_server/deploy.sh user@your-server
```

It stages the portal tools, syncs the code and your config, installs a nightly
backup cron job, and rebuilds the container.

### Profile ownership

Once hosted, the **server** owns your profile, because you can edit it from
your phone. A normal deploy therefore does not overwrite it. Seed it once, then
pull changes back into your local copy:

```bash
./mcp_server/deploy.sh user@host --seed-profile   # first time only
./mcp_server/deploy.sh user@host --pull-profile   # server -> local
```

Pushing on every deploy would silently destroy anything you had written from
your phone since the last one.

---

## Backups

`deploy.sh` installs `backup.sh` as a nightly cron job. It snapshots the
database with SQLite's `.backup` (safe against a live writer, unlike a file
copy) and tars the profile, keeping 30 days.

Worth having even if the host is already backed up: a whole-machine image
restores the machine, not a single bad edit, and it will back up a corrupted
database just as faithfully as a good one.

---

## A note on job boards and server IPs

Job boards treat traffic from data-centre IP ranges differently from home
connections. Searches from a VPS are more likely to be rate-limited or blocked
than the same searches from your laptop, and "personal use" is a harder
description to defend for a server running unattended.

If portal search stops returning results on a hosted instance, that is the
likely cause. Run searches from your own machine and use the `ingest_jobs` tool
to push results to the server.
