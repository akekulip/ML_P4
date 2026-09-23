# MVM brief (verbatim, as pasted by Philip on 2026-09-22)

> Source: ChatGPT conversation, pasted into Claude Code. Kept verbatim as the original design
> brief. Where research changed it, see `docs/research_findings.md` and the plan in
> `WORKING_NOTES.md` (four items marked CHANGED: replay dataset, Planter, framing, ports as features).

---

Yes—assuming you mean neuron.

In a standard feed-forward ANN, the output of one neuron can affect many neurons in the next layer through weighted connections:

$$ a_j = \sigma\left(\sum_i w_{ij}x_i+b_j\right) $$

So if neuron \(i\)'s output changes, every downstream neuron connected to it can change as well. That effect can then propagate through later layers:

```
Input
  ↓
Neuron A
  ↓
Neurons B, C, D
  ↓
Neurons E, F
  ↓
Output
```

That is effectively a cascade of influence through the network.

Two distinctions matter:

Within the same layer: in a normal feed-forward network, neurons usually do not directly affect each other.
Across layers: yes, neurons influence downstream neurons, potentially all the way to the final output.

For example:

```
        n1
       /  \
      ↓    ↓
     n3    n4
      \    /
       ↓  ↓
        n6
```

A change in n1 can alter both n3 and n4, which can then jointly alter n6.

There is also another kind of cascade during training. Backpropagation moves information in the opposite direction:

```
Forward:
input → hidden layers → output

Backward:
loss ← gradients ← hidden layers
```

So a neuron's weights affect downstream predictions during inference, while downstream error gradients affect how upstream weights are updated during training.

For recurrent neural networks, it becomes even more coupled because neuron/state outputs can influence future states:

$$ h_t=f(x_t,h_{t-1}) $$

so an effect at time \(t\) can cascade through \(t+1,t+2,\ldots\).

And this may connect to what you're thinking about: not every neuron contributes equally to every inference. In networks using ReLU, gating, sparsity, mixture-of-experts, conditional computation, etc., a particular input may effectively activate only part of the computation graph. That opens a very different line of thinking around input-dependent execution paths in ANNs.

---

**Today 11:26 AM — Can we do mvm as a graduate class project ??**

Yes. MVM can make a strong graduate class project, but the full research vision is too large for one semester. I would scope it as MVM-Lite: a demand-paged inference cache for a programmable data plane.

The class project does not need to solve the new research problem we were just isolating around irreversible feature state. Its purpose can be to prove the basic MVM systems abstraction works end-to-end.

The project I would build

```
                     Full DT / RF
                  Python inference server
                         │
                         │ miss
                         ▼
Packets ──► P4 Switch ──► MVM lookup
             │                │
             │             HIT│
             │                ▼
             │           prediction
             │
             └── miss ──► backend
                            │
                      full inference
                            │
                      page promotion
                            │
                            ▼
                    P4Runtime update
```

The switch contains only a bounded number of model pages. For the class version, define a page very simply as either a decision-tree subtree or an exact decision region. The complete model stays in Python.

This is technically practical because P4Runtime already supports inserting, modifying, deleting, and reading match-action table entries dynamically, which gives you the mechanism for loading and evicting MVM pages at runtime. BMv2 also supports the match types you would need—exact, ternary, range, and LPM—and runtime table insertion, so you do not need a physical Tofino switch to demonstrate the concept.

Use Planter rather than writing all ML→P4 machinery yourself

This is important for keeping the scope reasonable.

Planter already supports DT, RF, XGBoost and several other ML models, and can generate P4 implementations for BMv2 and Tofino. You can therefore use Planter as the full-model/reference implementation, then add MVM around it instead of spending half the semester reinventing model compilation.

A very practical scope would be:

