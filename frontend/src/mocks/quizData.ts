import type { Question } from '../stores/useQuizStore'

export const mockQuizQuestions: Question[] = [
  {
    id: 1,
    type: 'MCQ',
    question: 'Which activation function is most commonly associated with the vanishing gradient problem?',
    options: ['ReLU', 'Sigmoid', 'Leaky ReLU', 'Tanh'],
    answer: 'Sigmoid',
    explanation:
      'Sigmoid\'s derivative is always between 0 and 0.25, causing gradients to shrink exponentially.',
  },
  {
    id: 2,
    type: 'True/False',
    question: 'Dropout is applied during inference to improve prediction accuracy.',
    options: ['True', 'False'],
    answer: 'False',
    explanation:
      'Dropout is strictly a training technique. During inference, the full network is used.',
  },
  {
    id: 3,
    type: 'MCQ',
    question: 'What is the time complexity of a Segment Tree range query?',
    options: ['O(1)', 'O(log N)', 'O(N)', 'O(N log N)'],
    answer: 'O(log N)',
    explanation: 'The tree height is log N, and at most 4 nodes are visited per level.',
  },
  {
    id: 4,
    type: 'True/False',
    question: 'A Prefix Sum Array can handle point updates in O(1) time.',
    options: ['True', 'False'],
    answer: 'False',
    explanation: 'Prefix Sum updates take O(N) because all prefix sums must be recomputed.',
  },
  {
    id: 5,
    type: 'ShortAnswer',
    question: 'What does the "associative" property mean for a segment tree operation?',
    options: [],
    answer: 'The operation can be decomposed over a range',
    explanation: 'Associative operations like sum, min, max can be split and recombined.',
  },
]