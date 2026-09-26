# Arquitectura inicial — DISTRITTO Digital Platform

## Decisión 001 — GitHub no será la base transaccional

GitHub seguirá siendo el origen versionado del código y, durante la Fase 1, de las imágenes y del catálogo público.
GitHub Pages publica `site/`.

Las operaciones de alta de productos se realizan mediante una interfaz estática (`site/admin/`) que llama a un backend Python.
El backend conserva en secreto las credenciales de GitHub y realiza un único commit con el producto, sus imágenes y `catalog.json`.

No se almacenan tokens de GitHub en HTML ni JavaScript.

## Regla de imágenes

Ruta canónica:

`site/catalogo/<product_folder>/<variant_folder>/<n>.<ext>`

Ejemplo:

```text
site/catalogo/DTT-INS-001/
├── NEGRO/
│   ├── 1.webp   <- portada
│   ├── 2.webp
│   └── 3.webp
└── VERDE/
    ├── 1.webp   <- portada
    └── 2.webp
```

- Una referencia = un producto.
- Una referencia puede tener una o muchas variantes/color.
- Cada variante tiene carpeta propia.
- Las imágenes deben ser consecutivas `1..n`.
- `1` es siempre portada.
- El administrador selecciona fotos en el orden en que desea publicarlas; el backend las renombra.

## Fase 1

- Catálogo público.
- Datos externos al HTML en `site/data/catalog.json`.
- Panel para alta de productos.
- Variantes/colores.
- Imágenes.
- Publicación automática a GitHub.
- GitHub Actions -> GitHub Pages.

## Fase 2

Agregar PostgreSQL para:

- inventario;
- movimientos de inventario;
- ventas;
- sale_items;
- costos;
- usuarios/roles;
- auditoría.

No usar commits de GitHub para registrar ventas o movimientos de stock.

## Fase 3

Instrumentación de eventos y capa analítica.

## Fase 4

BI y modelos de recomendación, manteniendo fallback determinístico.
