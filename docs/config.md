# Configuration

Waldiez Runner provides extensive configuration options through environment variables, allowing you to customize server behavior, database connections, authentication, and task management settings.

## Configuration Sources

The application loads configuration from multiple sources in the following order of precedence:

1. **Environment variables** (highest priority)
2. **`.env` file** in the project root
3. **Default values** (lowest priority)

All environment variables use the prefix `WALDIEZ_RUNNER_` followed by the setting name in uppercase.

## Server Settings

### Basic Server Configuration

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| `host` | `WALDIEZ_RUNNER_HOST` | `127.0.0.1` | Server host address |
| `port` | `WALDIEZ_RUNNER_PORT` | `8000` | Server port (1-65535) |
| `domain_name` | `WALDIEZ_RUNNER_DOMAIN_NAME` | `localhost` | Domain name for the server |
| `max_jobs` | `WALDIEZ_RUNNER_MAX_JOBS` | `10` | Maximum concurrent jobs (1-100) |
| `force_ssl` | `WALDIEZ_RUNNER_FORCE_SSL` | `false` | Force HTTPS connections |
| `secret_key` | `WALDIEZ_RUNNER_SECRET_KEY` | *auto-generated* | Secret key for session management |
| `log_level` | `WALDIEZ_RUNNER_LOG_LEVEL` | `INFO` | Logging level |

### CORS and Security

| Setting | Environment Variable | Description |
|---------|---------------------|-------------|
| `trusted_hosts` | `WALDIEZ_RUNNER_TRUSTED_HOSTS` | Comma-separated list of trusted hosts |
| `trusted_origins` | `WALDIEZ_RUNNER_TRUSTED_ORIGINS` | Comma-separated list of trusted origins |
| `trusted_origin_regex` | `WALDIEZ_RUNNER_TRUSTED_ORIGIN_REGEX` | Regex pattern for trusted origins |

**Example:**

```shell
WALDIEZ_RUNNER_TRUSTED_HOSTS=localhost,example.com,api.example.com
WALDIEZ_RUNNER_TRUSTED_ORIGINS=http://localhost:3000,https://example.com
```

## Database Configuration

### PostgreSQL (Production)

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| `postgres` | `WALDIEZ_RUNNER_POSTGRES` | `false` | Enable PostgreSQL |
| `db_host` | `WALDIEZ_RUNNER_DB_HOST` | `localhost` | Database host |
| `db_port` | `WALDIEZ_RUNNER_DB_PORT` | `5432` | Database port |
| `db_user` | `WALDIEZ_RUNNER_DB_USER` | `postgres` | Database user |
| `db_password` | `WALDIEZ_RUNNER_DB_PASSWORD` | `password` | Database password |
| `db_name` | `WALDIEZ_RUNNER_DB_NAME` | `waldiez` | Database name |
| `db_url` | `WALDIEZ_RUNNER_DB_URL` | *auto-generated* | Complete database URL |

**Example PostgreSQL configuration:**

```shell
WALDIEZ_RUNNER_POSTGRES=true
WALDIEZ_RUNNER_DB_HOST=db.example.com
WALDIEZ_RUNNER_DB_PORT=5432
WALDIEZ_RUNNER_DB_USER=waldiez_user
WALDIEZ_RUNNER_DB_PASSWORD=secure_password
WALDIEZ_RUNNER_DB_NAME=waldiez_prod
```

### SQLite (Development)

When `WALDIEZ_RUNNER_POSTGRES=false`, the application uses SQLite:

- **Production**: `waldiez_database.sqlite3`
- **Testing**: `waldiez_test.db`

## Redis Configuration

Redis is used for task queuing and real-time communication.

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| `redis` | `WALDIEZ_RUNNER_REDIS` | `true` | Enable Redis |
| `redis_host` | `WALDIEZ_RUNNER_REDIS_HOST` | `localhost` | Redis host |
| `redis_port` | `WALDIEZ_RUNNER_REDIS_PORT` | `6379` | Redis port |
| `redis_db` | `WALDIEZ_RUNNER_REDIS_DB` | `0` | Redis database index (0-15) |
| `redis_scheme` | `WALDIEZ_RUNNER_REDIS_SCHEME` | `redis` | Redis scheme (`redis`, `rediss`, `unix`) |
| `redis_password` | `WALDIEZ_RUNNER_REDIS_PASSWORD` | *none* | Redis password |
| `redis_url` | `WALDIEZ_RUNNER_REDIS_URL` | *auto-generated* | Complete Redis URL |

