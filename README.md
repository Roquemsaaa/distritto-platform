# DISTRITTO Digital Platform v1.0

Versión integral local construida sobre la v0.2, sin reemplazar el diseño público que ya funcionaba.

## Incluye

- Catálogo público responsive.
- Productos y referencias.
- Variantes/colores.
- Imágenes por variante `1..n`, donde `1` es siempre la portada.
- Colecciones dinámicas.
- Precio de venta y costo unitario.
- Inventario por color/variante.
- Movimientos de inventario.
- Descuentos por producto, colección o catálogo.
- Ventas con descuento automático de stock y conservación del precio/costo histórico.
- Producción: materiales, cantidad, costos, desperdicio, rendimiento y entrada automática a inventario.
- Analítica de comportamiento.
- Caché analítica con TTL.
- Machine Learning desacoplado con ON/OFF, entrenamiento, registro de versiones y fallback.
- Configuración desde el Admin.
- Auditoría básica de operaciones.
- SQLite como base local.

## Eventos analíticos

Se capturan progresivamente:

- `page_view`
- `collection_view`
- `filter_applied`
- `product_view`
- `variant_view`
- `image_view`
- `whatsapp_click`
- `heartbeat`
- `recommendation_view`
- `recommendation_click`

Se utiliza `visitor_id` pseudónimo y `session_id`. No se recoge GPS ni dirección exacta.

## Caché

La tabla `events` guarda la información original. `cache_entries` almacena temporalmente agregados del dashboard para no recalcular todo cada vez.

Vaciar la caché **no elimina analytics**.

## Machine Learning separado

El módulo ML vive en `backend/app/ml_engine.py`.

- **ML OFF:** el catálogo, ventas, inventario, producción y analytics siguen funcionando; recomendaciones usan fallback determinístico.
- **ML ON:** si existe un modelo activo, usa `content+coview-v1`.
- Si el modelo falla, la API vuelve automáticamente al fallback.

## Cómo ejecutar en Visual Studio Code

1. Descomprime `distritto-platform-v1.0.zip`.
2. Abre esa carpeta en VS Code.
3. Abre `Terminal > New Terminal`.
4. Instala dependencias una sola vez:

```bash
python -m pip install -r backend/requirements.txt
```

5. Inicia la plataforma:

```bash
python start_local.py
```

6. Abre:

- Catálogo: `http://localhost:8000/`
- Admin: `http://localhost:8000/admin/`

La primera ejecución crea automáticamente:

`backend/data/distritto.db`

y migra los productos, variantes, inventario y descuentos existentes de la v0.2.

## Respaldo / rollback

La v0.2 no se modifica. Si quieres reiniciar la base v1.0 desde los datos originales, detén el servidor y elimina:

`backend/data/distritto.db`

Al volver a ejecutar `python start_local.py`, la base se reconstruye a partir de los JSON incluidos.

## Publicación

GitHub sigue siendo apropiado para código, versionado, imágenes y despliegues. Sin embargo, GitHub Pages por sí solo no ejecuta el backend Python ni debe utilizarse como base transaccional para ventas/inventario/analytics.

Antes de publicación real en Internet, el backend deberá desplegarse con almacenamiento persistente; para crecimiento posterior, la migración natural será SQLite -> PostgreSQL sin cambiar la interfaz del catálogo.


## Corrección v1.0.1 — Windows / Uvicorn reload

`start_local.py` ahora usa el patrón seguro de Windows:

```python
if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
```

Esto evita que `reload=True` vuelva a ejecutar Uvicorn recursivamente al crear el proceso de recarga.
