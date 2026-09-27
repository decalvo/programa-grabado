# Programa grabado

Preparación de fotos para grabado láser CO2 sobre madera: se recorta al sujeto y se separa la foto en capas por tono, para grabar cada capa con una potencia distinta y lograr más profundidad en la gama de cafés.

## Language

### Imagen

**Proyecto**:
El archivo propio del programa que guarda un trabajo en curso (foto de origen, recorte retocado y todos los ajustes) para reabrirlo y volver a exportar.
_Avoid_: Sesión, documento

**Foto de origen**:
La fotografía que carga el usuario, sin modificar.
_Avoid_: Imagen original, input

**Sujeto**:
La persona, las personas o la mascota que se conservan en el grabado; todo lo demás es fondo.
_Avoid_: Figura, objeto

**Recorte**:
La foto de origen con el fondo eliminado, de modo que solo queda el sujeto y el grabado no tiene márgenes cuadrados.
_Avoid_: Silueta, máscara (la máscara es solo el medio para obtener el recorte)

**Retoque**:
La corrección manual del recorte con un pincel que borra o recupera zonas donde la eliminación automática del fondo se equivocó.
_Avoid_: Edición, corrección

**Contorno**:
Una línea opcional que se graba siguiendo el borde del sujeto, como un trazo dibujado; el usuario decide si agregarla. No es una línea de corte. Va por dentro del borde del recorte y se graba sola: bajo ella no se graban las capas tonales.
_Avoid_: Borde, silueta, outline

### Separación tonal

**Capa tonal**:
Una de las cuatro partes en que se divide el recorte según el tono de cada píxel: Negro, Oscuro, Medio y Claro. Las capas son exclusivas: cada píxel pertenece a una sola capa. Negro, Oscuro y Medio se graban una sola vez cada una; Claro no se graba y queda como madera natural.
_Avoid_: Nivel, banda, contraste (el usuario dice "contraste" pero se refiere al tono)

**Corte tonal**:
El tono donde termina una capa tonal y empieza la siguiente. Hay tres: Negro/Oscuro, Oscuro/Medio y Medio/Claro; el programa propone su posición y el usuario la ajusta.
_Avoid_: Umbral, límite

**Tramado**:
El patrón de puntos con que se rellena cada capa tonal: los puntos son más densos del lado oscuro de la capa y más separados del lado claro, para que haya degradado dentro de ella.
_Avoid_: Dithering, relleno

**Semitono**:
Un tipo de tramado en que los puntos se agrupan en manchas redondas sobre una cuadrícula regular y crecen con la densidad, en lugar de repartirse sueltos como en Jarvis, Floyd-Steinberg o Stucki.
_Avoid_: Halftone, trama de puntos

**Vista previa**:
La imagen que muestra cómo quedaría el grabado: los puntos del tramado de cada capa tonal en su tono de café y el resto como madera natural.
_Avoid_: Render, preview

### Grabado

**Potencia de capa**:
La potencia del láser que se asigna en RDWorks a una capa tonal; las capas más oscuras usan más potencia.
_Avoid_: Intensidad

**Plantilla de calibración**:
Una cuadrícula de muestras que se graba en una madera para ver qué tono de café da cada potencia y elegir la potencia de cada capa tonal.
_Avoid_: Test, prueba de potencia
