# OCR Pipeline Output

Generated: 2026-07-03T00:20:32.771880+00:00
PDFs processed: 1
Total pages: 1

---

---
{}
---

*Technical Specification Sheet — Model XR-4500*
The following specifications define the electrical, thermal, and mechanical operating parameters for the XR-4500 series precision voltage reference module. All values are valid at TA = +25 °C unless otherwise noted. Parameters marked with an asterisk (*) are guaranteed by design and characterization but not production-tested.

| Parameter | Symbol | Min | Typ | Max | Unit | Tolerance | Test Condition | Temp | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Input Voltage | VIN | 4.5 | 5.0 | 5.5 | V | ±0.25 V | VOUT = 2.5 V, ILOAD = 0 mA | –40 to +85 °C | Regulated input |
| Output Voltage | VOUT | 2.495 | 2.500 | 2.505 | V | ±0.1 % | VIN = 5.0 V, ILOAD = 10 mA | +25 °C | Trimmed at factory |
| Temp. Coefficient | TCVOUT | — | 3 | 8 | ppm/°C | ±2.5 ppm | VIN = 5.0 V, box method | –40 to +125 °C | Grade A only |
| Load Regulation | ΔVOUT/ΔIL | — | 0.5 | 2.0 | mV/mA | — | 0 mA ≤ ILOAD ≤ 50 mA | +25 °C | Sourcing only |
| Line Regulation | ΔVOUT/ΔVIN | — | 0.1 | 1.0 | mV/V | — | 4.5 V ≤ VIN ≤ 15 V | +25 °C | DC measurement |
| Quiescent Current | IQ | — | 800 | 1200 | µA | ±200 µA | ILOAD = 0 mA, VIN = 5.0 V | +25 °C | No-load condition |
| Output Noise (0.1–10 Hz) | eN_p-p | — | 1.5 | 3.0 | µVp-p | — | BW = 0.1 Hz to 10 Hz | +25 °C | Peak-to-peak |
| Power Supply Rejection | PSRR | 80 | 100 | — | dB | — | f = 120 Hz, VIN = 5.0 V ± 0.5 V | +25 °C | Ripple rejection |
| Thermal Resistance (J-A) | θJA | — | 120 | 150 | °C/W | — | Still air, JEDEC 2S2P board | — | SOIC-8 package |

Doc #: SPEC-XR4500-2024-R3 | Date: 2024-11-15 | Confidential