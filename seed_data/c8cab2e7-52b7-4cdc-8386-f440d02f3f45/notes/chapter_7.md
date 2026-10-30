# Constant Acceleration and Integration


## The Inverse Problem of Motion

In physics, we often encounter the inverse problem of motion: given a particle's acceleration $A$, we must determine its position $X(t)$. Unlike differentiation, which is an algorithmic process of finding the ratio of changes, integration is a process of guessing. We seek a function whose second derivative is the constant $A$. Knowing that each derivative reduces the power of $T$ by one, we start by guessing a function proportional to $T^2$. If we assume $X(t) = T^2$, the first derivative is $2T$ and the second derivative is $2$. Since we require the second derivative to be $A$, we adjust our guess by multiplying $T^2$ by the constant $A/2$. This yields the function $X(t) = \frac{1}{2}AT^2$, which satisfies the condition that the second derivative is $A$. This represents a particle with constant acceleration $A$ that does not depend on time.


## Generalizing the Position Function

The function $X(t) = \frac{1}{2}AT^2$ is not the most general solution for position. In calculus, when integrating, we can add terms that are 'killed' by the act of differentiation. If we only took one derivative, we could add a constant $C$. However, because we are taking two derivatives, we can add both a constant $C$ and a term linear in time, $BT$. Adding $C$ does not change the second derivative because the derivative of a constant is zero. Adding $BT$ also does not change the second derivative because the first derivative is $B$ and the second derivative is zero. Thus, the most general expression for the position of a particle with constant acceleration $A$ is $X(t) = \frac{1}{2}AT^2 + BT + C$. This logic applies regardless of the coordinate system used, whether we label the position as $X$ or $Y$.


## Physical Significance of Integration Constants

Mathematically, $B$ and $C$ are constants, but as physicists, we must interpret their meaning. Knowing only the acceleration is insufficient to determine the particle's specific history; we need to know its initial state. By evaluating the position function at $T=0$, we find $X(0) = C$. Therefore, $C$ represents the initial position of the object, commonly denoted as $X_0$. To interpret $B$, we take the first derivative of the position function, which gives the velocity: $V(t) = AT + B$. Evaluating this at $T=0$ reveals that $V(0) = B$. Thus, $B$ is the initial velocity of the object, denoted as $V_0$. These constants allow us to distinguish between different objects undergoing the same constant acceleration, such as various objects falling under gravity, by accounting for their unique starting positions and initial speeds.


## The Kinematic Equation for Constant Acceleration

By identifying the constants of integration as the initial conditions, we arrive at the standard kinematic equation for constant acceleration: $X(t) = X_0 + V_0T + \frac{1}{2}AT^2$. This formula describes the position of a particle at any time $T$ given its initial position $X_0$, initial velocity $V_0$, and constant acceleration $A$. For example, in the case of an object falling under gravity, we set $A = -g$ (where $g \approx 9.8$ m/s²), assuming the upward direction is positive. The resulting formula $Y(t) = Y_0 + V_0T - \frac{1}{2}gT^2$ captures the motion of any object falling under gravity. This approach demonstrates how integration allows us to specialize our understanding of motion to a limited class of systems where acceleration is constant, providing a complete description of the particle's trajectory over time.
