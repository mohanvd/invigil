#include "nrf_scan.h"

#include <stdio.h>

#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "pico/stdlib.h"

#include "config.h"
#include "nrf24.h"

// The radio needs up to 100 ms after power-on before it takes commands
// (power on reset, nRF24L01+ Product Specification).
#define NRF_POWER_ON_RESET_US 100000

static spectrum_t window;
static uint8_t last_sweep[SPECTRUM_CHANNELS];

static void hal_transfer(void *ctx, const uint8_t *tx, uint8_t *rx, size_t len) {
    (void)ctx;
    gpio_put(NRF_PIN_CSN, 0);
    spi_write_read_blocking(NRF_SPI, tx, rx, len);
    gpio_put(NRF_PIN_CSN, 1);
}

static void hal_set_ce(void *ctx, bool high) {
    (void)ctx;
    gpio_put(NRF_PIN_CE, high);
}

static void hal_delay_us(void *ctx, uint32_t us) {
    (void)ctx;
    busy_wait_us_32(us);
}

static const nrf24_hal_t hal = {NULL, hal_transfer, hal_set_ce, hal_delay_us};

bool nrf_scan_init(void) {
    spi_init(NRF_SPI, NRF_SPI_HZ);
    spi_set_format(NRF_SPI, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
    gpio_set_function(NRF_PIN_SCK, GPIO_FUNC_SPI);
    gpio_set_function(NRF_PIN_MOSI, GPIO_FUNC_SPI);
    gpio_set_function(NRF_PIN_MISO, GPIO_FUNC_SPI);
    // A missing radio then reads as 0xFF instead of floating.
    gpio_pull_up(NRF_PIN_MISO);

    gpio_init(NRF_PIN_CSN);
    gpio_set_dir(NRF_PIN_CSN, GPIO_OUT);
    gpio_put(NRF_PIN_CSN, 1);
    gpio_init(NRF_PIN_CE);
    gpio_set_dir(NRF_PIN_CE, GPIO_OUT);
    gpio_put(NRF_PIN_CE, 0);

    sleep_until(from_us_since_boot(NRF_POWER_ON_RESET_US));

    if (!nrf24_probe(&hal)) {
        printf("  FAIL  nRF24L01: no answer on SPI0 (register read-back failed). Check wiring and power.\n"
               "        BLE keeps running, no spectrum messages will be sent\n");
        return false;
    }
    if (!nrf24_start_rx(&hal)) {
        printf("  FAIL  nRF24L01: answered, but RX settings did not stick\n"
               "        BLE keeps running, no spectrum messages will be sent\n");
        return false;
    }
    printf("  PASS  nRF24L01: answers on SPI0 at %d kHz, RX mode, auto-ack off\n", NRF_SPI_HZ / 1000);
    return true;
}

void nrf_scan_begin_window(void) {
    spectrum_reset(&window);
}

uint32_t nrf_scan_sweep(void) {
    uint64_t start = time_us_64();
    nrf24_sweep(&hal, last_sweep);
    return (uint32_t)(time_us_64() - start);
}

void nrf_scan_keep_sweep(void) {
    spectrum_add_sweep(&window, last_sweep);
}

void nrf_scan_end_window(void) {
    nrf24_standby(&hal);
    nrf24_flush_rx(&hal);
}

const spectrum_t *nrf_scan_window(void) {
    return &window;
}
