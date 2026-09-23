/* MVM-Lite CPU backend (Hulk). Answers every query the switch misses by running the full tree.
 *
 * serve IFACE TREE.bin VISION_MAC SELF_MAC
 *     read mvm queries with flags=0 (switch misses), traverse the decision tree on CPU, set
 *     klass/leaf, flags=2, and send the answer back towards Vision (the switch forwards it).
 * bench TREE.bin QUERIES.bin EXPECTED.bin
 *     CPU baseline: classify every query in memory, check against the offline tree.predict,
 *     and report per-query latency and throughput.
 * Features arrive as order-preserving float32 keys; the backend decodes them and compares
 * (double)float32 <= threshold exactly as sklearn does, so answers equal tree.predict.
 * Build: gcc -O2 -o hulk_backend hulk_backend.c
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <linux/if_packet.h>
#include <net/ethernet.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define MVM_PORT 50000
#define N_FEAT 10
#define HDR_LEN 42
#define FEAT_OFF 16  /* qid 4, flags 1, klass 1, leaf 2, t_in 4, t_pipe 4 */
#define MVM_LEN (FEAT_OFF + 4 * N_FEAT)
#define MAX_BATCH 64

typedef struct { int32_t feature; double threshold; int32_t left, right, klass; } __attribute__((packed)) node_t;
static node_t *nodes;

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + ts.tv_nsec;
}

static float key_to_f32(uint32_t k) {
    uint32_t bits = (k & 0x80000000u) ? (k ^ 0x80000000u) : ~k;
    float f;
    memcpy(&f, &bits, 4);
    return f;
}

static int classify(const uint32_t *keys, int *leaf) {
    int n = 0;
    while (nodes[n].left != -1) {
        double x = (double)key_to_f32(keys[nodes[n].feature]);
        n = (x <= nodes[n].threshold) ? nodes[n].left : nodes[n].right;
    }
    *leaf = n;
    return nodes[n].klass;
}

static void load_tree(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror("tree"); exit(1); }
    int32_t n;
    if (fread(&n, 4, 1, f) != 1) exit(1);
    nodes = malloc(sizeof(node_t) * n);
    if (fread(nodes, sizeof(node_t), n, f) != (size_t)n) { fprintf(stderr, "short tree file\n"); exit(1); }
    fclose(f);
    fprintf(stderr, "tree: %d nodes\n", n);
}

static void parse_mac(const char *s, uint8_t *m) {
    sscanf(s, "%hhx:%hhx:%hhx:%hhx:%hhx:%hhx", &m[0], &m[1], &m[2], &m[3], &m[4], &m[5]);
}

static int bench(const char *qpath, const char *epath) {
    FILE *fq = fopen(qpath, "rb"), *fe = fopen(epath, "rb");
    if (!fq || !fe) { perror("open"); return 1; }
    fseek(fq, 0, SEEK_END); long sz = ftell(fq); fseek(fq, 0, SEEK_SET);
    uint32_t nq = sz / (4 * (1 + N_FEAT));
    uint32_t *q = malloc(sz), *e = malloc(8 * nq);
    if (fread(q, 1, sz, fq) != (size_t)sz || fread(e, 8, nq, fe) != nq) { fprintf(stderr, "short read\n"); return 1; }
    uint32_t mismatches = 0;
    volatile int sink = 0;
    uint64_t best = UINT64_MAX;
    for (int rep = 0; rep < 20; rep++) {
        uint64_t t0 = now_ns();
        for (uint32_t i = 0; i < nq; i++) {
            int leaf;
            int k = classify(q + (size_t)i * (1 + N_FEAT) + 1, &leaf);
            sink += k;
            if (rep == 0 && ((uint32_t)k != e[2 * i] || (uint32_t)leaf != e[2 * i + 1])) mismatches++;
        }
        uint64_t dt = now_ns() - t0;
        if (dt < best) best = dt;
    }
    printf("{\"queries\": %u, \"mismatches\": %u, \"best_total_ns\": %llu, \"ns_per_query\": %.2f, \"qps_one_core\": %.0f}\n",
           nq, mismatches, (unsigned long long)best, (double)best / nq, nq / (best / 1e9));
    return mismatches ? 3 : 0;
}

