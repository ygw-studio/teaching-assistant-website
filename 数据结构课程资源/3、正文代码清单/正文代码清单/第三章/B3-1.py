from abc import ABCMeta,abstractmethod,abstractproperty

class IStack(metaclass=ABCMeta):
    @abstractmethod
    def clear(self):
        '''将栈置空'''
        pass
    @abstractmethod
    def isEmpty(self):
        '''判断栈是否为空'''
        pass
    @abstractmethod
    def length(self):
        '''返回栈的数据元素个数'''
        pass
    @abstractmethod
    def peek(self):
        '''返回栈顶元素'''
        pass
    @abstractmethod
    def push(self,x):
        '''数据元素x入栈'''
        pass
    @abstractmethod
    def pop(self):
        '''将栈顶元素出栈并返回'''
        pass
    @abstractmethod
    def display(self):
        '''输出栈中的所有元素'''
        pass

class SqStack(IStack):
    def __init__(self,maxSize):
        self.maxSize = maxSize # 栈的最大存储单元个数
        self.stackElem = [None] * self.maxSize # 顺序栈存储空间
        self.top = 0 # 指向栈顶元素的下一个存储单元位置

    def clear(self):
        '''将栈置空'''
        self.top = 0

    def isEmpty(self):
        '''判断栈是否为空'''
        return self.top == 0

    def length(self):
        '''返回栈的数据元素个数'''
        return self.top

    def peek(self):
        '''返回栈顶元素'''
        if not self.isEmpty():
            return self.stackElem[self.top-1]
        else:
            return None
    def push(self,x):
        '''数据元素x入栈'''
        if self.top == self.maxSize:
            raise Exception("栈已满")
        self.stackElem[self.top] = x
        self.top += 1

    def pop(self):
        '''将栈顶元素出栈并返回'''
        if self.isEmpty():
            return None
        self.top -= 1
        return self.stackElem[self.top]

    def display(self):
        '''输出栈中的所有元素'''
        for i in range(self.top-1,-1,-1):
            print(self.stackElem[i],end=' ')

def isMatched(str): 
    backref={
        ')':'(',
        ']':'[',
        '}':'{',
    }
    s = SqStack(100) 
    for c in str: 
        if c=='(' or c=='[' or c=='{':
            s.push(c)
        if c==')' or c==']' or c=='}':
            if s.isEmpty():
                return False
            if s.peek()==backref[c]:
                s.pop()
            else:
                return False        
    if s.isEmpty(): 
        return True 
    else:
        return False 

s1 = "{{}}()(hello){({world}{})}"
s2 = "{{}}()(hello){({world}(})}"
print("s1",end='')
if isMatched(s1):
    print("括号匹配成功")
else:
    print("括号匹配不成功")
print("s2",end='')
if isMatched(s2):
    print("括号匹配成功")
else:
    print("括号匹配不成功")