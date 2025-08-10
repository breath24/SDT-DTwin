# Implement Algorithm Collection

Create a comprehensive algorithm library in `algorithms.py` with the following components:

## Sorting Algorithms
1. **`quick_sort(arr)`** - Implement quicksort with random pivot selection
2. **`merge_sort(arr)`** - Implement merge sort algorithm
3. **`heap_sort(arr)`** - Implement heap sort using a binary heap
4. **`bubble_sort(arr)`** - Implement bubble sort (for comparison)

## Searching Algorithms
1. **`binary_search(arr, target)`** - Binary search on sorted array (return index or -1)
2. **`linear_search(arr, target)`** - Linear search (return index or -1)
3. **`find_kth_largest(arr, k)`** - Find the k-th largest element using quickselect

## Graph Algorithms
1. **`Graph` class** - Implement adjacency list representation with methods:
   - `add_vertex(vertex)` - Add vertex to graph
   - `add_edge(v1, v2, weight=1)` - Add edge (undirected by default)
   - `get_neighbors(vertex)` - Get all neighbors of a vertex
2. **`bfs(graph, start)`** - Breadth-first search returning visited order
3. **`dfs(graph, start)`** - Depth-first search returning visited order
4. **`dijkstra(graph, start)`** - Shortest path from start to all vertices
5. **`find_path(graph, start, end)`** - Find any path between two vertices

## Dynamic Programming
1. **`fibonacci(n)`** - Fibonacci with memoization
2. **`longest_common_subsequence(str1, str2)`** - LCS length
3. **`knapsack(weights, values, capacity)`** - 0/1 knapsack problem

## Data Structures
1. **`MinHeap` class** - Binary min heap with insert, extract_min, peek
2. **`Trie` class** - Prefix tree with insert, search, starts_with methods

Include comprehensive error handling, input validation, and performance analysis comments. Make all tests pass with `python -m pytest`.
