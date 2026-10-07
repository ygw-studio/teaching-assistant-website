"""Self-contained teaching examples; original textbook files stay in the resource ZIPs."""

EXAMPLES = {
    "sequence": ('''items = [10, 20, 30]
items.insert(1, 15)
items.remove(20)
print(items)
print("30的位置：", items.index(30))
''', '[10, 15, 30]\n30的位置： 2\n'),
    "linked": ('''class Node:
    def __init__(self, value, next=None):
        self.value, self.next = value, next

head = Node(1, Node(2, Node(3)))
head.next = Node(9, head.next)
values = []
current = head
while current is not None:
    values.append(current.value)
    current = current.next
print(values)
''', '[1, 9, 2, 3]\n'),
    "stack": ('''stack = []
for value in [1, 2, 3]:
    stack.append(value)
print("栈顶：", stack[-1])
print("出栈：", stack.pop())
print("剩余：", stack)
''', '栈顶： 3\n出栈： 3\n剩余： [1, 2]\n'),
    "brackets": ('''def matched(text):
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    for char in text:
        if char in '([{':
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False
    return not stack

print(matched("{[()]}"))
print(matched("([)]"))
''', 'True\nFalse\n'),
    "queue": ('''from collections import deque
queue = deque([1, 2, 3])
queue.append(4)
print("出队：", queue.popleft())
print("剩余：", list(queue))
''', '出队： 1\n剩余： [2, 3, 4]\n'),
    "circular": ('''capacity = 5
front, rear = 3, 1
length = (rear - front + capacity) % capacity
print("队列长度：", length)
print("是否为空：", front == rear)
print("是否已满：", (rear + 1) % capacity == front)
''', '队列长度： 3\n是否为空： False\n是否已满： False\n'),
    "priority": ('''import heapq
tasks = []
for order, (name, priority) in enumerate([("A", 2), ("B", 1), ("C", 1)]):
    heapq.heappush(tasks, (priority, order, name))
while tasks:
    print(heapq.heappop(tasks)[2])
''', 'B\nC\nA\n'),
    "string": ('''text = "Python数据结构"
print(text[0:6])
print(text.find("数据"))
print(text[:6] + "课程")
''', 'Python\n6\nPython课程\n'),
    "bf": ('''def find(text, pattern):
    for start in range(len(text) - len(pattern) + 1):
        offset = 0
        while offset < len(pattern) and text[start + offset] == pattern[offset]:
            offset += 1
        if offset == len(pattern):
            return start
    return -1

print(find("ababcabcacbab", "abcac"))
''', '5\n'),
    "kmp": ('''def kmp(text, pattern):
    if not pattern:
        return 0
    prefix = [0] * len(pattern)
    matched = 0
    for i in range(1, len(pattern)):
        while matched and pattern[i] != pattern[matched]:
            matched = prefix[matched - 1]
        if pattern[i] == pattern[matched]:
            matched += 1
        prefix[i] = matched
    matched = 0
    for i, char in enumerate(text):
        while matched and char != pattern[matched]:
            matched = prefix[matched - 1]
        if char == pattern[matched]:
            matched += 1
        if matched == len(pattern):
            return i - len(pattern) + 1
    return -1

print(kmp("ababcabcacbab", "abcac"))
''', '5\n'),
    "matrix": ('''matrix = [[1, 2, 3], [4, 5, 6]]
transposed = [[matrix[row][col] for row in range(2)] for col in range(3)]
print(transposed)
''', '[[1, 4], [2, 5], [3, 6]]\n'),
    "sparse": ('''matrix = [[0, 2, 0], [0, 0, 0], [3, 0, 4]]
triples = [(i, j, value) for i, row in enumerate(matrix)
           for j, value in enumerate(row) if value != 0]
print(triples)
''', '[(0, 1, 2), (2, 0, 3), (2, 2, 4)]\n'),
    "tree": ('''class Node:
    def __init__(self, value, left=None, right=None):
        self.value, self.left, self.right = value, left, right

def inorder(node):
    if node is None:
        return []
    return inorder(node.left) + [node.value] + inorder(node.right)

root = Node("A", Node("B", Node("D"), Node("E")), Node("C"))
print(inorder(root))
''', "['D', 'B', 'E', 'A', 'C']\n"),
    "depth": ('''def depth(tree):
    if tree is None:
        return 0
    value, left, right = tree
    return 1 + max(depth(left), depth(right))

tree = ("A", ("B", ("D", None, None), None), ("C", None, None))
print(depth(tree))
''', '3\n'),
    "huffman": ('''import heapq
weights = [5, 2, 9, 11, 8, 3, 7]
heapq.heapify(weights)
cost = 0
while len(weights) > 1:
    merged = heapq.heappop(weights) + heapq.heappop(weights)
    cost += merged
    heapq.heappush(weights, merged)
print("带权路径长度：", cost)
''', '带权路径长度： 120\n'),
    "bfs": ('''from collections import deque
graph = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
queue, visited, order = deque(["A"]), {"A"}, []
while queue:
    vertex = queue.popleft()
    order.append(vertex)
    for neighbor in graph[vertex]:
        if neighbor not in visited:
            visited.add(neighbor)
            queue.append(neighbor)
print(order)
''', "['A', 'B', 'C', 'D']\n"),
    "dfs": ('''graph = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
visited, order = set(), []
def dfs(vertex):
    visited.add(vertex)
    order.append(vertex)
    for neighbor in graph[vertex]:
        if neighbor not in visited:
            dfs(neighbor)
dfs("A")
print(order)
''', "['A', 'B', 'D', 'C']\n"),
    "kruskal": ('''edges = [(1, "A", "B"), (2, "B", "C"), (4, "A", "C")]
parent = {vertex: vertex for vertex in "ABC"}
def find(vertex):
    while parent[vertex] != vertex:
        parent[vertex] = parent[parent[vertex]]
        vertex = parent[vertex]
    return vertex
total = 0
for weight, a, b in sorted(edges):
    root_a, root_b = find(a), find(b)
    if root_a != root_b:
        parent[root_a] = root_b
        total += weight
        print(a, b, weight)
print("总权值：", total)
''', 'A B 1\nB C 2\n总权值： 3\n'),
    "prim": ('''import heapq
graph = {"A": [(1, "B"), (4, "C")], "B": [(1, "A"), (2, "C")], "C": [(4, "A"), (2, "B")]}
visited, heap, total = set(), [(0, "A")], 0
while heap:
    weight, vertex = heapq.heappop(heap)
    if vertex in visited:
        continue
    visited.add(vertex)
    total += weight
    for edge in graph[vertex]:
        if edge[1] not in visited:
            heapq.heappush(heap, edge)
print("总权值：", total)
''', '总权值： 3\n'),
    "dijkstra": ('''import heapq
graph = {"A": [(1, "B"), (4, "C")], "B": [(2, "C")], "C": []}
distance = {vertex: float("inf") for vertex in graph}
distance["A"] = 0
heap = [(0, "A")]
while heap:
    cost, vertex = heapq.heappop(heap)
    if cost != distance[vertex]:
        continue
    for weight, neighbor in graph[vertex]:
        candidate = cost + weight
        if candidate < distance[neighbor]:
            distance[neighbor] = candidate
            heapq.heappush(heap, (candidate, neighbor))
print(distance)
''', "{'A': 0, 'B': 1, 'C': 3}\n"),
    "floyd": ('''inf = float("inf")
distance = [[0, 1, 4], [inf, 0, 2], [inf, inf, 0]]
for k in range(3):
    for i in range(3):
        for j in range(3):
            distance[i][j] = min(distance[i][j], distance[i][k] + distance[k][j])
print(distance[0])
''', '[0, 1, 3]\n'),
    "topological": ('''from collections import deque
graph = {"A": ["C"], "B": ["C"], "C": ["D"], "D": []}
degree = dict.fromkeys(graph, 0)
for neighbors in graph.values():
    for neighbor in neighbors:
        degree[neighbor] += 1
queue = deque(vertex for vertex in graph if degree[vertex] == 0)
order = []
while queue:
    vertex = queue.popleft()
    order.append(vertex)
    for neighbor in graph[vertex]:
        degree[neighbor] -= 1
        if degree[neighbor] == 0:
            queue.append(neighbor)
print(order if len(order) == len(graph) else "图中存在环")
''', "['A', 'B', 'C', 'D']\n"),
    "insertion": ('''values = [5, 2, 4, 1, 3]
for i in range(1, len(values)):
    current, j = values[i], i - 1
    while j >= 0 and values[j] > current:
        values[j + 1] = values[j]
        j -= 1
    values[j + 1] = current
print(values)
''', '[1, 2, 3, 4, 5]\n'),
    "shell": ('''values = [2, 18, 23, 56, 78, 70, 45, 36, 72, 34]
gap = len(values) // 2
while gap:
    for i in range(gap, len(values)):
        current, j = values[i], i
        while j >= gap and values[j - gap] > current:
            values[j] = values[j - gap]
            j -= gap
        values[j] = current
    print("增量", gap, values)
    gap //= 2
''', '增量 5 [2, 18, 23, 56, 34, 70, 45, 36, 72, 78]\n增量 2 [2, 18, 23, 36, 34, 56, 45, 70, 72, 78]\n增量 1 [2, 18, 23, 34, 36, 45, 56, 70, 72, 78]\n'),
    "bubble": ('''values = [5, 2, 4, 1, 3]
for end in range(len(values) - 1, 0, -1):
    changed = False
    for i in range(end):
        if values[i] > values[i + 1]:
            values[i], values[i + 1] = values[i + 1], values[i]
            changed = True
    if not changed:
        break
print(values)
''', '[1, 2, 3, 4, 5]\n'),
    "quick": ('''def quicksort(values):
    if len(values) <= 1:
        return values
    pivot = values[len(values) // 2]
    left = [x for x in values if x < pivot]
    equal = [x for x in values if x == pivot]
    right = [x for x in values if x > pivot]
    return quicksort(left) + equal + quicksort(right)

print(quicksort([5, 2, 4, 1, 3]))
''', '[1, 2, 3, 4, 5]\n'),
    "selection": ('''values = [5, 2, 4, 1, 3]
for i in range(len(values) - 1):
    smallest = min(range(i, len(values)), key=lambda j: values[j])
    values[i], values[smallest] = values[smallest], values[i]
print(values)
''', '[1, 2, 3, 4, 5]\n'),
    "heap": ('''def sift_down(values, root, end):
    while 2 * root + 1 <= end:
        child = 2 * root + 1
        if child + 1 <= end and values[child] < values[child + 1]:
            child += 1
        if values[root] >= values[child]:
            return
        values[root], values[child] = values[child], values[root]
        root = child

values = [5, 2, 4, 1, 3]
for root in range(len(values) // 2 - 1, -1, -1):
    sift_down(values, root, len(values) - 1)
for end in range(len(values) - 1, 0, -1):
    values[0], values[end] = values[end], values[0]
    sift_down(values, 0, end - 1)
print(values)
''', '[1, 2, 3, 4, 5]\n'),
    "merge": ('''def merge_sort(values):
    if len(values) <= 1:
        return values
    middle = len(values) // 2
    left, right = merge_sort(values[:middle]), merge_sort(values[middle:])
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i]); i += 1
        else:
            result.append(right[j]); j += 1
    return result + left[i:] + right[j:]

print(merge_sort([5, 2, 4, 1, 3]))
''', '[1, 2, 3, 4, 5]\n'),
    "linear": ('''def search(values, target):
    for index, value in enumerate(values):
        if value == target:
            return index
    return -1
print(search([8, 3, 7, 1], 7))
print(search([8, 3, 7, 1], 9))
''', '2\n-1\n'),
    "binary": ('''def search(values, target):
    left, right = 0, len(values) - 1
    while left <= right:
        middle = (left + right) // 2
        if values[middle] == target:
            return middle
        if values[middle] < target:
            left = middle + 1
        else:
            right = middle - 1
    return -1

print(search([1, 3, 5, 7, 9], 7))
print(search([1, 3, 5, 7, 9], 4))
''', '3\n-1\n'),
    "bst": ('''class Node:
    def __init__(self, value):
        self.value, self.left, self.right = value, None, None

def insert(node, value):
    if node is None:
        return Node(value)
    if value < node.value:
        node.left = insert(node.left, value)
    elif value > node.value:
        node.right = insert(node.right, value)
    return node

def search(node, value):
    while node is not None:
        if value == node.value:
            return True
        node = node.left if value < node.value else node.right
    return False

root = None
for value in [5, 3, 7, 1, 4]:
    root = insert(root, value)
print(search(root, 4))
print(search(root, 9))
''', 'True\nFalse\n'),
    "hash": ('''buckets = [[] for _ in range(5)]
for value in [12, 7, 3, 17]:
    buckets[value % len(buckets)].append(value)
print(buckets)
target = 17
print(target in buckets[target % len(buckets)])
''', '[[], [], [12, 7, 17], [3], []]\nTrue\n'),
}
