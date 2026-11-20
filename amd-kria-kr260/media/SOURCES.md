# Image Sources

Image source: AMD. Board images are official AMD product/documentation images of the Kria KR260 Robotics Starter Kit (SK-KR260-G), reproduced here for identification in this quickstart. All trademarks are the property of their respective owners.

## kr260-product.png

- Original: https://www.amd.com/content/dam/amd/en/images/products/som/2362834-kr260-angle-1.jpg
- From the AMD Kria KR260 Robotics Starter Kit product page: https://www.amd.com/en/products/system-on-modules/kria/k26/kr260-robotics-starter-kit.html
- Modifications: converted JPEG to PNG, downscaled to 1100 px.

## kr260-connections.png

- Original (base image): https://www.amd.com/content/dam/amd/en/images/products/som/2362834-kr260-product.jpg
- From the AMD Kria KR260 Robotics Starter Kit product page: https://www.amd.com/en/products/system-on-modules/kria/k26/kr260-robotics-starter-kit.html
- Modifications: added numbered connector callouts (1-6) and a legend matching the README Hardware Setup steps, downscaled to 1000 px.
- Connector locations cross-checked against the official AMD Kria Ubuntu 24.04 boot guide "Step 2: Connect Everything" animation:
  https://xilinx.github.io/kria-apps-docs/kr260/linux_boot/ubuntu_24_04/build/html/docs/connections.html
  (image: https://xilinx.github.io/kria-apps-docs/kr260/linux_boot/ubuntu_24_04/build/html/_images/kr260-animated.gif)

## Callout reference

| # | Connector | Notes |
|---|-----------|-------|
| 1 | microSD card slot (J11) | Slot is mounted on the underside of the board edge; callout marks the edge position shown in the official connection animation |
| 2 | micro-USB JTAG/UART (J4) | "UART"/"J4" silkscreen beside the connector |
| 3 | PS Ethernet (J10D, top right port; J10C also works) | Board silkscreen marks the left stacked pair (in the top-down view) "PS ETH" and the right pair "PL ETH" (J10A/J10B) |
| 4 | USB 3.0 ports (U44/U46) | Two stacked dual Type-A connectors |
| 5 | DisplayPort (J6) | Between the power jack and the USB ports |
| 6 | 12V power jack (J12) | "12V PWR" silkscreen beside the barrel jack |
