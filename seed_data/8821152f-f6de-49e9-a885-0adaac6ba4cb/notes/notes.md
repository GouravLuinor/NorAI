# Course Introduction and Goals


## Course Overview and Instructors

This course, Introduction to Algorithms, is taught by Jason Ku, Eric Demaine, and Justin Solomon. The instructors will rotate teaching duties, with Jason Ku leading the first lecture. The primary objective of the course is to teach students how to solve computational problems. While coding is a component, the course emphasizes that the core skill set involves more than just writing code. Students will engage in significant amounts of writing to articulate their ideas, making this course distinct from others in the department. The focus is on theoretical understanding and the ability to convey that understanding to others, rather than solely focusing on implementation.


## Core Objectives

The course is built around three fundamental pillars of algorithm design and analysis: 1. Solving computational problems. 2. Proving the correctness of solutions. 3. Arguing the efficiency of solutions. Beyond these technical pillars, a major overarching theme is the communication of these ideas. Students are expected to move beyond simply instructing a computer and must learn to convince other people that their proposed solutions are both correct and efficient. This emphasis on communication and rigorous proof distinguishes this course from other departmental offerings.


## The Importance of Communication

A significant portion of the course involves writing to explain and justify algorithmic approaches. The instructor notes that students will perform more writing in this class than in many others, suggesting it functions similarly to a Communication Intensive (CI) course. The goal is to develop the ability to argue that a specific algorithm is better than alternatives. By the end of the course, students should be able to demonstrate that their solutions are correct and efficient, effectively communicating these concepts to peers and instructors rather than just producing functional code.


---

# Defining Computational Problems


## The Formal Definition of a Computational Problem

A computational problem is formally defined as a binary relation between a set of inputs and a set of outputs. We can visualize this as a bipartite graph where the left side represents all possible inputs and the right side represents all possible outputs. Edges in this graph connect specific inputs to their corresponding correct outputs. It is important to note that this mapping is not necessarily a function; a single input may map to multiple valid outputs. For example, if the problem is to find the index of the value 5 in an array, and the value 5 appears multiple times, any of those indices would be considered a correct output. This structure allows us to specify exactly which outputs are acceptable for any given input, providing a rigorous mathematical foundation for what it means to solve a problem computationally.


## Specifying Problems via Predicates

While we can define a problem by explicitly listing every input-output pair, this approach is impractical for most real-world scenarios because it would take an enormous amount of time to enumerate every possibility. Instead, we typically define computational problems using predicates. A predicate allows us to verify whether a given output is correct for a specific input. For instance, if the problem is to find the index of a value 5 in an array, we do not need to list every valid index for every possible array. We simply need a way to check if the value at a provided index is indeed 5. By using predicates, we can define problems over large or infinite input spaces without needing to explicitly map every individual instance, making the definition of problems much more efficient and scalable.


## Generalizing Problems: An Example

To illustrate the utility of generalizing problems, consider the task of determining if any two students in a classroom share the same birthday. Rather than treating this as a fixed, small-scale task, we can generalize the problem to any group of people. The lecturer notes that if there are more than 365 people in the room, the answer must be yes, according to the pigeonhole principle. This example highlights why we move away from small, hard-coded instances toward generalized definitions. By defining the problem in terms of inputs (the set of students) and a predicate (checking for matching birthdays), we create a framework that applies regardless of the specific number of students, allowing us to reason about the problem's properties more abstractly and effectively.


---

# Generalizing Problems and Algorithms


## Moving Beyond Fixed Inputs

The lecturer introduces the concept of generalizing computational problems by moving away from fixed, small-scale scenarios. While one might consider a specific classroom of students to check for shared birthdays, this approach is limited. Instead, the goal is to design algorithms that are general and robust enough to handle arbitrarily sized inputs. Whether the input consists of a few hundred students in a recitation, a larger group in a machine learning class, or even a massive dataset like a billion entries in a database, the algorithm must remain effective. By focusing on general problems with arbitrarily sized inputs, we can develop fixed-size procedures that scale appropriately. This shift in perspective is essential for creating computational tools that are not tied to a specific, small instance but are instead applicable to any valid input within the problem's domain.


## Defining the Algorithm as a Function

