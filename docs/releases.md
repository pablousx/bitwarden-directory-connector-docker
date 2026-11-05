# Releases del contenedor

La fuente de versión es [`release.json`](../release.json): `version` coincide con el release oficial de Bitwarden y `revision` identifica cambios de empaquetado. Por ejemplo, `2026.10.0-r2` conserva el binario de Bitwarden y cambia esta revisión del contenedor.

1. Revise las notas oficiales, dependencias, compatibilidad, seguridad y posibles migraciones de `data.json`.
2. Actualice la versión/checksum con el actualizador o incremente `revision` cuando cambie la imagen sin cambiar el binario oficial. Mantenga el enlace de código fuente de [`third_party/NOTICE`](../third_party/NOTICE).
3. Abra un PR enfocado. Apruebe su workflow si GitHub lo solicita y espere `Repository checks` y `validate`.
4. Fusione con squash. El workflow de `main` construye un único OCI, comprueba su identidad, ejecuta el humo y publica exactamente ese digest con SBOM/procedencia.
5. Si necesita un tag Git, use exactamente `v<version>-r<revision>` en el commit revisado. Un tag válido publica las etiquetas de commit y versión; nunca mueve `latest`. Las ejecuciones antiguas de `main` se omiten.
6. Prepare un release borrador de GitHub y genere notas con `.github/release.yml`. Revise los digests, cambios de compatibilidad y notas antes de publicarlo. No se crean tags ni releases de GitHub automáticamente.

Las etiquetas de versión y `latest` son mutables. Para despliegues inmutables use `ghcr.io/pablousx/bitwarden-directory-connector-docker@sha256:<digest>` con el digest real publicado por CI. Las reconstrucciones pueden incorporar paquetes Debian corregidos, pero cada ejecución publica el mismo artefacto que probó.

Antes de actualizar una instalación: detenga las sincronizaciones, haga una copia cifrada del volumen, pruebe la nueva imagen con `test` y revise el resultado antes de activar `sync`. Un rollback puede requerir restaurar también una copia anterior compatible del volumen. Véase [instalación y mantenimiento](../README.md#ghcr-y-mantenimiento).
