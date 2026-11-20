# ADR-0008: La tarifa va con el alumno, el precio se congela en la asistencia

- **Estado:** aceptada
- **Fecha:** 2026-11-20

## Contexto
Al pasar lista, cada asistencia copiaba el precio **de la clase** (30 €). La ficha del alumno ya
guardaba su tarifa (`default_plan_id`), pero nadie la leía: Paloma, del Grupo Reggio (21 €),
salía a 30 €. Kat quiere además crear y cambiar tarifas ella misma y hacer descuentos puntuales.

## Decisión
- **Manda la tarifa del alumno** cuando es una tarifa de grupo de clase suelta y la clase es de
  grupo (`attendance/service.price_for`, función pura). Si no tiene tarifa, tiene un bono o una
  tarifa individual, se cobra el precio de la clase como antes.
- **El precio se congela al marcar** (`attendances.price_cents`). Cambiar la tarifa de un alumno
  o el precio de una tarifa solo afecta a lo que se marque después. Lo cobrado no se reescribe.
- **Excepción puntual:** se puede cambiar el precio de una asistencia **pendiente**. Si ya está
  pagada, hay que deshacer el pago antes: así el pago y la asistencia nunca discrepan.
- **Tarifas en la app (Más → Tarifas)** para cualquier usuario con sesión (Kat decide los
  precios). Solo clases sueltas; los bonos llegan con la Fase 3. Se archivan, no se borran,
  porque las clases antiguas apuntan a ellas. No se archiva una tarifa con alumnos activos o con
  un horario fijo, ni la Normal (es la de los alumnos nuevos).
- **Corrección de datos en una migración** (no a mano en producción): los alumnos Reggio se
  buscan por `legacy_id` del Excel y pasan a `Grupo Reggio · clase suelta`.
- Todo cambio de precio o tarifa queda en el registro de actividad (`30 € → 18 €`).

## Alternativas descartadas
- **Recalcular el precio al mostrar:** cambiar una tarifa movería deudas antiguas. Inaceptable.
- **Categorías de alumno (Normal/Reggio) separadas de las tarifas:** otra tabla para lo mismo.
  Una tarifa de grupo ya *es* la categoría, y crecer es crear una tarifa nueva.
- **Precio por clase (clase Reggio vs clase Normal):** en la realidad, en la misma clase de los
  viernes conviven alumnos de las dos tarifas.
