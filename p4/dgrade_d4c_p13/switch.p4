#include <core.p4>
//#include <v1model.p4>
#include <tna.p4>
#include "headers.p4"
#include "util.p4"
#include "parsers.p4"

control SwitchIngress(
        inout header_t hdr,
        inout metadata_t ig_md,
        in ingress_intrinsic_metadata_t ig_intr_md,
        in ingress_intrinsic_metadata_from_parser_t ig_prsr_md,
        inout ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md,
        inout ingress_intrinsic_metadata_for_tm_t ig_tm_md) {

    @symmetric("hdr.ipv4.src_addr", "hdr.ipv4.dst_addr")
    @symmetric("ig_md.src_port", "ig_md.dst_port")
    Hash<bit<32>>(HashAlgorithm_t.CRC32) my_symmetric_hash;
    
    Register<bit<32>, bit<Register_Index_Size>>(Register_Table_Size) Register_total_bytes; //<register type, index>(index w registersize)
    RegisterAction<bit<32>, bit<Register_Index_Size>, bit<32>>(Register_total_bytes) Update_Register_total_bytes = { //<register type, index, out type>
        void apply(inout bit<32> value, out bit<32> read_value){ 
            value = value + (bit<32>) hdr.ipv4.total_len;
            read_value = value;
        }
    };
    RegisterAction<bit<32>, bit<Register_Index_Size>, bit<32>>(Register_total_bytes) Init_Register_total_bytes = { //<register type, index, out type>
        void apply(inout bit<32> value, out bit<32> read_value){ 
            value = (bit<32>) hdr.ipv4.total_len;
            read_value = value;
        }
    };
    
    action Update_total_bytes(){
        ig_md.total_bytes = Update_Register_total_bytes.execute(ig_md.slot);
    }
    action Init_total_bytes(){
        ig_md.total_bytes = Init_Register_total_bytes.execute(ig_md.slot);
    }
    

    Register<bit<16>, bit<Register_Index_Size>>(Register_Table_Size) Register_total_pkts;
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_total_pkts) Update_Register_total_pkts = { 
        void apply(inout bit<16> value, out bit<16> read_value){ 
            value = value + 1;
            read_value = value;
        }
    };
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_total_pkts) Init_Register_total_pkts = { 
        void apply(inout bit<16> value, out bit<16> read_value){ 
            value = 1;
            read_value = value;
        }
    };
    action Init_total_pkts(){
        ig_md.total_pkts = Init_Register_total_pkts.execute(ig_md.slot);
    }
    action Update_total_pkts(){
        ig_md.total_pkts = Update_Register_total_pkts.execute(ig_md.slot);
    }


    Register<bit<16>, bit<Register_Index_Size>>(Register_Table_Size) Register_max_pkt_length;
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_max_pkt_length) Update_Register_max_pkt_length = { 
        void apply(inout bit<16> value, out bit<16> read_value){
            if(hdr.ipv4.total_len > value){
                value = hdr.ipv4.total_len; 
            }
            read_value = value;
        }
    };
    action Update_max_pkt_length(){
        ig_md.max_pkt_length = Update_Register_max_pkt_length.execute(ig_md.slot);
    }
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_max_pkt_length) Init_Register_max_pkt_length = { 
        void apply(inout bit<16> value, out bit<16> read_value){
            value = hdr.ipv4.total_len;
            read_value = value;
        }
    };
    action Init_max_pkt_length(){
        Init_Register_max_pkt_length.execute(ig_md.slot);
    }


    Register<bit<16>, bit<Register_Index_Size>>(Register_Table_Size) Register_min_pkt_length;
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_min_pkt_length) Update_Register_min_pkt_length = { 
        void apply(inout bit<16> value, out bit<16> read_value){
        if(hdr.ipv4.total_len < value){
                value =  hdr.ipv4.total_len;
            }
            read_value = value;
        }
    };
    action Update_min_pkt_length(){
        ig_md.min_pkt_length = Update_Register_min_pkt_length.execute(ig_md.slot);
    }
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_min_pkt_length) Init_Register_min_pkt_length = { 
        void apply(inout bit<16> value, out bit<16> read_value){
            value = hdr.ipv4.total_len;
            read_value = value;
        }
    };
    action Init_min_pkt_length(){
        ig_md.min_pkt_length = Init_Register_min_pkt_length.execute(ig_md.slot);
    }



    Register<bit<16>, bit<Register_Index_Size>>(Register_Table_Size) Register_bin1;
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_bin1) Update_Register_bin1 = { 
        void apply(inout bit<16> value, out bit<16> read_value){ value = value + 1; read_value = value;}};
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_bin1) Read_Register_bin1 = { 
        void apply(inout bit<16> value, out bit<16> read_value){read_value = value;}};
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_bin1) Init0_Register_bin1 = { 
        void apply(inout bit<16> value, out bit<16> read_value){value=0; read_value=value;}};
    RegisterAction<bit<16>, bit<Register_Index_Size>, bit<16>>(Register_bin1) Init1_Register_bin1 = { 
        void apply(inout bit<16> value, out bit<16> read_value){value=1; read_value=value;}};
    action Read_bin1(){ig_md.bin1 = Read_Register_bin1.execute(ig_md.slot);}
    action Update_bin1(){ig_md.bin1 = Update_Register_bin1.execute(ig_md.slot);}
    action Init0_bin1(){Init0_Register_bin1.execute(ig_md.slot);}
    action Init1_bin1(){Init1_Register_bin1.execute(ig_md.slot);}
    
    Register<bit<8>, bit<Register_Index_Size>>(Register_Table_Size) Register_bin2;
    RegisterAction<bit<8>, bit<Register_Index_Size>, bit<8>>(Register_bin2) Update_Register_bin2 = { 
        void apply(inout bit<8> value, out bit<8> read_value){ value = value + 1; read_value = value;}};
    RegisterAction<bit<8>, bit<Register_Index_Size>, bit<8>>(Register_bin2) Read_Register_bin2 = { 
        void apply(inout bit<8> value, out bit<8> read_value){read_value = value;}};
    RegisterAction<bit<8>, bit<Register_Index_Size>, bit<8>>(Register_bin2) Init0_Register_bin2 = { 
         void apply(inout bit<8> value, out bit<8> read_value){value=0; read_value=value;}};
    RegisterAction<bit<8>, bit<Register_Index_Size>, bit<8>>(Register_bin2) Init1_Register_bin2 = { 
         void apply(inout bit<8> value, out bit<8> read_value){value=1; read_value=value;}};
    action Read_bin2(){ig_md.bin2 = Read_Register_bin2.execute(ig_md.slot);}
    action Update_bin2(){ig_md.bin2 = Update_Register_bin2.execute(ig_md.slot);}
    action Init0_bin2(){Init0_Register_bin2.execute(ig_md.slot);}
    action Init1_bin2(){Init1_Register_bin2.execute(ig_md.slot);}


    Register<bit<32>, bit<Register_Index_Size>>(Register_Table_Size) Register_last_pkt_timestamp;
    RegisterAction<bit<32>, bit<Register_Index_Size>, bit<32>>(Register_last_pkt_timestamp) Update_Register_last_pkt_timestamp = { 
        void apply(inout bit<32> value, out bit<32> read_value){
            read_value = ig_md.ipd-value;
            value = ig_md.ipd;
        }
    };
    RegisterAction<bit<32>, bit<Register_Index_Size>, bit<32>>(Register_last_pkt_timestamp) Init_Register_last_pkt_timestamp = { 
        void apply(inout bit<32> value, out bit<32> read_value){
            read_value = 0;
            value = ig_md.ipd;
        }
    };
    action Init_last_pkt_timestamp(){
        ig_md.ipd = Init_Register_last_pkt_timestamp.execute(ig_md.slot);
    }
    action Update_last_pkt_timestamp(){
        ig_md.ipd = Update_Register_last_pkt_timestamp.execute(ig_md.slot);
    }

    Register<bit<32>, bit<Register_Index_Size>>(Register_Table_Size) Register_min_ipd;
    RegisterAction<bit<32>, bit<Register_Index_Size>, bit<32>>(Register_min_ipd) Update_Register_min_ipd = { 
        void apply(inout bit<32> value, out bit<32> read_value){
            if(ig_md.ipd<value){
                value = ig_md.ipd;
            }
            read_value =  value;
        }
    };
    RegisterAction<bit<32>, bit<Register_Index_Size>, bit<32>>(Register_min_ipd) Init_Register_min_ipd = { 
        void apply(inout bit<32> value, out bit<32> read_value){
            value = 4294967295;
            read_value =  value;
        }
    };
    action Init_min_ipd(){
        ig_md.min_ipd = Init_Register_min_ipd.execute(ig_md.slot);
    }
    action Update_min_ipd(){
        ig_md.min_ipd = Update_Register_min_ipd.execute(ig_md.slot);
    }


    MathUnit<bit<32>>(MathOp_t.SQR, 1) square1; 
    Register<bit<32>, bit<Register_Index_Size>>(Register_Table_Size) Register_pkt_length_power_sum;
    RegisterAction<bit<32>, bit<Register_Index_Size>, bit<32>>(Register_pkt_length_power_sum) Update_Register_pkt_length_power_sum = { 
        void apply(inout bit<32> value, out bit<32> read_value){
            //value = value + square1.execute((bit<32>) hdr.ipv4.total_len);
            value = value + square1.execute((bit<32>) ig_md.zoom_pkt_length);
            read_value = value;
        }
    };
    RegisterAction<bit<32>, bit<Register_Index_Size>, bit<32>>(Register_pkt_length_power_sum) Init_Register_pkt_length_power_sum = { 
        void apply(inout bit<32> value, out bit<32> read_value){
            //value = square1.execute((bit<32>) hdr.ipv4.total_len);
            value = square1.execute((bit<32>) ig_md.zoom_pkt_length);
            read_value = value;
        }
    };
    action Update_pkt_length_power_sum(){
        ig_md.pkt_length_power_sum = Update_Register_pkt_length_power_sum.execute(ig_md.slot);
    }
    action Init_pkt_length_power_sum(){
        Init_Register_pkt_length_power_sum.execute(ig_md.slot);
    }

    
    MathUnit<bit<32>>(MathOp_t.SQR, 1) square2; 
    Register<bit<32>, bit<32>>(1) Register_total_bytes_power;
    RegisterAction<bit<32>, bit<32>, bit<32>>(Register_total_bytes_power) Update_Register_total_bytes_power = { 
        void apply(inout bit<32> value, out bit<32> read_value){
            value = square2.execute(ig_md.pkt_size_avg);
            read_value = value;
        }
    };
    action Update_total_bytes_power(){
        ig_md.total_bytes_power = Update_Register_total_bytes_power.execute(0);
    }


    // =====================================================================
    // D4c (variant P-b): per-way identity state.
    //   Register_id_{A,B}:     pair register, hi = 32-bit flow tag (the same
    //                          CRC32 flow_hash NetBeacon stores), lo = last-seen
    //                          time (NetBeacon's last_classified_timestamp).
    //   Register_result_{A,B}: bit 8 = "claimed at least once", bits 7:0 = result.
    //                          The claimed bit replaces the spec's tag==0 test: a
    //                          Tofino-1 SALU has two comparators and the probe
    //                          already uses both (own, recent), and its single
    //                          output is the predicate, so the tag cannot come out.
    // One SALU per way does the tag compare, the owner refresh and the idle
    // test in one access. The eleven feature registers stay single arrays of
    // 65536, indexed by the chosen slot {way, idx}.
    // =====================================================================
    // Second hash: independently keyed CRC-32 for table B. The coefficient is
    // the normal form of the emulator's polyirr polynomial for hash2_seed=7919
    // (reflected 0xa17d1390); it can be re-keyed at runtime through bfrt dynamic
    // hashing. Symmetric like NetBeacon's hash so both directions share a slot.
    CRCPolynomial<bit<16>>(16w0x3D65, true, false, false, 16w0xFFFF, 16w0xFFFF) poly_b16;
    CRCPolynomial<bit<32>>(32w0x09c8be85, true, false, false, 32w0xFFFFFFFF, 32w0xFFFFFFFF) poly_b;
    @symmetric("hdr.ipv4.src_addr", "hdr.ipv4.dst_addr")
    @symmetric("ig_md.src_port", "ig_md.dst_port")
    Hash<bit<32>>(HashAlgorithm_t.CUSTOM, poly_b) hash_b;

    CRCPolynomial<bit<16>>(16w0x8BB7, true, false, false, 16w0xFFFF, 16w0xFFFF) poly_t;
    Hash<bit<16>>(HashAlgorithm_t.CUSTOM, poly_t) hash_e1;
    Hash<bit<16>>(HashAlgorithm_t.CUSTOM, poly_t) hash_e2;
    action Hash_E1() { ig_md.ep1 = hash_e1.get({hdr.ipv4.src_addr, ig_md.src_port, hdr.ipv4.protocol}); }
    action Hash_E2() { ig_md.ep2 = hash_e2.get({hdr.ipv4.dst_addr, ig_md.dst_port, hdr.ipv4.protocol}); }
    // P13-fix: the keyed tag is no longer a separate register compared in its own
    // SALU. It is folded into the identity word the Probe SALU already compares
    // (id_key = flow_hash[31:16] ++ tag), so "own" == weak hash AND keyed tag
    // match, in ONE comparator. A keyed mismatch therefore IS "not own": no
    // Own_* action, no inherited verdict, no last-seen refresh, no feature update.
    action Hash_A() { ig_md.flow_hash  = my_symmetric_hash.get({hdr.ipv4.src_addr,hdr.ipv4.dst_addr,ig_md.src_port,ig_md.dst_port,hdr.ipv4.protocol}); }
    action Hash_B() { ig_md.flow_hash2 = hash_b.get({hdr.ipv4.src_addr,hdr.ipv4.dst_addr,ig_md.src_port,ig_md.dst_port,hdr.ipv4.protocol}); }

    Register<id_pair_t, bit<Way_Index_Size>>(Way_Table_Size) Register_id_A;
    Register<id_pair_t, bit<Way_Index_Size>>(Way_Table_Size) Register_id_B;

    // Pass 1: owner -> refresh last-seen. Returns the SALU 4-bit predicate over
    // (cmplo = own, cmphi = recent). Tofino-1 SALUs have a single output source,
    // so per-branch constants are not possible (bf-p4c: "cannot output constant
    // ... because the predicate is output in another control flow").
    RegisterAction<id_pair_t, bit<Way_Index_Size>, bit<8>>(Register_id_A) Probe_id_A = {
        void apply(inout id_pair_t v, out bit<8> rv) {
            // cmplo = own (weak-hash high half AND keyed tag match), cmphi = recent (idle < timeout); written
            // inline because bf-p4c rejects a bool local holding the subtraction.
            if (v.hi == ig_md.id_key) {
                v.lo = ig_md.now_timestamp;
            }
            rv = this.predicate(v.hi == ig_md.id_key,
                                ig_md.now_timestamp - v.lo < timeout_thres);
        }
    };
    RegisterAction<id_pair_t, bit<Way_Index_Size>, bit<8>>(Register_id_B) Probe_id_B = {
        void apply(inout id_pair_t v, out bit<8> rv) {
            // cmplo = own (weak-hash high half AND keyed tag match), cmphi = recent (idle < timeout); written
            // inline because bf-p4c rejects a bool local holding the subtraction.
            if (v.hi == ig_md.id_key) {
                v.lo = ig_md.now_timestamp;
            }
            rv = this.predicate(v.hi == ig_md.id_key,
                                ig_md.now_timestamp - v.lo < timeout_thres);
        }
    };
    // Recirculated pass: write the tag only. last-seen is NOT refreshed at a
    // takeover, exactly like NetBeacon (switch.p4:607,626 in the original).
    RegisterAction<id_pair_t, bit<Way_Index_Size>, bit<8>>(Register_id_A) Claim_id_A = {
        void apply(inout id_pair_t v) { v.hi = ig_md.id_key; }
    };
    RegisterAction<id_pair_t, bit<Way_Index_Size>, bit<8>>(Register_id_B) Claim_id_B = {
        void apply(inout id_pair_t v) { v.hi = ig_md.id_key; }
    };

    Register<bit<16>, bit<Way_Index_Size>>(Way_Table_Size) Register_result_A;
    // [15] lease expired (sticky), [14:8] epoch of last write (2^30 ns), [7:0] result; never-claimed == 0
    RegisterAction<bit<16>, bit<Way_Index_Size>, bit<16>>(Register_result_A) Read_Register_result_A = {
        void apply(inout bit<16> v, out bit<16> rv) {
            if (ig_md.wv - v >= LEASE_SH) { v = v | EXPIRED; }
            rv = v;
        }
    };
    RegisterAction<bit<16>, bit<Way_Index_Size>, bit<16>>(Register_result_A) Write_Register_result_A = {
        void apply(inout bit<16> v) { v = ig_md.wv; }
    };
    Register<bit<16>, bit<Way_Index_Size>>(Way_Table_Size) Register_result_B;
    // [15] lease expired (sticky), [14:8] epoch of last write (2^30 ns), [7:0] result; never-claimed == 0
    RegisterAction<bit<16>, bit<Way_Index_Size>, bit<16>>(Register_result_B) Read_Register_result_B = {
        void apply(inout bit<16> v, out bit<16> rv) {
            if (ig_md.wv - v >= LEASE_SH) { v = v | EXPIRED; }
            rv = v;
        }
    };
    RegisterAction<bit<16>, bit<Way_Index_Size>, bit<16>>(Register_result_B) Write_Register_result_B = {
        void apply(inout bit<16> v) { v = ig_md.wv; }
    };
    action Probe_A() { ig_md.st_a = Probe_id_A.execute(ig_md.flow_hash[Way_Index_Size-1:0]); }
    action Probe_B() { ig_md.st_b = Probe_id_B.execute(ig_md.flow_hash2[Way_Index_Size-1:0]); }
    action Read_result_A() { ig_md.res_a = Read_Register_result_A.execute(ig_md.flow_hash[Way_Index_Size-1:0]); }
    action Read_result_B() { ig_md.res_b = Read_Register_result_B.execute(ig_md.flow_hash2[Way_Index_Size-1:0]); }
    // Recirculated pass (claim or post-classification write), way from pass 1.
    // One action may drive only one stateful ALU (bf-p4c: "overlap ... require the
    // meter address hardware"), so tag and result are written by separate actions.
    action Claim_A()        { Claim_id_A.execute(ig_md.flow_hash[Way_Index_Size-1:0]); }
    action Claim_B()        { Claim_id_B.execute(ig_md.flow_hash2[Way_Index_Size-1:0]); }
    action Write_result_A() { Write_Register_result_A.execute(ig_md.flow_hash[Way_Index_Size-1:0]); ig_md.result = hdr.ipv4.ttl; }
    action Write_result_B() { Write_Register_result_B.execute(ig_md.flow_hash2[Way_Index_Size-1:0]); ig_md.result = hdr.ipv4.ttl; }

    // Placement outcomes. slot = way ++ idx addresses the shared feature registers.
    action Own_A() { ig_md.act = ACT_OWN; ig_md.way = 0; ig_md.slot = 1w0 ++ ig_md.flow_hash[Way_Index_Size-1:0]; ig_md.result = ig_md.res_a[7:0]; }
    action Own_B() { ig_md.act = ACT_OWN; ig_md.way = 1; ig_md.slot = 1w1 ++ ig_md.flow_hash2[Way_Index_Size-1:0]; ig_md.result = ig_md.res_b[7:0]; }
    action New_A() { ig_md.act = ACT_NEW; ig_md.way = 0; ig_md.slot = 1w0 ++ ig_md.flow_hash[Way_Index_Size-1:0]; }
    action New_B() { ig_md.act = ACT_NEW; ig_md.way = 1; ig_md.slot = 1w1 ++ ig_md.flow_hash2[Way_Index_Size-1:0]; }

    action noaction(){}
    

    action feat3_hit(bit<48> ind){ ig_md.feat3_encode = ind;}
    @pragma stage 0
    table Feat3{
        key = {ig_md.tcp_window: ternary;}
        actions={feat3_hit; noaction;}
        size = 165; 
        const default_action = noaction;
    }
    action feat4_hit(bit<8> ind){ig_md.feat4_encode =  ind;}
    @pragma stage 0
    table Feat4{
        key = {ig_md.tcp_data_offset: ternary;}
        actions={feat4_hit; noaction;}
        size = 8; 
        const default_action = noaction;
    }
    action feat5_hit(bit<144> ind){ig_md.feat5_encode = ind;}
    @pragma stage 0
    table Feat5{
        key = {hdr.ipv4.total_len: ternary;}
        actions={feat5_hit; noaction;}
        size = 256;
        const default_action = noaction;
    }
    action feat6_hit(bit<80> ind){ig_md.feat6_encode = (bit<72>)  ind;}
    @pragma stage 0
    table Feat6{
        key = {ig_md.udp_length: ternary;}
        actions={feat6_hit; noaction;}
        size = 150;
        const default_action = noaction;
    }
    action feat7_hit(bit<64> ind){ig_md.feat7_encode =  ind;}
    @pragma stage 0
    table Feat7{
        key = {hdr.ipv4.ttl: ternary;}
        actions={feat7_hit; noaction;}
        size = 90; 
        const default_action = noaction;
    }
    action feat8_hit(bit<8> ind){ig_md.feat8_encode =  ind;}
    @pragma stage 0
    table Feat8{
        key = {hdr.ipv4.protocol: ternary;}
        actions={feat8_hit; noaction;}
        size = 4; 
        const default_action = noaction;
    }
    action feat9_hit(bit<32> ind){ig_md.feat9_encode = (bit<24>) ind;}
    @pragma stage 0
    table Feat9{
        key = {hdr.ipv4.diffserv: ternary;}
        actions={feat9_hit; noaction;}
        size = 30; 
        const default_action = noaction;
    }

    action feat10_hit(bit<32> ind){ig_md.feat10_encode =  ind;}
    table Feat10{
        key = {ig_md.total_pkts: exact; ig_md.bin1: ternary;}
        actions={feat10_hit; noaction;}
        size = 180; 
        const default_action = noaction;
    }
    
    action feat11_hit(bit<32> ind){ig_md.feat11_encode = (bit<24>) ind;}
    table Feat11{
        key = {ig_md.total_pkts: exact; ig_md.bin2: ternary;}
        actions={feat11_hit; noaction;}
        size = 50; 
        const default_action = noaction;
    }
    
    action feat12_hit(bit<80> ind){ig_md.feat12_encode = (bit<72>) ind;} //pkt_size_avg
    table Feat12{
        key = {ig_md.total_pkts: exact; ig_md.pkt_size_avg: ternary;}
        actions = {feat12_hit; noaction;}
        size = 690;
        const default_action = noaction;
    }

    action feat13_hit(bit<80> ind){ig_md.feat13_encode = ind; } //pkt_size_max
    table Feat13{
        key = {ig_md.total_pkts: exact; ig_md.max_pkt_length: ternary;}
        actions = {feat13_hit; noaction;}
        size = 850;
        const default_action = noaction;
    }

    action feat14_hit(bit<48> ind){ig_md.feat14_encode = ind;} //pkt_size_min
    table Feat14{
        key = {ig_md.total_pkts: exact; ig_md.min_pkt_length: ternary;}
        actions = {feat14_hit; noaction;}
        size = 260;
        const default_action = noaction;
    }
    
    action feat15_hit(bit<80> ind){ig_md.feat15_encode = (bit<72>) ind; } //flow_ipd_min 
    table Feat15{
        key = {ig_md.total_pkts: exact; ig_md.min_ipd: ternary;}
        actions = {feat15_hit; noaction;}
        size = 990;
        const default_action = noaction;
    }

    action feat16_hit(bit<80> ind){ig_md.feat16_encode = ind;} //pkt_size_var
    table Feat16{
        key = {ig_md.total_pkts: exact; ig_md.pkt_length_power_sum: ternary;}
        actions={feat16_hit; noaction;}
        size = 1740;
        const default_action = noaction;
    }

    @pragma stage 4 
    table Update_total_bytes_table{actions={Update_total_bytes;} default_action=Update_total_bytes;}
    @pragma stage 4 
    table Init_total_bytes_table{actions={Init_total_bytes;} default_action=Init_total_bytes;}
    
    @pragma stage 4
    table Update_total_pkts_table{actions={Update_total_pkts;} default_action=Update_total_pkts;}
    @pragma stage 4
    table Init_total_pkts_table{actions={Init_total_pkts;}default_action=Init_total_pkts;}

    @pragma stage 4
    table Update_pkt_length_power_sum_table{actions={Update_pkt_length_power_sum;} default_action=Update_pkt_length_power_sum;}
    @pragma stage 4 
    table Init_pkt_length_power_sum_table{actions={Init_pkt_length_power_sum;}default_action=Init_pkt_length_power_sum;}

    @pragma stage 5
    table Init_max_pkt_length_table{actions={Init_max_pkt_length;} default_action=Init_max_pkt_length;}
    @pragma stage 5
    table Update_max_pkt_length_table{actions={Update_max_pkt_length;}default_action=Update_max_pkt_length;}
    
    @pragma stage 5
    table Init_min_pkt_length_table{actions={Init_min_pkt_length;} default_action=Init_min_pkt_length;}
    @pragma stage 5
    table Update_min_pkt_length_table{actions={Update_min_pkt_length;}default_action=Update_min_pkt_length;}

    @pragma stage 7
    table pkt_bin1{key= {hdr.ipv4.total_len:ternary;} actions={Update_bin1; Read_bin1; noaction;} size = 2; const default_action = noaction; }
    @pragma stage 7
    table Init_bin1_table{key= {hdr.ipv4.total_len:ternary;} actions={Init0_bin1; Init1_bin1; noaction;} size = 2; const default_action=noaction;}
    @pragma stage 7
    table pkt_bin2{key= {hdr.ipv4.total_len:ternary;} actions={Update_bin2; Read_bin2; noaction;} size = 2; const default_action = noaction; }
    @pragma stage 7
    table Init_bin2_table{key= {hdr.ipv4.total_len:ternary;} actions={Init0_bin2; Init1_bin2; noaction;} size = 2; const default_action=noaction;}

    @pragma stage 5
    table Init_last_pkt_timestamp_table{ actions={Init_last_pkt_timestamp;} default_action=Init_last_pkt_timestamp;}
    @pragma stage 5
    table Update_last_pkt_timestamp_table{actions={Update_last_pkt_timestamp;} default_action=Update_last_pkt_timestamp;}

    @pragma stage 7
    table Init_min_ipd_table{actions={Init_min_ipd;} default_action=Init_min_ipd;}
    @pragma stage 7
    table Update_min_ipd_table{actions={Update_min_ipd;} default_action=Update_min_ipd;}

    action SetFlowSize(bit<8> result){
        ig_md.flow_size = result; //long or short flow
    }
    @pragma stage 1
    table Flow_Size_Tree{
        key={
            // ig_md.feat1_encode:ternary;
            // ig_md.feat2_encode:ternary;
            ig_md.feat3_encode:ternary;
            ig_md.feat4_encode:ternary;
            ig_md.feat5_encode:ternary;
            ig_md.feat6_encode:ternary;
            ig_md.feat7_encode:ternary;
            ig_md.feat8_encode:ternary;
            ig_md.feat9_encode:ternary;
        }
        actions={
            SetFlowSize;
            noaction;
        }
        size = 185;
        const default_action = noaction;
    }
    
    action Set_flow_result(bit<8> result){
        ig_md.result = result;
    }

    table Flow_result{
        key={
            hdr.ipv4.src_addr: exact;
            hdr.ipv4.dst_addr: exact;
            ig_md.src_port:exact;
            ig_md.dst_port:exact;
            hdr.ipv4.protocol: exact;
        }
        actions={
            Set_flow_result;
            noaction;
        }
        size = 3000; 
        const default_action = noaction;
    }

    action SetClass_Pkt_Tree(bit<8> result,bit<8> confidence){
        ig_md.pkt_result = result;
        ig_md.pkt_conf = confidence;
    }
    table Pkt_Tree{
        key={
            // ig_md.feat1_encode:ternary;
            // ig_md.feat2_encode:ternary;
            ig_md.feat3_encode:ternary;
            ig_md.feat4_encode:ternary;
            ig_md.feat5_encode:ternary;
            ig_md.feat6_encode:ternary;
            ig_md.feat7_encode:ternary;
            ig_md.feat8_encode:ternary;
            ig_md.feat9_encode:ternary;
        }
        actions={
            SetClass_Pkt_Tree;
            noaction;
        }
        size = 390;
        const default_action = noaction;
    }
    
    action SetClass_Flow_Tree(bit<8> confidence, bit<8> result){
        ig_md.tree1_confidence = confidence; //0-100
        ig_md.result = result;
    }

    table Flow_Tree{
        key={
            ig_md.total_pkts: exact;
            // ig_md.feat1_encode:ternary;
            // ig_md.feat2_encode:ternary;
            ig_md.feat10_encode:ternary;
            ig_md.feat11_encode:ternary;
            ig_md.feat12_encode:ternary;
            ig_md.feat13_encode:ternary;
            ig_md.feat14_encode:ternary;
            ig_md.feat15_encode:ternary;
            ig_md.feat16_encode:ternary;
        }
        actions={
            SetClass_Flow_Tree;
            noaction;
        }
        size = 1710;
        const default_action = noaction;
    }
    
    action default_treat(){ hdr.ipv4.ttl = ig_md.result; }
    action treat1(bit<8> r){ hdr.ipv4.ttl = r; }
    action treat2(bit<8> r){ hdr.ipv4.ttl = r; }
    table Treatment{
        key = {ig_md.result:ternary; ig_md.pkt_result:ternary;}
        actions={
            default_treat;
            treat1;
            treat2;
        }
        size = 10;
        const default_action = default_treat;
    }

    apply{
        // Two separate actions: one action can carry only 32 bits of hash output
        // through the immediate path (bf-p4c: "immediate pathway 64 ... available bits 32").
        Hash_A();
        Hash_B();
        Hash_E1();
        Hash_E2();
        ig_md.bin1=0;
        ig_md.bin2=0;
        ig_md.pkt_length_power_sum=0;
        ig_md.ipd = 0;
        ig_md.total_pkts=0;
        ig_md.total_bytes=0;
        ig_md.min_pkt_length=0;
        ig_md.max_pkt_length=0;
        ig_md.min_ipd=0;
        ig_md.feat3_encode=0;
        ig_md.feat4_encode=0;
        ig_md.feat5_encode=0;
        ig_md.feat6_encode=0;
        ig_md.feat7_encode=0;
        ig_md.feat8_encode=0;
        ig_md.feat9_encode=0;
        ig_md.feat10_encode=0;
        ig_md.feat11_encode=0;
        ig_md.feat12_encode=0;
        ig_md.feat13_encode=0;
        ig_md.feat14_encode=0;
        ig_md.feat15_encode=0;
        ig_md.feat16_encode=0;

        ig_md.tree1_confidence= 0;
        ig_md.result = 0;
        ig_md.flow_size = 0;
        ig_md.act = ACT_NONE;
        ig_md.way = 0;

        ig_md.zoom_pkt_length = hdr.ipv4.total_len >> 2;

        ig_md.now_timestamp = (bit<32>) (ig_prsr_md.global_tstamp >> 20); // D1
        ig_md.wv = 1w0 ++ ig_prsr_md.global_tstamp[36:30] ++ hdr.ipv4.ttl;

        // idx_A = flow_hash[14:0], idx_B = flow_hash2[14:0], used as slices directly
        // (a separate copy into metadata cost one extra stage).

        Feat3.apply();
        Feat4.apply();
        Feat5.apply();
        Feat6.apply();
        Feat7.apply();
        Feat8.apply();
        Feat9.apply();

        Flow_Size_Tree.apply();
        ig_md.pkt_result = 0;
        Pkt_Tree.apply();
        ig_tm_md.ucast_egress_port = egress_port;

        // Keyed additive identity (ADD, not XOR: survives the linear XOR-fold alias).
        ig_md.tag = ig_md.ep1 + ig_md.ep2;
        ig_md.id_key = ig_md.flow_hash[31:16] ++ ig_md.tag;

        if(ig_intr_md.ingress_port == recirculate_port){ // recirculated pass: claim / result write in the way chosen in pass 1
            if (hdr.ethernet.dst_addr[0:0] == 1) {
                Claim_B();
                Write_result_B();
            } else {
                Claim_A();
                Write_result_A();
            }
            ig_md.tree1_confidence = hdr.ipv4.diffserv;
            ig_md.total_pkts = hdr.ipv4.identification;
        }
        else{
            Read_result_A();
            Read_result_B();
            if(!Flow_result.apply().hit){
                Probe_A();
                Probe_B();
                // A keyed-tag mismatch returns P_RECENT / P_IDLE (never P_OWN*), so the
                // alias falls to the newcomer path: result = 0, and the victim's slot is
                // seen as HELD (if recent, unresolved, lease live), so it cannot be taken.
                // ---- D4c placement (emulator two_way_policy="unclaimed_first") ----
                if (ig_md.st_a == P_OWN || ig_md.st_a == P_OWN_RECENT) {
                    Own_A();
                } else if (ig_md.st_b == P_OWN || ig_md.st_b == P_OWN_RECENT) {
                    Own_B();
                } else if (ig_md.flow_size > 50) {                 // long-predicted newcomer
                    if (ig_md.st_a == P_RECENT && ig_md.res_a[7:0] < 50 && ig_md.res_a[15:15] == 0) {        // A held
                        if (!(ig_md.st_b == P_RECENT && ig_md.res_b[7:0] < 50 && ig_md.res_b[15:15] == 0)) { // B takeable
                            New_B();
                        }                                                          // else: both held, refused
                    } else if (ig_md.st_b == P_RECENT && ig_md.res_b[7:0] < 50 && ig_md.res_b[15:15] == 0) { // only B held
                        New_A();
                    } else if (ig_md.res_a != 0 && ig_md.res_b == 0) {   // both takeable: prefer never-claimed B
                        New_B();
                    } else {
                        New_A();
                    }
                }

                // Owner and newcomer paths must be ONE if/else so bf-p4c sees the Init_* and
                // Update_* accesses of each feature register as mutually exclusive (two
                // separate ifs on ig_md.act cost two extra stages: critical path 13).
                if (ig_md.act == ACT_OWN) {
                if(ig_md.result<50){
                    pkt_bin1.apply();
                    pkt_bin2.apply();
                    Update_total_pkts_table.apply();
                    Update_total_bytes_table.apply();
                    Update_min_pkt_length_table.apply();
                    Update_max_pkt_length_table.apply();
                    Update_pkt_length_power_sum_table.apply();
                    ig_md.ipd = (bit<32>) ig_prsr_md.global_tstamp>>10; //Multiplex ipd as current time
                    Update_last_pkt_timestamp_table.apply();
                    Update_min_ipd_table.apply();

                    if (ig_md.total_pkts==2){
                        ig_md.pkt_size_avg = ig_md.total_bytes>>1;
                        //ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>1;
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum<<3; //if zoom before
                        Update_total_bytes_power();
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum-ig_md.total_bytes_power;
                        ig_md.tree1_confidence = 110;
                    }
                    else if (ig_md.total_pkts==4){
                        ig_md.pkt_size_avg = ig_md.total_bytes>>2;
                        //ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>2;
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum<<2; 
                        Update_total_bytes_power();
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum-ig_md.total_bytes_power;
                        ig_md.tree1_confidence = 110;
                    }
                    else if (ig_md.total_pkts==8){
                        ig_md.pkt_size_avg = ig_md.total_bytes>>3;
                        //ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>3;
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum<<1; 
                        Update_total_bytes_power();
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum-ig_md.total_bytes_power;
                        ig_md.tree1_confidence = 110;
                    }
                    else if(ig_md.total_pkts==32){
                        ig_md.pkt_size_avg = ig_md.total_bytes>>5;
                        //ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>5;
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>1; 
                        Update_total_bytes_power();
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum-ig_md.total_bytes_power;
                        ig_md.tree1_confidence = 110;
                    }
                    else if (ig_md.total_pkts==256){
                        ig_md.pkt_size_avg = ig_md.total_bytes>>8;
                        //ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>8;
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>4;
                        Update_total_bytes_power();
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum-ig_md.total_bytes_power;
                        ig_md.tree1_confidence = 110;
                    }
                    else if(ig_md.total_pkts==512){
                        ig_md.pkt_size_avg = ig_md.total_bytes>>9;
                        //ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>9;
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>5; 
                        Update_total_bytes_power();
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum-ig_md.total_bytes_power;
                        ig_md.tree1_confidence = 110;
                    }
                    else if (ig_md.total_pkts==1024){
                        ig_md.pkt_size_avg = ig_md.total_bytes>>10;
                        //ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>10;
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>6;
                        Update_total_bytes_power();
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum-ig_md.total_bytes_power;
                        ig_md.tree1_confidence = 110;
                    }
                    else if(ig_md.total_pkts==2048){
                        ig_md.pkt_size_avg = ig_md.total_bytes>>11;
                        //ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>11;
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum>>7; 
                        Update_total_bytes_power();
                        ig_md.pkt_length_power_sum = ig_md.pkt_length_power_sum-ig_md.total_bytes_power;
                        ig_md.tree1_confidence = 110;
                    }
                    if (ig_md.tree1_confidence==110){
                        Feat10.apply();
                        Feat11.apply();
                        Feat12.apply();
                        Feat13.apply();
                        Feat14.apply();
                        Feat15.apply();
                        Feat16.apply();
                        Flow_Tree.apply();
                        ig_tm_md.ucast_egress_port = recirculate_port; //recirculate
                        if(ig_md.result>50){ //determined
                            ig_dprsr_md.digest_type = 2;  //digest
                        }
                    }
                }   // if result<50
                }   // owner
                else {
                    if (ig_md.act == ACT_NEW) {
                        Init_bin1_table.apply();
                        Init_bin2_table.apply();
                        Init_total_pkts_table.apply();
                        Init_total_bytes_table.apply();
                        Init_min_pkt_length_table.apply();
                        Init_max_pkt_length_table.apply();
                        Init_pkt_length_power_sum_table.apply();
                        ig_md.ipd = (bit<32>) ig_prsr_md.global_tstamp>>10;//us
                        Init_last_pkt_timestamp_table.apply();
                        Init_min_ipd_table.apply();
                        ig_tm_md.ucast_egress_port = recirculate_port; // claim tag + result in the recirculated pass
                    }
                    ig_md.result = 0;   // newcomer (taken, refused or short): per-packet verdict
                }
            }       // Flow_result miss
        }           // not recirculated

        Treatment.apply();

        // debug
        // D4c: carry the chosen way to the recirculated pass (original: dst_addr = 0 "for filter").
        hdr.ethernet.dst_addr = (bit<48>) ig_md.way;
        ig_tm_md.bypass_egress = 1;
        if(hdr.ipv4.src_addr==0){
            ig_dprsr_md.drop_ctl = 1;
        }
    }
}

Pipeline(SwitchIngressParser(),
         SwitchIngress(),
         SwitchIngressDeparser(),
         EmptyEgressParser(),
         EmptyEgress(),
         EmptyEgressDeparser()) pipe;

Switch(pipe) main;
