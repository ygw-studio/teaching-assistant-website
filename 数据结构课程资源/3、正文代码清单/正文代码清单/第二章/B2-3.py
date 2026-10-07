class JosephusNode(object):
	def __init__(self,data,next=None,prior=None):
		self.data = data # 序号
		self.next = None # 下一个结点
		self.prior = None # 上一个结点

class JosephusList(object):
	def __init__(self):
		self.curLen = 0
		self.head = None

	def insert(self,x):
		if self.head is None:
			self.head = JosephusNode(x)
			self.head.next = self.head
			self.head.prior = self.head
		else:
			s = JosephusNode(x)
			s.next = self.head
			s.prior = self.head.prior
			self.head.prior.next = s
			self.head.prior = s
		self.curLen += 1

	def remove(self,x):
		p = self.head
		while True:
			if p.data==x:
				p.prior.next = p.next
				p.next.prior = p.prior
				if p is self.head:
					self.head = p.next
				self.curLen -= 1
				break
			p = p.next
			if p is self.head:
				break

	def display(self):
		p = self.head
		while True:
			print(p.data,end=' ')
			p = p.next
			if p is self.head:
				break

N = 6
M = 5
J = JosephusList()
for i in range(1,N+1):
	J.insert(i)

p = J.head
while J.curLen>1:	
	for i in range(M-1):
		p = p.next
	print(p.data,"出局")
	J.remove(p.data)
	p = p.next
print(p.data,"胜出")