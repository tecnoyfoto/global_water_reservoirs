[Leer en español](CHANGELOG.es.md)

# Changelog

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