static int serve(const char *iface, const char *vmac, const char *smac) {
    uint8_t vision[6], self[6];
    parse_mac(vmac, vision); parse_mac(smac, self);
    int sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (sock < 0) { perror("socket"); return 1; }
    struct ifreq ifr; memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, iface, IFNAMSIZ - 1);
    if (ioctl(sock, SIOCGIFINDEX, &ifr) < 0) { perror("ifindex"); return 1; }
    struct sockaddr_ll sll; memset(&sll, 0, sizeof(sll));
    sll.sll_family = AF_PACKET; sll.sll_protocol = htons(ETH_P_ALL); sll.sll_ifindex = ifr.ifr_ifindex;
    if (bind(sock, (struct sockaddr *)&sll, sizeof(sll)) < 0) { perror("bind"); return 1; }
    struct packet_mreq mr; memset(&mr, 0, sizeof(mr));
    mr.mr_ifindex = ifr.ifr_ifindex; mr.mr_type = PACKET_MR_PROMISC;
    setsockopt(sock, SOL_PACKET, PACKET_ADD_MEMBERSHIP, &mr, sizeof(mr));
    int buf = 64 << 20;
    setsockopt(sock, SOL_SOCKET, SO_RCVBUFFORCE, &buf, sizeof(buf));

    static uint8_t bufs[MAX_BATCH][256];
    struct mmsghdr in[MAX_BATCH], out[MAX_BATCH];
    struct iovec iov[MAX_BATCH], oiov[MAX_BATCH];
    struct sockaddr_ll addrs[MAX_BATCH];
    uint64_t answered = 0, last_report = now_ns();
    fprintf(stderr, "serving on %s\n", iface);
    for (;;) {
        memset(in, 0, sizeof(in));
        for (int i = 0; i < MAX_BATCH; i++) {
            iov[i].iov_base = bufs[i]; iov[i].iov_len = sizeof(bufs[i]);
            in[i].msg_hdr.msg_iov = &iov[i]; in[i].msg_hdr.msg_iovlen = 1;
            in[i].msg_hdr.msg_name = &addrs[i]; in[i].msg_hdr.msg_namelen = sizeof(addrs[i]);
        }
        int got = recvmmsg(sock, in, MAX_BATCH, MSG_WAITFORONE, NULL);  /* return as soon as one arrives */
        if (got <= 0) continue;
        int n_out = 0;
        for (int i = 0; i < got; i++) {
            uint8_t *p = bufs[i];
            if (addrs[i].sll_pkttype == PACKET_OUTGOING || in[i].msg_len < HDR_LEN + MVM_LEN) continue;
            if (p[12] != 0x08 || p[13] != 0x00 || p[23] != 17 || ((p[36] << 8) | p[37]) != MVM_PORT) continue;
            uint8_t *m = p + HDR_LEN;
            if (m[4] != 0) continue;                         /* only switch misses */
            uint32_t keys[N_FEAT];
            for (int f = 0; f < N_FEAT; f++) keys[f] = ntohl(*(uint32_t *)(m + FEAT_OFF + 4 * f));
            int leaf, k = classify(keys, &leaf);
            m[4] = 2; m[5] = (uint8_t)k; *(uint16_t *)(m + 6) = htons((uint16_t)leaf);
            memcpy(p, vision, 6); memcpy(p + 6, self, 6);
            oiov[n_out].iov_base = p; oiov[n_out].iov_len = in[i].msg_len;
            memset(&out[n_out], 0, sizeof(out[n_out]));
            out[n_out].msg_hdr.msg_iov = &oiov[n_out]; out[n_out].msg_hdr.msg_iovlen = 1;
            n_out++;
        }
        int sent = 0;
        while (sent < n_out) {
            int s = sendmmsg(sock, out + sent, n_out - sent, 0);
            if (s < 0) { perror("sendmmsg"); break; }
            sent += s;
        }
        answered += n_out;
        if (now_ns() - last_report > 5000000000ull) {
            fprintf(stderr, "answered %llu misses\n", (unsigned long long)answered);
            last_report = now_ns();
        }
    }
}

int main(int argc, char **argv) {
    if (argc >= 6 && !strcmp(argv[1], "serve")) { load_tree(argv[3]); return serve(argv[2], argv[4], argv[5]); }
    if (argc >= 5 && !strcmp(argv[1], "bench")) { load_tree(argv[2]); return bench(argv[3], argv[4]); }
    fprintf(stderr, "usage: %s serve IFACE TREE.bin VISION_MAC SELF_MAC | bench TREE.bin QUERIES.bin EXPECTED.bin\n", argv[0]);
    return 2;
}
