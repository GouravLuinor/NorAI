# Efficiency and Asymptotic Analysis


## Defining Algorithmic Efficiency

Efficiency is defined not just by how fast an algorithm runs, but by how it compares to other potential approaches for solving the same problem. A common, yet flawed, approach to measuring efficiency is to simply code an algorithm and time how long it takes to execute on a computer. This method is problematic because the result depends heavily on the specific hardware used. For instance, an algorithm running on a simple watch calculator will perform significantly slower than the same algorithm running on a powerful research computer, even if the underlying code is identical. Because hardware speed varies, measuring raw time does not provide a reliable, abstract measure of an algorithm's performance. Instead, we aim to abstract the machine out of the picture by assuming each fundamental operation takes a fixed amount of time. We then measure efficiency by counting how many of these fundamental operations the algorithm must perform to solve the problem, providing an abstract notion of performance rather than an implementation-dependent one.


## Input Size and Performance

Performance is not a static value; it depends on the size of the input data. For example, an algorithm designed to find a birthday will run faster when searching through a small section of people compared to searching through a much larger group. We typically use the variable $N$ to represent the size of the input, though the definition of input size depends on the context. If we are given an $N \times N$ array, the input size is $N^2$. If we are given a graph, the input size is typically defined as the number of vertices plus the number of edges, as this represents the space required to convey that information. By analyzing how performance changes relative to the input size, we can compare algorithms effectively. This approach allows us to understand how an algorithm scales as the input grows, which is a more useful metric than raw execution time on a specific machine.


## Asymptotic Notation

To formally describe performance relative to input size, we use asymptotic analysis. This involves three primary types of notation to bound the growth of functions: Big O notation, which provides an upper bound; Omega notation, which provides a lower bound; and Theta notation, which provides a tight bound by being bounded from both above and below. These notations allow us to categorize algorithms based on their growth rates. A common example is a linear time algorithm, where the performance is linear with respect to the size of the input, such as when adding elements to a list. By using these asymptotic tools, we can classify algorithms into common categories that relate input size to performance, helping us understand the efficiency of an algorithm in a general, machine-independent way.