Train one Decision Tree first. Don't start with ANN.
Compile/translate the tree into model pages.
Give the switch room for only, say, 8, 16, 32 or 64 pages.
Send traffic through BMv2.
If the relevant page is resident, infer immediately.
Otherwise, send the request to the Python backend.
Backend performs the complete inference.
Track page popularity.
Periodically load hot pages through P4Runtime and evict cold pages.
Measure what happens as cache capacity and traffic distribution change.

That is enough for a serious class project.

What the research question becomes

Don't present it as:

Can P4 run ML?

That's already established.

Present it as:

Can a programmable switch execute a model larger than its available inference resources by keeping only the model's current working set in the data plane?

Now you have a clean experimental hypothesis:

$$ \text{model working set} \ll \text{entire model} $$

for nonuniform workloads.

You can create an experiment where a tree has, for example,

$$ N=1000 $$

logical decision regions while the switch can hold only

$$ C=64. $$

Then vary workload locality.

Uniform workload

Every model region is equally likely:

$$ P(R_i)=1/N. $$

MVM should perform badly. That's actually useful.

Skewed workload

Maybe:

$$ 20\%\text{ of regions} \rightarrow 80\%\text{ of inference requests}. $$

Now MVM should achieve a much larger hit rate.

Workload shift

First:

R1–R20 hot

then halfway through:

R200–R220 hot

Now demonstrate that the data-plane working set adapts.

That third experiment is especially good because a static model partition cannot adapt.

Your key graph

The most important result could simply be:

$$ \text{Data-plane capacity} \quad\text{vs}\quad \text{Inference hit rate} $$

For example:

| Resident pages | MVM hit rate |
|---|---|
| 8 | 38% |
| 16 | 57% |
| 32 | 78% |
| 64 | 91% |
| 128 | 97% |

Then another plot:

$$ \text{time} \quad\text{vs}\quad \text{hit rate} $$

with a workload distribution change halfway through. You should see hit rate fall and then recover as MVM repopulates.

That visually tells the entire story.

Baselines matter

I would use three.

Full backend: every inference goes to Python.

Static: put the top \(C\) model regions into the switch once and never change them.

MVM: dynamically select the \(C\) resident regions.

You then compare:

$$ \text{hit rate} $$ $$ \text{backend inference count} $$ $$ \text{average inference latency} $$ $$ \text{table occupancy} $$ $$ \text{rule-update rate} $$

and, importantly,

$$ \text{prediction equivalence}. $$

MVM should return exactly the same predictions as the original model.

You don't need to claim a new ML algorithm.

What I would explicitly NOT put in the class project

Do not attempt all of this simultaneously:

- RDMA/RoCE
- GPU
- SmartNIC
- ANN
- dynamic feature-state materialization
- adversarial cache pollution
- sophisticated CIR synthesis
- Tofino-specific optimization
- multi-model tenancy
- cache coherence across model versions
- novel eviction algorithm
- hardware external memory

Those are where a semester project turns into a PhD dissertation.

For the class version:

$$ \boxed{ \text{DT + BMv2 + Python backend + P4Runtime + dynamic pages} } $$

is enough.

A very reasonable implementation

```
                  ┌────────────────────────┐
                  │ Python                 │
                  │                        │
                  │ complete DT            │
                  │ LFU/LRU manager        │
                  │ P4Runtime controller   │
                  └───────────┬────────────┘
                              │
                    install / evict
                              │
                              ▼
                  ┌────────────────────────┐
traffic ─────────►│ BMv2 P4 switch         │
                  │                        │
                  │ page_table             │
                  │ ┌────────────────────┐ │
                  │ │ model_page_id     │ │
                  │ │ predicate         │ │
                  │ │ prediction        │ │
                  │ └────────────────────┘ │
                  └──────────┬─────────────┘
                       HIT   │   MISS
                       │     │
                       ▼     ▼
                    result  Python
```

And because Planter supports standard classification and performance-oriented P4 mappings on BMv2, you already have a reasonable existing platform to build from rather than starting with raw P4.

Then the class project can feed directly into the research

