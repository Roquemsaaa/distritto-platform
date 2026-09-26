# DISTRITTO v1.0 — Arquitectura

## Capas

1. **Frontend público**: conserva el HTML/CSS/UX actual.
2. **Admin**: catálogo, colecciones, inventario, descuentos, ventas, producción, analytics, ML y configuración.
3. **FastAPI**: reglas de negocio y APIs.
4. **SQLite**: operación + eventos para la etapa local.
5. **Cache**: `cache_entries`; solo agregados temporales.
6. **ML Engine**: módulo independiente con feature flag y fallback obligatorio.

## Fuente de verdad

- Catálogo, inventario, ventas y eventos: SQLite.
- JSON antiguos: semilla de migración y respaldo inicial.
- Caché: nunca fuente de verdad.

## Modelo ML

El entrenamiento v1 combina atributos de contenido (colección, marca, tipo, cierre y colores) con co-vistas por sesión cuando existen datos. El modelo puede entrenarse sin estar activo. Activarlo/desactivarlo no modifica las demás capas.

## Seguridad para producción

En local el Admin no exige autenticación. En producción deberá utilizar `ADMIN_API_KEY`/autenticación real, HTTPS, secretos fuera del frontend y PostgreSQL o almacenamiento persistente equivalente.
