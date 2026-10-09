#include "nrf24.h"

bool nrf24_write_allowed(uint8_t reg, uint8_t value) {
    switch (reg) {
    case NRF24_REG_CONFIG:
        return (value & NRF24_PRIM_RX) != 0;  // never leave RX mode
    case NRF24_REG_EN_AA:
        return value == 0;  // auto-ack would make the radio answer packets
    case NRF24_REG_RF_CH:
        return value < SPECTRUM_CHANNELS;
    case NRF24_REG_RF_SETUP:
        return (value & (NRF24_CONT_WAVE | NRF24_PLL_LOCK)) == 0;
    case NRF24_REG_STATUS:
        return (value & ~NRF24_STATUS_FLAGS) == 0;  // only clears flags
    default:
        return false;
    }
}

static uint8_t read_reg(const nrf24_hal_t *hal, uint8_t reg) {
    uint8_t tx[2] = {(uint8_t)(NRF24_CMD_R_REGISTER | (reg & 0x1f)), NRF24_CMD_NOP};
    uint8_t rx[2] = {0, 0};
    hal->transfer(hal->ctx, tx, rx, 2);
    return rx[1];
}

static bool write_reg(const nrf24_hal_t *hal, uint8_t reg, uint8_t value) {
    if (!nrf24_write_allowed(reg, value)) {
        return false;
    }
    uint8_t tx[2] = {(uint8_t)(NRF24_CMD_W_REGISTER | (reg & 0x1f)), value};
    uint8_t rx[2];
    hal->transfer(hal->ctx, tx, rx, 2);
    return true;
}

bool nrf24_probe(const nrf24_hal_t *hal) {
    // A missing radio reads back as all ones (MISO pulled up or floating) or
    // all zeros, so test both bit patterns.
    static const uint8_t patterns[] = {0x55, 0x2a};
    hal->set_ce(hal->ctx, false);
    for (size_t i = 0; i < sizeof(patterns); i++) {
        write_reg(hal, NRF24_REG_RF_CH, patterns[i]);
        if (read_reg(hal, NRF24_REG_RF_CH) != patterns[i]) {
            return false;
        }
    }
    return true;
}

bool nrf24_start_rx(const nrf24_hal_t *hal) {
    hal->set_ce(hal->ctx, false);
    write_reg(hal, NRF24_REG_EN_AA, 0);
    write_reg(hal, NRF24_REG_RF_SETUP, NRF24_RF_SETUP_RX);
    write_reg(hal, NRF24_REG_RF_CH, 0);
    write_reg(hal, NRF24_REG_CONFIG, NRF24_CONFIG_RX);
    hal->delay_us(hal->ctx, NRF24_POWER_UP_US);
    nrf24_flush_rx(hal);
    write_reg(hal, NRF24_REG_STATUS, NRF24_STATUS_FLAGS);

    return read_reg(hal, NRF24_REG_CONFIG) == NRF24_CONFIG_RX &&
           read_reg(hal, NRF24_REG_EN_AA) == 0 &&
           read_reg(hal, NRF24_REG_RF_SETUP) == NRF24_RF_SETUP_RX;
}

bool nrf24_carrier(const nrf24_hal_t *hal, uint8_t channel) {
    hal->set_ce(hal->ctx, false);
    if (!write_reg(hal, NRF24_REG_RF_CH, channel)) {
        return false;
    }
    hal->set_ce(hal->ctx, true);
    hal->delay_us(hal->ctx, NRF24_RPD_WAIT_US);
    bool carrier = (read_reg(hal, NRF24_REG_RPD) & 0x01) != 0;
    hal->set_ce(hal->ctx, false);
    return carrier;
}

void nrf24_sweep(const nrf24_hal_t *hal, uint8_t rpd[SPECTRUM_CHANNELS]) {
    for (uint8_t c = 0; c < SPECTRUM_CHANNELS; c++) {
        rpd[c] = nrf24_carrier(hal, c) ? 1 : 0;
    }
}

void nrf24_flush_rx(const nrf24_hal_t *hal) {
    uint8_t tx = NRF24_CMD_FLUSH_RX;
    uint8_t rx;
    hal->transfer(hal->ctx, &tx, &rx, 1);
}

void nrf24_standby(const nrf24_hal_t *hal) {
    hal->set_ce(hal->ctx, false);
}
