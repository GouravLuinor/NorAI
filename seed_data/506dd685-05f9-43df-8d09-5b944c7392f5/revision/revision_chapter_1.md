# Revision Notes — Chapter 1: The Rise of Open-Weights Models and Local Deployment

## Key Exam Takeaways

- Open-weights models (e.g., Qwen 3.8) now offer performance parity with proprietary frontier models like Claude Opus 4.6.
- Quantization is essential for local execution, with 4-bit quantization being a standard for balancing memory usage and performance.
- Memory requirements scale linearly with context window size, necessitating significant VRAM/RAM for complex agentic tasks.
- Local deployment provides a cost-effective, private, and high-performance alternative to cloud-based AI services.

## Core Concepts Breakdown

- **Model Quantization**: The process of reducing the precision of model weights (e.g., from 16-bit to 4-bit) to decrease memory footprint and increase inference speed.
- **Agentic Terminal Coding**: A benchmark category measuring an AI's ability to autonomously execute commands and write code within a terminal environment.
- **Dynamic Quants**: An advanced compression technique allowing models to maintain high accuracy even when compressed to very low bit-depths, such as 1-bit.