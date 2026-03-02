#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string>
#include <sys/time.h>

#include "hls/ap_int.hpp"
#include "hls/hls_alloc.h"

#define N_SAMPLES 256
#define N_CLASSES 3
#define INPUT_AMP 512
#define TEMPLATE_AMP 64

static inline int16_t clamp_int16(int32_t x) {
    if (x > 32767) return 32767;
    if (x < -32768) return -32768;
    return (int16_t)x;
}

static inline int16_t tri_wave(int i, int period, int amp) {
    int t = i % period;
    int half = period / 2;
    int v = (t < half) ? t : (period - t);
    int centered = (v * 2) - half; // range [-half, half]
    return (int16_t)((centered * amp) / half);
}

static inline int16_t template_wave(int i, int cls) {
    switch (cls) {
        case 0:
            return tri_wave(i, 64, TEMPLATE_AMP);
        case 1:
            return (int16_t)(tri_wave(i, 64, TEMPLATE_AMP / 2) +
                             tri_wave(i, 32, TEMPLATE_AMP));
        case 2: {
            int16_t base = tri_wave(i, 64, TEMPLATE_AMP / 2);
            int16_t burst = ((i % 32) < 4) ? TEMPLATE_AMP : (int16_t)(-TEMPLATE_AMP);
            return (int16_t)(base + burst);
        }
        default:
            return 0;
    }
}

static inline uint32_t lcg_next(uint32_t *state) {
    *state = (*state * 1103515245u) + 12345u;
    return *state;
}

static void gen_signal(int16_t *out, int cls, uint32_t seed) {
    for (int i = 0; i < N_SAMPLES; ++i) {
        int16_t base;
        switch (cls) {
            case 0:
                base = tri_wave(i, 64, INPUT_AMP);
                break;
            case 1:
                base = (int16_t)(tri_wave(i, 64, INPUT_AMP / 2) +
                                 tri_wave(i, 32, INPUT_AMP));
                break;
            case 2: {
                int16_t slow = tri_wave(i, 64, INPUT_AMP / 2);
                int16_t burst = ((i % 32) < 4) ? INPUT_AMP : (int16_t)(-INPUT_AMP);
                base = (int16_t)(slow + burst);
                break;
            }
            default:
                base = 0;
                break;
        }

        uint32_t r = lcg_next(&seed);
        int16_t noise = (int16_t)((int32_t)((r >> 16) & 0xFF) - 128);
        out[i] = clamp_int16((int32_t)base + (int32_t)noise);
    }
}

void tinyml_accel(const int16_t *in, int32_t *out) {
#pragma HLS function top
#pragma HLS interface default type(axi_target)
#pragma HLS interface argument(in) type(axi_target) num_elements(N_SAMPLES)
#pragma HLS interface argument(out) type(axi_target) num_elements(N_CLASSES)

    int32_t acc0 = 0;
    int32_t acc1 = 0;
    int32_t acc2 = 0;

#pragma HLS loop pipeline II(1)
    for (int i = 0; i < N_SAMPLES; ++i) {
        int16_t x = in[i];
        acc0 += (int32_t)x * (int32_t)template_wave(i, 0);
        acc1 += (int32_t)x * (int32_t)template_wave(i, 1);
        acc2 += (int32_t)x * (int32_t)template_wave(i, 2);
    }

    out[0] = acc0;
    out[1] = acc1;
    out[2] = acc2;
}

#ifdef HAS_ACCELERATOR
std::string mode = "hw";
#else
std::string mode = "sw";
#endif

static int argmax3(const int32_t *scores) {
    int idx = 0;
    if (scores[1] > scores[idx]) idx = 1;
    if (scores[2] > scores[idx]) idx = 2;
    return idx;
}

static double timestamp() {
    struct timeval tp;
    int stat = gettimeofday(&tp, NULL);
    if (stat != 0) {
        printf("Error return from gettimeofday: %d\n", stat);
        return 0.0;
    }
    return (tp.tv_sec + tp.tv_usec * 1.0e-6);
}

int main(int argc, char **argv) {
    int cls = 0;
    uint32_t seed = 1;

    if (argc > 1) cls = atoi(argv[1]);
    if (argc > 2) seed = (uint32_t)atoi(argv[2]);
    if (cls < 0) cls = 0;
    if (cls >= N_CLASSES) cls = N_CLASSES - 1;

    int16_t *input = (int16_t *)hls_malloc(sizeof(int16_t) * N_SAMPLES, HLS_ALLOC_CACHED);
    int32_t *output = (int32_t *)hls_malloc(sizeof(int32_t) * N_CLASSES, HLS_ALLOC_CACHED);
    if (!input || !output) {
        printf("Allocation failed\n");
        return -1;
    }

    gen_signal(input, cls, seed);

    double t0 = timestamp();
    tinyml_accel(input, output);
    double t1 = timestamp();

    int pred = argmax3(output);

    printf("Tiny-ML demo (%s): input_class=%d pred=%d time=%f s\n",
           mode.c_str(), cls, pred, t1 - t0);
    printf("Scores: [%" PRId32 ", %" PRId32 ", %" PRId32 "]\n",
           output[0], output[1], output[2]);

    hls_free(input);
    hls_free(output);
    return 0;
}
