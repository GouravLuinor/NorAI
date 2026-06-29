// Mock data for Chapter 1 — Segment Trees
// Matches the revision card types from the mockup

export interface RevisionCard {
  type: 'definition' | 'algorithm' | 'example' | 'complexity' | 'hint' | 'mistake' | 'figure'
  title?: string
  term?: string
  description?: string
  steps?: string[]
  rows?: { label: string; value: string }[]
  caption?: string
}

export interface RevisionChapter {
  chapterId: number
  title: string
  lectureInfo: string
  lastEdited: string
  readTime: string
  sections: {
    heading: string
    anchor: string
    paragraphs?: string[]
    cards?: RevisionCard[]
  }[]
}

export const chapter1Revision: RevisionChapter = {
  chapterId: 1,
  title: 'Segment Trees: Introduction & Motivation',
  lectureInfo: 'Lecture 1 · 47 min',
  lastEdited: '2h ago',
  readTime: '6 min read',
  sections: [
    {
      heading: 'Core Concept',
      anchor: 'sec-core-concept',
      paragraphs: [
        'A Segment Tree is a specialized **binary tree** designed to represent an array through a hierarchy of intervals. It enables efficient range queries and point updates on dynamic arrays — something neither naive arrays nor prefix sums can do simultaneously.',
      ],
      cards: [
        {
          type: 'definition',
          title: 'Definition',
          term: 'Segment Tree',
          description:
            'A tree‑based data structure that stores information about intervals or segments. Each node represents a range of the original array, with the root covering the entire array and leaf nodes representing individual elements. Both range queries and point updates run in **O(log N)** time.',
        },
        {
          type: 'figure',
          caption: 'Segment Tree structure overview, 03:12',
        },
      ],
    },
    {
      heading: 'The Efficiency Gap',
      anchor: 'sec-efficiency-gap',
      paragraphs: [
        'When working with arrays, three common approaches exist for range queries and updates. Each has a different trade‑off profile:',
      ],
      cards: [
        {
          type: 'complexity',
          title: 'Range Analysis',
          term: 'Complexity comparison by approach',
          rows: [
            { label: 'Naive Array (linear scan)', value: 'O(N) query, O(1) update' },
            { label: 'Prefix Sum Array', value: 'O(1) query, O(N) update' },
            { label: 'Segment Tree', value: 'O(log N) query, O(log N) update' },
          ],
        },
        {
          type: 'hint',
          description:
            'The Segment Tree provides the optimal trade‑off for **dynamic arrays** where both queries and updates happen frequently. Neither naive arrays nor prefix sums can handle both efficiently.',
        },
      ],
    },
    {
      heading: 'How It Works',
      anchor: 'sec-how-it-works',
      paragraphs: [
        'A Segment Tree is built recursively. Start with the entire array range at the root, then repeatedly split each range at its midpoint until individual elements are reached.',
      ],
      cards: [
        {
          type: 'algorithm',
          title: 'Algorithm',
          term: 'Recursive tree construction',
          steps: [
            'Take the input array and the current range [L, R].',
            'If L == R, create a leaf node storing arr[L] and return.',
            'Compute mid = ⌊(L + R) / 2⌋.',
            'Recursively build the left child for range [L, mid].',
            'Recursively build the right child for range [mid+1, R].',
            'Create the parent node by combining the values of the two children (e.g., sum, min, max).',
          ],
        },
        {
          type: 'example',
          title: 'Worked Example',
          description:
            'For an array **[1, 3, 5, 7]**, the root covers [0, 3] and stores the sum 16. Its left child covers [0, 1] with sum 4 (1+3). Its right child covers [2, 3] with sum 12 (5+7). The leaves are the individual elements: 1, 3, 5, 7.',
        },
      ],
    },
    {
      heading: 'Key Properties',
      anchor: 'sec-key-properties',
      paragraphs: [
        'Segment Trees have several important structural properties that make them efficient:',
      ],
      cards: [
        {
          type: 'definition',
          title: 'Definition',
          term: 'Full Binary Tree',
          description:
            'Every node in a Segment Tree has either 0 or 2 children — never 1. This guarantees a balanced structure where the height is exactly ⌈log₂ N⌉ + 1, and the total number of nodes is at most 4N.',
        },
        {
          type: 'mistake',
          description:
            'A common confusion is thinking Segment Trees always use arrays for implementation. While array‑based implementations are popular for efficiency, the conceptual structure is a **node‑based tree**. The array representation is an optimization, not a requirement.',
        },
      ],
    },
  ],
}