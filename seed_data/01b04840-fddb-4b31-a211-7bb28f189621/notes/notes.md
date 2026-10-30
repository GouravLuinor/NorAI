# Introduction to Differentiation


## Overview of Differentiation

The study of differentiation begins with understanding the derivative through several lenses. The primary focus is the geometric interpretation, which examines the behavior of functions on a graph. Additionally, the course explores the physical interpretation of the derivative. Beyond these theoretical foundations, the derivative is highlighted for its fundamental importance across various disciplines, including science, engineering, economics, and political science. It is a critical tool for analyzing measurements in these fields. The overarching goal of this unit is to master the ability to differentiate any function that can be written down. As an example of the complexity to be mastered, the course aims to eventually calculate the derivative of functions such as $e^x \arctan(x)$. This sets the stage for a comprehensive approach to differentiation.


## Geometric Interpretation

The geometric interpretation of the derivative centers on the problem of finding the tangent line to the graph of a function $y = f(x)$ at a specific point $P = (x_0, y_0)$. Here, $x_0$ represents a fixed location on the x-axis. The process involves visualizing the graph of the function and identifying the specific point $P$ above the coordinate $x_0$. The objective is to construct a line that is tangent to the curve at that precise point. This geometric construction serves as the primary motivation for the study of derivatives in this unit. While the lecturer demonstrates the result by drawing the tangent line on the graph, the specific method or formula used to calculate this line is not yet revealed, establishing the need for the upcoming lessons on differentiation.


## Goals and Scope

The unit is designed to equip students with the skills to differentiate any function they encounter. This is described as a 'tall order' but a central objective of the curriculum. The lecturer emphasizes that by the end of the unit, students will be able to handle complex expressions, such as $e^x \arctan(x)$, using standard notation for the derivative, denoted as $\frac{d}{dx}$. The course moves from these conceptual foundations toward practical, universal application. The geometric problem of the tangent line is the starting point, but the scope extends to any function that can be written down. This progression from geometric visualization to algebraic manipulation of complex functions forms the core structure of the introduction to differentiation.


---

# Defining the Tangent Line


## Analytical Representation of a Line

To move from a visual understanding of a tangent line to an analytical one, we start with the standard equation for a line passing through a point $(x_0, y_0)$. The equation is given by $y - y_0 = m(x - x_0)$, where $m$ represents the slope of the line. To define this line specifically for a function $y = f(x)$ at a point $P$, we require two pieces of information. First, we need the coordinates of the point $P$. Since $P$ lies on the curve, its $y$-coordinate is determined by the function value at $x_0$, specifically $y_0 = f(x_0)$. This is a straightforward requirement. The second, more complex requirement is determining the slope $m$. In calculus, this slope is defined as the derivative of the function at that point, denoted as $f'(x_0)$. This derivative represents the slope of the tangent line to the curve at point $P$.


## Defining the Tangent Line via Secants

Distinguishing the tangent line from other lines that might intersect a curve is not always intuitive, especially since a curve might be 'wiggly' and cross a line at multiple points. The defining characteristic of a tangent line is found by considering a secant line passing through the fixed point $P$ and a second, varying point $Q$ on the curve. As the point $Q$ moves along the curve and gets closer and closer to the fixed point $P$, the slope of the secant line $PQ$ approaches the slope of the tangent line. Therefore, the tangent line is formally defined as the limit of the secant lines $PQ$ as $Q$ tends toward $P$. This limit-based approach allows us to move beyond mere geometric intuition and provides a concrete, analytical method to calculate the slope $m$ for any given function.


## Moving Toward Calculation

With the definition of the tangent line established as the limit of secant lines, we can now transition to computing these values using symbols and formulas. By fixing point $P$ and allowing point $Q$ to vary, we set the stage for calculating the slope of the secant line. This process involves two distinct steps that introduce fundamental notations used throughout calculus, including multivariable calculus. By articulating the tangent line as the limit of secant lines $PQ$ as $Q \to P$, we gain a robust framework to work out specific formulas for any example. This geometric interpretation provides the necessary bridge to the algebraic computations that follow in the study of derivatives.


---

# The Derivative Formula


## Defining the Slope of a Secant Line

