# ADR-0004: Login con sesión firmada, CSRF y cabeceras estrictas

- **Estado:** aceptada
- **Fecha:** 2026-11-11

## Contexto
La app guarda datos personales y de salud (RGPD). Hoy la usa una sola persona desde el móvil y
tiene que poder abrirse "en un toque", sin volver a escribir la contraseña cada día.

## Decisión
- **Usuarios en BD** (`users`), aunque de momento solo exista Kat: añadir a Lalo o a otra
  profesora no requiere cambiar el modelo.
- **argon2id** para las contraseñas (recomendado por OWASP). El login tarda lo mismo exista o no
  el email.
- **Sesión en una cookie firmada** (`SessionMiddleware` de Starlette): `HttpOnly`,
  `SameSite=Lax`, `Secure` en producción, 30 días. No hace falta tabla de sesiones.
- **CSRF de doble envío**: un token en la sesión que cada POST devuelve. HTMX lo manda en la
  cabecera `X-CSRF-Token` (puesta en `<body hx-headers>`) y los formularios clásicos en un campo
  oculto.
- **Límite de intentos**: 5 fallos por IP en 15 minutos, en memoria (con un solo proceso basta).
- **Cabeceras**: CSP estricta (`script-src 'self'`, sin JS ni estilos en línea), `nosniff`,
  `frame-ancestors 'none'`, y HSTS en producción. HTMX se sirve desde nuestro dominio
  (`static/js/htmx.min.js`, 2.0.4), no desde un CDN.

## Alternativas descartadas
- **JWT:** pensado para APIs entre servicios. Para una web con cookies añade complejidad y no
  aporta nada.
- **Login con Google / enlace mágico:** cómodo, pero depende de terceros o del email. Se puede
  añadir más adelante.
- **Sin login ("es solo para Kat"):** la URL será pública en la Fase 4. Hay datos de salud.

## Consecuencias
- ✅ Seguridad razonable con unas 150 líneas legibles (`core/security.py`).
- ⚠️ El límite de intentos en memoria se reinicia al reiniciar el servidor. Con varios procesos
  habría que moverlo a la BD.
- ⚠️ Cerrar sesión borra la cookie, pero una cookie robada vale hasta que caduque. Si llegara a
  pasar, se cambia `KATIU_SECRET_KEY` y se invalidan todas las sesiones.
