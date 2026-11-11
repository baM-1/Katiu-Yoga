# ADR-0002: Identidad visual de Katiu Yoga en lugar de "Boho Surf"

- **Estado:** aceptada (paleta revisada dos veces; vigente: "Marea turquesa")
- **Fecha:** 2026-11-11
- **Sustituye a:** la sección 6 ("Boho Surf") del prompt maestro

## Contexto
El prompt proponía una identidad nueva, "Boho Surf", por si Kat no tenía marca (D5). Kat sí tiene
marca: *Pautas de diseño 2026* y una lista de precios en la misma línea. La app es una
herramienta interna, pero Kat la abrirá a diario y debe sentirse suya.

## Decisión
- **Paleta oficial**, con los colores muestreados del manual:
  Bosque `#3D4A3B`, Lino `#F3EEE4`, Terracota `#CC6633`, Oliva `#667059` y Arena `#C8B296`.
  Los códigos que trae impresos el manual (`66cc33`, `111111`, `6633ff`...) son de una
  plantilla y no coinciden con las muestras que se ven, así que se toman las muestras.
- **Refresh "Bosque & Lino"** (aprobado por Lalo el 2026-11-11): se parte de la paleta oficial y
  se ajusta para la interfaz. Todos los textos cumplen AA:

  | Token | Hex | Uso | Contraste sobre lino |
  |---|---|---|---|
  | Bosque | `#34433A` | texto, navegación, logo | 9,1:1 |
  | Bosque profundo | `#26322B` | titulares | 11,7:1 |
  | Lino / Papel | `#F4EFE6` / `#FBF9F5` | fondo / tarjetas | n/a |
  | Terracota | `#C8602E` | estrella, iconos y acentos grandes | 3,6:1 (no se usa para texto) |
  | Terracota tinta | `#A2461C` | botón primario, enlaces | 5,4:1 |
  | Salvia | `#5D6A50` | texto secundario, "asistió" | 5,0:1 |
  | Arena | `#CDB896` | bordes (decorativo) | n/a |
  | Miel *(nuevo)* | `#8A5F0C` | pendiente de pago | 4,9:1 |
  | Granada *(nuevo)* | `#9E3B2E` | errores, deshacer | 5,9:1 |

  La marca no traía colores de estado (pendiente, error), así que se añaden Miel y Granada, de
  la misma familia terrosa. Cada estado tiene además un tinte claro de fondo.
- **Tipografía:** la marca usa *Abril Text* (TypeTogether, de pago). En la web usamos
  **Newsreader** (Google Fonts, libre), la serif disponible más parecida, e **Inter** para la
  interfaz. Si Kat tiene licencia web de Abril Text, el cambio es una sola línea en
  `--font-display`.
- **Logo:** se extrae del manual como PNG en alfa y se aplica como máscara CSS pintada con
  `var(--logo)`. Así hay una sola imagen que sale en Bosque en modo claro y en Lino en modo
  oscuro, sin deformarla ni añadirle efectos (lo que prohíbe el manual).
- **Motivo gráfico:** la estrella dibujada a mano sustituye a la "ola".
- **Modo oscuro "bosque de noche":** fondo `#232B24` y texto Lino.

## Consecuencias
- ✅ La app y el material de Kat (Instagram, lista de precios) hablan el mismo idioma.
- ✅ Contraste AA garantizado por tokens, no por fuerza de voluntad.
- ✅ Hay dos capas de tokens (marca → roles). El modo oscuro solo reasigna roles.
- ⚠️ El logo es un raster de 560 px. Conviene pedir el SVG original.
- ⚠️ Newsreader es una aproximación a Abril Text, no la tipografía oficial.

## Revisión 2: "Marea turquesa" (vigente)
Lalo revisó "Bosque & Lino" y le pareció "otoñal y serio, como una tienda de hogar". Pidió un
aire más surfero. Se mostraron dos direcciones en un móvil, "A · Atardecer en Ericeira" y
"B · Marea turquesa", y **eligió la B**.

- Se mantienen de la marca el **logo** (pasa a azul océano), la **estrella**, la tipografía
  serif y el **coral**, que hereda la terracota.
- Paleta nueva: océano `#14384A`, arena `#FBF7EF`, turquesa `#16A3A8` / tinta `#0F7480`,
  coral `#FF8A66`, sol `#FFC547`, alga `#2E7D5B`, miel `#8A5D00` y granada `#B23A2E`. Todos los
  textos ≥ 4,5:1. El detalle está en `docs/DESIGN_SYSTEM.md`.
- Modo oscuro "mar de noche" (`#0E2230`).
