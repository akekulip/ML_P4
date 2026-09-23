/* MVM-Lite query client (Vision). Replays queries into the switch and records every answer.
 *
 * Each query is Ethernet/IPv4/UDP(dst 50000)/mvm with the 10 order-preserving feature keys.
 * Hits come back from the switch (flags=1), misses come back from Hulk's CPU backend (flags=2).
 * Sends are paced at --rate queries per second in batches of --batch (sendmmsg); a receive thread
 * reads answers with recvmmsg. Output (binary, one record per query id):
 *   u64 send_ns, u64 recv_ns (0 = lost), u8 flags, u8 klass, u16 leaf, u32 t_pipe_ns
 * Build: gcc -O2 -pthread -o vision_client vision_client.c
 * Usage: sudo ./vision_client IFACE QUERIES.bin OUT.bin RATE DST_MAC SRC_MAC [BATCH]
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <linux/if_packet.h>
#include <net/ethernet.h>
#include <net/if.h>
#include <pthread.h>
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
#define HDR_LEN (14 + 20 + 8)
#define FEAT_OFF 16  /* qid 4, flags 1, klass 1, leaf 2, t_in 4, t_pipe 4 */
#define MVM_LEN (FEAT_OFF + 4 * N_FEAT)
#define PKT_LEN (HDR_LEN + MVM_LEN)
#define MAX_BATCH 64

typedef struct { uint64_t send_ns, recv_ns; uint8_t flags, klass; uint16_t leaf; uint32_t t_pipe; } __attribute__((packed)) rec_t;

static int sock;
static rec_t *recs;
static uint32_t nq;
static volatile int done_sending = 0;
static volatile uint64_t received = 0;

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + ts.tv_nsec;
}

static void parse_mac(const char *s, uint8_t *m) {
    sscanf(s, "%hhx:%hhx:%hhx:%hhx:%hhx:%hhx", &m[0], &m[1], &m[2], &m[3], &m[4], &m[5]);
}

static uint16_t ip_csum(const uint8_t *h) {
    uint32_t s = 0;
    for (int i = 0; i < 20; i += 2) s += (h[i] << 8) | h[i + 1];
    while (s >> 16) s = (s & 0xffff) + (s >> 16);
    return (uint16_t)~s;
}

static void *receiver(void *arg) {
    (void)arg;
    static uint8_t bufs[MAX_BATCH][256];
    struct mmsghdr msgs[MAX_BATCH];
    struct iovec iov[MAX_BATCH];
    struct sockaddr_ll addrs[MAX_BATCH];
    uint64_t idle_since = 0;
    for (;;) {
        memset(msgs, 0, sizeof(msgs));
        for (int i = 0; i < MAX_BATCH; i++) {
            iov[i].iov_base = bufs[i]; iov[i].iov_len = sizeof(bufs[i]);
            msgs[i].msg_hdr.msg_iov = &iov[i]; msgs[i].msg_hdr.msg_iovlen = 1;
            msgs[i].msg_hdr.msg_name = &addrs[i]; msgs[i].msg_hdr.msg_namelen = sizeof(addrs[i]);
        }
        int got = recvmmsg(sock, msgs, MAX_BATCH, MSG_DONTWAIT, NULL);
        uint64_t t = now_ns();
        if (got <= 0) {
            if (done_sending) {
                if (!idle_since) idle_since = t;
                if (t - idle_since > 2000000000ull) break;   /* 2 s without answers after the last send */
            }
            continue;
        }
        idle_since = 0;
        for (int i = 0; i < got; i++) {
            const uint8_t *p = bufs[i];
            if (addrs[i].sll_pkttype == PACKET_OUTGOING || msgs[i].msg_len < PKT_LEN) continue;
            if (p[12] != 0x08 || p[13] != 0x00 || p[23] != 17) continue;
            if (((p[36] << 8) | p[37]) != MVM_PORT) continue;
            const uint8_t *m = p + HDR_LEN;
            uint8_t flags = m[4];
            if (flags == 0) continue;                         /* our own query seen on the wire */
            uint32_t qid = ntohl(*(const uint32_t *)m);
            if (qid >= nq || recs[qid].recv_ns) continue;
            recs[qid].recv_ns = t;
            recs[qid].flags = flags;
            recs[qid].klass = m[5];
            recs[qid].leaf = ntohs(*(const uint16_t *)(m + 6));
            recs[qid].t_pipe = ntohl(*(const uint32_t *)(m + 12));
            received++;
        }
    }
    return NULL;
}