To determine the slope of a secant line passing through two points P and Q on a curve, we first establish a coordinate system. Let point P be located at $x_0$ on the x-axis, with its corresponding height on the curve being $f(x_0)$. We define a horizontal distance from $x_0$ to a new point as $\Delta x$, which represents the change in x. Correspondingly, the vertical distance between the heights of these two points is denoted as $\Delta f$, representing the change in f. The slope of the secant line connecting P and Q is defined by the ratio of these two quantities: $\frac{\Delta f}{\Delta x}$. This ratio provides the slope of the secant line, serving as the foundational measurement for understanding the behavior of the function over the interval defined by $\Delta x$.


## The Formal Limit Definition of the Derivative

The derivative, denoted as $f'(x_0)$, represents the slope of the tangent line at point P. To derive this, we consider the limit as the horizontal distance $\Delta x$ approaches 0. By identifying point P as $(x_0, f(x_0))$ and point Q as $(x_0 + \Delta x, f(x_0 + \Delta x))$, we can express the change in f as the difference between the function values at these two points: $f(x_0 + \Delta x) - f(x_0)$. Substituting this into our slope ratio, we arrive at the formal definition of the derivative: $$f'(x_0) = \lim_{\Delta x \to 0} \frac{f(x_0 + \Delta x) - f(x_0)}{\Delta x}$$ This formula is the most important tool for computing derivatives, as it allows us to calculate the slope of the tangent line by evaluating the limit of the difference quotient as the interval $\Delta x$ shrinks to zero.


## Application of the Derivative Formula

With the formal definition of the derivative established, we can apply it to specific functions to find their rates of change. The lecturer introduces the function $f(x) = 1/x$ as the first example. This function is chosen because it is sufficiently complicated to yield an interesting result while remaining straightforward enough to compute the derivative efficiently. The process involves plugging the function $f(x) = 1/x$ directly into the difference quotient formula derived previously. Visually, this process corresponds to taking a point on the hyperbola and determining the slope of the tangent line at that specific location. By systematically applying the limit definition, we can determine the derivative for various functions, effectively translating the geometric concept of a tangent line into an algebraic calculation.


---

# Example: Derivative of 1/x


## Setting up the Difference Quotient

To find the derivative of $f(x) = 1/x$ at a general point $x_0$, we begin by constructing the difference quotient, which represents the slope of the secant line. The formula for the difference quotient is $\frac{\Delta f}{\Delta x} = \frac{f(x_0 + \Delta x) - f(x_0)}{\Delta x}$. Substituting the function $f(x) = 1/x$, we obtain the expression $\frac{\frac{1}{x_0 + \Delta x} - \frac{1}{x_0}}{\Delta x}$. This expression is inherently complex because it involves a difference in the numerator and a difference in the denominator (the change in $x$). At this stage, directly evaluating the limit as $\Delta x \to 0$ results in an indeterminate $0/0$ form, necessitating algebraic simplification before we can proceed to the limit.


## Algebraic Simplification

To simplify the difference quotient, we first factor out $1/\Delta x$. We then combine the terms in the numerator over a common denominator, which is $(x_0 + \Delta x)x_0$. This yields the expression $\frac{1}{\Delta x} \left( \frac{x_0 - (x_0 + \Delta x)}{(x_0 + \Delta x)x_0} \right)$. Simplifying the numerator, $x_0 - (x_0 + \Delta x)$ becomes $-\Delta x$. The expression now reads $\frac{1}{\Delta x} \left( \frac{-\Delta x}{(x_0 + \Delta x)x_0} \right)$. We can now perform two crucial cancellations: the $\Delta x$ in the denominator and the $\Delta x$ in the numerator cancel out. This leaves us with the simplified expression $-\frac{1}{(x_0 + \Delta x)x_0}$. This form is now amenable to taking the limit, as the problematic division by zero has been removed.


## Taking the Limit and Plausibility Check

With the expression simplified to $-\frac{1}{(x_0 + \Delta x)x_0}$, we can now take the limit as $\Delta x \to 0$. By setting $\Delta x = 0$, we obtain the derivative $f'(x_0) = -\frac{1}{x_0^2}$. To verify this result, we perform a plausibility check. First, the derivative is negative, which is consistent with the graph of $1/x$ having a negative slope. Second, as $x_0$ increases toward infinity, the magnitude of the slope $-1/x_0^2$ decreases, which matches the visual observation that the curve becomes less steep as we move further to the right. We can further confirm this by substituting a specific value, such as $x_0 = 3$, into the simplified expression, which yields $-1/9$ as $\Delta x$ approaches zero, confirming the general formula.


