[Leer en español](CHANGELOG.es.md)

# Changelog

## 1.1.28 - 2026-09-07

### Added

- Expanded SAIH Ebro coverage from the 12 reservoirs on the general basin map
  to all 82 reservoirs currently exposing usable public data through the
  official regional maps, daily summary, and current station values.
- Added reservoirs requested by users, including Pajares and González Lacasa.

### Changed

- Discover the official SAIH Ebro regional map catalogue dynamically and
  deduplicate reservoirs by their stable station code.
- Cache Ebro catalogue discovery and refresh only the sources required by the
  selected reservoirs, with bounded request concurrency.
- Preserve existing Ebro device and entity identifiers.

## 1.1.27 - 2026-09-04

### Fixed

- Restored CH Duero connectivity on Home Assistant installations that reject
  the invalid FNMT intermediate certificate sent by the upstream server, while
  keeping full TLS verification enabled.
- Build the CH Duero TLS context in Home Assistant's executor to avoid blocking
  the event loop.
- Retry transient CH Duero network, HTTP, timeout, and invalid-response errors.
- Parse localized thousands and decimal separators in CH Duero values, fixing
  the reported volume for the Almendra reservoir.

## 1.1.26 - 2026-09-03

### Fixed

- Isolate all SAIH Guadalquivir requests from the site's ASP.NET cookies, which
  could make the server return an incomplete reservoir table.
- Parse and merge both the summary and detailed provincial reservoir tables so
  capacity, level, volume, and percentage are available for every reservoir
  published by the source.

## 1.1.25 - 2026-08-22

### Fixed

- Build the SAIH Ebro TLS context in Home Assistant's executor to avoid
  blocking the event loop.
- Remove duplicate root-level brand icons; Home Assistant uses the copies in
  the `brand` directory.

## 1.1.24 - 2026-07-24

### Fixed

- Restored SAIH Ebro connectivity by adding the official FNMT intermediate CA
  omitted by the upstream server, while keeping full TLS verification enabled.

### Changed

- Added retries for transient SAIH Ebro network errors and timeouts.
- Added detailed provider error logging to the configuration and options flows.

## 1.1.23 - 2026-07-05

### Added

- Added HACS validation workflow.
- Added Hassfest validation workflow.

### Changed

- Simplified `hacs.json` to match the current HACS validation schema.
- Removed UTF-8 BOM markers from Python files.
- Sorted manifest keys for Hassfest.

## 1.1.22 - 2026-05-21

### Added

- Prepared public release documentation in English and Spanish.
- Added HACS metadata.

### Changed

- Refactored MITECO basin providers to share a common implementation.
- Simplified basin-specific MITECO providers into declarative definitions.
- Improved Spanish and Catalan translation strings.

### Notes

- Mexico was investigated but not added because accessible structured CONAGUA/SEMARNAT data was stale.
- This version is intended as a release-candidate style build before public sharing.

## 1.1.20 - 2026-05-21

### Added

- Tinto, Odiel y Piedras basin.
- Internal Basque Country basins.

## 1.1.18 - 2026-05-21

### Added

- Guadalete-Barbate basin.

### Changed

- Rounded numeric sensor values before exposing them to Home Assistant.

## 1.1.16 - 2026-05-21

### Added

- Cuenca Mediterránea Andaluza.

## 1.1.15 - 2026-05-21

### Added

- Galicia Costa.

## 1.1.14 - 2026-05-21

### Added

- Cantabrian basin hub covering Cantábrico Oriental and Cantábrico Occidental.

## 1.1.13 - 2026-05-20

### Added

- Miño-Sil basin.

## 1.1.12 and earlier

### Added

- Initial Spain and United States providers.
- Catalunya, Duero, Ebro, Guadiana, Guadalquivir, Júcar, Segura and Tajo support.
- MITECO fallback provider.
- USBR RISE support for selected United States reservoirs.
- Config flow, options flow, aggregate sensors and diagnostics.