This is the attractive part.

Class project:

Does demand-paged ML inference work in a programmable data plane?

Then, assuming it works, your research asks much harder questions:

```
Class project
     │
     ▼
Model pages / working set
     │
     ├──────────────► exact semantic regions
     │
     ├──────────────► stateful feature working sets
     │
     ├──────────────► irreversible feature state
     │
     ├──────────────► ASIC + SmartNIC hierarchy
     │
     └──────────────► inference amplification attacks
```

So none of the project effort is wasted.

Given that you already work with P4/Tofino and have dealt with real pipeline-resource limitations, I would actually make BMv2 completion the required deliverable and a Tofino-1 port the stretch goal. That prevents BF-SDE/compiler issues from consuming the entire class project while still giving you a path to a much stronger hardware result afterward.

If this is, say, a 6–10 week graduate networking project, MVM-Lite is very appropriately scoped. The full speculative feature-state version we arrived at today is not; I would protect that for the research project.

---

**Today 2:47 PM — Good . Because this is a Machine Learnign class, venthough the P4 implementation will take time, I want to get in unto something that thw class and teacher will appereciate....research more including dataset to use, performance metric to measure etc.**

Yes. I would reshape it so the ML contribution is the center of the class project, while P4 becomes the deployment proof.

The project I would pitch is:

MVM: Workload-Adaptive Virtual Memory for Decision-Tree Inference

How model complexity, temporal inference locality, and distribution shift affect the ability to execute ML under a bounded inference-memory budget.

That gives your professor a real ML study: classification, hyperparameter tuning, pruning, imbalance, temporal distribution shift, model complexity, inference-path locality, and deployment fidelity. P4 is then the interesting systems endpoint.

## 1. The questions we should actually answer

I would structure the class project around four research questions.

RQ1 — Prediction: Can a compact decision tree using network-observable features detect malicious traffic with competitive predictive performance?

RQ2 — Inference locality: When real network traffic is processed chronologically, are model executions uniformly distributed across the tree, or does a small subset of leaves account for most predictions?

RQ3 — Complexity vs. cacheability: As we increase tree depth/leaf count, does classification improve while the inference working set becomes less cacheable?

RQ4 — Adaptation: Given room for only \(K\) model pages/leaves, can MVM adapt to changing traffic distributions and preserve a high fraction of in-data-plane inference compared with static placement?

Those questions make this an ML project even if the P4 implementation is incomplete.

## 2. The hypotheses

I would state explicit hypotheses before running anything.

H1 — Execution locality exists

For chronological traffic,

$$ P(L_i) $$

over decision-tree leaves will be highly nonuniform.

So perhaps 10–20% of the leaves handle 80–90% of inference requests.

That is the fundamental justification for MVM.

H2 — More complex models are harder to virtualize

Increasing:

$$ \text{max\_depth} $$

or

$$ \text{number of leaves} $$

may improve F1, but should split traffic into increasingly many execution regions.

Thus:

$$ \text{predictive performance}\uparrow $$

while potentially:

$$ \text{working-set locality}\downarrow. $$

That accuracy/cacheability tradeoff is a genuinely nice ML experiment.

H3 — Static placement fails under shift

If the traffic distribution moves from:

Leaves {3,7,11,14} hot

to:

Leaves {25,28,31,39} hot

a static top-\(K\) implementation should degrade.

MVM should adapt.

H4 — Paging does not change the ML model

If a model page is resident, its prediction must equal the original tree. If it misses, the backend executes the original tree.

Therefore:

$$ \text{Fidelity}_{MVM}=100\% $$

should be achievable in the basic design.

This separates model accuracy from deployment fidelity.

## 3. Dataset: I would use TON_IoT as the primary dataset

After looking through the alternatives, my first choice is the TON_IoT network dataset.

