export const chapter1NotesMd = `# Segment Trees: Introduction & Motivation

## Core Idea
A tree-based data structure designed to optimize range-based operations and point updates on dynamic arrays.

## Key Concepts
- **Point Access**: Retrieving a single element at index $i$.
- **Range Query**: Performing an operation (sum, min, max, etc.) across a contiguous block $[L, R]$.
- **Dynamic Data**: Datasets requiring frequent modifications to elements alongside frequent queries.
- **Associative Operations**: Operations that can be decomposed over a range (e.g., sum, product, min, max).

## Complexity Comparison

| Method | Range Query | Point Update | Best Use Case |
| :--- | :--- | :--- | :--- |
| **Naive (Array)** | $O(N)$ | $O(1)$ | Minimal queries |
| **Prefix Sum** | $O(1)$ | $O(N)$ | Static arrays (no updates) |
| **Segment Tree** | $O(\\log N)$ | $O(\\log N)$ | **Dynamic arrays** (frequent both) |

## Important Observations
- **The Efficiency Gap**: Naive range scans ($O(N)$) create performance bottlenecks in large datasets.
- **Dynamic Limitation**: Prefix Sum arrays are unsuitable for dynamic data because a single element update forces an $O(N)$ recomputation.
- **The Balance**: Segment Trees provide the optimal trade-off by maintaining logarithmic efficiency for both queries and updates.

## Code Example

\`\`\`cpp
void build(int node, int start, int end) {
    if (start == end) {
        tree[node] = arr[start];
        return;
    }
    int mid = (start + end) / 2;
    build(2 * node, start, mid);
    build(2 * node + 1, mid + 1, end);
    tree[node] = tree[2 * node] + tree[2 * node + 1];
}
\`\`\`

## Applications
- Range Sum Query (RSQ)
- Range Minimum/Maximum Query (RMQ)
- Range Product Query
`