# The Derivative Formula


## Defining the Slope of a Secant Line

To determine the slope of a secant line passing through two points P and Q on a curve, we first establish a coordinate system. Let point P be located at $x_0$ on the x-axis, with its corresponding height on the curve being $f(x_0)$. We define a horizontal distance from $x_0$ to a new point as $\Delta x$, which represents the change in x. Correspondingly, the vertical distance between the heights of these two points is denoted as $\Delta f$, representing the change in f. The slope of the secant line connecting P and Q is defined by the ratio of these two quantities: $\frac{\Delta f}{\Delta x}$. This ratio provides the slope of the secant line, serving as the foundational measurement for understanding the behavior of the function over the interval defined by $\Delta x$.


## The Formal Limit Definition of the Derivative

The derivative, denoted as $f'(x_0)$, represents the slope of the tangent line at point P. To derive this, we consider the limit as the horizontal distance $\Delta x$ approaches 0. By identifying point P as $(x_0, f(x_0))$ and point Q as $(x_0 + \Delta x, f(x_0 + \Delta x))$, we can express the change in f as the difference between the function values at these two points: $f(x_0 + \Delta x) - f(x_0)$. Substituting this into our slope ratio, we arrive at the formal definition of the derivative: $$f'(x_0) = \lim_{\Delta x \to 0} \frac{f(x_0 + \Delta x) - f(x_0)}{\Delta x}$$ This formula is the most important tool for computing derivatives, as it allows us to calculate the slope of the tangent line by evaluating the limit of the difference quotient as the interval $\Delta x$ shrinks to zero.


## Application of the Derivative Formula

With the formal definition of the derivative established, we can apply it to specific functions to find their rates of change. The lecturer introduces the function $f(x) = 1/x$ as the first example. This function is chosen because it is sufficiently complicated to yield an interesting result while remaining straightforward enough to compute the derivative efficiently. The process involves plugging the function $f(x) = 1/x$ directly into the difference quotient formula derived previously. Visually, this process corresponds to taking a point on the hyperbola and determining the slope of the tangent line at that specific location. By systematically applying the limit definition, we can determine the derivative for various functions, effectively translating the geometric concept of a tangent line into an algebraic calculation.
