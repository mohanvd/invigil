// Receive-only nRF24L01+ driver for the channel sweep.
//
// The radio is only ever a receiver. This driver has no code for any transmit
// command (W_TX_PAYLOAD, W_TX_PAYLOAD_NO_ACK, W_ACK_PAYLOAD, REUSE_TX_PL),
// and every register write goes through an allow-list that refuses a value
// that would leave RX mode, turn auto-ack on, or start the carrier test mode.
// The host tests record every SPI byte to prove it.
//
// Register and timing values are from the nRF24L01+ Product Specification v1.0.

#ifndef INVIGIL_NRF24_H
#define INVIGIL_NRF24_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "spectrum.h"

// Wait after CE goes high before RPD is valid: 130 us RX settling (Tstby2a)
// plus 40 us for the received power detector (section 6.4).
#define NRF24_RPD_WAIT_US 170
// Power down to standby: 1.5 ms with a typical crystal, up to 4.5 ms (Tpd2stby).
#define NRF24_POWER_UP_US 5000

// Registers
#define NRF24_REG_CONFIG 0x00
#define NRF24_REG_EN_AA 0x01
#define NRF24_REG_RF_CH 0x05
#define NRF24_REG_RF_SETUP 0x06
#define NRF24_REG_STATUS 0x07
#define NRF24_REG_RPD 0x09

// CONFIG bits
#define NRF24_MASK_RX_DR 0x40
#define NRF24_MASK_TX_DS 0x20
#define NRF24_MASK_MAX_RT 0x10
#define NRF24_PWR_UP 0x02
#define NRF24_PRIM_RX 0x01

// RF_SETUP bits that must never be set: CONT_WAVE makes the chip transmit a
// constant carrier, PLL_LOCK is a test mode that goes with it.
#define NRF24_CONT_WAVE 0x80
#define NRF24_PLL_LOCK 0x10

// STATUS interrupt flags, cleared by writing 1.
#define NRF24_STATUS_FLAGS 0x70

// Commands. Only these four are ever sent.
#define NRF24_CMD_R_REGISTER 0x00
#define NRF24_CMD_W_REGISTER 0x20
#define NRF24_CMD_FLUSH_RX 0xE2
#define NRF24_CMD_NOP 0xFF

// RX mode with all three interrupts masked (IRQ is not connected) and CRC off.
#define NRF24_CONFIG_RX (NRF24_MASK_RX_DR | NRF24_MASK_TX_DS | NRF24_MASK_MAX_RT | NRF24_PWR_UP | NRF24_PRIM_RX)
// 1 Mbps, so the receive filter is about 1 MHz wide and each channel reads
// its own 1 MHz. RF_PWR is the lowest setting; it only matters for transmit,
// which never happens.
#define NRF24_RF_SETUP_RX 0x00

// Hardware access. The unit implements it with the Pico SDK, the tests with a fake.
typedef struct {
    void *ctx;
    // One SPI transaction: CSN low, len bytes out and in at the same time, CSN high.
    void (*transfer)(void *ctx, const uint8_t *tx, uint8_t *rx, size_t len);
    void (*set_ce)(void *ctx, bool high);
    void (*delay_us)(void *ctx, uint32_t us);
} nrf24_hal_t;

// Writes two test patterns to RF_CH and reads them back. False if the radio
// does not answer (not wired, no power, wrong pins). Leaves CE low.
bool nrf24_probe(const nrf24_hal_t *hal);

// Powers up in RX mode with auto-ack off, then reads the settings back.
// False if they did not stick. Leaves CE low (standby).
bool nrf24_start_rx(const nrf24_hal_t *hal);

// Reads one channel (0..125): CE low, set RF_CH, CE high, wait
// NRF24_RPD_WAIT_US, read RPD, CE low. True if a carrier was above the
// RPD threshold.
bool nrf24_carrier(const nrf24_hal_t *hal, uint8_t channel);

// Reads all channels 0..125 in order. rpd[c] is 1 if channel c had a carrier.
void nrf24_sweep(const nrf24_hal_t *hal, uint8_t rpd[SPECTRUM_CHANNELS]);

// Drops anything in the RX FIFO without reading it. Payloads are never read.
void nrf24_flush_rx(const nrf24_hal_t *hal);

// CE low: standby, not listening.
void nrf24_standby(const nrf24_hal_t *hal);

// The register write allow-list, exposed for the tests. True if the write is
// one this driver may make.
bool nrf24_write_allowed(uint8_t reg, uint8_t value);

#endif
