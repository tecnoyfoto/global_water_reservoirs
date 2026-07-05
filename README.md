[Leer en español](README.es.md)

# Global Water Reservoirs for Home Assistant

Global Water Reservoirs is an **unofficial** Home Assistant custom integration for tracking reservoir storage data from public water-data sources.

The integration creates one hub per selected data source or basin, and one device per selected reservoir. Each reservoir exposes normalized sensors such as stored volume, percentage, level when available, data timestamp and data age.

The first public focus is Spain, where public reservoir data is available from multiple official sources. The integration also includes initial support for selected United States reservoirs through USBR RISE.

## Current Status

Version `1.1.22` is a release-candidate style build.

Current priorities:

- Provide useful reservoir data in Home Assistant.
- Prefer official or public institutional sources.
- Keep polling conservative and configurable.
- Avoid adding sources that are stale, fragile or misleading.

Mexico has been investigated, including CONAGUA and SEMARNAT public endpoints. Those endpoints currently expose structured reservoir data, but the accessible datasets found during development were stale, so Mexico is **not included yet**.

## Highlights

- Config flow UI, no YAML required.
- Multiple hubs in the same Home Assistant instance.
- Reservoir selection during setup.
- Options flow to add/remove reservoirs later.
- Configurable update interval.
- Individual reservoir sensors.
- Aggregate hub sensors.
- Diagnostics with useful metadata.
- English, Spanish and Catalan translations.
- Conservative display precision for percentages and volumes.

## Supported Countries and Sources

### Spain

Spain is split into basin/data-source hubs. Depending on the basin, the integration uses more specific basin services or MITECO's reservoir map layer.

Supported hubs include:

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
- Spain fallback through MITECO weekly/map data

### United States

- USBR / RISE reservoir conditions for selected reservoirs.

US support is narrower than Spain support and should be treated as an early data-source implementation.

## Entities

Reservoir devices may expose:

- **Percent**: reservoir fill percentage.
- **Volume**: stored water volume in `hm³`.
- **Level**: water level in meters where the source provides it.
- **Capacity**: reservoir capacity in `hm³`.
- **Data timestamp**: timestamp of the source data.
- **Data age**: age of the latest source data.

Hub devices may expose:

- **Aggregate percent**
- **Total volume**
- **Total capacity**
- **Reservoir count**
- **Reservoirs with data**
- **Reservoirs with stale data**
- **Latest data timestamp**

Entities are created only when the selected source provides the required data.

## Installation

### HACS

1. Open **HACS -> Integrations**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/tecnoyfoto/global_water_reservoirs` as an **Integration**.
4. Install **Global Water Reservoirs**.
5. Restart Home Assistant.

### Manual

Copy the integration folder into your Home Assistant configuration:

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

Then restart Home Assistant.

## Configuration

Add the integration from:

**Settings -> Devices & services -> Add integration -> Global Water Reservoirs**

The setup flow asks for:

- **Country**
- **Data source / basin**
- **Reservoirs to add**
- **Update interval**

Each data source creates its own hub. You can add several hubs if you want to track reservoirs from different basins.

## Options

Open:

**Settings -> Devices & services -> Global Water Reservoirs -> Configure**

Options let you:

- Add or remove reservoirs from an existing hub.
- Change the update interval.

Saving options reloads the affected config entry automatically.

## Data Freshness

The integration exposes timestamp and data-age sensors so you can tell how fresh each source is.

Some official sources update several times a day. Others update daily or weekly. The integration does not invent data; when a source is old or unavailable, the diagnostic sensors make that visible.

## Privacy and Diagnostics

The integration does not require credentials.

Diagnostics include selected reservoir keys, provider information and normalized reservoir data useful for debugging. There are no passwords, tokens or account details to redact because the integration only uses public data sources.

## Known Limitations

- Public water-data services can change without notice.
- Some sources expose volume and percentage but not water level.
- MITECO-backed basin hubs usually reflect the latest data available in MITECO's map layer, not necessarily real-time telemetry.
- Mexico is intentionally not included yet because the structured public datasets found so far are stale.
- United States support is currently limited to the USBR RISE provider implemented in this integration.

## Troubleshooting

- **No reservoirs appear during setup**: the selected data source may be temporarily unavailable. Try again later and check Home Assistant logs.
- **A reservoir has no level sensor**: the selected source may not publish water level for that reservoir.
- **Data looks old**: check the data timestamp and data-age sensors. Some official sources publish daily or weekly, not hourly.
- **You want to add more reservoirs to a hub**: open the integration options and select additional reservoirs.
- **A public source changed its format**: open an issue with diagnostics and the affected data source.

## Translations

Included languages:

- English
- Spanish
- Catalan

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

Released under the [MIT](LICENSE) license.
