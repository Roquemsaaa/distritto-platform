# Arquitectura v0.2

## Problema corregido
`python -m http.server` es un servidor estático. No acepta operaciones de escritura.

## Desarrollo local
FastAPI sirve simultáneamente:
- el catálogo;
- `/admin/`;
- la API de administración.

Esto permite probar CRUD real antes de conectar GitHub.

## Separación de datos
- `catalog.json`: catálogo y colecciones.
- `inventory.json`: unidades por variante.
- `discounts.json`: reglas promocionales.

## Inventario
El stock pertenece a la variante/color, no al producto general.

No se asumió stock cero para productos migrados: se usa `null` = sin registrar.

## Producción
Después de validar v0.2:
- catálogo/assets pueden sincronizarse a GitHub;
- datos transaccionales pasan a PostgreSQL;
- autenticación real protege el panel;
- eventos analíticos se almacenan aparte.
