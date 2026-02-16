#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string>
#include <sys/time.h>

#include "hls/ap_int.hpp"
#include "hls/hls_alloc.h"

#define N_SAMPLES 256
#define N_FEATURES 32
#define N_HIDDEN 12
#define N_CLASSES 6
#define INPUT_AMP 512

static const int8_t W1_POS[N_CLASSES][N_FEATURES] = {
    {-57, -21, 16, 53, 57, 21, -16, -53, -57, -21, 16, 53, 57, 21, -16, -53,
     -57, -21, 16, 53, 57, 21, -16, -53, -57, -21, 16, 53, 57, 21, -16, -53},
    {-70, 22, 49, -6, -13, 42, 33, -58, -70, 22, 49, -6, -13, 42, 33, -58,
     -70, 22, 49, -6, -13, 42, 33, -58, -70, 22, 49, -6, -13, 42, 33, -58},
    {-29, -83, -65, -47, 29, -63, -81, -99, -29, -83, -65, -47, 29, -63, -81, -99,
     -29, -83, -65, -47, 29, -63, -81, -99, -29, -83, -65, -47, 29, -63, -81, -99},
    {73, 73, -73, -73, 73, 73, -73, -73, 73, 73, -73, -73, 73, 73, -73, -73,
     73, 73, -73, -73, 73, 73, -73, -73, 73, 73, -73, -73, 73, 73, -73, -73},
    {-57, -21, 16, 53, 57, 21, -16, -53, -18, -30, 49, -18, -30, 49, -18, -30,
     7, -16, -7, 16, 7, -16, -7, 16, -12, 12, 0, -12, 12, 0, -12, 12},
    {6, -102, 6, -102, 6, -102, 6, -102, 6, -102, 6, -102, 6, -102, 6, -102,
     6, -102, 6, -102, 6, -102, 6, -102, 6, -102, 6, -102, 6, -102, 6, -102}};

static inline int16_t clamp_int16(int32_t x) {
    if (x > 32767) return 32767;
    if (x < -32768) return -32768;
    return (int16_t)x;
}

static inline int16_t tri_wave(int i, int period, int amp) {
    int t = i % period;
    int half = period / 2;
    int v = (t < half) ? t : (period - t);
    int centered = (v * 2) - half;
    return (int16_t)((centered * amp) / half);
}

static inline int16_t square_wave(int i, int period, int amp) {
    return ((i % period) < (period / 2)) ? (int16_t)amp : (int16_t)(-amp);
}

static inline int16_t chirp_wave(int i, int amp) {
    int seg = i >> 6;
    int period = (seg == 0) ? 64 : ((seg == 1) ? 48 : ((seg == 2) ? 32 : 24));
    return tri_wave(i * (seg + 1), period, amp);
}

static inline int16_t impulse_train(int i, int stride, int amp) {
    int m = i % stride;
    if (m == 0) return (int16_t)amp;
    if (m == (stride / 2)) return (int16_t)(-amp);
    return (int16_t)(-amp / 8);
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
                base = (int16_t)(tri_wave(i, 64, INPUT_AMP / 2) + tri_wave(i, 32, INPUT_AMP));
                break;
            case 2: {
                int16_t slow = tri_wave(i, 64, INPUT_AMP / 2);
                int16_t burst = ((i % 32) < 4) ? INPUT_AMP : (int16_t)(-INPUT_AMP);
                base = (int16_t)(slow + burst);
                break;
            }
            case 3:
                base = square_wave(i, 32, INPUT_AMP);
                break;
            case 4:
                base = chirp_wave(i, INPUT_AMP);
                break;
            case 5:
                base = impulse_train(i, 16, INPUT_AMP);
                break;
            default:
                base = 0;
                break;
        }

        uint32_t r = lcg_next(&seed);
        int16_t noise = (int16_t)((int32_t)((r >> 16) & 0xFF) - 128);
        out[i] = clamp_int16((int32_t)base + (int32_t)noise);
    }
}

static void extract_features(const int16_t *in, int16_t *feat) {
    for (int b = 0; b < N_FEATURES; ++b) {
        int32_t sum = 0;
        for (int i = 0; i < 8; ++i) {
            sum += in[(b << 3) + i];
        }
        feat[b] = (int16_t)(sum >> 3);
    }
}

void tinyml_accel(const int16_t *in, int32_t *out) {
#pragma HLS function top
#pragma HLS interface default type(axi_target)
#pragma HLS interface argument(in) type(axi_target) num_elements(N_SAMPLES)
#pragma HLS interface argument(out) type(axi_target) num_elements(N_CLASSES)

    int16_t feat[N_FEATURES];
    int32_t hidden[N_HIDDEN];

    extract_features(in, feat);

    // Layer 1: projection against six learned templates, with pos/neg ReLU split.
    for (int c = 0; c < N_CLASSES; ++c) {
        int32_t sum = 0;
#pragma HLS loop pipeline II(1)
        for (int i = 0; i < N_FEATURES; ++i) {
            sum += (int32_t)feat[i] * (int32_t)W1_POS[c][i];
        }
        hidden[c] = (sum > 0) ? sum : 0;
        hidden[c + N_CLASSES] = (sum < 0) ? -sum : 0;
    }

    // Layer 2: linear classifier on hidden activations.
    for (int c = 0; c < N_CLASSES; ++c) {
        int32_t score = (hidden[c] << 6) - (hidden[c + N_CLASSES] << 6);
        for (int k = 0; k < N_CLASSES; ++k) {
            if (k != c) score -= (hidden[k] << 3);
        }
        out[c] = score;
    }
}

#ifdef HAS_ACCELERATOR
std::string mode = "hw";
#else
std::string mode = "sw";
#endif

static int argmaxN(const int32_t *scores) {
    int idx = 0;
    for (int i = 1; i < N_CLASSES; ++i) {
        if (scores[i] > scores[idx]) idx = i;
    }
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

    int pred = argmaxN(output);

    printf("Tiny-NN demo (%s): input_class=%d pred=%d time=%f s\n", mode.c_str(), cls, pred, t1 - t0);
    printf("Scores: [");
    for (int i = 0; i < N_CLASSES; ++i) {
        if (i) printf(", ");
        printf("%" PRId32, output[i]);
    }
    printf("]\n");

    hls_free(input);
    hls_free(output);
    return 0;
}
