# Sistema de diseño · "Marea turquesa"

> Catálogo vivo: `uv run fastapi dev` → **/_estilo** (solo en desarrollo).
> Decisión y contrastes: [ADR-0002](adr/0002-identidad-de-marca.md).

## Idea
Una escuela de surf al amanecer: arena clara, agua turquesa, la espuma, el coral del atardecer y
el sol en los números. El logo y la tipografía serif son de la marca de Kat, y la paleta les da
el aire de mar que pidió Lalo. Nada de lila, lotos ni cuencos.

## Tokens (`static/css/tokens.css`)
Hay dos capas: **marca** (`--oceano`, `--turquesa`…) y **roles** (`--text`, `--accent-ink`,
`--ok`…). Los componentes **solo usan roles**. El modo oscuro "mar de noche" reasigna roles y
no toca ningún componente.

| Rol | Claro | Uso |
|---|---|---|
| `--bg` | arena `#FBF7EF` | fondo |
| `--surface` | espuma `#FFFFFF` | tarjetas |
| `--text` / `--text-strong` | océano `#14384A` / `#0C2734` | texto / titulares |
| `--text-muted` | `#3F6676` | secundario (5,8:1) |
| `--accent-ink` | turquesa tinta `#0F7480` | botón primario, enlaces (5,1:1) |
| `--accent` | turquesa `#16A3A8` | foco, borde de "hoy" (no texto) |
| `--decor` | coral `#FF8A66` | ola, estrella (decorativo) |
| `--ok` / `--ok-bg` | alga `#2E7D5B` / `#D5F0EC` | asistió |
| `--warn` / `--warn-bg` | miel `#8A5D00` / `#FFE9A8` | pendiente de pago |
| `--danger` / `--danger-bg` | granada `#B23A2E` / `#FFDCD3` | error, deshacer |
| `--bar-num` | sol `#FFC547` | importes sobre la barra oscura (9,8:1) |

## Tipografía
- **Newsreader** (serif, en lugar de Abril Text, que es de pago): titulares y frases con
  carácter en itálica (`.lede`).
- **Inter**: toda la interfaz. 16 px como mínimo en los inputs, para que iOS no haga zoom.

## Forma
Radios de 12/16/22 px. Las tarjetas usan una **esquina orgánica** (`--radius-organic`: abajo a
la izquierda, 8 px). Los objetivos táctiles miden **48 px como mínimo** (`--tap`), y las filas
de la lista 64 px.

## Componentes
| Componente | Clase | Notas |
|---|---|---|
| Botón | `.btn`, `.btn--ghost`, `.btn--danger`, `.btn--block` | `:active` encoge un 3 % |
| Pill de estado | `.pill--ok/warn/danger` | |
| Tarjeta | `.card` | esquina orgánica |
| Tarjeta de clase | `.class-card`, `--today` | hora grande en serif |
| Fila de pasar lista | `.roster-item`, `.is-on`, `.is-paid` | toque = asistió, botón derecho = pagado |
| Barra de totales | `.totals` | `role="status"` + `aria-live` |
| Buscador | `.search` | filtra al instante (`data-filter`) |
| Desplegable | `.disclosure` | "+ Alumno nuevo" sin salir de la pantalla |
| Lista | `.list`, `.list-row` | alumnos, ajustes |
| Navegación | `.tabbar` | Hoy · Alumnos · Dinero · Más |
| Divisor | `partials/divider.html` | dos trazos y la estrella del logo, en coral |
| Formulario | `.field`, `.form-row`, `.check`, `.form-actions` | editar ficha; fechas sin desbordar |
| Iconos | `{{ icon("sun") }}` | Lucide inline, `currentColor` |

## Microinteracciones
- Al marcar a alguien, la tarjeta pasa a fondo `--ok-bg` con el avatar en verde ✓, y una franja
  de luz la recorre en 200 ms.
- Todo respeta `prefers-reduced-motion`.

## Tono
Cercano, cálido y breve: "¡Clase lista! 🌊", "Hoy no hay clase. Día de mar 🏄‍♀️", "Nadie se
llama así… ¿alumno nuevo?". Nunca "Registro guardado correctamente".

## Accesibilidad
Contraste AA medido en cada par de colores. Foco visible (anillo turquesa). Etiquetas reales en
los inputs. `aria-pressed` en los toques. `aria-live` en los totales. Sin estilos ni scripts en
línea (lo exige la CSP).

## Tono de los textos
Yoga y sánscrito con humor, sin referencias al surf (petición de Kat, 2026-11-11). Ejemplos:
"Hoy no hay clase. Savasana oficial.", "Que fluya el prana.", "Aún en postura del niño".
Frases cortas, tuteo y sin emojis en los mensajes de la app.

## Logo
`static/img/logo-katiu-yoga.svg` (vectorial, entregado por Lalo). Se usa como máscara CSS: se
pinta con `--logo`, así cambia de color solo en modo oscuro.
