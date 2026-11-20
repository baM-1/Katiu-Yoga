# ADR-0009: Cancelar y mover clases sin pelearse con el horario

- **Estado:** aceptada
- **Fecha:** 2026-11-21

## Contexto
Las clases fijas (viernes 9:00…) se crean solas cada semana a partir del horario (ADR-0005).
Kat necesita: quitar una clase concreta que no se va a dar, moverla solo una semana y cambiar
una clase fija para siempre.

## Decisión
- **Cancelar marca, no borra** (`class_sessions.cancelled`). Si se borrara, el generador la
  volvería a crear sola al abrir Hoy. Una cancelada sigue viéndose tachada en Hoy y se puede
  **reactivar**. No se puede pasar lista en ella.
- **Solo se cancela o mueve una clase sin nadie marcado.** Así nunca se pierde una asistencia ni
  un cobro por el camino. Kat quita antes a la gente de la lista.
- **Mover una semana = cancelar la original + crear una clase extra** con el mismo tipo, precio,
  duración y lugar, y una nota "Movida desde el vie 27/11 09:00". El horario fijo no cambia.
- **Cambiar una clase fija** edita la franja y rehace sus próximas clases **vacías**. Las que
  ya tienen gente o están canceladas se respetan.
- **El generador no duplica una hora ocupada:** si ya hay una clase activa ese día a esa hora
  (por ejemplo, una movida ahí), no crea otra.
- Todo queda en el registro de actividad.

## Alternativas descartadas
- **Borrar la clase y apuntar "excepciones" en otra tabla:** dos sitios para la misma verdad.
- **Mover cambiando fecha y hora de la misma fila:** la fecha original quedaría libre y el
  horario volvería a crear la clase allí.