An algorithm is defined as a fixed-size machine or procedure that maps inputs to outputs. Unlike a problem specification, which describes the desired outcome or the relationship between inputs and outputs, an algorithm is the mechanism that performs the computation. For an algorithm to be considered correct, it must take a valid input and produce a correct output as defined by the problem. If an algorithm produces an incorrect output for a given input, it fails the criteria for correctness. Essentially, an algorithm acts as a function where every input in the domain is mapped to a single, correct output. This functional view highlights that the algorithm's primary responsibility is to reliably transform input data into the specific, correct result required by the problem specification.


## Correctness and Determinism

The lecturer emphasizes the necessity of deterministic algorithms that consistently yield correct results. When an algorithm processes an input, it must generate an output that aligns with the problem's requirements. If a problem allows for multiple potential outputs, the algorithm must still ensure that the output it produces is one of the correct ones. Producing an incorrect output for a valid input renders the algorithm incorrect. The focus is on creating procedures that are reliable across all possible inputs. By viewing the algorithm as a function that maps inputs to correct outputs, we establish a clear standard for evaluating whether a proposed solution successfully solves a computational problem. This deterministic approach ensures that for any given input within the domain, the algorithm will consistently provide a valid and correct answer.


---

# Example: The Birthday Problem


## The Birthday Problem Algorithm

The birthday problem is approached by defining a clear, step-by-step procedure to identify if any two individuals in a group share the same birthday. The algorithm begins by ordering the students and assigning each a unique number from one to the total number of students in the class. The interviewer then proceeds to interview each student one by one. For every student, the interviewer asks for their birthday and records it. The core of the procedure relies on maintaining this record of birthdays. As each new student provides their birthday, the interviewer checks the existing record to see if that specific date has already been noted. If a match is found, the algorithm terminates and returns a result indicating that a pair has been identified. If no match is found, the student's birthday is added to the record, and the process continues with the next student.


## Procedure Steps

The algorithm follows a structured sequence for each student: 
- Interview the student to obtain their birthday.
- Check if the obtained birthday already exists within the current record.
- If a match is found, return the identified pair and stop the process.
- If no match is found, add the new student's birthday to the record and proceed to the next student.
- If all students have been interviewed without finding a match, return that no such pair exists.


## Defining Algorithms as Procedures

The lecturer clarifies that an algorithm is a procedure designed to take specific inputs and produce a correct output. While the verbal description provided for the birthday problem may not be sufficient for a computer to execute directly, it serves as a clear plan that any human could follow to reach the correct result. Regarding the mathematical definition of a function, the lecturer specifies that an algorithm is viewed as a binary relation where every input maps to exactly one output. This perspective focuses on the transformation of input to output rather than constraints like functional programming's avoidance of external state or I/O. Ultimately, an algorithm is a plan that ensures correctness in producing an output from a given input.


---

# Proving Correctness with Induction


## The Need for Formal Correctness

When we design an algorithm, we are essentially creating a recipe or a procedure that takes an input and produces an output. While it is straightforward to manually verify that an algorithm works for a small number of inputs—such as checking the birthday problem against four students by testing all combinations of matches—this approach becomes impractical as the input size grows. If we have 300 students, testing every possibility is impossible. As computer scientists, we often write code of a constant size that must handle arbitrarily large inputs, which typically involves looping or recursion. To formally argue that such an algorithm is correct for any input size, we rely on mathematical induction. This technique allows us to move beyond manual verification of small cases and establish a rigorous proof that the algorithm behaves as expected for all possible inputs, which is why inductive reasoning is a fundamental prerequisite for this course.


## Setting Up the Inductive Proof

To structure an inductive proof for an algorithm, we require three main components: a base case, an inductive hypothesis, and an inductive step. The inductive hypothesis is a statement that we assume holds for a smaller value, which we then use to argue the correctness for a larger value in our well-ordered set. For the birthday problem, we define our hypothesis based on the number of students interviewed, $K$. Specifically, the hypothesis states: 'If the first $K$ students contain a match, the algorithm returns a match before interviewing student $K+1$.' By maintaining this property throughout the execution, we ensure that when we reach the end of the class (where $N$ is the total number of students), the algorithm will have correctly identified a pair if one exists, or returned 'none' if no match is found among the $N$ students.


## Base Case and Inductive Step

