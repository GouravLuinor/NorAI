# Revision Notes — Chapter 3: Mathematical Mechanisms: Weights, Biases, and Activation

## Key Exam Takeaways

- A neuron's output is calculated as $\sigma(\sum w_i a_i + b)$, where $\sigma$ is the sigmoid function.
- Weights determine the feature pattern, while biases determine the activation threshold.
- Layer transitions are efficiently computed using matrix-vector multiplication: $a_{next} = \sigma(Wa + b)$.
- Total network parameters include all weights and biases across every layer.

## Core Concepts Breakdown

- **Weighted Sum**: The linear combination of input values scaled by their respective weights.
- **Sigmoid Function**: A non-linear function that maps any real number to a value between 0 and 1.
- **Bias**: An additive constant that shifts the activation threshold of a neuron.
- **Weight Matrix**: A structured array where each row represents the weights connecting to a specific neuron in the next layer.