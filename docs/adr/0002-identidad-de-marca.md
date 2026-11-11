# ADR-0002: Identidad visual de Katiu Yoga en lugar de "Boho Surf"

- **Estado:** aceptada
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
- **Terracota de texto** `#A8501F`: la terracota oficial sobre lino da 3,3:1 y no pasa el nivel AA
  para texto normal. Se reserva para acentos grandes (la estrella, iconos) y se usa una versión
  oscurecida para el texto y los botones (4,7:1).
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
- ⚠️ El logo es un raster de 560 px. Conviene pedir el SVG original.
- ⚠️ Newsreader es una aproximación a Abril Text, no la tipografía oficial.
