[Header: 3 Boot Configurations]

Table 3-2. Description of Timing Parameters for the Strapping Pins
| Parameter | Description | Min (ms) |
| :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------ | :------- |
| t<sub>SU</sub> | Setup time is the time reserved for the power rails to stabilize before the CHIP_PU pin is pulled high to activate the chip. | 0 |
| t<sub>H</sub> | Hold time is the time reserved for the chip to read the strapping pin values after CHIP_PU is already high and before these pins start operating as regular IO pins. | 1 |

[Diagram: Timing diagram showing tSU and tH for CHIP_PU and Strapping pin signals, relative to V_IH_nRST and V_IH thresholds.]
t<sub>SU</sub>
t<sub>H</sub>
V_IH_nRST
V_IH
CHIP_PU
Strapping pin
Figure 3-1. Visualization of Timing Parameters for the Strapping Pins

## 3.1 Chip Boot Mode Control
GPIO0 and GPIO2 control the boot mode after the reset is released. See Table 3-3 *Chip Boot Mode Control*.

Table 3-3. Chip Boot Mode Control
| Boot Mode | GPIO0 | GPIO2 |
| :----------------------- | :---- | :-------- |
| **SPI Boot Mode** | 1 | Any value |
| Joint Download Boot Mode <sup>2</sup> | 0 | 0 |

<sup>1</sup> **Bold** marks the default value and configuration.
<sup>2</sup> Joint Download Boot mode supports the following download methods:
*   SDIO Download Boot
*   UART Download Boot

In Joint Download Boot mode, the detailed boot flow of the chip is put below 3-2.

Espressif Systems
23
Submit Documentation Feedback
ESP32 Series Datasheet v5.2