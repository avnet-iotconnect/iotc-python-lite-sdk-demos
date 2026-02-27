#ifndef _TINYML_COMPLEX_ACCELERATOR_DRIVER_H
#define _TINYML_COMPLEX_ACCELERATOR_DRIVER_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "tinyml_complex_memory_map.h"



void* tinyml_accel_setup(uint32_t base_addr = TINYML_ACCEL_BASE_ADDR);
void tinyml_accel_teardown();


void tinyml_accel_memcpy_write_in(void* in, uint64_t byte_size, void *virt_addr);
void tinyml_accel_memcpy_read_in(void* in, uint64_t byte_size, void *virt_addr);
void tinyml_accel_dma_write_in(void* in, uint64_t byte_size, void *virt_addr);
void tinyml_accel_dma_read_in(void* in, uint64_t byte_size, void *virt_addr);

void tinyml_accel_memcpy_write_out(void* out, uint64_t byte_size, void *virt_addr);
void tinyml_accel_memcpy_read_out(void* out, uint64_t byte_size, void *virt_addr);
void tinyml_accel_dma_write_out(void* out, uint64_t byte_size, void *virt_addr);
void tinyml_accel_dma_read_out(void* out, uint64_t byte_size, void *virt_addr);

void tinyml_accel_write_batch_n(uint32_t val,  void *virt_addr);
uint32_t tinyml_accel_read_batch_n(void *virt_addr);

int tinyml_accel_is_idle(void *virt_addr);

void tinyml_accel_start(void *virt_addr);

void tinyml_accel_join(void *virt_addr);


void tinyml_accel_hls_driver(void* in, void* out, uint32_t batch_n, uint32_t base_addr = TINYML_ACCEL_BASE_ADDR);

void tinyml_accel_write_input_and_start(void* in, uint32_t batch_n, void *virt_addr);

void tinyml_accel_join_and_read_output(void* out, void *virt_addr);

#ifdef __cplusplus
}
#endif

#endif