---

# Calculus in Context: A Word Problem


## The Nature of Calculus Word Problems

The lecturer notes that calculus often has a reputation for being difficult, but argues this is largely due to the context in which problems are presented. In real-world applications, a calculus problem is typically embedded within a larger structure that requires applying mathematical knowledge from grade school through high school. The actual calculus component is often a routine, isolated step, while the rest of the work involves managing these surrounding complexities. To illustrate this, the lecturer introduces a geometry problem: finding the area of a triangle enclosed by the coordinate axes and a tangent line to the curve $y = 1/x$. This problem is chosen because it directly utilizes the geometric interpretation of the derivative, which is the only type of word problem currently accessible given the course's progress.


## Setting Up the Geometry Problem

To solve the problem, we focus on the first quadrant and the hyperbola $y = 1/x$. We select a specific point on this curve, denoted as $(x_0, y_0)$, which serves as the point of tangency for our line. The goal is to calculate the area of the triangle formed by the axes and the tangent line at this point. To do this, we must identify the base and the height of the triangle. The base corresponds to the x-intercept of the tangent line, and the height corresponds to the y-intercept. Establishing clear notation—using $x$ and $y$ for variables and $x_0$ and $y_0$ for the specific point—is described as nearly half the battle in solving such problems.


## The Role of Calculus

The lecturer emphasizes that there is only one specific step in this entire process that requires calculus: determining the equation of the tangent line. Once the tangent line equation is derived using the derivative (the 'magic number' or slope), the remaining work is purely geometric. We start the tangent line equation as $Y - y_0 = m(X - x_0)$, where $m$ is the slope at the point $(x_0, y_0)$. By isolating this calculus step, the problem transitions from a calculus exercise into a standard geometry problem of finding intercepts and calculating the area of a triangle. This approach demonstrates how calculus acts as a tool within a broader mathematical context.


---

# Solving the Geometry Problem


## Finding the X-Intercept

To solve the geometry problem, we begin with the equation of the tangent line at a point $(x_0, y_0)$ on the curve $y = 1/x$. The derivative of $f(x) = 1/x$ is $f'(x) = -1/x^2$, so the tangent line equation is $y - y_0 = -1/x_0^2(x - x_0)$. To find the X-intercept, we set $y = 0$ in this equation. Since $y_0 = f(x_0) = 1/x_0$, we substitute these values to get $0 - 1/x_0 = -1/x_0^2(x - x_0)$. Simplifying the right side yields $-1/x_0 = -x/x_0^2 + 1/x_0$. Rearranging the terms, we move $-x/x_0^2$ to the left and $1/x_0$ to the right to obtain $x/x_0^2 = 2/x_0$. Multiplying both sides by $x_0^2$ results in the X-intercept $x = 2x_0$.


## Using Symmetry for the Y-Intercept

Once the X-intercept is found to be $2x_0$, we can determine the Y-intercept using a symmetry shortcut. The lecturer claims that by observing the geometry, the Y-intercept is $2y_0$. This symmetry arises from the mirror-like nature of the curve $y = 1/x$ around the diagonal $y = x$. This involves exchanging the roles of $x$ and $y$. Because the original equation $y = 1/x$ is equivalent to $xy = 1$, which can also be written as $x = 1/y$, the equation is invariant under the swap of $x$ and $y$. This symmetry implies that any formula derived for the X-intercept can be mirrored to find the Y-intercept by swapping the variables. If one does not wish to rely on this symmetry, the Y-intercept can also be calculated algebraically by setting $x = 0$ in the tangent line equation.


## Calculus and Multiple Variables

The lecturer concludes the geometric derivation with a remark on the nature of calculus. While the course is titled 'Single Variable Calculus', the process of solving this geometry problem demonstrates that we are often required to handle multiple variables simultaneously—such as $x, y, x_0,$ and $y_0$—to reach a solution. This ability to manage several quantities at once is described as one of the most challenging aspects of calculus. By systematically identifying the intercepts and utilizing the inherent symmetry of the function $y = 1/x$, we successfully resolve the geometry problem, allowing for the calculation of the area defined by the tangent line and the axes.


---

# Variables and Notation


## Variable Management and Complexity

