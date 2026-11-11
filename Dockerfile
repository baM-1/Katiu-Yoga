# Imagen de producción de Katiu Yoga.
# Dos etapas: en "build" se instalan dependencias con uv; la imagen final solo lleva
# Python, el entorno virtual, el código y Litestream (copia de seguridad en streaming).

FROM python:3.13-slim AS build
COPY --from=astral/uv:0.11 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Primero solo las dependencias: Docker reutiliza esta capa mientras uv.lock no cambie.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY README.md alembic.ini ./
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
RUN uv sync --locked --no-dev

FROM python:3.13-slim
COPY --from=litestream/litestream:0.3.13 /usr/local/bin/litestream /usr/local/bin/litestream
RUN useradd --create-home --uid 1000 katiu && mkdir -p /data && chown katiu /data
WORKDIR /app
COPY --from=build --chown=katiu /app /app
COPY deploy/litestream.yml /etc/litestream.yml
COPY deploy/start.sh /usr/local/bin/start.sh
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    KATIU_ENVIRONMENT=production \
    KATIU_DATABASE_URL=sqlite:////data/katiu.db
USER katiu
EXPOSE 8000
CMD ["/usr/local/bin/start.sh"]
