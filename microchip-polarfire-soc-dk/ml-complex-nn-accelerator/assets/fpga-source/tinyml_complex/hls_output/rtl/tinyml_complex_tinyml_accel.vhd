-- ----------------------------------------------------------------------------
-- Smart High-Level Synthesis Tool Version 2025.2
-- Copyright (c) 2015-2025 Microchip Technology Inc. All Rights Reserved.
-- For support, please visit https://onlinedocs.microchip.com/v2/keyword-lookup?keyword=techsupport&redirect=true&version=latest.
-- Date: Sat Feb 14 12:37:08 2026
-- ----------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.std_logic_arith.all;




entity tinyml_accel_top_vhdl is
port (
	clk   :        in     std_logic;
	reset   :        in     std_logic;
	axi4target_arready   :        out    std_logic;
	axi4target_arvalid   :        in     std_logic;
	axi4target_araddr   :        in     std_logic_vector(20-1 downto 0);
	axi4target_arid   :        in     std_logic_vector(0 downto 0);
	axi4target_arburst   :        in     std_logic_vector(1 downto 0);
	axi4target_arlen   :        in     std_logic_vector(7 downto 0);
	axi4target_arsize   :        in     std_logic_vector(2 downto 0);
	axi4target_arcache   :        in     std_logic_vector(3 downto 0);
	axi4target_arlock   :        in     std_logic_vector(1 downto 0);
	axi4target_arprot   :        in     std_logic_vector(2 downto 0);
	axi4target_arqos   :        in     std_logic_vector(3 downto 0);
	axi4target_arregion   :        in     std_logic_vector(3 downto 0);
	axi4target_aruser   :        in     std_logic_vector(0 downto 0);
	axi4target_rready   :        in    std_logic;
	axi4target_rvalid   :        out    std_logic;
	axi4target_rdata   :        out    std_logic_vector(63 downto 0);
	axi4target_rid   :        out    std_logic_vector(0 downto 0);
	axi4target_rlast   :        out    std_logic;
	axi4target_rresp   :        out    std_logic_vector(1 downto 0);
	axi4target_ruser   :        out    std_logic_vector(0 downto 0);
	axi4target_awready   :        out    std_logic;
	axi4target_awvalid   :        in     std_logic;
	axi4target_awaddr   :        in     std_logic_vector(20-1 downto 0);
	axi4target_awid   :        in     std_logic_vector(0 downto 0);
	axi4target_awburst   :        in     std_logic_vector(1 downto 0);
	axi4target_awlen   :        in     std_logic_vector(7 downto 0);
	axi4target_awsize   :        in     std_logic_vector(2 downto 0);
	axi4target_awcache   :        in     std_logic_vector(3 downto 0);
	axi4target_awlock   :        in     std_logic_vector(1 downto 0);
	axi4target_awprot   :        in     std_logic_vector(2 downto 0);
	axi4target_awqos   :        in     std_logic_vector(3 downto 0);
	axi4target_awregion   :        in     std_logic_vector(3 downto 0);
	axi4target_awuser   :        in     std_logic_vector(0 downto 0);
	axi4target_wready   :        out    std_logic;
	axi4target_wvalid   :        in     std_logic;
	axi4target_wdata   :        in     std_logic_vector(63 downto 0);
	axi4target_wlast   :        in     std_logic;
	axi4target_wstrb   :        in     std_logic_vector(7 downto 0);
	axi4target_wuser   :        in     std_logic_vector(0 downto 0);
	axi4target_bvalid   :        out    std_logic;
	axi4target_bready   :        in     std_logic;
	axi4target_bid   :        out    std_logic_vector(0 downto 0);
	axi4target_bresp   :        out    std_logic_vector(1 downto 0);
	axi4target_buser   :        out    std_logic_vector(0 downto 0)
);

-- Put your code here ...

end tinyml_accel_top_vhdl;

architecture behavior of tinyml_accel_top_vhdl is