int main(int argc, char **argv) {
    if (argc < 7) { fprintf(stderr, "usage: %s IFACE QUERIES.bin OUT.bin RATE DST_MAC SRC_MAC [BATCH]\n", argv[0]); return 2; }
    const char *iface = argv[1];
    double rate = atof(argv[4]);
    int batch = argc > 7 ? atoi(argv[7]) : 8;
    if (batch < 1) batch = 1;
    if (batch > MAX_BATCH) batch = MAX_BATCH;
    uint8_t dst[6], src[6];
    parse_mac(argv[5], dst); parse_mac(argv[6], src);

    FILE *fq = fopen(argv[2], "rb");
    if (!fq) { perror("queries"); return 1; }
    fseek(fq, 0, SEEK_END); long sz = ftell(fq); fseek(fq, 0, SEEK_SET);
    nq = sz / (4 * (1 + N_FEAT));
    uint32_t *q = malloc(sz);
    if (fread(q, 1, sz, fq) != (size_t)sz) { perror("read"); return 1; }
    fclose(fq);
    recs = calloc(nq, sizeof(rec_t));

    sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
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
    setsockopt(sock, SOL_SOCKET, SO_SNDBUFFORCE, &buf, sizeof(buf));

    /* packet template */
    static uint8_t pk[MAX_BATCH][PKT_LEN];
    uint8_t tmpl[PKT_LEN]; memset(tmpl, 0, sizeof(tmpl));
    memcpy(tmpl, dst, 6); memcpy(tmpl + 6, src, 6); tmpl[12] = 0x08; tmpl[13] = 0x00;
    uint8_t *ip = tmpl + 14;
    ip[0] = 0x45; *(uint16_t *)(ip + 2) = htons(20 + 8 + MVM_LEN); ip[8] = 64; ip[9] = 17;
    ip[12] = 10; ip[13] = 0; ip[14] = 1; ip[15] = 1;      /* 10.0.1.1 */
    ip[16] = 10; ip[17] = 0; ip[18] = 1; ip[19] = 2;      /* 10.0.1.2 */
    *(uint16_t *)(ip + 10) = htons(ip_csum(ip));
    uint8_t *udp = tmpl + 34;
    *(uint16_t *)udp = htons(50001); *(uint16_t *)(udp + 2) = htons(MVM_PORT); *(uint16_t *)(udp + 4) = htons(8 + MVM_LEN);

    pthread_t th;
    pthread_create(&th, NULL, receiver, NULL);
    usleep(200000);

    struct mmsghdr msgs[MAX_BATCH];
    struct iovec iov[MAX_BATCH];
    double interval = batch / rate * 1e9;
    uint64_t t0 = now_ns(), next = t0;
    for (uint32_t i = 0; i < nq; i += batch) {
        int n = (nq - i < (uint32_t)batch) ? (int)(nq - i) : batch;
        while (now_ns() < next) ;                           /* busy-wait pacing */
        memset(msgs, 0, sizeof(msgs));
        for (int j = 0; j < n; j++) {
            uint32_t *r = q + (size_t)(i + j) * (1 + N_FEAT);
            memcpy(pk[j], tmpl, PKT_LEN);
            uint8_t *m = pk[j] + HDR_LEN;
            *(uint32_t *)m = htonl(r[0]);
            for (int f = 0; f < N_FEAT; f++) *(uint32_t *)(m + FEAT_OFF + 4 * f) = htonl(r[1 + f]);
            iov[j].iov_base = pk[j]; iov[j].iov_len = PKT_LEN;
            msgs[j].msg_hdr.msg_iov = &iov[j]; msgs[j].msg_hdr.msg_iovlen = 1;
        }
        uint64_t ts = now_ns();
        int sent = 0;
        while (sent < n) {
            int s = sendmmsg(sock, msgs + sent, n - sent, 0);
            if (s < 0) { perror("sendmmsg"); break; }
            sent += s;
        }
        for (int j = 0; j < n; j++) recs[q[(size_t)(i + j) * (1 + N_FEAT)]].send_ns = ts;
        next += (uint64_t)interval;
    }
    uint64_t t_end = now_ns();
    done_sending = 1;
    pthread_join(th, NULL);

    FILE *fo = fopen(argv[3], "wb");
    fwrite(recs, sizeof(rec_t), nq, fo);
    fclose(fo);
    fprintf(stderr, "sent %u queries in %.3f s (%.0f qps offered), received %llu answers\n",
            nq, (t_end - t0) / 1e9, nq / ((t_end - t0) / 1e9), (unsigned long long)received);
    return 0;
}
