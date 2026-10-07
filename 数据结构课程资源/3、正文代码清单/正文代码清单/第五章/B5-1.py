from abc import ABCMeta,abstractmethod,abstractproperty

class IQueue(metaclass=ABCMeta):
    @abstractmethod
    def clear(self):
        '''将队列置空'''
        pass
    @abstractmethod
    def isEmpty(self):
        '''判断队列是否为空'''
        pass
    @abstractmethod
    def length(self):
        '''返回队列的数据元素个数'''
        pass
    @abstractmethod
    def peek(self):
        '''返回队首元素'''
        pass
    @abstractmethod
    def offer(self,x):
        '''将数据元素x插入到队列成为队尾元素'''
        pass
    @abstractmethod
    def poll(self):
        '''将队首元素删除并返回其值'''
        pass
    @abstractmethod
    def display(self):
        '''输出队列中的所有元素'''
        pass

class Node(object):
    def __init__(self,data=None,next=None):
        self.data = data
        self.next = next

class LinkQueue(IQueue):
    def __init__(self):
        self.front = None # 队首指针
        self.rear = None # 队尾指针

    def clear(self):
        '''将队列置空'''
        self.front = None
        self.rear = None

    def isEmpty(self):
        '''判断队列是否为空'''
        return self.front is None

    def length(self):
        '''返回队列的数据元素个数'''
        p = self.front
        i = 0
        while p is not None:
            p = p.next
            i +=1
        return i

    def peek(self):
        '''返回队首元素'''
        if self.isEmpty():
            return None
        else:
            return self.front.data

    def offer(self,x):
        '''将数据元素x插入到队列成为队尾元素'''
        s = Node(x,None)
        if not self.isEmpty():
            self.rear.next = s
        else:
            self.front = s
        self.rear = s

    def poll(self):
        '''将队首元素删除并返回其值'''
        if self.isEmpty():
            return None
        p = self.front
        self.front = self.front.next
        if p == self.rear: # 删除结点为队尾结点时需要修改rear
            self.rear = None
        return p.data

    def display(self):
        '''输出队列中的所有元素'''
        p = self.front
        while p is not None:
            print(p.data,end=' ')
            p = p.next

class BiTreeNode(object):
    def __init__(self,data=None,lchild=None,rchild=None):
        self.data = data
        self.lchild = lchild
        self.rchild = rchild

class BiTree(object):
    def __init__(self,root=None):
        self.root = root

    def createBiTree(order):
        q = LinkQueue()
        root = BiTreeNode(order[0])
        bt = BiTree(root)
        q.offer(root)
        for i in range(1,len(order)):
            c = order[i]
            node = q.peek()
            if node.lchild is None:
                newNode = BiTreeNode(c)
                node.lchild = newNode
                q.offer(newNode)
            elif node.rchild is None:
                newNode = BiTreeNode(c)
                node.rchild = newNode
                q.offer(newNode)
                q.poll()
        return bt

    def preOrder(root):
        if root is not None:
            print(root.data,end=' ')
            BiTree.preOrder(root.lchild)
            BiTree.preOrder(root.rchild)

    def inOrder(root):
        if root is not None:
            BiTree.inOrder(root.lchild)
            print(root.data,end=' ')
            BiTree.inOrder(root.rchild)

    def postOrder(root):
        if root is not None:
            BiTree.postOrder(root.lchild)
            BiTree.postOrder(root.rchild)
            print(root.data,end=' ')

bt = BiTree.createBiTree('123456789')
print("先序遍历:")
BiTree.preOrder(bt.root)
print()
print("中序遍历:")
BiTree.inOrder(bt.root)
print()
print("后序遍历:")
BiTree.postOrder(bt.root)
print()

