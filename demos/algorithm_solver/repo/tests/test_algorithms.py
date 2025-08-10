import pytest
from algorithms import (
    quick_sort, merge_sort, heap_sort, bubble_sort,
    binary_search, linear_search, find_kth_largest,
    Graph, bfs, dfs, dijkstra, find_path,
    fibonacci, longest_common_subsequence, knapsack,
    MinHeap, Trie
)

# ============================================================================
# SORTING TESTS
# ============================================================================

def test_quick_sort():
    assert quick_sort([64, 34, 25, 12, 22, 11, 90]) == [11, 12, 22, 25, 34, 64, 90]
    assert quick_sort([]) == []
    assert quick_sort([1]) == [1]
    assert quick_sort([3, 2, 1]) == [1, 2, 3]

def test_merge_sort():
    assert merge_sort([64, 34, 25, 12, 22, 11, 90]) == [11, 12, 22, 25, 34, 64, 90]
    assert merge_sort([]) == []
    assert merge_sort([1]) == [1]
    assert merge_sort([5, 2, 8, 1, 9]) == [1, 2, 5, 8, 9]

def test_heap_sort():
    assert heap_sort([64, 34, 25, 12, 22, 11, 90]) == [11, 12, 22, 25, 34, 64, 90]
    assert heap_sort([]) == []
    assert heap_sort([1]) == [1]
    assert heap_sort([4, 1, 3, 2, 16, 9, 10, 14, 8, 7]) == [1, 2, 3, 4, 7, 8, 9, 10, 14, 16]

def test_bubble_sort():
    assert bubble_sort([64, 34, 25, 12, 22, 11, 90]) == [11, 12, 22, 25, 34, 64, 90]
    assert bubble_sort([]) == []
    assert bubble_sort([1]) == [1]

# ============================================================================
# SEARCHING TESTS
# ============================================================================

def test_binary_search():
    arr = [1, 3, 5, 7, 9, 11, 13, 15]
    assert binary_search(arr, 7) == 3
    assert binary_search(arr, 1) == 0
    assert binary_search(arr, 15) == 7
    assert binary_search(arr, 6) == -1
    assert binary_search([], 5) == -1

def test_linear_search():
    arr = [64, 34, 25, 12, 22, 11, 90]
    assert linear_search(arr, 25) == 2
    assert linear_search(arr, 64) == 0
    assert linear_search(arr, 90) == 6
    assert linear_search(arr, 100) == -1
    assert linear_search([], 5) == -1

def test_find_kth_largest():
    assert find_kth_largest([3, 2, 1, 5, 6, 4], 2) == 5
    assert find_kth_largest([3, 2, 3, 1, 2, 4, 5, 5, 6], 4) == 4
    assert find_kth_largest([1], 1) == 1
    assert find_kth_largest([7, 10, 4, 3, 20, 15], 3) == 10

# ============================================================================
# GRAPH TESTS
# ============================================================================

def test_graph_basic_operations():
    g = Graph()
    g.add_vertex("A")
    g.add_vertex("B")
    g.add_vertex("C")
    
    g.add_edge("A", "B", 5)
    g.add_edge("B", "C", 3)
    g.add_edge("A", "C", 7)
    
    neighbors_a = g.get_neighbors("A")
    assert len(neighbors_a) == 2
    assert ("B", 5) in neighbors_a
    assert ("C", 7) in neighbors_a

def test_bfs():
    g = Graph()
    for vertex in ["A", "B", "C", "D", "E"]:
        g.add_vertex(vertex)
    
    g.add_edge("A", "B")
    g.add_edge("A", "C")
    g.add_edge("B", "D")
    g.add_edge("C", "E")
    
    result = bfs(g, "A")
    assert result[0] == "A"
    assert "B" in result
    assert "C" in result
    assert len(result) == 5

