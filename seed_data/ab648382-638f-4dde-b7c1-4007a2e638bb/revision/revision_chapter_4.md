# Revision Notes — Chapter 4: Parameterization and Linear Algebra in Deep Learning

## Key Exam Takeaways

- Neural networks function as composite mathematical mappings from input space to output space using matrix-vector multiplication.
- Network parameters (weights and biases) total approximately 13,000 in the discussed model, which are tuned during training.
- Sigmoid functions map values to (0, 1) but suffer from slow training due to gradient saturation.
- ReLU (max(0, A)) is the modern standard for deep learning due to its computational efficiency and superior training stability.

## Core Concepts Breakdown

- **Weight Matrix**: A collection of parameters that scale input values to determine the strength of connections between neurons.
- **Activation Function**: A non-linear function applied to the weighted sum of inputs to allow the network to learn complex patterns.
- **ReLU**: An activation function defined as max(0, x) that mitigates vanishing gradient issues in deep networks.