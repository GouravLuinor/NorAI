# Derivative of Power Functions


## Setting up the Derivative of x^n

To find the derivative of the function $f(x) = x^n$ (where $n$ is a positive integer), we start by forming the difference quotient $\frac{\Delta f}{\Delta x} = \frac{(x + \Delta x)^n - x^n}{\Delta x}$. In this calculation, we treat $x$ as fixed while $\Delta x$ varies. The lecturer notes that using $x_0$ notation is unnecessary and cumbersome, so we simply use $x$. The goal is to simplify this expression algebraically to determine the limit as $\Delta x$ approaches zero. This requires expanding the term $(x + \Delta x)^n$.


## Applying the Binomial Theorem

To expand $(x + \Delta x)^n$, we use the binomial theorem. The expansion is $(x + \Delta x)^n = x^n + n x^{n-1} \Delta x + \text{junk}$. The 'junk' represents higher-order terms involving $(\Delta x)^2, (\Delta x)^3$, and so on, which we denote as $O((\Delta x)^2)$. We only need the first two terms of this expansion for our derivative calculation. Substituting this back into our difference quotient, we get $\frac{1}{\Delta x} (x^n + n x^{n-1} \Delta x + O((\Delta x)^2) - x^n)$. The $x^n$ terms cancel out, leaving $\frac{1}{\Delta x} (n x^{n-1} \Delta x + O((\Delta x)^2))$. Dividing by $\Delta x$ yields $n x^{n-1} + O(\Delta x)$. As $\Delta x$ goes to zero, the $O(\Delta x)$ term disappears, leaving the derivative $\frac{d}{dx} x^n = n x^{n-1}$.


## Extension to Polynomials

The power rule $\frac{d}{dx} x^n = n x^{n-1}$ is a powerful tool that extends directly to polynomials. For example, if we differentiate $f(x) = x^3 + 5x^{10}$, we apply the rule to each term individually. The derivative of $x^3$ is $3x^2$, and the derivative of $5x^{10}$ is $5 \cdot 10 x^9 = 50x^9$. Thus, the derivative of the entire polynomial is $3x^2 + 50x^9$. The lecturer emphasizes that the binomial theorem is a general formula, but for the purposes of finding the derivative, we only require the first two terms of the expansion, as all other higher-order terms vanish in the limit as $\Delta x$ approaches zero.
