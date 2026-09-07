[Read this in English](CHANGELOG.md)

# Historial de cambios

## 1.1.28 - 2026-09-07

### Añadido

- Ampliada la cobertura de SAIH Ebro desde los 12 embalses del mapa general de
  la cuenca hasta los 82 embalses que actualmente ofrecen datos públicos
  utilizables mediante los mapas regionales, el resumen diario y los valores
  actuales de las estaciones oficiales.
- Añadidos embalses solicitados por los usuarios, incluidos Pajares y González
  Lacasa.

### Cambiado

- Descubrimiento dinámico del catálogo oficial de mapas regionales de SAIH
  Ebro y eliminación de duplicados mediante el código estable de cada estación.
- Caché del catálogo del Ebro y actualización exclusiva de las fuentes
  necesarias para los embalses seleccionados, con concurrencia limitada.
- Conservados los identificadores existentes de dispositivos y entidades del
  Ebro.

## 1.1.27 - 2026-09-04

### Corregido

- Restaurada la conexión con CH Duero en instalaciones de Home Assistant que
  rechazan el certificado intermedio FNMT inválido enviado por el servidor de
  origen, manteniendo activa toda la verificación TLS.
- Creación del contexto TLS de CH Duero en el ejecutor de Home Assistant para
  evitar el bloqueo del bucle de eventos.
- Añadidos reintentos para errores transitorios de red, HTTP, tiempo de espera
  y respuestas inválidas de CH Duero.
- Añadida compatibilidad con separadores de miles y decimales en los valores de
  CH Duero, corrigiendo el volumen indicado para el embalse de Almendra.

## 1.1.26 - 2026-09-03

### Corregido

- Aisladas todas las peticiones de SAIH Guadalquivir de las cookies ASP.NET del
  sitio, que podían provocar que el servidor devolviese una tabla de embalses
  incompleta.
- Analizadas y combinadas las tablas provinciales resumidas y detalladas para
  ofrecer capacidad, nivel, volumen y porcentaje en todos los embalses
  publicados por la fuente.

## 1.1.25 - 2026-08-22

### Corregido

- Creación del contexto TLS de SAIH Ebro en el ejecutor de Home Assistant para
  evitar el bloqueo del bucle de eventos.
- Eliminados los iconos de marca duplicados de la raíz; Home Assistant utiliza
  las copias del directorio `brand`.

## 1.1.24 - 2026-07-24

### Corregido

- Restaurada la conexión con SAIH Ebro mediante la CA intermedia oficial de la
  FNMT omitida por el servidor de origen, manteniendo activa toda la
  verificación TLS.

### Cambiado

- Añadidos reintentos para errores de red y tiempos de espera transitorios de
  SAIH Ebro.
- Añadido el registro detallado de errores de los proveedores en los flujos de
  configuración y opciones.

## 1.1.23 - 2026-07-05

### Añadido

- Añadido workflow de validación HACS.
- Añadido workflow de validación Hassfest.

### Cambiado

- Simplificado `hacs.json` para cumplir el esquema actual de validación de HACS.
- Eliminados marcadores BOM UTF-8 de ficheros Python.
- Ordenadas las claves del manifest para Hassfest.

## 1.1.22 - 2026-05-21

### Añadido

- Documentación de publicación en español e inglés.
- Metadatos para HACS.

### Cambiado

- Refactor de proveedores MITECO para compartir una implementación común.
- Los proveedores MITECO por cuenca pasan a ser definiciones pequeñas y declarativas.
- Mejoradas cadenas de traducción en español y catalán.

### Notas

- México se investigó, pero no se añadió porque los datos estructurados accesibles de CONAGUA/SEMARNAT estaban desactualizados.
- Esta versión queda como release candidate antes de compartir públicamente.

## 1.1.20 - 2026-05-21

### Añadido

- Cuenca Tinto, Odiel y Piedras.
- Cuencas Internas del País Vasco.

## 1.1.18 - 2026-05-21

### Añadido

- Cuenca Guadalete-Barbate.

### Cambiado

- Redondeo de valores numéricos antes de exponerlos a Home Assistant.

## 1.1.16 - 2026-05-21

### Añadido

- Cuenca Mediterránea Andaluza.

## 1.1.15 - 2026-05-21

### Añadido

- Galicia Costa.

## 1.1.14 - 2026-05-21

### Añadido

- Cuenca del Cantábrico, cubriendo Cantábrico Oriental y Cantábrico Occidental.

## 1.1.13 - 2026-05-20

### Añadido

- Cuenca del Miño-Sil.

## 1.1.12 y anteriores

### Añadido

- Primeros proveedores para España y Estados Unidos.
- Soporte para Catalunya, Duero, Ebro, Guadiana, Guadalquivir, Júcar, Segura y Tajo.
- Proveedor de respaldo MITECO.
- Soporte USBR RISE para algunos embalses de Estados Unidos.
- Flujo de configuración, flujo de opciones, sensores agregados y diagnósticos.
