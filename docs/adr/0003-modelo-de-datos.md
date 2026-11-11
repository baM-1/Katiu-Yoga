# ADR-0003: Modelo de datos (céntimos, precios copiados, saldo calculado)

- **Estado:** aceptada
- **Fecha:** 2026-11-11

## Contexto
En el Excel, el dinero mezcla `int` y `float`, los totales salen de fórmulas que se rompen (el
RESUMEN_MENSUAL tiene una fila con otra fórmula) y no existen los bonos. La lista de precios 2026
introduce paquetes de 4 y 8 clases con caducidad y penaliza las cancelaciones tardías.

## Decisión
1. **Céntimos enteros** para todo importe (`price_cents`, `amount_cents`).
2. **Precio copiado** en cada nivel (plan → clase → asistencia): el histórico es inmutable.
3. **Nada derivado en la BD**: saldos, deudas y rankings se calculan en los services.
4. **Plan = una línea de la lista de precios** (`kind` drop_in/pack, `format`, `modality`). Un bono
   comprado es un `PackPurchase` con su caducidad. Las asistencias lo descuentan con
   `pack_purchase_id`.
5. **`AttendanceStatus.LATE_CANCEL`** modela "no vino, pero cuenta".
6. **IDs enteros internos + `legacy_id`** para trazar el Excel.
7. **Alembic** para versionar el esquema. Un test verifica que las migraciones y los modelos
   coinciden.

## Alternativas descartadas
- **`Decimal` en la BD:** correcto, pero SQLite no tiene un tipo decimal real. `int` es universal y
  más simple.
- **Guardar el saldo en `students`:** rápido de leer, pero se desincroniza (es justo el error del
  Excel).
- **Un plan por familia con tres precios:** obliga a añadir columnas cada vez que aparezca un bono
  nuevo. Una fila por opción escala mejor.

## Consecuencias
- ✅ El dinero cuadra al céntimo y el histórico no cambia aunque cambien las tarifas.
- ⚠️ Calcular saldos en cada consulta cuesta algo más (irrelevante con cientos de filas). Si
  algún día hace falta, se cachea, pero la verdad sigue siendo la suma.
