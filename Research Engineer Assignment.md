# **AI Research Engineer Take-Home Assignment**

**Duration:** 2–3 hours max.  
**AI tools:** Freely allowed, including Claude Code, Codex, ChatGPT, and other coding agents.

### **The Challenge**

Can you improve coding-agent performance by changing how a model uses inference-time compute, without training the model?

Explore techniques such as best-of-N sampling, iterative refinement, and different novel techniques. Your goal is to discover when additional inference compute creates genuine value and how to maximize coding performance under practical resource constraints.

### **1\. Choose Your Approach**

Start with DeepSWE, a benchmark for real-world software engineering tasks: [https\://github.com/datacurve-ai/deep-swe](https://github.com/datacurve-ai/deep-swe)

Select a reproducible subset of 10 tasks. Alternatively, use another objectively verifiable coding benchmark and justify your choice.

Form a specific hypothesis about how your inference-time strategy could improve performance over a simpler baseline.

### **2\. Implement and Experiment**

Build a minimal implementation and compare it against a meaningful baseline.

**Constraints:**

* Maximum  \$100 in metered inference API spend for the measured experiment.  
* No model fine-tuning or additional training.  
* Use the same tasks and correctness criteria across comparisons.

You may use any models, APIs, and libraries. Record actual token usage, costs, latency, and model-call counts.

### **3\. Analyze the Trade-offs**

**Required deliverable: Cost–performance Pareto curves.**

Compare your approach against the baseline across multiple inference budgets. Plot task success rate against actual inference cost.

Identify:

* The Pareto frontier and dominated configurations.  
* How performance changes as inference spending increases.  
* Where diminishing returns appear.  
* How latency, verification overhead, and reliability affect your conclusions.

Which strategy would you choose under a fixed budget, and why?

### **4\. Make a Research Bet**

Identify the biggest limitation of your approach.

What is the cheapest experiment that could disprove your hypothesis? If you had two additional weeks, what would you investigate next?

### **Deliverables**

1. **Implementation:** Reproducible code and experiment instructions.  
2. **Results:** Per-task outcomes, actual costs, latency, and model-call counts.  
3. **Pareto plot:** Cost versus task success across multiple inference budgets.  
4. **Research memo:** Maximum 3 pages, covering your hypothesis, findings, limitations, and next steps.  
5. **Agent trajectories:** Share relevant Claude Code, Codex, or other coding-agent session transcripts or exported logs. Include prompts, tool calls, code changes, experiment outputs, and important decision points where available. Redact credentials and sensitive information.

### **Evaluation Criteria**

* Research taste: 25%  
* Experimental rigor: 25%  
* Technical execution: 20%  
* Trade-off analysis: 20%  
* Intellectual honesty: 10%

We value informative experiments over sophisticated implementations. Negative results are acceptable. AI tools are encouraged; the quality of your reasoning and experimental decisions matters more than the volume of code.

