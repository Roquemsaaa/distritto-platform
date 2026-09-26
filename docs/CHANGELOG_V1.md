# v0.2 -> v1.0

**CONSERVAR**: catálogo visual, tarjetas, modal, WhatsApp, personalización, producto/variante, regla de imágenes.

**REFACTORIZAR**: JSON deja de ser base operativa y se convierte en semilla. SQLite es la fuente de verdad local.

**AÑADIR**: costos, ventas, movimientos, producción, analytics, caché, auditoría, configuración y ML desacoplado.

**REGLA INVARIABLE DE IMÁGENES**: una referencia puede tener varios colores; cada color tiene carpeta; fotos `1..n`; foto `1` = portada.