It was designed around IoT/IIoT and Industry 4.0 environments and includes network traffic plus attacks such as DoS, DDoS, ransomware, backdoor, injection, scanning, password attacks, XSS, and MITM. The official release provides raw and processed datasets and, importantly for us, attack ground truth with timestamps.

The processed network dataset contains fields such as:

```
timestamp
source/destination port
protocol
service
duration
source/destination bytes
connection state
source/destination packet counts
DNS fields
HTTP fields
SSL fields
...
label
attack type
```

The timestamp is exactly what MVM needs for chronological replay.

The commonly used TON_IoT train/test network sample contains roughly 461k observations; one published preprocessing study reports about 300k benign and 161k malicious observations and also highlights host-specific fields such as source/destination IPs that should be removed when building a generalizable classifier.

Official TON_IoT dataset

Why it fits MVM unusually well

We need time, not just rows.

Do not shuffle this dataset immediately.

We want:

```
t1 → flow → leaf 17
t2 → flow → leaf 17
t3 → flow → leaf 4
t4 → flow → leaf 17
...
```

because that sequence lets us measure:

- temporal locality;
- cache hits;
- reuse distance;
- workload shifts;
- adaptation time.

A shuffled intrusion dataset destroys much of the MVM question.

## 4. Secondary dataset: IoT-23

If we have enough time, this is the best second dataset.

IoT-23 contains 23 separate IoT traffic scenarios: 20 malware captures and 3 benign captures, including real IoT devices. The project reports more than 500 hours of traffic, over 760 million packets and roughly 325 million labeled flows. It provides the PCAPs and timestamped Zeek conn.log.labeled flows.

We absolutely would not process all 325 million flows for a class project.

Pick perhaps:

- one Mirai scenario;
- another malware family;
- Amazon Echo benign;
- Philips Hue benign;
- one additional scenario.

IoT-23 becomes our:

“Does the locality observation generalize beyond TON_IoT?”

experiment.

Official IoT-23 dataset

## 5. I would not make CICIDS2017 the main dataset

It is popular and gives PCAPs plus more than 80 CICFlowMeter features.

But that popularity is partly why I would avoid it as the primary benchmark. There are substantial concerns around evaluation methodology and source-file effects. A recent reproducibility audit, for example, shows dramatically different results between random splitting and source-file holdout because attack families are tied strongly to particular source files.

Using TON_IoT + IoT-23 will make the project look more considered than:

“We downloaded CICIDS, did an 80/20 random split, and got 99.9% accuracy.”

## 6. The features should be deliberately constrained

This is another place where the professor can see genuine ML thinking.

I would create two feature sets.

Feature set A — sanitized ML baseline

Use most useful network features but remove:

```
timestamp       # retain only for ordering
src_ip
dst_ip
label
attack type
unique IDs
```

IP addresses are especially dangerous because models can simply learn the experiment topology rather than attack behavior. TON_IoT studies have explicitly removed timestamp and source/destination IPs for this reason.

Feature set B — data-plane-feasible features

Something roughly like:

```
src_port
dst_port
protocol
duration
src_bytes
dst_bytes
src_pkts
dst_pkts
src_ip_bytes
dst_ip_bytes
TCP/connection state
```

The standardized NF-ToN-IoT work is useful here because its compact NetFlow version uses fields such as ports, protocol, bytes, packets, TCP flags and flow duration, while its V2 dataset expands to 43 common NetFlow features.

This gives us another ML question:

How much predictive accuracy do we sacrifice by limiting ourselves to network/data-plane-computable features?

Excellent class material.

## 7. Don't make the P4 switch compute these features initially

That will consume the whole semester.

For the class project:

```
precomputed flow features
         ↓
ML classifier
         ↓
MVM
         ↓
P4 deployment
```

For the P4 proof, put the features into a test/custom packet header, like the standard classification workflow used by Planter.

Actual line-rate feature extraction can be future work.

That keeps us focused on ML.

## 8. Models: use more than just DT

I would train three models:

