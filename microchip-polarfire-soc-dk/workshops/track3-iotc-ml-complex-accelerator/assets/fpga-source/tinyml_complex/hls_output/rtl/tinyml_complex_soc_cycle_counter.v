// ©2021 Microchip Technology Inc. and its subsidiaries
//
// Subject to your compliance with these terms, you may use this Microchip software and any derivatives 
// exclusively with Microchip products. You are responsible for complying with third party license terms
// applicable to your use of third party software (including open source software) that may accompany this
// Microchip software. SOFTWARE IS “AS IS.” NO WARRANTIES, WHETHER EXPRESS, IMPLIED OR STATUTORY, APPLY 
// TO THIS SOFTWARE, INCLUDING ANY IMPLIED WARRANTIES OF NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS 
// FOR A PARTICULAR PURPOSE. IN NO EVENT WILL MICROCHIP BE LIABLE FOR ANY INDIRECT, SPECIAL, PUNITIVE,
// INCIDENTAL OR CONSEQUENTIAL LOSS, DAMAGE, COST OR EXPENSE OF ANY KIND WHATSOEVER RELATED TO THE SOFTWARE, 
// HOWEVER CAUSED, EVEN IF MICROCHIP HAS BEEN ADVISED OF THE POSSIBILITY OR THE DAMAGES ARE FORESEEABLE. 
// TO THE FULLEST EXTENT ALLOWED BY LAW, MICROCHIP’S TOTAL LIABILITY ON ALL CLAIMS LATED TO THE SOFTWARE 
// WILL NOT EXCEED AMOUNT OF FEES, IF ANY, YOU PAID DIRECTLY TO MICROCHIP FOR THIS SOFTWARE. MICROCHIP OFFERS 
// NO SUPPORT FOR THE SOFTWARE. YOU MAY CONTACT MICROCHIP AT 
// https://www.microchip.com/en-us/support-and-training/design-help/client-support-services TO INQUIRE ABOUT 
// SUPPORT SERVICES AND APPLICABLE FEES, IF AVAILABLE.

// 
// This module implements a hardware counter with a AXI4 slave interface.  
// The counter is 48-bit, so the address space of the AXI4 slave is 8byte 
// (prepend 16'b0). The counter increments by 1 every clock cycle.
// Reading the AXI4 slave returns the counter value on the right next cycle 
// after receiving read request (AR).
// Writing to the AXI4 slave will overwrite the counter value. Response (B) 
// is sent back right after write data (W) is received.
//

module tinyml_complex_soc_cycle_counter #(
  parameter AXI_DATA_WIDTH = 64,
  parameter AXI_ID_WIDTH = 5,
  parameter AXI_ADDR_WIDTH = 8
) (
  input                               i_clk,
  input                               i_reset,

  output                              o_axi4target_arready,
  input                               i_axi4target_arvalid,
  input  [AXI_ADDR_WIDTH  - 1:0]      i_axi4target_araddr,
  input  [AXI_ID_WIDTH    - 1:0]      i_axi4target_arid,
  input  [1:0]                        i_axi4target_arburst,
  input  [7:0]                        i_axi4target_arlen,
  input  [2:0]                        i_axi4target_arsize,
  input  [3:0]                        i_axi4target_arcache,   // Ignore.
  input  [1:0]                        i_axi4target_arlock,    // Ignore.
  input  [2:0]                        i_axi4target_arprot,    // Ignore.
  input  [3:0]                        i_axi4target_arqos,     // Ignore.
  input  [3:0]                        i_axi4target_arregion,  // Ignore.
  input  [0:0]                        i_axi4target_aruser,    // Ignore.

  input                               i_axi4target_rready,
  output reg                          o_axi4target_rvalid,
  output [AXI_DATA_WIDTH  - 1:0]      o_axi4target_rdata,
  output reg [AXI_ID_WIDTH    - 1:0]  o_axi4target_rid,
  output                              o_axi4target_rlast,
  output [1:0]                        o_axi4target_rresp,
  output [0:0]                        o_axi4target_ruser,

  output                              o_axi4target_awready,
  input                               i_axi4target_awvalid,
  input  [AXI_ADDR_WIDTH - 1:0]       i_axi4target_awaddr,
  input  [AXI_ID_WIDTH   - 1:0]       i_axi4target_awid,
  input  [1:0]                        i_axi4target_awburst,
  input  [7:0]                        i_axi4target_awlen,
  input  [2:0]                        i_axi4target_awsize,
  input  [3:0]                        i_axi4target_awcache,   // Ignore.
  input  [1:0]                        i_axi4target_awlock,    // Ignore.
  input  [2:0]                        i_axi4target_awprot,    // Ignore.
  input  [3:0]                        i_axi4target_awqos,     // Ignore.
  input  [3:0]                        i_axi4target_awregion,  // Ignore.
  input  [0:0]                        i_axi4target_awuser,    // Ignore.

  output                              o_axi4target_wready,
  input                               i_axi4target_wvalid,
  input  [AXI_DATA_WIDTH  - 1:0]      i_axi4target_wdata,
  input                               i_axi4target_wlast,
  input  [(AXI_DATA_WIDTH/8)-1:0]     i_axi4target_wstrb,
  input  [0:0]                        i_axi4target_wuser,     // Ignore.

  output reg                          o_axi4target_bvalid,
  input                               i_axi4target_bready,
  output reg [AXI_ID_WIDTH - 1:0]     o_axi4target_bid,
  output [1:0]                        o_axi4target_bresp,
  output [0:0]                        o_axi4target_buser
);

  localparam COUNT_WIDTH = 48; // E.g. 48bit @ 200MHz ~ 16 days before counter wraps around

  reg [COUNT_WIDTH-1:0] cnt;

  assign o_axi4target_arready = 1'b1;
  assign o_axi4target_rdata   = {16'b0,cnt};
  assign o_axi4target_rlast   = 1;   
  assign o_axi4target_rresp   = 0;   
  assign o_axi4target_ruser   = 0;
  assign o_axi4target_awready = 1;
  assign o_axi4target_wready  = 1;
  assign o_axi4target_bresp   = 0;
  assign o_axi4target_buser   = 0;

  always @(posedge i_clk) begin
    if (i_axi4target_rready) o_axi4target_rvalid <= 0;
    if (i_axi4target_arvalid) begin
      o_axi4target_rvalid <= 1;
      o_axi4target_rid <= i_axi4target_arid;
    end
  end

  always @(posedge i_clk) begin
    if (i_axi4target_awvalid) o_axi4target_bid <= i_axi4target_awid;
    if (i_axi4target_bready) o_axi4target_bvalid <= 0;
    if (i_axi4target_wvalid) o_axi4target_bvalid <= 1;
  end

  always @(posedge i_clk) begin
    cnt <= cnt + 1'b1;
    if (i_axi4target_wvalid) cnt <= i_axi4target_wdata[COUNT_WIDTH-1:0];
    if (i_reset) cnt <= 0;
  end
  
endmodule


