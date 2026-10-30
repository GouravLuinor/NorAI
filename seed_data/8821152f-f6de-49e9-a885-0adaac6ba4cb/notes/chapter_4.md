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