| Model | Purpose |
|---|---|
| Logistic Regression | simple linear baseline |
| Decision Tree | main MVM model |
| Random Forest | stronger nonlinear accuracy baseline |

Possibly XGBoost if the class has covered boosting, but it isn't necessary.

We should demonstrate:

We selected DT for MVM because of its model structure and hardware suitability, not because it happened to be the only model we tried.

Planter already supports DT, RF, XGBoost and numerous other models and can generate implementations for BMv2 and Tofino.

## 9. Decision-tree pruning becomes an important ML experiment

This may be my favorite part of the project.

Train trees with:

$$ d_{\max}\in \{4,6,8,10,12,16,\text{None}\} $$

and/or vary:

$$ \text{max\_leaf\_nodes}. $$

Also experiment with cost-complexity pruning:

$$ \alpha. $$

For every tree record:

- Macro F1
- MCC
- depth
- number of nodes
- number of leaves
- average path length
- leaf entropy
- top-K leaf coverage
- MVM hit rate

Then we can discover something like:

```
depth     Macro-F1     leaves     K=32 hit rate
------------------------------------------------
4          .84           13            100%
6          .91           41             93%
8          .94          117             81%
10         .946         301             62%
14         .947         890             39%
```

If we got a result shaped like that, it would be extremely useful.

The best model for conventional ML might be depth 14.

The best model for bounded in-network inference might be depth 8.

Now we've turned deployment constraints into an ML model-selection problem.

## 10. That gives us a new model-selection objective

Ordinary model selection says:

$$ M^*=\arg\max_M F_1(M). $$

Our experiment can examine:

$$ M^* = \arg\max_M \left[ F_1(M) - \lambda C(M) \right], $$

where \(C(M)\) could represent inference working-set cost.

Or don't invent a combined score at all—show the Pareto frontier:

```
                 ↑ F1
                 │
             ●
           ●
        ●
     ●
  ●
  └────────────────────► resident model pages
```

Models on the frontier are not dominated in both accuracy and resource cost.

That is very ML-class appropriate.

## 11. Primary ML metrics

Do not headline accuracy.

Cybersecurity datasets are imbalanced.

For binary benign/malicious classification I would report:

Macro F1
$$ F1_{macro} = \frac{F1_{\text{benign}}+F1_{\text{attack}}}{2}. $$
Attack-class precision/recall/F1

Especially:

$$ Recall_{\text{attack}} = \frac{TP}{TP+FN}. $$

Missing an attack matters.

Matthews Correlation Coefficient
$$ MCC= \frac{TP\cdot TN-FP\cdot FN} {\sqrt{(TP+FP)(TP+FN)(TN+FP)(TN+FN)}}. $$

MCC is particularly useful under imbalance.

PR-AUC

For binary detection, I would prioritize precision-recall AUC over ROC-AUC when the positive class is relatively rare.

Balanced accuracy
$$ BA= \frac{TPR+TNR}{2}. $$

And show the confusion matrix.

## 12. Multiclass is a valuable extension

TON_IoT gives:

```
normal
backdoor
ddos
dos
injection
mitm
password
ransomware
scanning
xss
```

This is much harder because some classes are rare.

Make:

Primary task
$$ \text{benign vs malicious} $$
Extension
$$ 10\text{-class classification}. $$

For multiclass use:

- macro-F1;
- per-class recall;
- balanced accuracy;
- confusion matrix.

This also produces a richer MVM experiment:

Are some attack classes concentrated in a small number of leaves while others spread across the tree?

That's a very interesting ML question.

## 13. The new metrics specific to MVM

This is where the project becomes distinctive.

A. Leaf popularity

For each sample:

$$ L(x)=\text{leaf ID reached by }x. $$

Estimate:

$$ p_i=P(L=L_i). $$

Plot leaf rank against frequency.

If the curve is heavily skewed, MVM has a reason to exist.

B. Top-\(K\) coverage

