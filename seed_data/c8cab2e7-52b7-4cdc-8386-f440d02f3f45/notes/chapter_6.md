# Velocity, Acceleration, and Calculus


## Interpreting Position-Time Graphs

A position-time graph ($x$ versus $t$) represents the motion of an object. A common misconception is that the shape of the graph mimics the physical path of the object; however, the graph depicts position over time, not a spatial trajectory. If the graph moves up and down, the object is simply moving back and forth along a line, such as crossing the origin and moving to the left before turning around to return to the right. Mathematically, $x$ is a function of time, $x(t)$. While some functions have specific names like $t^2$, $\sin(t)$, or $\log(t)$, a particle's motion can often be described by complex functions that do not have standard names. Understanding how to interpret these graphs is the first step in analyzing motion, as they provide the raw data for calculating velocity and acceleration.


## Average Velocity

Average velocity, denoted by $\bar{v}$, is defined by observing an object at two distinct instances in time, $t_1$ and $t_2$. The average velocity is the change in position divided by the change in time: $\bar{v} = \frac{x(t_2) - x(t_1)}{t_2 - t_1}$. While useful, average velocity does not capture the full detail of an object's motion. For instance, if an object starts at a position, moves around, and returns to the exact same starting position, the average velocity is zero because the total displacement is zero. This result is identical to an object that never moved at all. Because average velocity only considers the endpoints, it is an incomplete description of the motion that occurred between those two times.


## Instantaneous Velocity and Derivatives

To determine velocity at a specific instant, we use the principles of calculus. We consider a small finite time interval $\Delta t$ and the corresponding change in position $\Delta x$. The average velocity over this interval is $\frac{\Delta x}{\Delta t}$, which graphically represents the slope of a straight line connecting two points on the $x(t)$ curve. As we shrink $\Delta t$ toward zero, the straight line becomes tangent to the curve at that specific point. The instantaneous velocity $v(t)$ is defined as the limit of this ratio as $\Delta t$ approaches zero, written as the derivative $v(t) = \frac{dx}{dt}$. This derivative is equivalent to the tangent of the angle $\theta$ of the tangent line on the graph. This process allows us to define velocity 'right now,' similar to how a car's speedometer provides a reading at a single moment.


## Acceleration and Constant Motion

Once the first derivative (velocity) is established, we can take further derivatives. The derivative of velocity with respect to time is called acceleration, $a(t) = \frac{dv}{dt}$, which is also the second derivative of position, $a(t) = \frac{d^2x}{dt^2}$. While one can theoretically take any number of derivatives, only the first two have standard physical names. The third derivative has no common name because no fundamental equations, such as $F=ma$, explicitly require it. We often focus on a specific class of problems where acceleration is constant. A primary example is objects falling near the Earth's surface, which all experience the same constant acceleration $g \approx 9.8 \text{ m/s}^2$. Mastering these constant acceleration problems is a critical skill in mechanics.