**Example Redis configurations:**

```shell
# Basic Redis
WALDIEZ_RUNNER_REDIS=true
WALDIEZ_RUNNER_REDIS_HOST=redis.example.com
WALDIEZ_RUNNER_REDIS_PORT=6379
WALDIEZ_RUNNER_REDIS_DB=0

# Redis with authentication
WALDIEZ_RUNNER_REDIS_PASSWORD=redis_password

# Redis with SSL
WALDIEZ_RUNNER_REDIS_SCHEME=rediss

# Unix socket
WALDIEZ_RUNNER_REDIS_SCHEME=unix
WALDIEZ_RUNNER_REDIS_HOST=/var/run/redis/redis.sock
```

## Authentication

Waldiez Runner supports multiple authentication methods that can be used independently or together.

### Local Authentication (HS256 Tokens)

Basic JWT authentication using HMAC-SHA256 signatures.

| Setting | Environment Variable | Description |
|---------|---------------------|-------------|
| `use_local_auth` | `WALDIEZ_RUNNER_USE_LOCAL_AUTH` | Enable local JWT authentication |
| `local_client_id` | `WALDIEZ_RUNNER_LOCAL_CLIENT_ID` | Client ID for local auth |
| `local_client_secret` | `WALDIEZ_RUNNER_LOCAL_CLIENT_SECRET` | Client secret for local auth |

### OIDC/OAuth2 Authentication

Integration with OIDC providers like Keycloak, Auth0, Google, etc.

| Setting | Environment Variable | Description |
|---------|---------------------|-------------|
| `use_oidc_auth` | `WALDIEZ_RUNNER_USE_OIDC_AUTH` | Enable OIDC authentication |
| `oidc_issuer_url` | `WALDIEZ_RUNNER_OIDC_ISSUER_URL` | OIDC issuer URL |
| `oidc_audience` | `WALDIEZ_RUNNER_OIDC_AUDIENCE` | Expected audience claim |
| `oidc_jwks_url` | `WALDIEZ_RUNNER_OIDC_JWKS_URL` | JWKS endpoint URL |
| `oidc_jwks_cache_ttl` | `WALDIEZ_RUNNER_OIDC_JWKS_CACHE_TTL` | JWKS cache TTL in seconds (1-3600) |

**Example OIDC configuration:**

```shell
WALDIEZ_RUNNER_USE_OIDC_AUTH=true
WALDIEZ_RUNNER_OIDC_ISSUER_URL=https://keycloak.example.com/realms/waldiez
WALDIEZ_RUNNER_OIDC_AUDIENCE=waldiez-api
WALDIEZ_RUNNER_OIDC_JWKS_URL=https://keycloak.example.com/realms/waldiez/protocol/openid-connect/certs
WALDIEZ_RUNNER_OIDC_JWKS_CACHE_TTL=3600
```

### External Authentication

Custom authentication verification through external services.

| Setting | Environment Variable | Description |
|---------|---------------------|-------------|
| `enable_external_auth` | `WALDIEZ_RUNNER_ENABLE_EXTERNAL_AUTH` | Enable external auth verification |
| `external_auth_verify_url` | `WALDIEZ_RUNNER_EXTERNAL_AUTH_VERIFY_URL` | URL for auth verification |
| `external_auth_secret` | `WALDIEZ_RUNNER_EXTERNAL_AUTH_SECRET` | Secret for external auth |

### Task Permissions

Fine-grained permission control for task operations.

| Setting | Environment Variable | Description |
|---------|---------------------|-------------|
| `task_permission_verify_url` | `WALDIEZ_RUNNER_TASK_PERMISSION_VERIFY_URL` | URL for permission verification |
| `task_permission_secret` | `WALDIEZ_RUNNER_TASK_PERMISSION_SECRET` | Secret for task permissions |

## Task Management

### Task Execution Settings

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| `input_timeout` | `WALDIEZ_RUNNER_INPUT_TIMEOUT` | `300` | Input timeout in seconds (1-3600) |
| `max_task_duration` | `WALDIEZ_RUNNER_MAX_TASK_DURATION` | `0` | Maximum task duration in seconds (0 = no limit) |
| `keep_task_for_days` | `WALDIEZ_RUNNER_KEEP_TASK_FOR_DAYS` | `7` | Days to keep completed tasks (0 = delete immediately) |