Sort leaves by frequency:

$$ p_{(1)}\ge p_{(2)}\ge\ldots $$

and define:

$$ C(K)= \sum_{i=1}^{K}p_{(i)}. $$

Example interpretation:

$$ C(32)=0.87 $$

means:

the 32 most frequently executed leaves handle 87% of inference requests.

This may be the single most important ML/MVM metric.

C. Working-set size

Report:

$$ W_{90} $$

= minimum number of leaves needed to cover 90% of test inferences.

Similarly:

$$ W_{95}, W_{99}. $$

Don't claim this metric as our fundamental theoretical invention; just use it as a very understandable experimental measurement.

D. Leaf entropy
$$ H(L)= -\sum_i p_i\log p_i. $$

Normalize:

$$ H_N= \frac{H(L)}{\log N_L}. $$

Interpretation:

```
H_N ≈ 0  → highly concentrated inference
H_N ≈ 1  → inference spread uniformly
```

This lets us compare trees with different numbers of leaves.

That is a strong ML metric.

E. Reuse distance

For chronological samples:

```
L4, L4, L17, L4, L2, L17, ...
```

measure how many distinct leaves occur between accesses to the same leaf.

This directly characterizes whether caching should work.

## 14. Distribution shift should be measured, not just eyeballed

Divide the held-out chronological stream into windows:

$$ D_1,D_2,\ldots,D_T. $$

For each window compute leaf distribution:

$$ P_t(L). $$

Then measure divergence from the training distribution or preceding window.

For example, Jensen-Shannon divergence:

$$ JS(P_t\Vert P_{t-1}). $$

Then plot:

```
time
│
├── JS divergence
├── MVM hit rate
└── cache updates
```

Now we may see:

```
distribution shift ↑
        ↓
hit rate ↓
        ↓
cache adapts
        ↓
hit rate recovers
```

That makes the adaptation story quantitatively convincing.

## 15. The actual MVM experiment

For a trained tree with perhaps 500 leaves, artificially constrain the "ASIC" to:

$$ K\in \{8,16,32,64,128,256\}. $$

Only \(K\) leaves may be resident.

On each inference:

```
feature vector x
      ↓
resident leaf rule?
   /          \
 YES           NO
 │             │
prediction   backend tree
               │
             leaf ID
               │
        cache/admission policy
```

## 16. Compare multiple page-replacement policies

We should not just show one algorithm.

Use:

Static Top-K

Select the most frequent leaves from training.

Never change them.

This is the most important baseline.

LRU

Evict least recently used.

LFU

Evict least frequently used.

Decayed LFU

Use exponentially decaying popularity:

$$ S_i(t) = \gamma S_i(t-1)+I[L_t=i]. $$

This forgets old traffic patterns.

That is probably the most natural MVM policy for distribution shift.

Oracle

For each evaluation window, assume we magically know its top \(K\) leaves.

This isn't deployable.

It is the upper bound.

So our plots become:

```
Oracle
Adaptive MVM
LRU
LFU
Static
```

Excellent experimental structure.

## 17. MVM system metrics

Cache hit rate
$$ HR= \frac{N_{\text{switch}}} {N_{\text{total}}}. $$

Backend offload reduction
$$ OR= 1- \frac{N_{\text{backend,MVM}}} {N_{\text{backend,baseline}}}. $$

If baseline sends everything to backend:

$$ OR=HR. $$

Cache churn
$$ CR= \frac{\text{insertions}+\text{evictions}} {\text{number of requests}}. $$

Important because constant P4 table updates are undesirable.

Adaptation time

After detecting a workload change:

$$ T_{\text{recover}} $$

= time/number of samples until MVM returns to perhaps 90% of its new steady-state hit rate.

Miss regret

Compare to oracle:

$$ R= M_{\text{MVM}}-M_{\text{oracle}}. $$

Lower is better.

This is an elegant online-performance metric.

