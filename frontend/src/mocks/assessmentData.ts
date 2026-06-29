export interface AssessmentQuestion {
  question_id: number
  chapter_id: number
  type: 'MCQ' | 'True/False' | 'Short Answer' | 'Fill in the Blank' | 'Complexity' | 'Scenario' | 'Conceptual'
  difficulty: 'Easy' | 'Medium' | 'Hard'
  concepts: string[]
  question: string
  options: string[]
  answer: string
  explanation: string
}

export const chapter1Assessment: AssessmentQuestion[] = [
  {
    question_id: 1,
    chapter_id: 1,
    type: 'MCQ',
    difficulty: 'Easy',
    concepts: ['Point Access Complexity'],
    question:
      'In a standard array‑based data management system, what is the time complexity of accessing a single element at a specific index?',
    options: ['O(1)', 'O(log N)', 'O(N)', 'O(N log N)'],
    answer: 'O(1)',
    explanation:
      'Accessing a single element at a specific index in a standard array is highly efficient and takes constant time, or O(1).',
  },
  {
    question_id: 2,
    chapter_id: 1,
    type: 'True/False',
    difficulty: 'Medium',
    concepts: ['Prefix Sum vs Segment Tree'],
    question:
      'If an array is dynamic and elements are frequently modified, a Prefix Sum Array is more efficient than a Segment Tree for performing range sum queries.',
    options: ['True', 'False'],
    answer: 'False',
    explanation:
      'While Prefix Sum Arrays offer O(1) queries, updating an element in a Prefix Sum Array takes O(N) time. A Segment Tree is more efficient for dynamic data because it handles both updates and queries in O(log N) time.',
  },
  {
    question_id: 3,
    chapter_id: 1,
    type: 'Complexity',
    difficulty: 'Medium',
    concepts: ['Naive Range Query Complexity'],
    question:
      'What is the worst‑case time complexity of performing a range query using a naive linear scan approach on an array of size N?',
    options: [],
    answer: 'O(N)',
    explanation:
      'In the worst case, a naive range query must iterate through the entire array from index L to R, which can span all N elements.',
  },
  {
    question_id: 4,
    chapter_id: 1,
    type: 'Scenario',
    difficulty: 'Hard',
    concepts: ['Dynamic Data Requirements'],
    question:
      'A developer is building a system for a real‑time leaderboard where player scores are constantly being updated, and the system must frequently calculate the sum of scores within specific rank ranges. Why would a Segment Tree be a better choice than a Prefix Sum Array for this application?',
    options: [],
    answer:
      'A Prefix Sum Array would require O(N) time to recompute sums every time a player\'s score is updated, creating a bottleneck. A Segment Tree maintains O(log N) efficiency for both the frequent updates and the frequent range sum queries.',
    explanation:
      'The Segment Tree provides the necessary balance for dynamic datasets, ensuring that neither frequent modifications nor frequent queries become a computational bottleneck by keeping both at O(log N).',
  },
  {
    question_id: 5,
    chapter_id: 1,
    type: 'Fill in the Blank',
    difficulty: 'Easy',
    concepts: ['Point Access vs Range Query'],
    question:
      'In the context of array operations, retrieving a single element at a specific index is called ____ access, whereas performing an operation across a contiguous block of elements is called a range query.',
    options: [],
    answer: 'point',
    explanation:
      'The notes distinguish between "Point Access" (retrieving a single element) and "Range Query" (operating on a block of elements).',
  },
  {
    question_id: 6,
    chapter_id: 1,
    type: 'Short Answer',
    difficulty: 'Medium',
    concepts: ['Segment Tree Update Complexity'],
    question:
      'What is the time complexity of a single point update operation when using a Segment Tree?',
    options: [],
    answer: 'O(log N)',
    explanation:
      'A Segment Tree is designed to reduce the time complexity of both range queries and point updates to O(log N).',
  },
]