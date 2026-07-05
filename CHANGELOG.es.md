[Read this in English](CHANGELOG.md)

# Historial de cambios

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
