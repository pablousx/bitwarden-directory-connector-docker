# syntax=docker/dockerfile:1
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3 AS download
ARG TARGETARCH
RUN test "$TARGETARCH" = amd64
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip python3 && rm -rf /var/lib/apt/lists/*
COPY release.json /release.json
RUN python3 -c 'import json; d=json.load(open("/release.json")); print(d["version"]); print(d["sha256"])' > /release.txt \
    && version=$(sed -n '1p' /release.txt) && checksum=$(sed -n '2p' /release.txt) \
    && curl --fail --location --proto '=https' --tlsv1.2 --retry 3 "https://github.com/bitwarden/directory-connector/releases/download/v${version}/bwdc-linux-${version}.zip" -o /bwdc.zip \
    && echo "${checksum}  /bwdc.zip" | sha256sum --check --strict \
    && mkdir /out && unzip /bwdc.zip -d /out \
    && test -f /out/bwdc && test -f /out/dc_native.linux-x64-gnu.node \
    && chmod 0755 /out/bwdc

FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libsecret-1-0 libstdc++6 libatomic1 python3 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 connector && useradd --uid 10001 --gid 10001 --home-dir /data --no-create-home connector \
    && mkdir /data && chown 10001:10001 /data && chmod 0700 /data
COPY --from=download /out/bwdc /out/dc_native.linux-x64-gnu.node /usr/local/lib/bwdc/
RUN ln -s /usr/local/lib/bwdc/bwdc /usr/local/bin/bwdc
COPY scripts/entrypoint.py /usr/local/bin/connector
COPY release.json /usr/local/share/connector/release.json
COPY LICENSE /usr/local/share/connector/LICENSE
COPY third_party/bitwarden-LICENSE.txt third_party/NOTICE /usr/local/share/connector/
LABEL org.opencontainers.image.title="Bitwarden Directory Connector (community container)" \
      org.opencontainers.image.description="Official Directory Connector CLI with a minimal periodic sync supervisor" \
      org.opencontainers.image.licenses="MIT AND GPL-3.0-only"
ENV HOME=/data BITWARDENCLI_CONNECTOR_APPDATA_DIR=/data BITWARDENCLI_CONNECTOR_PLAINTEXT_SECRETS=true
USER 10001:10001
WORKDIR /data
ENTRYPOINT ["python3", "/usr/local/bin/connector"]
CMD ["test"]
