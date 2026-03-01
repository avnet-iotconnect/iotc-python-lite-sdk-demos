#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string>
#include <sys/time.h>

#include "hls/hls_alloc.h"

#define N_CLASSES 6
#define N_SAMPLES 256
#define N_FEATURES 64
#define N_HIDDEN1 96
#define N_HIDDEN2 48
#define INPUT_AMP 640
#define MAX_BATCH 1024

#include "model_weights.h"

static inline int16_t clamp_int16(int32_t x) {
    if (x > 32767) return 32767;
    if (x < -32768) return -32768;
    return (int16_t)x;
}

static inline int32_t iabs32(int32_t x) {
    return (x < 0) ? -x : x;
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

static inline int16_t saw_wave(int i, int period, int amp) {
    int t = i % period;
    int centered = (t * 2) - period;
    return (int16_t)((centered * amp) / period);
}

static inline int16_t ring_wave(int i, int amp, int decay_shift) {
    int seg = i >> 5;
    int env = amp >> ((seg > 7) ? 7 : seg);
    env = env >> decay_shift;
    return tri_wave(i * ((seg & 1) ? 3 : 2), 32, env);
}

static inline uint32_t lcg_next(uint32_t *state) {
    *state = (*state * 1664525u) + 1013904223u;
    return *state;
}

static void gen_signal(int16_t *out, int cls, uint32_t seed) {
    for (int i = 0; i < N_SAMPLES; ++i) {
        int32_t base = 0;
        switch (cls) {
            case 0:
                base = tri_wave(i, 64, INPUT_AMP) + tri_wave(i, 16, INPUT_AMP / 6);
                break;
            case 1:
                base = square_wave(i, 32, INPUT_AMP / 2) + tri_wave(i, 48, INPUT_AMP / 2);
                break;
            case 2:
                base = tri_wave(i, 40, INPUT_AMP / 2) + saw_wave(i * 3, 64, INPUT_AMP / 2);
                break;
            case 3: {
                int burst = ((i % 64) < 12) ? INPUT_AMP : -(INPUT_AMP / 3);
                base = burst + tri_wave(i, 24, INPUT_AMP / 3);
                break;
            }
            case 4:
                base = ring_wave(i, INPUT_AMP, 1) + tri_wave(i * 5, 32, INPUT_AMP / 4);
                break;
            case 5:
                base = ((i % 16) == 0) ? INPUT_AMP : ((i % 16) == 8 ? -INPUT_AMP : -(INPUT_AMP / 8));
                base += saw_wave(i, 128, INPUT_AMP / 4);
                break;
            default:
                base = 0;
                break;
        }

        uint32_t r = lcg_next(&seed);
        int32_t noise = ((int32_t)((r >> 16) & 0xFF) - 128) * 2;
        out[i] = clamp_int16(base + noise);
    }
}

static void extract_features(const int16_t *in, int16_t *feat) {
    for (int f = 0; f < N_FEATURES; ++f) {
        int base = f << 2;
        int32_t x0 = in[base + 0];
        int32_t x1 = in[base + 1];
        int32_t x2 = in[base + 2];
        int32_t x3 = in[base + 3];

        int32_t low = (x0 + x1 + x2 + x3) >> 2;
        int32_t high = ((x3 - x0) + (x2 - x1)) >> 1;
        int32_t grad = ((x3 + x2) - (x1 + x0));
        int32_t energy = (iabs32(x0) + iabs32(x1) + iabs32(x2) + iabs32(x3)) >> 2;

        int32_t y = 0;
        switch (f & 3) {
            case 0:
                y = low;
                break;
            case 1:
                y = high;
                break;
            case 2:
                y = grad;
                break;
            default:
                y = energy - 192;
                break;
        }
        feat[f] = clamp_int16(y);
    }
}

static void tinyml_accel_single(const int16_t *in, int32_t *out) {

    int16_t feat[N_FEATURES];
    int32_t h1[N_HIDDEN1];
    int32_t h2[N_HIDDEN2];

    extract_features(in, feat);

    for (int h = 0; h < N_HIDDEN1; ++h) {
        int32_t acc = ((int32_t)B1[h]) << BIAS_PRE_SHIFT;
#pragma HLS loop pipeline II(1)
        for (int i = 0; i < N_FEATURES; ++i) {
            acc += (int32_t)feat[i] * (int32_t)W1[h][i];
        }
        acc >>= L1_ACC_SHIFT;
        h1[h] = (acc > 0) ? acc : 0;
    }

    for (int h = 0; h < N_HIDDEN2; ++h) {
        int32_t acc = ((int32_t)B2[h]) << BIAS_PRE_SHIFT;
#pragma HLS loop pipeline II(1)
        for (int i = 0; i < N_HIDDEN1; ++i) {
            int32_t x = h1[i] >> L2_INPUT_SHIFT;
            acc += x * (int32_t)W2[h][i];
        }
        acc >>= L2_ACC_SHIFT;
        h2[h] = (acc > 0) ? acc : 0;
    }

    for (int c = 0; c < N_CLASSES; ++c) {
        int32_t acc = ((int32_t)B3[c]) << BIAS_PRE_SHIFT;
#pragma HLS loop pipeline II(1)
        for (int i = 0; i < N_HIDDEN2; ++i) {
            int32_t x = h2[i] >> L3_INPUT_SHIFT;
            acc += x * (int32_t)W3[c][i];
        }
        out[c] = acc;
    }
}

void tinyml_accel(const int16_t *in, int32_t *out, int batch_n) {
#pragma HLS function top
#pragma HLS interface default type(axi_target)
#pragma HLS interface argument(in) type(axi_target) dma(true) num_elements(N_SAMPLES * MAX_BATCH)
#pragma HLS interface argument(out) type(axi_target) dma(true) num_elements(N_CLASSES * MAX_BATCH)

    int n = batch_n;
    if (n < 1) n = 1;
    if (n > MAX_BATCH) n = MAX_BATCH;

    for (int b = 0; b < n; ++b) {
        tinyml_accel_single(in + (b * N_SAMPLES), out + (b * N_CLASSES));
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
    int batch_n = 1;

    if (argc > 1) cls = atoi(argv[1]);
    if (argc > 2) seed = (uint32_t)atoi(argv[2]);
    if (argc > 3) batch_n = atoi(argv[3]);
    if (cls < 0) cls = 0;
    if (cls >= N_CLASSES) cls = N_CLASSES - 1;
    if (batch_n < 1) batch_n = 1;
    if (batch_n > MAX_BATCH) batch_n = MAX_BATCH;

#ifdef HAS_ACCELERATOR
    hls_alloc_memory_type_t alloc_policy = HLS_ALLOC_NONCACHED;
#else
    hls_alloc_memory_type_t alloc_policy = HLS_ALLOC_CACHED;
#endif

    // DMA interfaces are declared with MAX_BATCH element counts, so allocate full
    // backing buffers from hls_malloc regardless of the requested runtime batch.
    int16_t *input = (int16_t *)hls_malloc(sizeof(int16_t) * N_SAMPLES * MAX_BATCH, alloc_policy);
    int32_t *output = (int32_t *)hls_malloc(sizeof(int32_t) * N_CLASSES * MAX_BATCH, alloc_policy);
    if (!input || !output) {
        printf("Allocation failed\n");
        return -1;
    }

    for (int b = 0; b < batch_n; ++b) {
        gen_signal(input + (b * N_SAMPLES), cls, seed + (uint32_t)b);
    }

    double t0 = timestamp();
    tinyml_accel(input, output, batch_n);
    double t1 = timestamp();
    double total_time = t1 - t0;
    double avg_time = total_time / (double)batch_n;

    int hist[N_CLASSES] = {0};
    int64_t score_sum[N_CLASSES] = {0};
    int match_count = 0;

    for (int b = 0; b < batch_n; ++b) {
        int32_t *scores = output + (b * N_CLASSES);
        int pred = argmaxN(scores);
        hist[pred]++;
        if (pred == cls) {
            match_count++;
        }
        for (int c = 0; c < N_CLASSES; ++c) {
            score_sum[c] += scores[c];
        }
    }

    int pred_mode = 0;
    for (int c = 1; c < N_CLASSES; ++c) {
        if (hist[c] > hist[pred_mode]) pred_mode = c;
    }

    int32_t avg_scores[N_CLASSES];
    for (int c = 0; c < N_CLASSES; ++c) {
        avg_scores[c] = (int32_t)(score_sum[c] / batch_n);
    }

    printf("Tiny-Complex demo (%s): input_class=%d pred=%d time=%f s\n", mode.c_str(), cls, pred_mode, avg_time);
    printf("Scores: [");
    for (int i = 0; i < N_CLASSES; ++i) {
        if (i) printf(", ");
        printf("%" PRId32, avg_scores[i]);
    }
    printf("]\n");
    printf(
        "Batch: n=%d mode_count=%d match_count=%d match_rate=%.6f total_time=%f avg_time=%f\n",
        batch_n,
        hist[pred_mode],
        match_count,
        (double)match_count / (double)batch_n,
        total_time,
        avg_time
    );

    hls_free(input);
    hls_free(output);
    return 0;
}
