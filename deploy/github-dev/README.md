# Local Argilla 2.8 deployment

This deployment runs Argilla 2.8.0 with PostgreSQL, Elasticsearch 8.17.0,
Redis, and the Argilla background worker. The web application is exposed only
on `127.0.0.1:6900`.

Start or update it from this directory:

```bash
docker compose pull
docker compose up -d
docker compose ps
```

Open <http://127.0.0.1:6900> and sign in with `owner` / `12345678`. The local
API key is `owner.apikey` and the initial workspace is `admin`.

The containers use `restart: unless-stopped`, so Docker restarts the stack
after a daemon or machine restart. Runtime data is stored in four named Docker
volumes whose names start with `argilla-v2-`.

Optional overrides can be placed in an ignored `.env` file:

```dotenv
ARGILLA_BIND_ADDRESS=127.0.0.1
ARGILLA_PORT=6900
ARGILLA_USERNAME=owner
ARGILLA_PASSWORD=12345678
ARGILLA_API_KEY=owner.apikey
ARGILLA_WORKSPACE=admin
BACKGROUND_NUM_WORKERS=2
# Required when importing gated or private Hugging Face datasets.
HF_TOKEN=hf_your_read_token
```

The same `HF_TOKEN` is available to the web server and background worker. The
server uses it for dataset previews, and the worker uses it for the import job.