**Task Duration Behavior:**

- When `max_task_duration > 0`: Tasks exceeding this duration are automatically terminated
- When `max_task_duration = 0`: No time limit is enforced
- Terminated tasks receive a `SIGTERM` signal and return code `-1`

## Environment File Example

Create a `.env` file in your project root:

```shell
# Server Configuration
WALDIEZ_RUNNER_HOST=0.0.0.0
WALDIEZ_RUNNER_PORT=8000
WALDIEZ_RUNNER_DOMAIN_NAME=api.example.com
WALDIEZ_RUNNER_MAX_JOBS=20
WALDIEZ_RUNNER_FORCE_SSL=true
WALDIEZ_RUNNER_LOG_LEVEL=INFO

# Security
WALDIEZ_RUNNER_SECRET_KEY=your-super-secret-key-here
WALDIEZ_RUNNER_TRUSTED_HOSTS=api.example.com,localhost
WALDIEZ_RUNNER_TRUSTED_ORIGINS=https://app.example.com,http://localhost:3000

# Database
WALDIEZ_RUNNER_POSTGRES=true
WALDIEZ_RUNNER_DB_HOST=postgres.example.com
WALDIEZ_RUNNER_DB_PORT=5432
WALDIEZ_RUNNER_DB_USER=waldiez_user
WALDIEZ_RUNNER_DB_PASSWORD=secure_db_password
WALDIEZ_RUNNER_DB_NAME=waldiez_production

# Redis
WALDIEZ_RUNNER_REDIS=true
WALDIEZ_RUNNER_REDIS_HOST=redis.example.com
WALDIEZ_RUNNER_REDIS_PORT=6379
WALDIEZ_RUNNER_REDIS_DB=0
WALDIEZ_RUNNER_REDIS_PASSWORD=secure_redis_password

# Authentication
WALDIEZ_RUNNER_USE_OIDC_AUTH=true
WALDIEZ_RUNNER_OIDC_ISSUER_URL=https://auth.example.com/realms/waldiez
WALDIEZ_RUNNER_OIDC_AUDIENCE=waldiez-api
WALDIEZ_RUNNER_OIDC_JWKS_URL=https://auth.example.com/realms/waldiez/protocol/openid-connect/certs

# Task Management
WALDIEZ_RUNNER_INPUT_TIMEOUT=600
WALDIEZ_RUNNER_MAX_TASK_DURATION=3600
WALDIEZ_RUNNER_KEEP_TASK_FOR_DAYS=14
```

## Development vs Production

### Development Mode

```shell
WALDIEZ_RUNNER_DEV=true
WALDIEZ_RUNNER_LOG_LEVEL=DEBUG
WALDIEZ_RUNNER_POSTGRES=false  # Uses SQLite
WALDIEZ_RUNNER_FORCE_SSL=false
```

### Production Mode

```shell
WALDIEZ_RUNNER_DEV=false
WALDIEZ_RUNNER_LOG_LEVEL=INFO
WALDIEZ_RUNNER_POSTGRES=true
WALDIEZ_RUNNER_FORCE_SSL=true
WALDIEZ_RUNNER_SECRET_KEY=your-production-secret-key
```

## Configuration Validation

The application validates all configuration settings on startup:

- **Port numbers** must be between 1-65535
- **Job limits** must be between 1-100
- **Secret keys** must be at least 32 characters (64 for client secrets)
- **OIDC settings** are validated when OIDC auth is enabled
- **Database connections** are tested during startup

## Troubleshooting

### Common Configuration Issues

**Invalid secret key length:**

```text
RuntimeError: secret_key is not (correctly) set
```

Solution: Ensure your secret key is at least 32 characters long.

**Missing OIDC configuration:**

```text
ValueError: OIDC issuer URL is required
```

Solution: When `WALDIEZ_RUNNER_USE_OIDC_AUTH=true`, all OIDC settings must be provided.

**Database connection errors:**
Check your database settings and ensure the database server is accessible and credentials are correct.

**Redis connection issues:**
Verify Redis is running and accessible at the specified host/port, and check authentication if required.
