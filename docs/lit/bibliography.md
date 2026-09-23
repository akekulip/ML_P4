# Bibliography for the downgrade-attack paper

Every entry below came back from a tool call during the 2026-09-23 round table. Where a DOI, arXiv id or URL was not returned, the entry says so. "Abstract only" means nobody read the full text; confirm those against the full text before citing any specific claim.

## Victim systems and the in-network ML they belong to

- **NetBeacon.** Zhou et al., USENIX Security 2023. Paper: https://www.usenix.org/system/files/usenixsecurity23-zhou-guangmeng.pdf. Code: https://github.com/IDP-code/NetBeacon. Read in full. Its fallback to a per-packet model is discussed in the paper but never measured.
- **Brain-on-Switch (BoS).** NSDI 2024. arXiv 2403.11090. Code: https://github.com/InspiringGroup-Lab/Brain-on-Switch. Read in full. Its escalation to the server tier is inline, and its collision budget exists only in the code.
- **IIsy.** Paper: arXiv 2205.08243, with a ToN 2024 version. Code: https://github.com/In-Network-Machine-Learning/IIsy. The public artifact is a Python simulation on the Iris dataset.
- **Planter.** Code: https://github.com/In-Network-Machine-Learning/Planter.
- **SpliDT.** SIGCOMM 2025, DOI 10.1145/3718958.3750475, also listed at NSDI'26 (https://www.usenix.org/conference/nsdi26/presentation/parvez). arXiv 2509.00397.
- **Proteus.** WWW 2026, DOI 10.1145/3774904.3792381. Abstract only. No code was found.
- **Helios.** WWW 2025, DOI 10.1145/3696410.3714742. Abstract only.
- **Flowrest.** ToN 2025. Code: https://github.com/nds-group/Flowrest.
- **ACORN.** arXiv 2512.09809. Abstract only. It has no hybrid tier, fallback or residency component.
- **Turbolearn.** APNet 2026. UNVERIFIED: the ACM page returned HTTP 403, and no code was found.
- **Also retrieved through Semantic Scholar (abstract only):**
  - pForest
  - SwitchTree
  - FlowLens (NDSS'21)
  - Taurus
  - N3IC
  - Mousika
  - Henna
  - Homunculus
  - Dryad
  - In-Forest
  - Leo (NSDI'24)
  - Jewel
  - Quark
  - Pegasus
  - FENIX
  - DUNE
  - PipeTree
  - LoFi
  - approximate-key caching (INFOCOM'21)
  - JITI
  - Peregrine
  - DIDA

## Attacks on data-plane feature extractors and data structures

- **SketchFeature.** Kim, Mirnajafizadeh, Kim, Jang and Nyang, NDSS 2025. Paper page: https://www.ndss-symposium.org/ndss-paper/sketchfeature-high-quality-per-flow-feature-extractor-towards-security-aware-data-plane/. Code: https://github.com/ISRL-EWHA/SketchFeature. Read in full. It attacks FlowLens and NetWarden. It compares NetBeacon only on clean traffic.
- **Sketch resilience through LSB sharing.** Yang et al., arXiv 2503.11777. Read in full. It attacks sketches only; no classifier is involved.
- **Probabilistic data structures in adversarial environments.** Clayton, Patton and Shrimpton, CCS 2019. https://eprint.iacr.org/2019/1221.pdf.
- **Count-Keeper.** Markelon, Filic and Shrimpton, CCS 2023. https://eprint.iacr.org/2023/1366.
- **Automated attack discovery in data plane systems.** Kang, Xing and Chen, CSET 2019. https://www.usenix.org/system/files/cset19-paper_kang.pdf.
- **CASTAN.** Pedrosa et al., SIGCOMM 2018. https://dl.acm.org/doi/10.1145/3230543.3230573.

## Timing attacks and rule-state exhaustion in SDN and programmable switches

- **Heracles.** Nam, Lim, Zhou, Gu and Kang, NDSS 2026. https://www.ndss-symposium.org/ndss-paper/on-the-security-risks-of-memory-adaptation-and-augmentation-in-data-plane-dos-mitigation/. Code: https://github.com/hcnam/sim-cerberus.
- **Sonchack et al.** ACSAC 2016. DOI 10.1145/2991079.2991081.
- **Wang, Mittal and Rexford.** CCR 2022. DOI 10.1145/3544912.3544914.
- **FloodGuard.** DSN 2015. https://people.engr.tamu.edu/guofei/paper/FloodGuard_DSN15.pdf.
- **Scotch.** CoNEXT 2014. https://conferences2.sigcomm.org/co-next/2014/CoNEXT_papers/p403.pdf.
- **Retrieved as metadata only:**
  - Liu, Reiter and Sekar, ICDCS 2017
  - LOFT (SecureComm 2017)
  - Tuple Space Explosion (CoNEXT 2019)
  - AVANT-GUARD
  - SPHINX
  - Poseidon (NDSS 2020)
  - Jaqen (USENIX Security 2021)

## Overload attacks on IDSs and slow paths

- **Insertion, Evasion, and Denial of Service.** Ptacek and Newsham, 1998. Semantic Scholar record dbddc17fecdfe3e5e1462beff80107a8397521a9.
- **Backtracking algorithmic complexity attacks against a NIDS.** Smith, Estan and Jha, ACSAC 2006. https://pages.cs.wisc.edu/~smithr/pubs/acsac2006.pdf.
- **Tolerating overload attacks against packet capturing systems.** Papadogiannakis et al., USENIX ATC 2012. https://www.usenix.org/conference/atc12/technical-sessions/presentation/papadogiannakis. The EuroSec 2010 companion paper on selective packet discarding was also retrieved.
- **Pigasus.** OSDI 2020. https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf. Pigasus 2.0: https://dl.acm.org/doi/pdf/10.1145/3546037.3546065.
- **Suricata exception policies (7.0.x documentation).** https://docs.suricata.io/en/suricata-7.0.11/configuration/exception-policies.html.

## Attacks that force the expensive path in ML models, and evasion

- **DeepSloth.** ICLR 2021. https://arxiv.org/pdf/2010.02432.
- **AESOP.** arXiv 2605.10987.
- **NetMasquerade.** arXiv 2510.14906.

## Caching and eviction structures in the data plane

- **HashPipe.** SOSR 2017. https://arxiv.org/pdf/1611.04825.
- **Elastic Sketch.** SIGCOMM 2018. https://conferences.sigcomm.org/events/apnet2018/papers/elastic_sketch.pdf.
- **P4LRU.** SIGCOMM 2023. DOI 10.1145/3603269.3604813.
- **Retrieved as metadata only:** CacheFlow (SOSR 2016), NetCache (SOSP 2017), DistCache (FAST 2019), HeavyKeeper, PRECISION, TinyLFU.

## Survey

- **Programmable data planes for intrusion detection.** Computer Networks, 2026. https://www.sciencedirect.com/science/article/pii/S1389128626002148. UNVERIFIED: nobody confirmed that it contains the sentence claiming BoS robustness is an open problem.
