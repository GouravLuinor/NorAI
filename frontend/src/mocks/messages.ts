import type { Message } from '../stores/useThreadStore'

export const mockMessages: Message[] = [
  {
    id: '1',
    role: 'assistant',
    content: 'Hey! Notes for **Ch 01 — Segment Trees** are loaded. What do you want to dig into?',
    timestamp: '11:38 PM',
  },
  {
    id: '2',
    role: 'user',
    content: 'What is a segment tree?',
    timestamp: '11:41 PM',
  },
  {
    id: '3',
    role: 'assistant',
    content: `A Segment Tree is a specialized **full binary tree** designed to represent an array through a hierarchy of intervals. It works by recursively partitioning an array range into smaller sub‑ranges to store information about different segments.

**Sources**
• Structure and Properties of Segment Trees > Core Concepts`,
    timestamp: '11:41 PM',
  },
  {
    id: '4',
    role: 'user',
    content: 'Yeah teach me with an example',
    timestamp: '11:43 PM',
  },
  {
    id: '5',
    role: 'assistant',
    content: `Let's use a simple array of four numbers: **[1, 3, 5, 7]**.

To build the tree, start with the whole range [0, 3] at the root. Split at the midpoint into left child [0, 1] and right child [2, 3]. Keep splitting until you reach leaf nodes representing individual elements.

The lecture slide on **Recursive Tree Construction** illustrates this step by step.`,
    timestamp: '11:43 PM',
  },
]