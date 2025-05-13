# Common Measurement Units Reference

This document provides a reference for common measurement units to use with the measurement schema, following UCUM (Unified Code for Units of Measure) and QUDT (Quantities, Units, Dimensions, and Types) standards.

## Temperature

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Temperature   | Celsius   | Cel       | General temperature measurements |
| Temperature   | Kelvin    | K         | SI base unit for temperature |
| Temperature   | Fahrenheit| [degF]    | UCUM code for degrees Fahrenheit |

## Length/Distance

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Length        | meter     | m         | SI base unit for length |
| Length        | kilometer | km        | Long distances |
| Length        | centimeter| cm        | Small measurements |
| Length        | millimeter| mm        | Precision measurements |
| Length        | micrometer| um        | Microscopic measurements |
| Length        | nanometer | nm        | Atomic-scale measurements |
| Length        | inch      | [in_i]    | Imperial/US customary |
| Length        | foot      | [ft_i]    | Imperial/US customary |
| Length        | mile      | [mi_i]    | Long distances (Imperial) |

## Mass

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Mass          | kilogram  | kg        | SI base unit for mass |
| Mass          | gram      | g         | Small mass measurements |
| Mass          | milligram | mg        | Very small mass measurements |
| Mass          | pound     | [lb_av]   | Imperial/US customary |
| Mass          | ounce     | [oz_av]   | Imperial/US customary |

## Time

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Time          | second    | s         | SI base unit for time |
| Time          | minute    | min       | 60 seconds |
| Time          | hour      | h         | 60 minutes |
| Time          | day       | d         | 24 hours |
| Time          | millisecond| ms       | 1/1000 second |
| Time          | microsecond| us       | 1/1,000,000 second |
| Time          | nanosecond | ns       | 1/1,000,000,000 second |

## Frequency

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Frequency     | hertz     | Hz        | SI unit for frequency (1/s) |
| Frequency     | kilohertz | kHz       | 1,000 Hz |
| Frequency     | megahertz | MHz       | 1,000,000 Hz |
| Frequency     | gigahertz | GHz       | 1,000,000,000 Hz |

## Electric Properties

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| ElectricCurrent | ampere  | A         | SI base unit for electric current |
| ElectricPotential | volt  | V         | Voltage |
| ElectricResistance | ohm  | Ohm       | Resistance |
| ElectricCapacitance | farad | F       | Capacitance |
| ElectricInductance | henry | H        | Inductance |
| ElectricConductance | siemens | S     | Conductance |

## Power and Energy

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Power         | watt      | W         | SI unit for power |
| Power         | kilowatt  | kW        | 1,000 watts |
| Power         | megawatt  | MW        | 1,000,000 watts |
| Energy        | joule     | J         | SI unit for energy |
| Energy        | kilojoule | kJ        | 1,000 joules |
| Energy        | kilowatt-hour | kW.h  | Common energy unit (3,600,000 J) |

## Pressure

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Pressure      | pascal    | Pa        | SI unit for pressure |
| Pressure      | kilopascal | kPa      | 1,000 pascals |
| Pressure      | bar       | bar       | 100,000 pascals |
| Pressure      | atmosphere | atm      | Standard atmospheric pressure |
| Pressure      | millimeter of mercury | mm[Hg] | Traditional pressure unit |

## Data Transfer and Storage

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| DataRate      | bit per second | bit/s | Basic data transfer rate |
| DataRate      | kilobit per second | kbit/s | 1,000 bit/s |
| DataRate      | megabit per second | Mbit/s | 1,000,000 bit/s |
| DataRate      | gigabit per second | Gbit/s | 1,000,000,000 bit/s |
| DataAmount    | byte      | By       | 8 bits |
| DataAmount    | kilobyte  | kBy      | 1,000 bytes |
| DataAmount    | megabyte  | MBy      | 1,000,000 bytes |
| DataAmount    | gigabyte  | GBy      | 1,000,000,000 bytes |

## Signal Strength and Ratios

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| PowerRatio    | decibel   | dB        | Logarithmic ratio |
| SignalStrength | dBm      | dB[mW]    | Power relative to 1 mW |
| SignalToNoiseRatio | dB   | dB        | Signal to noise ratio |
| SoundPressureLevel | dB[SPL] | dB[SPL] | Sound pressure level |

## Speed/Velocity

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Velocity      | meter per second | m/s | SI unit for velocity |
| Velocity      | kilometer per hour | km/h | Common speed unit |
| Velocity      | mile per hour | [mi_i]/h | Imperial speed unit |

## Area

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Area          | square meter | m2      | SI unit for area |
| Area          | square kilometer | km2  | Large areas |
| Area          | hectare   | ha        | Land area (10,000 m²) |
| Area          | square foot | [sft_i] | Imperial area unit |
| Area          | square mile | [mi_i]2 | Large Imperial areas |

## Volume

| Quantity Kind | Unit Name | Unit Code | Notes |
|---------------|-----------|-----------|-------|
| Volume        | cubic meter | m3      | SI unit for volume |
| Volume        | liter     | l         | Common volume unit (0.001 m³) |
| Volume        | milliliter | ml       | Small volumes |
| Volume        | gallon    | [gal_us]  | US liquid gallon |
| Volume        | fluid ounce | [foz_us]| US fluid ounce |

## Usage Examples

```json
{
  "quantity_kind": "Temperature",
  "value": 22.6,
  "unit": "Cel",
  "uncertainty": 0.3
}
```

```json
{
  "quantity_kind": "SignalStrength",
  "value": -67.5,
  "unit": "dB[mW]",
  "timestamp": "2025-05-13T11:59:27Z",
  "observed_by": "dev.wifi-scanner-001"
}
```

```json
{
  "quantity_kind": "DataRate",
  "value": 867.3,
  "unit": "Mbit/s",
  "feature_of_interest": "tm.wifi-channel-5"
}
```

## References

- [UCUM Specification](https://ucum.org/ucum.html)
- [QUDT Ontology](https://www.qudt.org/)