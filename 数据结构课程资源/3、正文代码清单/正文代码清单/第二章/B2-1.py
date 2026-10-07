from abc import ABCMeta,abstractmethod,abstractproperty

class IList(metaclass=ABCMeta):
	@abstractmethod
	def clear(self):
		'''将线性表置成空表'''
		pass
	@abstractmethod
	def isEmpty(self):
		'''判断线性表是否为空表'''
		pass
	@abstractmethod
	def length(self):
		'''返回线性表的长度'''
		pass
	@abstractmethod
	def get(self,i):
		'''读取并返回线性表中的第i个数据元素'''
		pass
	@abstractmethod
	def insert(self,i,x):
		'''插入x作为第i个元素'''
		pass
	@abstractmethod
	def remove(self,i):
		'''删除第i个元素'''
		pass
	@abstractmethod
	def indexOf(self,x):
		'''返回元素x首次出现的位序号'''
		pass
	@abstractmethod
	def display(self):
		'''输出线性表中各个数据元素的值'''
		pass

class Node(object):
	def __init__(self,data=None,next=None):
		self.data = data
		self.next = next

class LinkList(IList):
	def __init__(self):
		self.head = Node() # 构造函数初始化头结点

	def create(self,l,order):
		if order:
			self.create_tail(l)
		else:
			self.create_head(l)

	def create_tail(self,l):
		for item in l:
			self.insert(self.length(),item)

	def create_head(self,l):
		for item in l:
			self.insert(0,item)

	def clear(self):
		'''将线性表置成空表'''
		self.head.data = None
		self.head.next = None

	def isEmpty(self):
		'''判断线性表是否为空表'''
		return self.head.next == None

	def length(self):
		'''返回线性表的长度'''
		p = self.head.next
		length = 0
		while p is not None:
			p = p.next
			length += 1
		return length

	def get(self,i):
		'''读取并返回线性表中的第i个数据元素'''
		p = self.head.next # p指向单链表的首结点
		j = 0
		# 从首结点开始向后查找，直到p指向第i个结点或者p为null
		while j<i and p is not None:
			p = p.next
			j += 1
		if j>i or p is None: # i不合法时抛出异常
			raise Exception("第"+i+"个数据元素不存在")
		return p.data

	def insert(self,i,x):
		'''(带头结点)插入x作为第i个元素'''
		p = self.head
		j = -1
		while p is not None and j < i-1:
			p = p.next
			j += 1
		if j>i-1 or p is None:
			raise Exception("插入位置不合法")
		s = Node(x,p.next)
		p.next = s

	'''
	def insert(self,i,x):
		# (不带头结点)插入x作为第i个元素
		p = self.head
		j = -1
		while p is not None and j < i-1:
			p = p.next
			j += 1
		if j>i-1 or p is None:
			raise Exception("插入位置不合法")
		s = Node(data=x)
		if i==0:
			s.next = self.head
		else:
			s.next = p.next
			p.next = s
	'''

	def remove(self,i):
		'''删除第i个元素'''
		p = self.head
		j = -1
		# 寻找第i个结点的前驱结点
		while p is not None and j<i-1:
			p = p.next
			j += 1
		if j>i-1 or p.next is None:
			raise Exception("删除位置不合法")
		p.next = p.next.next

	def indexOf(self,x):
		'''返回元素x首次出现的位序号'''
		p = self.head.next
		j = 0
		while p is not None and not (p.data == x):
			p = p.next
			j += 1
		if p is not None:
			return j
		else:
			return -1

	def display(self):
		'''输出线性表中各个数据元素的值'''
		p = self.head.next
		while p is not None:
			print(p.data,end=' ')
			p = p.next

L = LinkList()
for i in range(8):
	s = input()
	L.insert(i,s)
# 依次输入：赵壹、钱贰、孙叁、李肆、周伍、吴陆、郑柒、王捌
# 注意每输入一个人名后键入一次回车
# (1)
print("(1)班级学生：",end='')
L.display()
print("班级人数：",end='')
print(L.length())
# (2)
print("(2)'李肆'在表中的位置:",L.indexOf("李肆"))
# (3)
L.insert(L.indexOf("王捌")+1,"冯玖")
L.remove(L.indexOf("赵壹"))
print("(3)现在该班级学生：",end='')
L.display()
print()