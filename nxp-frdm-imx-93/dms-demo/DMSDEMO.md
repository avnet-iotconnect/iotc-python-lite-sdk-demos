# i.MX 93 AI Vision Demo: Driver Monitoring System

# 1. Introduction
This document will help guide you to enable the Driver Monitoring System demo on your NXP FRDM i.MX 93 Development Board.

# 2. Prerequisites
It is expected that you have already followed [the main README guide](../README.md) for this board which means you have:
  * Already created your device in IoTConnect
  * Already connected to your board serially (or via SSH) so that you have access to its terminal
  * Already installed the IoTConnect Python Lite SDK on your board

To utilize the AI vision demos on the i.MX 93, you will also need a UVC-compliant USB camera (**modern webcams that require drivers will not work**). If you do not already own one, [this one](https://www.digikey.com/en/products/detail/dfrobot/FIT0701/13166487?utm_adgroup=&utm_source=google&utm_medium=cpc&utm_campaign=PMax%20Shopping_Product_Low%20ROAS%20Categories&utm_term=&utm_content=&utm_id=go_cmp-20243063506_adg-_ad-__dev-c_ext-_prd-13166487_sig-Cj0KCQjwr9m3BhDHARIsANut04Z3EUiWzjUUq3cYHS7OLaj6bW-ueFx3Sh8pO7NgQwhyBYT0FjGrmZgaAtb2EALw_wcB&gad_source=1&gclid=Cj0KCQjwr9m3BhDHARIsANut04Z3EUiWzjUUq3cYHS7OLaj6bW-ueFx3Sh8pO7NgQwhyBYT0FjGrmZgaAtb2EALw_wcB) is suitable. 
