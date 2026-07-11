# Mathematical Formulations

To satisfy the academic rigor requirements of your dissertation, here are the formal mathematical definitions of your system architecture. You can copy these directly into your thesis (they are written in standard LaTeX math syntax).

## 1. Retrieval-Augmented Generation (RAG) Space

The Impact Assessor and Obligation Extractor utilize semantic search over Pinecone vector indexes. 

Let $\mathcal{D} = \{d_1, d_2, \dots, d_n\}$ be the corpus of historical contract parses and internal policies. A pre-trained embedding function (e.g., HuggingFace SentenceTransformer or LLaMA-3 embeddings) maps any text into a high-dimensional continuous vector space $\mathbb{R}^d$:

$$ \phi: \mathcal{T} \rightarrow \mathbb{R}^d $$

For a given user query or extracted obligation $q$, the system calculates its embedding $\mathbf{v}_q = \phi(q)$. The semantic similarity between the query and a document $d_i$ is computed using **Cosine Similarity**:

$$ \text{sim}(q, d_i) = \frac{\mathbf{v}_q \cdot \mathbf{v}_{d_i}}{\|\mathbf{v}_q\|_2 \|\mathbf{v}_{d_i}\|_2} = \frac{\sum_{j=1}^{d} v_{q,j} v_{d_i,j}}{\sqrt{\sum_{j=1}^{d} v_{q,j}^2} \sqrt{\sum_{j=1}^{d} v_{d_i,j}^2}} $$

The retrieval module returns the top-$k$ documents that maximize this similarity score to construct the augmented context window $C_q$:

$$ C_q = \underset{D \subset \mathcal{D}, |D|=k}{\text{argmax}} \sum_{d \in D} \text{sim}(q, d) $$

---

## 2. Agentic ReAct Loop as a Markov Decision Process (MDP)

The inner execution of the `ObligationExtractorAgent` and `ImpactAssessorAgent` follows the ReAct (Reasoning and Acting) paradigm. This can be formalized as a partially observable Markov Decision Process (POMDP).

At step $t$, the agent receives an observation $o_t \in \mathcal{O}$ (e.g., the output of an MCP tool). The agent generates a thought $h_t \in \mathcal{H}$ (the reasoning trace) and selects an action $a_t \in \mathcal{A}$ (calling a tool or emitting the final JSON). 

The LLM policy $\pi_\theta$ models the joint probability of generating the thought and action given the history of previous interactions $c_t = (o_1, h_1, a_1, \dots, o_t)$:

$$ P(h_t, a_t | c_t) = \pi_\theta(h_t, a_t | c_t) $$

The transition function $\mathcal{T}$ represents the external environment (the MCP tools), which yields the next observation based on the action taken:

$$ o_{t+1} = \mathcal{T}(a_t) $$

The agent loops until $a_t = \text{FINISH}$, yielding the final structured JSON object.

---

## 3. Blackboard Orchestration (LangGraph State Transition)

Unlike traditional peer-to-peer agent networks, **BlackBox-Regulatory-Guardian** utilizes a centralized Blackboard pattern (Shared State) for deterministic orchestration.

Let the `MultiAgentState` be a state vector $\mathbf{S}_t \in \mathcal{S}$ containing the aggregated conversation history, regulatory data, extracted obligations, and impact assessments at execution step $t$.

The orchestration graph consists of a set of specialized agent nodes $\mathcal{N} = \{N_{mon}, N_{ext}, N_{ass}, N_{rep}\}$. Each node $N_i$ acts as a deterministic transformation function on the global state:

$$ \mathbf{S}_{t+1} = \mathbf{S}_t \oplus f_i(\mathbf{S}_t) $$

Where $\oplus$ denotes the state update operation (e.g., dictionary key overwrite or list append) defined by the LangGraph reducer functions. 

The routing function $\mathcal{R}$ determines the next node to execute based on the current state:

$$ N_{next} = \mathcal{R}(\mathbf{S}_{t+1}) $$

This guarantees that data flows unidirectionally ($N_{mon} \rightarrow N_{ext} \rightarrow N_{ass}$) without recursive conversational loops, ensuring stability for enterprise ETL processing.
