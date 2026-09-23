/* MVM-Lite: demand-paged decision-tree leaves on BMv2 (v1model).
 *
 * The controller injects one query per flow as a P4Runtime packet-out: a packet_out header
 * (query id) followed by a feature header of 10 order-preserving 32-bit keys (see
 * src/mvm/p4encode.py). leaf_tbl holds at most K resident leaves, one range-match entry per
 * leaf (leaves of one tree are disjoint, so a constant priority suffices). Every query returns
 * to the controller as a packet-in carrying the query id, hit flag, class and leaf id; on a miss
 * the controller runs the full tree and installs/evicts leaf entries by P4Runtime writes.
 */
#include <core.p4>
#include <v1model.p4>

#define CPU_PORT 255

@controller_header("packet_out")
header packet_out_t {
    bit<32> query_id;
}

@controller_header("packet_in")
header packet_in_t {
    bit<32> query_id;
    bit<8>  hit;
    bit<8>  klass;
    bit<16> leaf_id;
}

header features_t {
    bit<32> f0; bit<32> f1; bit<32> f2; bit<32> f3; bit<32> f4;
    bit<32> f5; bit<32> f6; bit<32> f7; bit<32> f8; bit<32> f9;
}

struct headers_t {
    packet_in_t  packet_in;
    packet_out_t packet_out;
    features_t   feat;
}

struct metadata_t {
    bit<8>  hit;
    bit<8>  klass;
    bit<16> leaf_id;
}

parser MvmParser(packet_in pkt, out headers_t hdr, inout metadata_t meta,
                 inout standard_metadata_t std) {
    state start {
        transition select(std.ingress_port) {
            CPU_PORT: parse_packet_out;
            default: accept;
        }
    }
    state parse_packet_out {
        pkt.extract(hdr.packet_out);
        pkt.extract(hdr.feat);
        transition accept;
    }
}

control MvmVerifyChecksum(inout headers_t hdr, inout metadata_t meta) { apply { } }

control MvmIngress(inout headers_t hdr, inout metadata_t meta, inout standard_metadata_t std) {
    action leaf_hit(bit<16> leaf_id, bit<8> klass) {
        meta.hit = 1;
        meta.leaf_id = leaf_id;
        meta.klass = klass;
    }
    action leaf_miss() {
        meta.hit = 0;
        meta.leaf_id = 0;
        meta.klass = 0;
    }
    table leaf_tbl {
        key = {
            hdr.feat.f0: range; hdr.feat.f1: range; hdr.feat.f2: range; hdr.feat.f3: range;
            hdr.feat.f4: range; hdr.feat.f5: range; hdr.feat.f6: range; hdr.feat.f7: range;
            hdr.feat.f8: range; hdr.feat.f9: range;
        }
        actions = { leaf_hit; leaf_miss; }
        default_action = leaf_miss();
        size = 1024;
    }
    apply {
        if (hdr.packet_out.isValid() && hdr.feat.isValid()) {
            leaf_tbl.apply();
            hdr.packet_in.setValid();
            hdr.packet_in.query_id = hdr.packet_out.query_id;
            hdr.packet_in.hit = meta.hit;
            hdr.packet_in.klass = meta.klass;
            hdr.packet_in.leaf_id = meta.leaf_id;
            hdr.packet_out.setInvalid();
            std.egress_spec = CPU_PORT;
        } else {
            mark_to_drop(std);
        }
    }
}

control MvmEgress(inout headers_t hdr, inout metadata_t meta, inout standard_metadata_t std) { apply { } }

control MvmComputeChecksum(inout headers_t hdr, inout metadata_t meta) { apply { } }

control MvmDeparser(packet_out pkt, in headers_t hdr) {
    apply {
        pkt.emit(hdr.packet_in);
        pkt.emit(hdr.feat);
    }
}

V1Switch(MvmParser(), MvmVerifyChecksum(), MvmIngress(), MvmEgress(), MvmComputeChecksum(), MvmDeparser()) main;
