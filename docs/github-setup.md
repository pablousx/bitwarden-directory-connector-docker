# Configuración de GitHub

Este proyecto adapta los archivos y la automatización de la plantilla open source de pablousx. Los archivos se versionan; los ajustes, etiquetas, reglas y funciones de seguridad requieren configuración por API. El script no cambia visibilidad, no crea repositorios, no publica releases ni guarda tokens administrativos en Actions.

## Aplicar la configuración

1. Autentique `gh` con una cuenta que tenga administración del repositorio.
2. Suba los archivos mediante un PR y espere a que `Repository checks` y `validate` pasen en el commit actual de la rama predeterminada.
3. Revise la vista previa y después aplíquela:

```sh
python3 scripts/setup_repository.py --repo pablousx/bitwarden-directory-connector-docker
python3 scripts/setup_repository.py --repo pablousx/bitwarden-directory-connector-docker --apply
```

La vista previa solo lee la API. `--apply` reconcilia ajustes y etiquetas sin borrar etiquetas ajenas. Solo administra las dos reglas cuyos nombres aparecen en `.github/rulesets/`; no elimina otras reglas ni la protección clásica de ramas. Si hay reglas superpuestas, todas siguen aplicándose. Las operaciones no son transaccionales: si una falla, lo anterior puede haber quedado aplicado. Revise el resultado y repita tras resolver errores.

La regla de CI solo se activa cuando **ambos** checks de GitHub Actions pasan en el SHA actual de la rama predeterminada. Si falta alguno, el script informa trabajo pendiente y termina con error. No interprete como aprobación un check manual `workflow_dispatch` sobre una rama de PR: la protección necesita la ejecución nativa de `pull_request` o `push` admitida por GitHub.

## Ajustes y diferencias respecto a la plantilla

| Área | Configuración |
| --- | --- |
| Colaboración | Issues habilitados; wiki y proyectos deshabilitados; discussions sin cambios |
| Fusiones | Solo squash; título/cuerpo del PR; borrado de ramas fusionadas |
| Actions | Token de lectura por defecto; SHA completo obligatorio para Actions externas |
| Bot de releases | Creación de PRs habilitada: el workflow necesita `contents: write` y `pull-requests: write` |
| Dependencias | Alertas y actualizaciones de seguridad; Dependabot semanal para Actions y Docker |
| Rama predeterminada | PR, conversaciones resueltas, historial lineal, sin force-push ni eliminación |
| CI obligatoria | `Repository checks` y `validate`, ligados a GitHub Actions; rama actualizada |
| Bypass | Ninguno, incluido el propietario; conserva las protecciones de este proyecto |
| Seguridad pública | Reportes privados de vulnerabilidades, secret scanning y push protection |

La plantilla permite al mantenedor un bypass permanente y deshabilita la creación/aprobación de PRs por Actions. Aquí se adapta: no se concede bypass y se mantiene habilitado el ajuste que necesita el actualizador para crear PRs. El bot no aprueba ni fusiona PRs. GitHub puede exigir **Approve workflows** en sus PRs; el mantenedor debe aprobar la ejecución y esperar los dos checks nativos antes de fusionar.

Por defecto no se exige otra aprobación, para permitir el mantenimiento con un único propietario. `--approvals 1` añade revisión cuando haya otra persona mantenedora. CODEOWNERS enruta revisiones a `@pablousx` sin exigir autoaprobación.

Las funciones exclusivas de repositorios públicos se omiten mientras el repositorio sea privado. Si el plan no admite reglas en un repositorio privado, el script lo informa como no disponible y termina con error; no cambia de plan ni hace público el repositorio. Otros errores también se informan y no se tratan como éxito. El cambio de visibilidad es una operación separada que requiere revisar archivos e historial antes de ejecutarse.

Antes del lanzamiento público, confirme que funciona el formulario de reportes privados y el correo de conducta de [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md). El alcance de licencias se explica en el [README](../README.md#licencias).

CodeQL, environments, cuentas de patrocinio y políticas de tags se añaden cuando exista una necesidad concreta; no se crean credenciales, jobs vacíos ni cuentas de financiación ficticias. La imagen conserva su publicación con permisos acotados, SBOM y procedencia. Consulte el [proceso de releases](releases.md).
