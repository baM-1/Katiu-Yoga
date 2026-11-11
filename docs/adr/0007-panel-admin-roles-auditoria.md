# ADR-0007: Panel de Admin con rol de administrador y registro de actividad

- **Estado:** aceptada
- **Fecha:** 2026-11-11

## Contexto
Lalo necesita gestionar la app sin abrir la terminal del servidor: dar de alta usuarios, poner
contraseñas nuevas, saber si la copia de seguridad va bien y poder llevarse los datos. Kat no
necesita nada de eso y no debe verlo. Hay datos de salud (RGPD).

## Decisión
- **Autenticación ≠ autorización.** El login dice *quién eres*; el campo `users.is_admin` dice
  *qué puedes hacer*. Un rol booleano basta para dos personas; si algún día hay más perfiles
  (otra profe), se convierte en una tabla de roles sin tocar las pantallas.
- **`/admin` responde 404 a quien no es admin.** No revela que existe. La comprobación vive en
  una sola dependencia (`AdminUser`, en `core/web.py`): imposible olvidarla en una ruta nueva
  del router de admin.
- **Salvaguardas:** nadie puede desactivarse a sí mismo y siempre queda un admin activo.
- **Registro de actividad (`audit_events`) de solo añadir.** Guarda *quién, qué, cuándo y sobre
  qué id*, nunca contenido: ni nombres, ni teléfonos, ni el texto de salud ("cambió salud" sí;
  qué pone, no). En un intento de entrada fallido no se guarda el email tecleado. El nombre del
  alumno se une al mostrarlo, así que si se borra una ficha el registro no conserva sus datos.
- **Estado de la copia sin credenciales en la app.** Litestream expone métricas en
  `127.0.0.1:9090` (solo dentro de la máquina). El panel compara la posición del WAL local con
  la de la réplica en R2: si coinciden, "Al día". La app no necesita las claves de R2.
- **Exportar a Excel por POST con CSRF**, sin caché (`no-store`) y sin notas de salud salvo que
  se marquen expresamente. Cada exportación queda registrada.

## Alternativas descartadas
- **App de admin separada (otro dominio/proceso):** más aislamiento, pero el doble de despliegue
  para dos usuarios. Las fronteras ya están dibujadas (`admin/`), se puede separar más tarde.
- **SQLAdmin / panel genérico de tablas:** rápido, pero deja editar cualquier fila saltándose las
  reglas de negocio (validaciones, consentimiento). Preferimos pocas acciones con sentido.
- **Leer R2 directamente desde la app:** daría la fecha exacta de la última instantánea, pero
  obliga a meter las claves de R2 en la app y una dependencia nueva (boto3).
- **Guardar el detalle completo en la auditoría ("antes/después"):** útil para depurar, pero
  copiaría datos de salud a una segunda tabla. No.

## Consecuencias
- Lalo se da de alta como admin una vez con `scripts/make_admin.py`; el resto, desde la app.
- La tabla `audit_events` crece con cada toque (~100 filas por clase). A este ritmo son unos
  pocos MB al año; si molesta, se purga lo de más de 12 meses.
