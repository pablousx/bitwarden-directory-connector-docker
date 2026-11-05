# bitwarden-directory-connector-docker

Imagen comunitaria de **Bitwarden Directory Connector CLI** basada exclusivamente en su distribución Linux oficial, sin recompilar ni modificar `bwdc`. No es una imagen publicada o soportada por Bitwarden.

Versión inicial: **2026.10.0-r1**. El binario y `dc_native.linux-x64-gnu.node` proceden del [release oficial](https://github.com/bitwarden/directory-connector/releases/tag/v2026.10.0); el SHA-256 está fijado en [`release.json`](release.json) y se comprueba antes de extraerlos. Debian slim está fijado por digest, con actualizaciones propuestas por Dependabot. El runtime incluye Python 3 estándar para gestionar secretos, bloqueo y señales; no instala pip ni dependencias Python externas. Las herramientas de descarga quedan fuera de la imagen final.

## Compatibilidad

Solo **linux/amd64**, la arquitectura de la distribución Linux oficial. Un host ARM64 necesita emulación amd64; no se anuncia una imagen ARM nativa. Docker Engine y Docker Compose v2 son suficientes. No requiere puertos entrantes, cron, interfaz gráfica, D-Bus ni acceso privilegiado.

Se conservan los proveedores y las opciones de sincronización que admite la CLI oficial:

| `BWDC_DIRECTORY` | Proveedor | Credencial opcional por entorno | Configuración oficial |
| --- | --- | --- | --- |
| `0` | Active Directory / LDAP | `LDAP_PASSWORD` | [LDAP/AD](https://bitwarden.com/help/ldap-directory/) |
| `1` | Microsoft Entra ID | `ENTRA_KEY` | [Entra ID](https://bitwarden.com/help/azure-directory/) |
| `2` | Google Workspace | `GSUITE_KEY` | [Google Workspace](https://bitwarden.com/help/gsuite-directory/) |
| `3` | Okta | `OKTA_TOKEN` | [Okta](https://bitwarden.com/help/okta-directory/) |
| `4` | OneLogin | `ONELOGIN_SECRET` | [OneLogin](https://bitwarden.com/help/onelogin-directory/) |

Los identificadores de tenant, URL LDAP, filtros, grupos, usuarios y demás opciones se configuran en el **`data.json` oficial**, no con nombres de variables inventados por esta imagen. El [almacenamiento oficial](https://bitwarden.com/help/directory-sync-shared/) explica el formato y ofrece una plantilla. También puede prepararse una configuración con la aplicación oficial; las credenciales deben reintroducirse en la CLI, porque el almacén seguro del escritorio no se exporta. No edite el archivo mientras la CLI o el servicio estén ejecutándose.

## Instalación con Compose

1. Copie `.env.example` a `.env`. Ajuste el servidor y el proveedor. Para Bitwarden EU utilice `https://vault.bitwarden.eu`; para una instalación propia, su URL HTTPS.
2. Cree `secrets/` con permiso `0700`. Guarde el `client_id` y el `client_secret` de la **API de la organización** en `secrets/client_id` y `secrets/client_secret`, sin comillas. Obtenga estas credenciales como propietario de la organización. No son la clave API personal ni la contraseña maestra.
3. Los archivos deben poder ser leídos por UID `10001` dentro del contenedor. En Compose local puede usar archivos `0444` dentro del directorio `0700`; en Linux también puede asignarlos a UID `10001` y modo `0400`. Compose monta estos archivos individualmente como solo lectura; sus opciones `uid`/`mode` no cambian los permisos de archivos bind-mounted. Mantenga `secrets/` fuera de Git y de directorios compartidos.
4. Construya la imagen y consulte la CLI:

```sh
docker compose build --pull
docker compose run --rm connector --version
docker compose run --rm connector --help
```

El volumen nombrado `connector-data` conserva `data.json`, credenciales y caché de sincronización. Se crea con el propietario `10001:10001`. Si utiliza un bind mount, prepare el directorio con ese propietario y modo `0700`; no ejecute el servicio como root para corregir permisos.

Prepare un `data.json` con la plantilla enlazada en la documentación oficial y los valores de su proveedor. Guárdelo en una ubicación privada y legible por UID `10001`. Impórtelo en un volumen **nuevo**:

```sh
docker compose run --rm \
  -v "$PWD/data.json:/bootstrap/data.json:ro" \
  -e BWDC_CONFIG_FILE=/bootstrap/data.json \
  connector configure
```

La importación se realiza solo si `/data/data.json` no existe. No sobrescribe una configuración persistida. Las variables de servidor, proveedor y credenciales presentes se aplican después de la importación. Compruebe que `.env` selecciona el mismo proveedor que su archivo.

Para introducir la credencial del directorio sin colocarla en argumentos del proceso, monte su archivo y utilice la variable correspondiente. Ejemplo LDAP:

```sh
docker compose run --rm \
  -v "$PWD/secrets/ldap_password:/run/secrets/ldap_password:ro" \
  -e LDAP_PASSWORD_FILE=/run/secrets/ldap_password \
  connector configure
```

Después autentique una vez la organización y pruebe los resultados:

```sh
docker compose run --rm connector login
docker compose run --rm connector test
```

La autenticación permanece en el volumen. `login` explícito evita reautenticar en cada reinicio; la CLI devuelve error si ya hay una sesión. Para rotar las credenciales de la organización: detenga el servicio, ejecute `logout`, actualice los archivos y ejecute `login`. Los cambios de credenciales del directorio se aplican con `configure` o en el siguiente arranque con las variables apropiadas.

**Revise el resultado de `test`, los filtros y las opciones de eliminación antes de sincronizar.** `test` simula la sincronización, pero consulta servicios externos y puede mostrar datos del directorio. El comando predeterminado de la imagen y del Compose base es `test`: no inicia sincronizaciones periódicas por sí solo.

Para una sincronización real única:

```sh
docker compose run --rm connector sync
```

Para activar el servicio periódico, una vez validada la configuración:

```sh
docker compose -f compose.yaml -f compose.sync.yaml up -d
docker compose logs --tail=50 connector
```

Cada ciclo ejecuta `bwdc sync` inmediatamente y espera `BWDC_SYNC_INTERVAL` segundos **después de terminar**. No solapa ciclos. Un error detiene el proceso con el código de salida de la CLI; `unless-stopped` permite a Docker reiniciarlo. Los logs periódicos muestran estado y código, no el contenido del directorio. Supervise errores y reinicios; no se incluye una comprobación de salud que afirme verificar conectividad o éxito de sincronización.

Antes de hacer pruebas, cambiar el servidor, editar datos o ejecutar cualquier comando sobre el mismo volumen:

```sh
docker compose -f compose.yaml -f compose.sync.yaml stop
docker compose run --rm connector test
```

Un bloqueo de archivo rechaza otro comando concurrente de esta imagen. No protege frente a programas externos que ignoren ese bloqueo; no comparta el volumen con la aplicación de escritorio ni con otra organización. Cada organización requiere su propio volumen y servicio. El supervisor reenvía SIGTERM/SIGINT al grupo de procesos de la CLI y deja de programar ciclos; Docker aplica el límite de parada de 30 segundos.

## Variables

| Variable | Valor predeterminado / comportamiento |
| --- | --- |
| `BWDC_SERVER` | Opcional en la imagen; el Compose usa `https://vault.bitwarden.com`. Se aplica con `bwdc config server`. |
| `BWDC_DIRECTORY` | Opcional en la imagen; el Compose usa `0`. Solo acepta `0`–`4`. |
| `BWDC_CONFIG_FILE` | Ruta de un `data.json` para importar una vez; debe ser un objeto JSON. |
| `BWDC_SYNC_INTERVAL` | `300`; entero de 1 a 99999999 segundos, solo para `run`. |
| `BW_CLIENTID`, `BW_CLIENTSECRET` | Credenciales de organización para `login`. Deben proporcionarse juntas. |
| `LDAP_PASSWORD`, `ENTRA_KEY`, `GSUITE_KEY`, `OKTA_TOKEN`, `ONELOGIN_SECRET` | Se aplican usando `bwdc config … --secretenv`; opcionales si ya están persistidas. |
| Cualquiera de las siete credenciales anteriores + `_FILE` | Lee el archivo completo, quitando saltos de línea finales. Admite claves Google multilínea. No combine variable directa y `_FILE`. |
| `BITWARDENCLI_CONNECTOR_APPDATA_DIR` | `/data`; si lo cambia, monte y dé permisos al nuevo directorio. |
| `BITWARDENCLI_CONNECTOR_PLAINTEXT_SECRETS` | `true`; modo oficial para un entorno sin keyring. Cambiarlo requiere proveer un almacén de credenciales compatible. |
| `NODE_EXTRA_CA_CERTS` | Ruta opcional a un PEM adicional montado en solo lectura, para certificados internos. |

El entorno también conserva las variables que reconoce la CLI oficial. No desactive la verificación TLS. La configuración automática se aplica al ejecutar `configure`, `login`, `test`, `sync` o `run`; los demás argumentos se pasan a la CLI. `bwdc` está disponible dentro de la imagen para herramientas externas, aunque ejecutarlo directamente omite el bloqueo del supervisor.

Para opciones soportadas por la CLI, por ejemplo invitaciones:

```sh
docker compose run --rm connector config sync.inviteUsersAfterProvisioning false
docker compose run --rm connector data-file
docker compose run --rm connector last-sync users
```

## Seguridad y persistencia

En modo headless, **Bitwarden guarda secretos sin cifrar en `data.json`** ([explicación oficial](https://bitwarden.com/help/directory-sync-shared/)). `_FILE` evita introducirlos en Compose o en los argumentos de procesos, pero no cifra el volumen. Restrinja el acceso al host y al socket Docker, use almacenamiento cifrado y proteja las copias de seguridad. El supervisor crea archivos con `umask 077` y fija `data.json` a `0600` al configurar. Los comandos manuales de la CLI pueden imprimir información sensible: no publique sus resultados ni active depuración en logs compartidos.

La imagen usa UID/GID `10001`, no contiene credenciales y no expone puertos. Compose elimina capabilities, impide elevar privilegios, usa raíz de solo lectura y un `/tmp` temporal. Solo `/data` debe ser persistente. Conceda a la cuenta del directorio los permisos mínimos recomendados por su proveedor. Las credenciales de prueba en los tests son desechables.

Para copiar o editar el volumen, detenga primero el servicio. Conserve **todo** `/data`, incluidas credenciales y caché, en una copia cifrada. Restaurar una versión anterior de la imagen puede requerir restaurar también su copia anterior del volumen si el release nuevo ha migrado el esquema. `docker compose down` conserva el volumen; `down -v` lo elimina y pierde la configuración.

## GHCR y mantenimiento

Los workflows están preparados para un repositorio GitHub, pero este directorio por sí solo no publica imágenes. Suba los archivos a su repositorio, habilite GitHub Actions y permita a Actions crear PRs en Settings → Actions → General si quiere las actualizaciones automáticas. El token integrado necesita `packages:write` para publicar; no se requiere un PAT para GHCR. En organizaciones, revise también las políticas del paquete y de Actions. Cambie la visibilidad del paquete si desea acceso público.

`Validate and publish` valida tests, construcción y humo real en amd64 antes de publicar. Los PRs solo validan. Un push a la rama predeterminada o una ejecución manual desde esa rama publica `ghcr.io/<propietario>/<repositorio>:2026.10.0-r1`, `:sha-<commit-completo>` y `:latest`. Los nombres se normalizan a minúsculas. Un tag Git opcional debe coincidir exactamente con `v<version>-r<revision>`; publica las etiquetas de versión y commit, sin mover `latest`. Se adjuntan SBOM y procedencia BuildKit. No se configura firma externa de imágenes.

Para usar la imagen publicada, configure `BWDC_IMAGE=ghcr.io/<propietario>/<repositorio>:2026.10.0-r1` en `.env`, ejecute `docker compose pull` y despliegue con el override de sincronización. Prefiera un digest `@sha256:…` para despliegues inmutables. `latest` y la etiqueta de versión pueden reconstruirse; la etiqueta de commit identifica el código de este wrapper, y el digest identifica la imagen exacta. Si el paquete es privado, autentique Docker contra GHCR antes del pull.

`Check official releases` consulta diariamente el último release estable oficial y propone un PR cambiando `release.json`. Rechaza releases sin ZIP Linux o sin digest SHA-256, URLs ajenas, retrocesos y cambios de checksum para la misma versión. **Construye y prueba el candidato antes de abrir el PR**, porque los PRs creados con `GITHUB_TOKEN` no disparan otro workflow `pull_request`. El PR requiere revisión humana; al fusionarlo, la rama predeterminada publica la imagen. Una ejecución sin cambios no abre un PR. No se actualiza ningún contenedor instalado automáticamente.

El número de Bitwarden se conserva; `revision` permite cambios de este wrapper o reconstrucciones de seguridad (`2026.10.0-r2`, etc.). Increméntelo cuando cambie la imagen sin cambiar de release oficial. Dependabot propone actualizaciones semanales de la base y de Actions fijadas por SHA. Revise regularmente avisos de seguridad y reconstruya para incorporar paquetes Debian corregidos: los paquetes apt no están congelados, por lo que la construcción es verificable respecto al binario oficial pero no reproducible byte por byte.

Antes de actualizar: revise las [notas oficiales](https://github.com/bitwarden/directory-connector/releases), detenga el servicio, haga una copia cifrada de `/data`, cambie a la etiqueta/digest elegido, ejecute `test` con esa imagen y active el servicio. Para rollback detenga el servicio, restaure la copia compatible del volumen y seleccione el digest anterior.

## Validación local

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_image.py
docker compose config --quiet
docker compose -f compose.yaml -f compose.sync.yaml config --quiet
```

El humo construye la distribución oficial, comprueba versión, ruta de datos, UID, configuración mediante el módulo nativo y el fallo de un `test` sin autenticar. Sus contenedores usan datos efímeros y `--network=none`. Los tests del supervisor usan una CLI simulada para verificar secretos, intervalos, bloqueo, señales y códigos de error; no demuestran conectividad con proveedores reales. Las pruebas de integración con una organización o directorio de prueba corresponden al administrador antes de activar sincronizaciones.

Referencia adicional: [CLI oficial](https://bitwarden.com/help/directory-sync-cli/), [programación de sincronizaciones](https://bitwarden.com/help/schedule-directory-sync/), [código fuente oficial](https://github.com/bitwarden/directory-connector). El binario se redistribuye con los términos y avisos del proyecto original; la imagen incluye su [licencia GPLv3](third_party/bitwarden-LICENSE.txt), los [avisos](third_party/NOTICE) y el enlace al código fuente correspondiente al release en `/usr/local/share/connector/`.
