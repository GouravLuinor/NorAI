# Parameterization and Linear Algebra in Deep Learning


## 1. NEURAL NETWORKS AS MATHEMATICAL FUNCTIONS

At its core, a neural network is a complex, composite mathematical function. It maps an input vector $x \in \mathbb{R}^n$ to an output vector $y \in \mathbb{R}^m$. In the context of digit classification, the input is a 784-dimensional vector (representing pixels) and the output is a 10-dimensional vector (representing digits 0-9). The transformation is defined by layers of neurons, where each neuron acts as a container for a scalar value, and the network's behavior is governed by approximately 13,000 parameters, specifically weights ($W$) and biases ($b$).


## 2. THE MECHANICS OF PARAMETERIZATION

The transformation between layers is primarily achieved through matrix-vector multiplication. For a given layer, the output $z$ is calculated as $z = Wx + b$. This linear operation is followed by a non-linear activation function. The 'learning' process in deep learning is essentially the iterative optimization of these 13,000 weights and biases to minimize the error between the network's output and the true label. The complexity of the network—its ability to recognize patterns—is directly proportional to the depth and the number of these parameters.


## 3. COMPARISON OF ACTIVATION FUNCTIONS

| Feature | Sigmoid | ReLU (Rectified Linear Unit) |
| :--- | :--- | :--- |
| Formula | $\sigma(x) = \frac{1}{1 + e^{-x}}$ | $f(x) = \max(0, x)$ |
| Range | $(0, 1)$ | $[0, \infty)$ |
| Biological Analogy | Neuron firing state | Threshold-based activation |
| Training Efficiency | Slow (Vanishing Gradient) | Fast (Standard for Deep Nets) |


## 4. KEY TAKEAWAYS ON ACTIVATION FUNCTIONS

- **Sigmoid Limitations:** Historically used to mimic biological neurons, but its saturating nature leads to vanishing gradients, making it difficult to train deep networks.
- **ReLU Advantages:** The Rectified Linear Unit is currently the industry standard. It acts as an identity function for positive inputs and zero for negative inputs.
- **Mathematical Simplicity:** ReLU's simplicity ($max(0, A)$) allows for faster computation and more stable gradient propagation during backpropagation.
