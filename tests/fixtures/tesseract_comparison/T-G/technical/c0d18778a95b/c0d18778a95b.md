---
title: ESP32 Series Datasheet
document_type: datasheet
language: en
publisher: Espressif Systems
revision: v5.2
---

## 3 Boot Configurations

Table 3-2. Description of Timing Parameters for the Strapping Pins

| Parameter | Description | Min (ms) |
|---|---|---|
| tSU | Setup time is the time reserved for the power rails to stabilize before the CHIP_PU pin is pulled high to activate the chip. | 0 |
| tH | Hold time is the time reserved for the chip to read the strapping pin values after CHIP_PU is already high and before these pins start operating as regular IO pins. | 1 |

[Diagram: Waveform showing CHIP_PU and Strapping pin signals with tSU and tH timing parameters. Labels: tSU, tH, CHIP_PU, V_IH_nRST, V_IH, Strapping pin]
Figure 3-1. Visualization of Timing Parameters for the Strapping Pins

### 3.1 Chip Boot Mode Control

GPIO0 and GPIO2 control the boot mode after the reset is released. See *Table 3-3 Chip Boot Mode Control*.

Table 3-3. Chip Boot Mode Control

| Boot Mode | GPIO0 | GPIO2 |
|---|---|---|
| SPI Boot Mode | 1 | Any value |
| Joint Download Boot Mode ² | 0 | 0 |

¹ Bold marks the default value and configuration.
² Joint Download Boot mode supports the following
download methods:
* SDIO Download Boot
* UART Download Boot

In Joint Download Boot mode, the detailed boot flow of the chip is put below *3-2*.

Espressif Systems
23
Submit Documentation Feedback
ESP32 Series Datasheet v5.2