The base case is the simplest scenario where we can verify our hypothesis. For the birthday problem, the most efficient base case is $K=0$. After interviewing zero students, we have performed no work, and it is trivially true that there is no match among zero students. Thus, the predicate holds. With the base case established, we proceed to the inductive step. We assume the inductive hypothesis is true for some $K=K'$, and we consider the case for $K'+1$. This allows us to break the problem down into a smaller interface, avoiding the need to consider the entire set at once. We analyze two scenarios: either a match was already found in the first $K'$ students (in which case the algorithm has already returned the correct answer), or we must check the $K'+1$ student against the existing record to see if a new match is created.


## Case Analysis and Conclusion

The inductive step relies on a case analysis to maintain the inductive hypothesis: 1. **Case 1:** If the first $K'$ students already contain a match, the algorithm has already returned the correct pair as per our inductive hypothesis. 2. **Case 2:** If there is no match in the first $K'$ students, we interview the $(K'+1)$-th student. We then check if this new student's birthday exists in our record. If it does, we have found a match and return it. If not, we have successfully re-established the inductive hypothesis for $K'+1$ students. This process demonstrates that the algorithm is correct for any $K$. While this level of formality is rigorous, the practical goal in this class is to communicate your algorithm clearly enough that a peer could implement it. This inductive framework is a tool you will use throughout the course to ensure your algorithms are logically sound.


---

# Efficiency and Asymptotic Analysis


## Defining Algorithmic Efficiency

Efficiency is defined not just by how fast an algorithm runs, but by how it compares to other potential approaches for solving the same problem. A common, yet flawed, approach to measuring efficiency is to simply code an algorithm and time how long it takes to execute on a computer. This method is problematic because the result depends heavily on the specific hardware used. For instance, an algorithm running on a simple watch calculator will perform significantly slower than the same algorithm running on a powerful research computer, even if the underlying code is identical. Because hardware speed varies, measuring raw time does not provide a reliable, abstract measure of an algorithm's performance. Instead, we aim to abstract the machine out of the picture by assuming each fundamental operation takes a fixed amount of time. We then measure efficiency by counting how many of these fundamental operations the algorithm must perform to solve the problem, providing an abstract notion of performance rather than an implementation-dependent one.


## Input Size and Performance

Performance is not a static value; it depends on the size of the input data. For example, an algorithm designed to find a birthday will run faster when searching through a small section of people compared to searching through a much larger group. We typically use the variable $N$ to represent the size of the input, though the definition of input size depends on the context. If we are given an $N \times N$ array, the input size is $N^2$. If we are given a graph, the input size is typically defined as the number of vertices plus the number of edges, as this represents the space required to convey that information. By analyzing how performance changes relative to the input size, we can compare algorithms effectively. This approach allows us to understand how an algorithm scales as the input grows, which is a more useful metric than raw execution time on a specific machine.


## Asymptotic Notation

To formally describe performance relative to input size, we use asymptotic analysis. This involves three primary types of notation to bound the growth of functions: Big O notation, which provides an upper bound; Omega notation, which provides a lower bound; and Theta notation, which provides a tight bound by being bounded from both above and below. These notations allow us to categorize algorithms based on their growth rates. A common example is a linear time algorithm, where the performance is linear with respect to the size of the input, such as when adding elements to a list. By using these asymptotic tools, we can classify algorithms into common categories that relate input size to performance, helping us understand the efficiency of an algorithm in a general, machine-independent way.


---

# Common Running Time Functions


## Defining Running Time Categories

Algorithms are categorized by their running time functions, which describe how performance scales with input size $N$. Constant time operations do not depend on the input size at all. Logarithmic time is highly efficient, appearing nearly constant at large scales. Linear time, denoted as $\Theta(N)$, serves as a primary baseline for comparison. Moving beyond these, we encounter $N \log N$ (log-linear) time, which eventually behaves like a linear function with a constant multiplier. Quadratic time, $\Theta(N^2)$, is a specific instance of polynomial time. In general, polynomial time is defined as $\Theta(N^C)$ for some constant $C$. In this course, polynomial time is typically considered the threshold for an efficient algorithm, whereas exponential time, such as $2^{\Theta(N)}$, is considered inefficient and performs poorly as $N$ increases.


## Visualizing Growth Rates

To understand the difference between these functions, we can plot them on a graph with $N$ on the horizontal axis (up to 1,000) and running time on the vertical axis. Constant time appears as a flat horizontal line. Linear time appears as a straight diagonal line. Logarithmic time grows slowly, staying closer to the constant line than the linear line, and effectively flattens out as $N$ becomes very large. Conversely, exponential time functions grow extremely rapidly, appearing as a steep, nearly vertical line on the same scale. Quadratic and $N \log N$ functions fall between linear and exponential growth. Because exponential functions grow so much faster than polynomial functions, they are generally avoided. The goal is to keep the running time from increasing too rapidly relative to the input size.


## Models of Computation

To measure these running times accurately, we must establish a formal model of computation that defines which operations are considered to take constant time. Without a defined model, it is impossible to count fundamental operations. In this class, we utilize the Word RAM model. This model is chosen for its theoretical brevity and provides a standard framework for determining what a computer is allowed to do in a fixed, constant amount of time. Defining this model is a necessary step before we can rigorously analyze the efficiency of various algorithms.


---

# The Word RAM Model


## The Word RAM Model Fundamentals

The Word RAM model serves as our theoretical framework for analyzing algorithms. At its core, it assumes random access memory, meaning we can access any location in memory in constant time. Conceptually, memory is treated as a string of bits—a sequence of ones and zeros. A computer consists of a CPU that holds a small amount of information and operates on it. The CPU possesses instructions to randomly access specific memory locations, retrieve data, perform operations, and write results back. Crucially, we do not address individual bits. Instead, modern computers are byte-addressable, meaning there is a unique address for every consecutive eight-bit chunk. This structure allows the CPU to interact with memory in fixed-size units, which are fundamental to how we model computational efficiency and memory access.


## Word Size and Addressing Limitations

A 'word' is defined as the fixed number of bits the CPU can retrieve from memory and operate on in a single cycle. Modern computers typically utilize a 64-bit word size. Historically, 32-bit architectures were common, which imposed significant constraints on memory addressing. Because an address must be stored within a word in the CPU, a 32-bit system can only address $2^{32}$ distinct memory locations. This equates to a limit of approximately 4 gigabytes of addressable memory, necessitating the partitioning of larger hard drives into 4-gigabyte chunks in the past. In contrast, a 64-bit word size allows for addressing up to 20 exabytes, a capacity far exceeding current global data storage requirements, effectively removing this specific architectural bottleneck for modern applications.


## CPU Operations and Complexity

In the Word RAM model, the CPU performs operations on data retrieved from memory. Available operations generally include: 
- Integer arithmetic
- Logical operations
- Bitwise operations
- Comparison of two words
- Constant-time read/write access to memory addresses

The CPU is designed to operate on a constant amount of information at once; typically, it takes two words, performs an operation, and produces a third word. Because the CPU operates on a constant amount of memory in constant time, any algorithm requiring operations on a linear amount of memory will inherently take linear time. This model provides the standard basis for analyzing the efficiency of algorithms, focusing on the time required to process data based on these fundamental, constant-time operations.


---

# Data Structures and Course Overview


## Introduction to Data Structures

The course will focus on data structures for the first half, specifically the first eight lectures. Unlike the CPU model which operates on a constant amount of data, data structures are designed to store and manage large amounts of information. The goal is to support various operations on this non-constant amount of data efficiently. A fundamental example of a data structure is the static array, which can be used to maintain records, such as a list of birthdays. This approach differs from high-level languages like Python, which provide built-in structures like lists, sets, and dictionaries. While convenient, these Python abstractions often obscure the underlying performance costs, as there is significant code between the user and the computer. By studying data structures directly, we aim to understand how to store information to make specific operations faster.


## Problem-Solving Strategies

To solve algorithmic problems in this class, there are two primary strategies. First, one can reduce a new problem to a solution for a problem that is already known and understood. Second, one can design a custom algorithm, which is typically recursive in nature. These design paradigms are essential tools for tackling the various challenges presented throughout the course. Whether we are storing data in a structure, solving a sorting problem, or performing a search within a graph, these two approaches—reduction and recursive design—form the backbone of our methodology. Understanding when to apply each strategy is a key skill for algorithm design.


## Course Roadmap

The course is structured into three main segments, each culminating in a quiz: 
- **Quiz 1 (Lectures 1-8):** Focuses on data structures and sorting algorithms.
- **Quiz 2:** Covers shortest path algorithms and graph theory.
- **Final Segment:** Dedicated to dynamic programming.

This progression moves from fundamental data storage and manipulation to more complex algorithmic paradigms, providing a comprehensive overview of computational problem-solving.