def test_dfs():
    g = Graph()
    for vertex in ["A", "B", "C", "D"]:
        g.add_vertex(vertex)
    
    g.add_edge("A", "B")
    g.add_edge("A", "C")
    g.add_edge("B", "D")
    
    result = dfs(g, "A")
    assert result[0] == "A"
    assert len(result) == 4

def test_dijkstra():
    g = Graph()
    for vertex in ["A", "B", "C", "D"]:
        g.add_vertex(vertex)
    
    g.add_edge("A", "B", 4)
    g.add_edge("A", "C", 2)
    g.add_edge("B", "C", 1)
    g.add_edge("B", "D", 5)
    g.add_edge("C", "D", 8)
    
    distances = dijkstra(g, "A")
    assert distances["A"] == 0
    assert distances["B"] == 3  # A->C->B
    assert distances["C"] == 2  # A->C
    assert distances["D"] == 8  # A->C->B->D

def test_find_path():
    g = Graph()
    for vertex in ["A", "B", "C", "D"]:
        g.add_vertex(vertex)
    
    g.add_edge("A", "B")
    g.add_edge("B", "C")
    g.add_edge("C", "D")
    
    path = find_path(g, "A", "D")
    assert path is not None
    assert path[0] == "A"
    assert path[-1] == "D"
    assert len(path) == 4

    # Test disconnected graph
    g.add_vertex("E")
    path = find_path(g, "A", "E")
    assert path is None

# ============================================================================
# DYNAMIC PROGRAMMING TESTS
# ============================================================================

def test_fibonacci():
    assert fibonacci(0) == 0
    assert fibonacci(1) == 1
    assert fibonacci(5) == 5
    assert fibonacci(10) == 55
    assert fibonacci(15) == 610

def test_longest_common_subsequence():
    assert longest_common_subsequence("ABCDGH", "AEDFHR") == 3  # "ADH"
    assert longest_common_subsequence("AGGTAB", "GXTXAYB") == 4  # "GTAB"
    assert longest_common_subsequence("", "ABC") == 0
    assert longest_common_subsequence("ABC", "") == 0
    assert longest_common_subsequence("ABC", "ABC") == 3

def test_knapsack():
    weights = [10, 20, 30]
    values = [60, 100, 120]
    capacity = 50
    assert knapsack(weights, values, capacity) == 220  # items 1 and 2
    
    weights = [2, 1, 3, 2]
    values = [12, 10, 20, 15]
    capacity = 5
    assert knapsack(weights, values, capacity) == 37  # items 0, 1, 3

# ============================================================================
# DATA STRUCTURE TESTS
# ============================================================================

def test_min_heap():
    heap = MinHeap()
    
    # Test insertion and peek
    heap.insert(10)
    heap.insert(5)
    heap.insert(15)
    heap.insert(2)
    
    assert heap.peek() == 2
    assert heap.size() == 4
    
    # Test extraction
    assert heap.extract_min() == 2
    assert heap.peek() == 5
    assert heap.size() == 3
    
    assert heap.extract_min() == 5
    assert heap.extract_min() == 10
    assert heap.extract_min() == 15
    assert heap.size() == 0

def test_min_heap_empty():
    heap = MinHeap()
    with pytest.raises(IndexError):
        heap.peek()
    with pytest.raises(IndexError):
        heap.extract_min()

def test_trie():
    trie = Trie()
    
    # Test insertion and search
    trie.insert("apple")
    trie.insert("app")
    trie.insert("application")
    
    assert trie.search("app") == True
    assert trie.search("apple") == True
    assert trie.search("appl") == False
    assert trie.search("banana") == False
    
    # Test prefix matching
    assert trie.starts_with("app") == True
    assert trie.starts_with("appl") == True
    assert trie.starts_with("applic") == True
    assert trie.starts_with("ban") == False
    assert trie.starts_with("") == True  # Empty prefix should match

def test_trie_empty():
    trie = Trie()
    assert trie.search("word") == False
    assert trie.starts_with("prefix") == False
    assert trie.starts_with("") == True
