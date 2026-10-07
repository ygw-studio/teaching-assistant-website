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

N = 5
q = LinkQueue()
s = 0
# 先添加两个1进入队列
q.offer(1)
q.offer(1)
for i in range(1,N+1):
    # 各行间插入一个0
    q.offer(0)
    for j in range(1,i+3):
        # 退出一个系数temp
        temp = q.poll()
        # 计算下一行的系数并加入队列
        q.offer(temp+s);
        s = temp
        if(j!=i+2):
            print(s,end=' ')
    # 换行
    print()