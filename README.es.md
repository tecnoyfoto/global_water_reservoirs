[Read this in English](README.md)

# Embalses globales para Home Assistant

Embalses globales es una integración personalizada **no oficial** para Home Assistant que permite seguir datos de almacenamiento de embalses desde fuentes públicas.

La integración crea un hub por fuente de datos o cuenca seleccionada, y un dispositivo por cada embalse elegido. Cada embalse expone sensores normalizados como volumen almacenado, porcentaje, nivel cuando existe, fecha/hora del dato y antigüedad del dato.

El primer foco público es España, donde hay datos disponibles desde varias fuentes oficiales. La integración también incluye soporte inicial para algunos embalses de Estados Unidos mediante USBR RISE.

## Estado actual

La versión `1.1.22` es una versión tipo release candidate.

Prioridades actuales:

- Ofrecer datos útiles de embalses dentro de Home Assistant.
- Priorizar fuentes oficiales o institucionales públicas.
- Mantener intervalos de actualización conservadores y configurables.
- Evitar fuentes antiguas, frágiles o engañosas.

México se ha investigado, incluyendo endpoints públicos de CONAGUA y SEMARNAT. Esos endpoints exponen datos estructurados, pero los conjuntos accesibles encontrados durante el desarrollo estaban desactualizados, así que México **todavía no está incluido**.

## Puntos destacados

- Configuración desde la interfaz, sin YAML.
- Varios hubs en la misma instancia de Home Assistant.
- Selección de embalses durante la configuración.
- Flujo de opciones para añadir o quitar embalses más tarde.
- Intervalo de actualización configurable.
- Sensores individuales por embalse.
- Sensores agregados por hub.
- Diagnósticos con metadatos útiles.
- Traducciones en español, inglés y catalán.
- Precisión de visualización conservadora para porcentajes y volúmenes.

## Países y fuentes soportadas

### España

España se organiza en hubs por cuenca o fuente de datos. Según la cuenca, la integración usa servicios específicos o la capa de embalses de MITECO.

Hubs soportados:

- Catalunya
- Cuenca del Duero
- Cuenca del Ebro
- Cuenca del Guadiana
- Cuenca del Guadalquivir
- Cuenca del Júcar
- Cuenca del Segura
- Cuenca del Tajo
- Cuenca del Miño-Sil
- Cuenca del Cantábrico
- Galicia Costa
- Cuenca Mediterránea Andaluza
- Cuenca Guadalete-Barbate
- Cuenca Tinto, Odiel y Piedras
- Cuencas Internas del País Vasco
- Respaldo España mediante datos semanales/mapa de MITECO

### Estados Unidos

- Condiciones de embalses mediante USBR / RISE para embalses seleccionados.

El soporte de Estados Unidos es más limitado que el de España y debe considerarse una primera implementación de esa fuente.

## Entidades

Los dispositivos de embalse pueden exponer:

- **Porcentaje**: porcentaje de llenado.
- **Volumen**: volumen almacenado en `hm³`.
- **Nivel**: nivel del agua en metros cuando la fuente lo publica.
- **Capacidad**: capacidad del embalse en `hm³`.
- **Fecha/hora del dato**: fecha del dato publicado por la fuente.
- **Antigüedad del dato**: antigüedad del último dato.

Los hubs pueden exponer:

- **Porcentaje agregado**
- **Volumen total**
- **Capacidad total**
- **Embalses**
- **Embalses con datos**
- **Embalses con datos antiguos**
- **Último dato recibido**

Las entidades solo se crean cuando la fuente seleccionada publica el dato necesario.

## Instalación

### HACS

1. Abre **HACS -> Integrations**.
2. Abre el menú de tres puntos y entra en **Custom repositories**.
3. Añade `https://github.com/tecnoyfoto/global_water_reservoirs` como **Integration**.
4. Instala **Global Water Reservoirs**.
5. Reinicia Home Assistant.

### Manual

Copia la carpeta de la integración en tu configuración de Home Assistant:

```text
config/
  custom_components/
    global_water_reservoirs/
      __init__.py
      manifest.json
      config_flow.py
      const.py
      coordinator.py
      sensor.py
      diagnostics.py
      providers/
      translations/
```

Después reinicia Home Assistant.

## Configuración

Añade la integración desde:

**Ajustes -> Dispositivos y servicios -> Añadir integración -> Global Water Reservoirs**

El flujo te pedirá:

- **País**
- **Fuente de datos / cuenca**
- **Embalses a añadir**
- **Intervalo de actualización**

Cada fuente de datos crea su propio hub. Puedes añadir varios hubs si quieres seguir embalses de distintas cuencas.

## Opciones

Abre:

**Ajustes -> Dispositivos y servicios -> Global Water Reservoirs -> Configurar**

Las opciones permiten:

- Añadir o quitar embalses de un hub existente.
- Cambiar el intervalo de actualización.

Al guardar opciones, la entrada se recarga automáticamente.

## Frescura de los datos

La integración expone sensores de fecha/hora y antigüedad del dato para que puedas ver claramente cómo de reciente es cada fuente.

Algunas fuentes oficiales actualizan varias veces al día. Otras actualizan a diario o semanalmente. La integración no inventa datos: si una fuente está antigua o no disponible, los sensores de diagnóstico lo hacen visible.

## Privacidad y diagnósticos

La integración no requiere credenciales.

Los diagnósticos incluyen claves de embalses seleccionados, información del proveedor y datos normalizados útiles para depuración. No hay contraseñas, tokens ni datos de cuenta que redactar porque la integración solo usa fuentes públicas.

## Limitaciones conocidas

- Los servicios públicos pueden cambiar sin previo aviso.
- Algunas fuentes publican volumen y porcentaje, pero no nivel.
- Los hubs basados en MITECO reflejan normalmente el último dato disponible en la capa de MITECO, no telemetría en tiempo real.
- México no está incluido todavía porque las fuentes públicas estructuradas encontradas hasta ahora están desactualizadas.
- Estados Unidos está limitado al proveedor USBR RISE implementado actualmente.

## Solución de problemas

- **No aparecen embalses durante la configuración**: la fuente puede estar temporalmente no disponible. Inténtalo más tarde y revisa los registros de Home Assistant.
- **Un embalse no tiene sensor de nivel**: la fuente seleccionada puede no publicar nivel para ese embalse.
- **El dato parece antiguo**: revisa los sensores de fecha/hora y antigüedad del dato. Algunas fuentes oficiales publican a diario o semanalmente, no cada hora.
- **Quieres añadir más embalses a un hub**: abre las opciones de la integración y selecciona embalses adicionales.
- **Una fuente pública cambia de formato**: abre una issue con diagnósticos y la fuente afectada.

## Traducciones

Idiomas incluidos:

- Español
- Inglés
- Catalán

## Historial de cambios

Consulta [CHANGELOG.es.md](CHANGELOG.es.md).

## Licencia

Publicado bajo licencia [MIT](LICENSE).
