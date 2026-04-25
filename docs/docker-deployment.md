# Docker / PostgreSQL Deployment

This deployment runs one FastAPI container that serves both the API and built frontend, plus one PostgreSQL container.

## Local or VPS Quick Start

1. Copy the example environment file:

   ```bash
   cp .env.docker.example .env.docker
   ```

2. Fill required secrets in `.env.docker`:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Put the first value into `SECRET_KEY`, the second into `ENCRYPTION_KEY`, and set strong values for `ADMIN_PASSWORD` and `POSTGRES_PASSWORD`.

   If your server can pull Docker Hub directly, set `DOCKER_IMAGE_PREFIX=`. The default uses a Docker Hub mirror prefix for networks where Docker Hub is slow or unavailable.

3. Start the stack:

   ```bash
   docker compose --env-file .env.docker up --build -d
   ```

4. Verify:

   ```bash
   curl http://127.0.0.1:9800/health
   ```

5. Open:

   ```text
   http://127.0.0.1:9800
   ```

## Reverse Proxy

For Nginx, proxy your domain to `127.0.0.1:9800`:

```nginx
location / {
    proxy_pass http://127.0.0.1:9800;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Then update `.env.docker`:

```env
ALLOWED_ORIGINS=https://your-domain.com
```

Restart:

```bash
   docker compose --env-file .env.docker up -d
```

## Notes

- `.env.docker` is intentionally ignored by git and must not be committed.
- PostgreSQL data is persisted in the `postgres_data` Docker volume.
- Platform mode uses the configured platform API keys and consumes user credits.
- BYOK mode uses each user's saved API config and does not consume platform credits.
