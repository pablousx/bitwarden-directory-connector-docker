# Contribuir

Las contribuciones son bienvenidas. Para cambios importantes, abra un issue antes de empezar; las correcciones pequeñas pueden llegar directamente como PR.

1. Cree un fork y una rama desde `main`.
2. Mantenga el cambio enfocado y siga el estilo existente.
3. Añada pruebas cuando cambie el comportamiento y actualice la documentación pertinente.
4. Ejecute las comprobaciones del [README](README.md#validación-local).
5. Explique en el PR el problema, el resultado y las comprobaciones realizadas.

Para reproducir problemas de directorio use datos desechables y una organización de prueba. No incluya credenciales, `data.json` real, datos personales, secretos de CI ni resultados sin redactar de `bwdc test`. No pruebe contra producción desde CI.

Los PRs ejecutan `Repository checks` y `validate` con permisos de lectura y sin publicar imágenes. Los workflows del bot pueden necesitar aprobación del mantenedor; la ejecución nativa del PR debe pasar antes de fusionar. Se usa squash merge y no hay bypass configurado para los mantenedores.

Respete el [código de conducta](CODE_OF_CONDUCT.md). Informe vulnerabilidades mediante el canal privado de [SECURITY.md](SECURITY.md). El código propio y la documentación se contribuyen bajo [MIT](LICENSE); las distribuciones oficiales de Bitwarden mantienen sus [términos y avisos](third_party/NOTICE).
