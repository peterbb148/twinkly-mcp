# Twinkly phone remote

The existing Render service serves a static, touch-friendly remote at
`/remote`. It works in the browser and can be added to the Home Screen from
Safari on iOS or installed from Chrome on Android. Playback requires a
connection to the server.

## Configure Render and the wall

- Set `TWINKLY_API_KEY` on Render and in the wall client. Render rejects access
  to the privileged API if the key is unset.
- Set `TWINKLY_REMOTE_KEY` on Render to a separate high-entropy secret. Generate
  a URL-safe key with `openssl rand -hex 32`.
- Set `TWINKLY_REMOTE_PRESETS` to a comma-separated allowlist of card IDs, such
  as `party-flame,skal`. IDs are matched case-insensitively. The remote lists only
  approved IDs that the wall has registered since the service started. Start
  the wall with MCP polling enabled so it registers the catalog and receives
  commands. Run the wall client from a Twinkly Wall checkout containing
  both cards in `config/cards.d` to make **Party Flame** and **Skål**
  available. Skål displays a left-to-right `SKÅL!` message on the landscape wall.
- After deploying, verify that `/api/cards` returns HTTP 401 without the main
  key and that the wall can poll using its bearer credential.

Print a QR code for the following URL, replacing the placeholder locally
with the remote key.

```text
https://twinkly-mcp.onrender.com/remote#key=<remote-key>
```

Use an offline QR generator and keep the printed code private. Guests see
the presets immediately after a successful scan. The browser removes the
fragment from its address bar and exchanges it in a request header for a
two-hour session cookie. The session grants access only to the approved
preset list and playback. Rescan the same QR after the session expires.

Anyone with the QR can use it. To revoke access, change the remote key on
Render and redeploy. This invalidates existing remote sessions. Print a
replacement QR with the new key.

## Local verification

Run `uv run --locked pytest tests/test_remote.py` to exercise the QR exchange,
cookie expiry, rotation, preset allowlist, and privileged routes. For a
browser check, run Uvicorn at `https://localhost:8000` with a trusted local
certificate, distinct test keys, and `TWINKLY_REMOTE_PRESETS=clock`. Register
the test catalog as the wall would before opening the QR URL.

```bash
curl --fail-with-body https://localhost:8000/api/cards/register \
  -H "Authorization: Bearer ${TWINKLY_API_KEY}" \
  -H 'Content-Type: application/json' \
  --data '{"cards":["clock"]}'
```

Open `https://localhost:8000/remote#key=<remote-key>` using the local remote
key and tap **Clock**. Confirm the `run_card` command through the privileged
`/api/commands/poll` endpoint using the MCP bearer key.
