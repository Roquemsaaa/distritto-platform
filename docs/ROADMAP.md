# Roadmap

## Fase 0 — Auditoría
Estado: iniciada / estructura actual migrada sin alterar diseño conceptual.

## Fase 1 — Catálogo administrable
1. Separar presentación, lógica y datos.
2. Migrar catálogo existente a JSON.
3. Crear panel de alta de referencias y variantes.
4. Aplicar convención de imágenes 1..n.
5. Backend Python para commits seguros a GitHub.
6. GitHub Actions para Pages.
7. Pruebas de publicación.

## Fase 2 — Operación
1. PostgreSQL.
2. Inventario por variante.
3. Movimientos de inventario.
4. Ventas y detalle de venta.
5. Costos y margen.
6. Estados automáticos de stock.
7. Usuarios, roles y auditoría.

## Fase 3 — Analytics
1. session_id / visitor_id pseudónimo.
2. product_view.
3. recommendation_view/click.
4. WhatsApp lead.
5. purchase.
6. Dashboards.

## Fase 4 — ML
1. Baseline por reglas.
2. Popularidad.
3. Content-based.
4. Collaborative filtering cuando existan datos suficientes.
5. Híbrido y ranking si el volumen lo justifica.