## 18. Fidelity is separate from accuracy

This distinction needs to be explicit in the paper/presentation.

Suppose the original tree has:

$$ F1=0.93. $$

MVM does not magically improve this.

It should preserve:

$$ \hat y_{MVM}(x) = \hat y_{DT}(x) $$

for every sample.

Define:

$$ \text{Fidelity} = \frac{ |\{x:\hat y_{MVM}(x)=\hat y_{DT}(x)\}| } N. $$

Target:

$$ \boxed{100\%} $$

unless P4 quantization/mapping introduces differences.

This is especially useful with Planter because Planter already distinguishes the original model's classification, theoretical mapped-pipeline classification, and actual P4-target classification.

## 19. Latency evaluation

If we get BMv2 running, measure:

$$ L_{\text{hit}} $$

and

$$ L_{\text{miss}}. $$

Average:

$$ E[L] = HR\cdot L_{\text{hit}} + (1-HR)\cdot L_{\text{miss}}. $$

Report:

- mean;
- p50;
- p95;
- p99.

But we must be careful:

BMv2 latency is not Tofino latency.

Use BMv2 to demonstrate behavior and correctness, not to claim ASIC line-rate performance.

If you get access to the Tofino-1:

stretch goal: compile/run the same bounded-leaf mechanism there and report actual resources.

## 20. What exactly is an MVM "page"?

For this class project, make this extremely simple:

$$ \boxed{\text{one decision-tree leaf/path = one model page}} $$

Each leaf already corresponds to a region of feature space:

```
duration ≤ 1.2
AND packets > 7
AND dst_port ≤ 1024
       ↓
malicious
```

Page:

```
page_id = leaf_37
predicates = {...}
class = malicious
```

No CIR generation.

No vote-aware expansion.

No new tree algorithm.

Those are distractions for this project.

## 21. Implementation path using Planter

Planter is useful because it already maps trained models such as DT/RF/XGBoost onto programmable targets, including BMv2 and Tofino. Its purpose is specifically rapid prototyping of in-network ML inference.

Planter repository

For a DT, Planter-style mapping commonly separates:

```
feature tables
      ↓
feature codes
      ↓
tree/code table
      ↓
class
```

Recent work adopting the Planter scheme describes feature threshold tables followed by code tables representing tree paths/leaves.

That gives us a very practical MVM-Lite implementation:

```
Feature encoding tables
     always resident

             ↓

Final tree/leaf entries
     dynamically paged

             ↓
      K-entry budget
```

On a missing final leaf entry:

default action → backend

The backend:

- evaluates the complete tree;
- gets the correct leaf;
- updates MVM state;
- optionally installs that leaf entry.

That's achievable.

And we can be transparent that MVM-Lite virtualizes the decision portion, not every byte of the model representation.

## 22. The figure I most want from this class project

I want this:

```
Macro F1
  ↑
  │                        ●
  │                    ●
  │                ●
  │           ●
  │       ●
  └──────────────────────────────→
       inference working-set size
```

Each point is a different tree complexity.

Underneath it, another plot:

```
MVM hit rate
100% │
     │         Oracle ─────────
 80% │       MVM ─────────────
     │      /
 60% │  Static ────────\
     │                  \
 40% │                   \
     └────────────────────────── time
                      ↑
                workload shift
```

Together they tell the entire project story.

## 23. Experimental matrix

I would keep the core matrix roughly this size:

| Dimension | Values |
|---|---|
| Dataset | TON_IoT; IoT-23 stretch |
| Task | binary; multiclass stretch |
| Models | LR, DT, RF |
| DT depth | 4, 6, 8, 10, 12, 16 |
| MVM capacity | 8, 16, 32, 64, 128, 256 leaves |
| Placement | Static, LRU, LFU, Decayed-LFU, Oracle |
| Evaluation | IID + chronological |
| Deployment | Python simulator → BMv2 → Tofino stretch |

