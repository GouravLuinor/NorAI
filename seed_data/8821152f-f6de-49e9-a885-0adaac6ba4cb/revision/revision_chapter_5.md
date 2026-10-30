# Revision Notes — Chapter 5: Proving Correctness with Induction

## Key Exam Takeaways

- Induction is used to prove algorithm correctness for arbitrarily large inputs.
- The inductive hypothesis must be defined to maintain a specific property as the input size increases.
- The base case (e.g., K=0) provides the starting point for the inductive chain.
- Case analysis during the inductive step isolates the logic to smaller, manageable segments.
- The goal of a proof is to communicate the algorithm's logic clearly enough for implementation.

## Core Concepts Breakdown

- **Induction**: A mathematical technique used to prove that an algorithm works for all possible input sizes by establishing a base case and an inductive step.
- **Inductive hypothesis**: A statement assumed to be true for a value K, which is then used to prove the statement holds for K+1.
- **Base case**: The simplest possible input (e.g., zero students) where the algorithm's correctness is trivially verified.
- **Case analysis**: Breaking the inductive step into distinct scenarios to show that the algorithm maintains its correctness property regardless of the specific input conditions.