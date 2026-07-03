# OCR Pipeline Output

Generated: 2026-07-03T03:02:55.144111+00:00
PDFs processed: 2
Total pages: 2

---

---
title: ESP32 Series Datasheet
document_type: datasheet
language: en
publisher: Espressif Systems
series: ESP32 Series
revision: v5.2
pages: '52'
---

[Header: 5 Electrical Characteristics]
[p. 52]

# 5 Electrical Characteristics

## 5.1 Absolute Maximum Ratings

Stresses above those listed in *Table 5-1 Absolute Maximum Ratings* may cause permanent damage to the device. These are stress ratings only and normal operation of the device at these or any other conditions beyond those indicated in *Section 5.2 Recommended Power Supply Characteristics* is not implied. Exposure to absolute-maximum-rated conditions for extended periods may affect device reliability.

Table 5-1. Absolute Maximum Ratings

| Parameter                     | Description              | Min  | Max  | Unit |
| :---------------------------- | :----------------------- | :--- | :--- | :--- |
| VDDA, VDD3P3, VDD3P3_RTC, VDD3P3_CPU, VDD_SDIO | Allowed input voltage    | –0.3 | 3.6  | V    |
| Ioutput<sup>1</sup>           | Cumulative IO output current | —  | 1200 | mA   |
| T<sub>STORE</sub>             | Storage temperature      | –40  | 150  | °C   |

1 The product proved to be fully functional after all its IO pins were pulled high while being connected to ground for 24 consecutive hours at ambient temperature of 25 °C.

## 5.2 Recommended Power Supply Characteristics

Table 5-2. Recommended Power Supply Characteristics

| Parameter                                     | Description                               | Min           | Typ | Max | Unit |
| :-------------------------------------------- | :---------------------------------------- | :------------ | :-- | :-- | :--- |
| VDDA, VDD3P3_RTC, VDD3P3, VDD_SDIO (3.3 V mode) <sup>note 1</sup> | Voltage applied to power supply pins per power domain | 2.3/3.0 <sup>note 2</sup> | 3.3 | 3.6 | V    |
| VDD3P3_CPU                                    | Voltage applied to power supply pin       | 1.8           | 3.3 | 3.6 | V    |
| I<sub>VDD</sub>                               | Current delivered by external power supply | 0.5           | —   | —   | A    |
| T <sup>note 3</sup>                           | Operating temperature                     | –40           | —   | 125 | °C   |

1.  *   VDD_SDIO works as the power supply for the related IO, and also for an external device. Please refer to the *Appendix IO_MUX* of this datasheet for more details.
    *   VDD_SDIO can be sourced internally by the ESP32 from the VDD3P3_RTC power domain:
        *   When VDD_SDIO operates at 3.3 V, it is driven directly by VDD3P3_RTC through a 6 Ω resistor, therefore, there will be some voltage drop from VDD3P3_RTC.
        *   When VDD_SDIO operates at 1.8 V, it can be generated from ESP32’s internal LDO. The maximum current this LDO can offer is 40 mA, and the output voltage range is 1.65 V ~ 2.0 V.
    *   VDD_SDIO can also be driven by an external power supply.
    *   Please refer to *Section 2.5.2 Power Scheme*, for more information.
2.  *   Chips with a 3.3 V flash or PSRAM in-package: this minimum voltage is 3.0 V;
    *   Chips with no flash or PSRAM in-package: this minimum voltage is 2.3 V;
    *   For more information, see *Section 1 ESP32 Series Comparison*.
3.  The operating temperature of ESP32-U4WDH and ESP32-D0WDRH2-V3 ranges from –40 °C to 85 °C, due to the in-package flash or PSRAM. For other chips that have no in-package flash or PSRAM, their operating temperature is –40 °C ~ 125 °C.

Espressif Systems
Submit Documentation Feedback
ESP32 Series Datasheet v5.2

---

---
title: ESP32 Series Datasheet
document_type: datasheet
language: en
publisher: Espressif Systems
series: ESP32 Series
revision: v5.2
pages: '23'
---

## 3 Boot Configurations

Table 3-2. Description of Timing Parameters for the Strapping Pins
| Parameter | Description | Min (ms) |
|---|---|---|
| tSU | Setup time is the time reserved for the power rails to stabilize before the CHIP_PU pin is pulled high to activate the chip. | 0 |
| tH | Hold time is the time reserved for the chip to read the strapping pin values after CHIP_PU is already high and before these pins start operating as regular IO pins. | 1 |

[Diagram: Waveform showing CHIP_PU and Strapping pin voltages (VIH_nRST, VIH) with timing parameters tSU and tH]
Figure 3-1. Visualization of Timing Parameters for the Strapping Pins

## 3.1 Chip Boot Mode Control

GPIO0 and GPIO2 control the boot mode after the reset is released. See Table 3-3 Chip Boot Mode Control.

Table 3-3. Chip Boot Mode Control
| Boot Mode | GPIO0 | GPIO2 |
|---|---|---|
| SPI Boot Mode | 1 | Any value |
| Joint Download Boot Mode ² | 0 | 0 |

¹ **Bold** marks the default value and configuration.
² Joint Download Boot mode supports the following
download methods:
*   SDIO Download Boot
*   UART Download Boot

In Joint Download Boot mode, the detailed boot flow of the chip is put below 3-2.

Espressif Systems
23
Submit Documentation Feedback
ESP32 Series Datasheet v5.2