That is already a lot of experiments.

## 24. Ablations your professor will appreciate

Do at least these:

Without identifiers vs with identifiers. Show what happens if IP addresses are included. If performance jumps suspiciously, explain why that may be topology memorization rather than genuine attack learning.

Full features vs deployable features. Quantify the predictive price of P4-feasible features.

Shuffled vs chronological inference. Show that MVM depends on temporal locality; shuffling should damage cache performance.

Pruned vs unpruned tree. Show the accuracy/resource-locality tradeoff.

Static vs adaptive placement. This validates MVM's central claim.

Those ablations make it feel much more like a research project than an engineering demo.

## 25. Evaluation hygiene

A few things I would insist on:

- Do not perform SMOTE or other oversampling before the split.
- Never use type as an input feature—it is the detailed label.
- Keep ts for ordering but not classification.
- Exclude source/destination IP in the main experiments.
- Fit encoders/scalers using training data only.
- Tune hyperparameters on validation only.
- Freeze the model before the MVM streaming experiment.
- Do not retrain the tree during MVM tests; otherwise we mix model drift with cache adaptation.
- Run cache experiments with a cold start.
- Report several seeds where randomness exists.
- Report confidence intervals or bootstrap intervals for the primary ML metrics.

This is the sort of methodology that will matter more to an ML professor than whether the P4 table has 17 or 18 lines of code.

## 26. Suggested project scope

I would classify deliverables like this.

**Must complete**

Python/ML:

- TON_IoT cleaning;
- binary classifier;
- LR/DT/RF comparison;
- DT hyperparameter/pruning study;
- inference leaf analysis;
- MVM simulator;
- static/LRU/LFU/adaptive policies;
- temporal workload-shift evaluation;
- complete performance plots.

If we finish only this, the project can still earn a strong grade.

**Should complete**

BMv2:

- P4 representation of bounded leaf pages;
- runtime insert/delete;
- hit versus miss;
- backend fallback;
- end-to-end fidelity.

**Stretch**

Tofino-1:

- compilation;
- table/resource occupancy;
- runtime updates;
- hardware latency/throughput.

That ordering protects the ML class grade from P4 compiler problems.

## 27. The class-project contribution statement

I would not make an aggressive novelty claim. Something like this is much cleaner:

This project investigates whether ML inference itself exhibits a temporal working set. Using network intrusion classification as a case study, we quantify how decision-tree complexity affects both predictive performance and inference locality, and evaluate a bounded adaptive model-memory layer that keeps only frequently exercised decision regions in the fast path while preserving the predictions of the complete model.

Then the three contributions are:

- Measurement: quantify decision-tree inference locality under chronological network traffic.
- ML analysis: characterize the relationship between model complexity, predictive quality, and working-set size.
- Prototype: implement MVM, dynamically materializing a bounded working set in a programmable data plane with exact backend fallback.

That is coherent.

**What I would choose right now**

- Dataset: TON_IoT network dataset.
- Primary task: binary intrusion detection.
- Main model: pruned Decision Tree.
- Comparators: Logistic Regression + Random Forest.
- MVM page: one DT leaf/path.
- Capacities: 8–256 leaves.
- Policies: static top-K, LRU, LFU, decayed-LFU, oracle.
- Primary ML metric: macro-F1 + MCC + attack recall.
- Primary MVM metric: hit/offload rate.
- Most important analysis metric: top-\(K\) leaf coverage and \(W_{90}/W_{95}\).
- Primary shift metric: windowed leaf-distribution Jensen-Shannon divergence.
- Deployment: Python first, BMv2 second, Tofino stretch.

If the experiment reveals that, say, a 300-leaf DT needs only 32 resident leaves to serve 85–90% of a chronological workload, while a deeper 900-leaf model improves macro-F1 by only 0.3 points but doubles \(W_{90}\), you have a class project with a much more interesting conclusion than simply “P4 can run a decision tree.”