In calculus problems, we often deal with many variables simultaneously, such as $x, y, x_0,$ and $y_0$. While we perform single-variable calculus, the underlying reality often involves numerous variables interacting. A significant source of confusion is the deliberate sloppiness in how we use variable names. To avoid creating an excessive number of unique names, we reuse symbols for different purposes within the same problem. For example, in calculating intercepts for a tangent line, the symbol $y$ might represent the function $y = 1/x$ in one context, while representing the horizontal line $y = 0$ in another. This practice, while potentially confusing, is a matter of convenience. It is far more practical to allow a letter to change its role during a computation than to invent new variables for every distinct geometric feature. Maintaining clarity while navigating these shifting roles is a fundamental skill in managing the complexity of calculus.


## Geometric Application and Invariance

The lecturer demonstrates the utility of these methods by calculating the area of a triangle formed by the tangent line to the curve $y = 1/x$ at the point $(x_0, y_0)$. The base of the triangle is $2x_0$ and the height is $2y_0$. The area is calculated as $\frac{1}{2} \times (2x_0) \times (2y_0) = 2x_0y_0$. Since $y_0 = 1/x_0$, this simplifies to $2x_0(1/x_0) = 2$. Interestingly, the area of the triangle is constant and does not depend on the specific choice of the point $(x_0, y_0)$. This result is a specific property of the function $1/x$. This example highlights why keeping track of variables is essential: even when the final result is a simple constant, the intermediate steps require careful handling of multiple, sometimes overlapping, variable definitions to arrive at the correct geometric interpretation.


## Derivative Notations

Different notations for the derivative are used interchangeably in calculus. These include:

* **Newton's Notation**: Denoted as $f'$ or $\dot{y}$. This is a compact way to represent the derivative.
* **Leibniz's Notation**: Includes forms such as $\frac{df}{dx}$, $\frac{dy}{dx}$, $\frac{d}{dx}f$, and $\frac{d}{dx}y$. 

These notations are used interchangeably and are both considered extremely useful. A notable characteristic of Leibniz's notation is that it sometimes omits the underlying base point (e.g., $x_0$). While this can be a nuisance, it is common practice to leave out such information, requiring the student to infer the missing context from the problem. Understanding these different symbolic representations is crucial for reading and communicating mathematical ideas effectively.


---

# Derivative of Power Functions


## Setting up the Derivative of x^n

To find the derivative of the function $f(x) = x^n$ (where $n$ is a positive integer), we start by forming the difference quotient $\frac{\Delta f}{\Delta x} = \frac{(x + \Delta x)^n - x^n}{\Delta x}$. In this calculation, we treat $x$ as fixed while $\Delta x$ varies. The lecturer notes that using $x_0$ notation is unnecessary and cumbersome, so we simply use $x$. The goal is to simplify this expression algebraically to determine the limit as $\Delta x$ approaches zero. This requires expanding the term $(x + \Delta x)^n$.


## Applying the Binomial Theorem

To expand $(x + \Delta x)^n$, we use the binomial theorem. The expansion is $(x + \Delta x)^n = x^n + n x^{n-1} \Delta x + \text{junk}$. The 'junk' represents higher-order terms involving $(\Delta x)^2, (\Delta x)^3$, and so on, which we denote as $O((\Delta x)^2)$. We only need the first two terms of this expansion for our derivative calculation. Substituting this back into our difference quotient, we get $\frac{1}{\Delta x} (x^n + n x^{n-1} \Delta x + O((\Delta x)^2) - x^n)$. The $x^n$ terms cancel out, leaving $\frac{1}{\Delta x} (n x^{n-1} \Delta x + O((\Delta x)^2))$. Dividing by $\Delta x$ yields $n x^{n-1} + O(\Delta x)$. As $\Delta x$ goes to zero, the $O(\Delta x)$ term disappears, leaving the derivative $\frac{d}{dx} x^n = n x^{n-1}$.


## Extension to Polynomials

The power rule $\frac{d}{dx} x^n = n x^{n-1}$ is a powerful tool that extends directly to polynomials. For example, if we differentiate $f(x) = x^3 + 5x^{10}$, we apply the rule to each term individually. The derivative of $x^3$ is $3x^2$, and the derivative of $5x^{10}$ is $5 \cdot 10 x^9 = 50x^9$. Thus, the derivative of the entire polynomial is $3x^2 + 50x^9$. The lecturer emphasizes that the binomial theorem is a general formula, but for the purposes of finding the derivative, we only require the first two terms of the expansion, as all other higher-order terms vanish in the limit as $\Delta x$ approaches zero.
