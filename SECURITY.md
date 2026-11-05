# Política de seguridad

## Versiones mantenidas

Las correcciones del contenedor se aplican al código actual de `main` y a la revisión más reciente de la distribución oficial fijada en `release.json`. Las imágenes y revisiones anteriores no tienen garantía de recibir correcciones. Revise los releases oficiales de Bitwarden y las propuestas de actualización antes de desplegarlas.

Este proyecto mantiene el empaquetado y el supervisor; no es una distribución soportada por Bitwarden. Una vulnerabilidad del producto original debe coordinarse también con [Bitwarden](https://bitwarden.com/help/is-bitwarden-audited/#reporting-a-vulnerability).

## Reportar una vulnerabilidad

No abra un issue o PR público con detalles de una vulnerabilidad. Use [Security → Advisories → Report a vulnerability](https://github.com/pablousx/bitwarden-directory-connector-docker/security/advisories/new). Si el formulario no está disponible, escriba en privado a [pablousx@outlook.com](mailto:pablousx@outlook.com).

Incluya versiones o digests afectados, una reproducción mínima con datos ficticios, impacto y posibles mitigaciones. Nunca envíe credenciales reales ni datos privados del directorio. Dé tiempo para investigar y coordinar la corrección antes de divulgar detalles. No se promete un plazo de respuesta ni una recompensa.

## Límites conocidos

El modo headless oficial guarda secretos sin cifrar en el volumen. Los archivos `_FILE` protegen su introducción, pero no cifran `data.json`. Restrinja el acceso al host, al socket Docker y a las copias de seguridad; consulte el [README](README.md#seguridad-y-persistencia). Los resultados de `test` pueden contener información del directorio y deben redactarse antes de compartirlos.
