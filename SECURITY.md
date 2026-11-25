# Security and privacy

- Keep `data/me.json`, client tokens, local model weights, run artifacts, logs, and deployment-specific configuration out of Git.
- Copy `data/me.example.json` to `data/me.json` only in your local checkout.
- Keep `data/clients.json` private; it contains bearer tokens.
- Use a reverse proxy with TLS, request limits, and authentication before exposing the HTTP API publicly.
- Report a suspected leak privately to the repository owner; do not paste secrets into a public issue.
