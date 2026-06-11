# Virtuoso Specification

## 1. Overview

- Name: **Virtuoso** – CLI coding agent.
- Mission: Build enterprise-level software and apps step-by-step on an **8 GB RAM laptop** (no cloud required except optional expert fallback).
- Performance target: **Speed close to Claude Code CLI** (sub-second latency for simple edits; 2–5 s for complex reasoning steps) while solving hard multi-file tasks.

## 2. Core Architectural Blueprint

### Reasoning Engine

Virtuoso is not a single model. It is a **reasoning orchestrator** that coordinates multiple reasoning strategies and tool interactions. The architecture should support Tree of Thoughts or Graph of Thoughts workflows, enabling multi-step decomposition, exploration of alternative plans, and iterative refinement.

### Planner-Executor Split

- **Planner**: analyzes the task, creates a multi-step plan, and decomposes large requests into tractable subgoals.
- **Coder**: generates and edits code based on the plan and context.
- **Debugger**: validates generated changes, finds inconsistencies, and suggests fixes.
- **Reviewer**: checks output quality, verifies requirements, and summarizes the outcome.

### Sandboxed Execution

All external actions run in an isolated environment. Use `agentOS` or `Modal` to sandbox bash, file writes, and command execution. This protects the host machine and enables safe experiments.

### Tool Set

A minimal but powerful tool collection includes:

- `ripgrep` for fast repository search
- `glob` for file discovery
- `read_file` for safe file reads
- `write_file` for controlled updates
- `bash` for local shell commands inside the sandbox
- `fetch_url` for optional reference retrieval

### Persistent Memory

Store project-specific context in a repository-local constitution file: `.virtuoso-context.md`. This file captures project goals, coding standards, architecture notes, and agent preferences.

## 3. Open-Source Reference Projects (must study and/or reuse)

| Project | Why it matters |
|---|---|
| **OpenClaw** | Orchestration layer, session management, permission systems. |
| **Hermes Agent** (Nous Research) | 76% less code, 0.8 s cold start, 4500x faster search. |
| **SWE-agent-LM-7B** | Fine-tuned 7B model that solves real GitHub issues (teacher-student distillation). |
| **mini-swe-agent** | 100-line core, bash-only, >74% on SWE-bench. |
| **MapCoder-Lite** | Turns a single 7B model into 4 specialists – doubles accuracy. |
| **Oracle’s `agent-reasoning`** | 16 reasoning strategies (ToT, GoT, etc.) for any Ollama model. |
| **agentOS** | WebAssembly-based sandbox – near-zero cold starts, 32x cheaper. |
| **Qwen2.5-Coder 7B** (quantized Q4_K_M) | Primary model – fits in 8 GB RAM. |
| **OpenClacky** | 16-tool agent that matches Claude Code at lower cost. |
| **RAG-Lighter** | Lightweight retrieval for code search. |

## 4. Required Components (to be built or integrated)

- **Model serving** – Ollama with `qwen2.5-coder:7b` (Q4_K_M) and optionally `qwen2.5-coder:1.5b` for trivial tasks.
- **Reasoning orchestrator** – Wrap the model with `agent-reasoning` using Tree of Thoughts (depth 3, width 3).
- **Multi-agent loop** – Implement MapCoder-Lite pattern: Planner → Coder → Debugger → Reviewer, all using the same 7B model but different prompts.
- **Tools** – Use `ripgrep` for search, `glob` for file finding, and a safe `bash` executor inside a sandbox.
- **Sandbox** – Integrate `agentOS` or `Modal` for isolated, temporary environments.
- **Memory** – Maintain a rolling summary of the project state in a `.virtuoso` directory (last 10 actions, current file, errors).
- **Performance optimisation** – Cache frequently used code snippets; use `ripgrep` with `--max-count` to avoid context overrun.

## 5. Step-by-Step Development Roadmap

### Phase 0 – Setup (1 day)

- Install Ollama, pull `qwen2.5-coder:7b` (quantized).
- Create basic Python/Node CLI skeleton that can send prompts to Ollama.
- Implement a single-turn “code generation” command.

### Phase 1 – Reasoning & Tools (2–3 days)

- Integrate `agent-reasoning` – start with Tree of Thoughts for multi-step planning.
- Add `ripgrep` and `read_file` tools. Agent can search for a function name and read only relevant lines.
- Implement a **Plan-Review-Execute** loop: plan generated, user (or self) approves, then execute.

### Phase 2 – Multi-Agent Specialisation (3–5 days)

- Implement MapCoder-Lite pattern: four specialised sub-agents (Planner, Coder, Debugger, Reviewer) all calling the same model but with different system prompts.
- Add a simple in-memory “board” to pass tasks between them.

### Phase 3 – Sandbox & Safety (2–3 days)

- Integrate `agentOS` (or `Modal`). All bash commands and file writes go into a temporary sandbox that resets after each task.
- Implement permission prompts for dangerous operations (e.g., network calls, deleting files outside sandbox).

### Phase 4 – Memory & Context Management (2 days)

- Implement a sliding window summariser that keeps the last 10 actions and current file contents under 4k tokens.
- Store project constitution (`.virtuoso-context.md`) that the agent reads on each run.

### Phase 5 – Expert Fallback (optional, 2 days)

- Add a “call expert” mode: when the local model fails twice, send a request to a cloud model (Claude Code API or GPT-5.5) for that specific subtask and cache the solution for local fine-tuning.

### Phase 6 – Testing & Benchmarking (2–3 days)

- Run on SWE-bench lite (subset) – target ≥40% resolution.
- Measure latency per step – should stay under 5 seconds for 90% of operations.

## 6. Detailed Implementation Guidelines

- **Language**:
  - Python for speed of prototyping.
  - Go/Rust for final binary.
  - Recommendation: start with Python, then rewrite performance-critical parts in Rust.

- **CLI interface**:
  - Commands like `/plan`, `/code`, `/debug`, `/review`, `/status`.

- **Configuration file**:
  - `virtuoso.yaml` (model name, sandbox type, max tokens, etc.).

- **Logging**:
  - Every reasoning step and tool call logged to `.virtuoso/logs/` for debugging.

## 7. Expected Performance & Trade-offs

- **Speed**:
  - With Tree of Thoughts (3 branches), a complex task may take 10–15 seconds (vs. 2–3 seconds for Claude Code on the same task).
  - Simpler edits will be under 2 seconds.

- **Accuracy**:
  - On SWE-bench, expect 40–45% resolve rate (Claude Code ~70%).
  - For well-defined enterprise workflows (spec-driven), practical effectiveness will be much higher.

- **Memory**:
  - ~6–7 GB RAM used by Ollama + agent process. Leaves headroom for small IDEs.

## 8. References & Further Reading

- [SWE-agent paper](https://arxiv.org/abs/2405.15793)
- [MapCoder paper](https://arxiv.org/abs/2405.11412)
- [Tree of Thoughts paper](https://arxiv.org/abs/2305.10601)
- [AgentMesh multi-agent framework](https://github.com/langchain-ai/agentmesh)