component tinyml_accel_top is
port (
	clk   :        in     std_logic;
	reset   :        in     std_logic;
	axi4target_arready   :        out    std_logic;
	axi4target_arvalid   :        in     std_logic;
	axi4target_araddr   :        in     std_logic_vector(20-1 downto 0);
	axi4target_arid   :        in     std_logic_vector(0 downto 0);
	axi4target_arburst   :        in     std_logic_vector(1 downto 0);
	axi4target_arlen   :        in     std_logic_vector(7 downto 0);
	axi4target_arsize   :        in     std_logic_vector(2 downto 0);
	axi4target_arcache   :        in     std_logic_vector(3 downto 0);
	axi4target_arlock   :        in     std_logic_vector(1 downto 0);
	axi4target_arprot   :        in     std_logic_vector(2 downto 0);
	axi4target_arqos   :        in     std_logic_vector(3 downto 0);
	axi4target_arregion   :        in     std_logic_vector(3 downto 0);
	axi4target_aruser   :        in     std_logic_vector(0 downto 0);
	axi4target_rready   :        in    std_logic;
	axi4target_rvalid   :        out    std_logic;
	axi4target_rdata   :        out    std_logic_vector(63 downto 0);
	axi4target_rid   :        out    std_logic_vector(0 downto 0);
	axi4target_rlast   :        out    std_logic;
	axi4target_rresp   :        out    std_logic_vector(1 downto 0);
	axi4target_ruser   :        out    std_logic_vector(0 downto 0);
	axi4target_awready   :        out    std_logic;
	axi4target_awvalid   :        in     std_logic;
	axi4target_awaddr   :        in     std_logic_vector(20-1 downto 0);
	axi4target_awid   :        in     std_logic_vector(0 downto 0);
	axi4target_awburst   :        in     std_logic_vector(1 downto 0);
	axi4target_awlen   :        in     std_logic_vector(7 downto 0);
	axi4target_awsize   :        in     std_logic_vector(2 downto 0);
	axi4target_awcache   :        in     std_logic_vector(3 downto 0);
	axi4target_awlock   :        in     std_logic_vector(1 downto 0);
	axi4target_awprot   :        in     std_logic_vector(2 downto 0);
	axi4target_awqos   :        in     std_logic_vector(3 downto 0);
	axi4target_awregion   :        in     std_logic_vector(3 downto 0);
	axi4target_awuser   :        in     std_logic_vector(0 downto 0);
	axi4target_wready   :        out    std_logic;
	axi4target_wvalid   :        in     std_logic;
	axi4target_wdata   :        in     std_logic_vector(63 downto 0);
	axi4target_wlast   :        in     std_logic;
	axi4target_wstrb   :        in     std_logic_vector(7 downto 0);
	axi4target_wuser   :        in     std_logic_vector(0 downto 0);
	axi4target_bvalid   :        out    std_logic;
	axi4target_bready   :        in     std_logic;
	axi4target_bid   :        out    std_logic_vector(0 downto 0);
	axi4target_bresp   :        out    std_logic_vector(1 downto 0);
	axi4target_buser   :        out    std_logic_vector(0 downto 0)
);
end component;

begin


tinyml_accel_top_inst : tinyml_accel_top
port map (
	clk   =>       clk,
	reset   =>       reset,
	axi4target_arready   =>       axi4target_arready,
	axi4target_arvalid   =>       axi4target_arvalid,
	axi4target_araddr   =>       axi4target_araddr,
	axi4target_arid   =>       axi4target_arid,
	axi4target_arburst   =>       axi4target_arburst,
	axi4target_arlen   =>       axi4target_arlen,
	axi4target_arsize   =>       axi4target_arsize,
	axi4target_arcache   =>       axi4target_arcache,
	axi4target_arlock   =>       axi4target_arlock,
	axi4target_arprot   =>       axi4target_arprot,
	axi4target_arqos   =>       axi4target_arqos,
	axi4target_arregion   =>       axi4target_arregion,
	axi4target_aruser   =>       axi4target_aruser,
	axi4target_rready   =>       axi4target_rready,
	axi4target_rvalid   =>       axi4target_rvalid,
	axi4target_rdata   =>       axi4target_rdata,
	axi4target_rid   =>       axi4target_rid,
	axi4target_rlast   =>       axi4target_rlast,
	axi4target_rresp   =>       axi4target_rresp,
	axi4target_ruser   =>       axi4target_ruser,
	axi4target_awready   =>       axi4target_awready,
	axi4target_awvalid   =>       axi4target_awvalid,
	axi4target_awaddr   =>       axi4target_awaddr,
	axi4target_awid   =>       axi4target_awid,
	axi4target_awburst   =>       axi4target_awburst,
	axi4target_awlen   =>       axi4target_awlen,
	axi4target_awsize   =>       axi4target_awsize,
	axi4target_awcache   =>       axi4target_awcache,
	axi4target_awlock   =>       axi4target_awlock,
	axi4target_awprot   =>       axi4target_awprot,
	axi4target_awqos   =>       axi4target_awqos,
	axi4target_awregion   =>       axi4target_awregion,
	axi4target_awuser   =>       axi4target_awuser,
	axi4target_wready   =>       axi4target_wready,
	axi4target_wvalid   =>       axi4target_wvalid,
	axi4target_wdata   =>       axi4target_wdata,
	axi4target_wlast   =>       axi4target_wlast,
	axi4target_wstrb   =>       axi4target_wstrb,
	axi4target_wuser   =>       axi4target_wuser,
	axi4target_bvalid   =>       axi4target_bvalid,
	axi4target_bready   =>       axi4target_bready,
	axi4target_bid   =>       axi4target_bid,
	axi4target_bresp   =>       axi4target_bresp,
	axi4target_buser   =>       axi4target_buser
);

end behavior;
