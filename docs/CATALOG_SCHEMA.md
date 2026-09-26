# Esquema de catálogo v1

## Product

- `id`: identificador estable.
- `brand`
- `name`
- `collection_id`
- `reference`: referencia comercial única.
- `price_cop`: precio numérico en COP.
- `description`
- `tags[]`
- `closure`
- `type`
- `product_folder`
- `active`
- `variants[]`

## Variant

- `id`
- `name`: nombre del color/variante.
- `color_hex`: color visual del selector.
- `folder`: carpeta física de imágenes.
- `sku`: reservado para inventario por variante.
- `active`
- `images[]`: ordenadas; índice 0 corresponde a foto 1/portada.

## Regla importante

El estado `Última unidad`, `Pocas unidades` o `Agotado` NO forma parte todavía del catálogo v1.
En la Fase 2 será calculado a partir de inventario real.
