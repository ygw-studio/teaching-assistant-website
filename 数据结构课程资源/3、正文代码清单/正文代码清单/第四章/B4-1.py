from abc import ABCMeta,abstractmethod,abstractproperty

class IString(metaclass=ABCMeta):
    @abstractmethod
    def clear(self):
        '''将字符串置成空串'''
        pass
    @abstractmethod
    def isEmpty(self):
        '''判断是否为空串'''
        pass
    @abstractmethod
    def length(self):
        '''返回串的长度'''
        pass
    @abstractmethod
    def charAt(self,i):
        '''读取并返回串中的第i个数据元素'''
        pass
    @abstractmethod
    def subString(self,begin,end):
        '''返回位序号从begin到end-1的子串'''
        pass
    @abstractmethod
    def insert(self,i,str):
        '''在第i个字符之前插入子串str'''
        pass
    @abstractmethod
    def delete(self,begin,end):
        '''删除位序号从begin到end-1的子串'''
        pass
    @abstractmethod
    def concat(self,str):
        '''将str连接到字符串的后面'''
        pass
    @abstractmethod
    def compareTo(self,str):
        '''比较str和当前字符串的大小'''
        pass
    @abstractmethod
    def indexOf(self,str,begin):
        '''从位序号为begin的字符开始搜索与str相等的子串'''
        pass

class SqString(IString):
    def __init__(self,obj=None):
        if obj is None: # 构造空串
            self.strValue = [] # 字符数组存放串值
            self.curLen = 0 # 当前串的长度
        elif isinstance(obj,str): # 以字符串构造串
            self.curLen = len(obj)
            self.strValue = [None] * self.curLen
            for i in range(self.curLen):
                self.strValue[i] = obj[i]           
        elif isinstance(obj,list): # 以字符列表构造串
            self.curLen = len(obj)
            self.strValue = [None] * self.curLen
            for i in range(self.curLen):
                self.strValue[i] = obj[i]           

    def clear(self):
        '''将字符串置成空串'''
        self.curLen = 0

    def isEmpty(self):
        '''判断是否为空串'''
        return self.curLen == 0

    def length(self):
        '''返回串的长度'''
        return self.curLen

    def charAt(self,i):
        '''读取并返回串中的第i个数据元素'''
        if i<0 or i>=self.curLen:
            raise IndexError("String index out of range")
        return self.strValue[i]

    def allocate(self,newCapacity):
        '''将串的长度扩充为newCapacity'''
        tmp = self.strValue
        self.strValue = [None] * newCapacity
        for i in range(self.curLen):
            self.strValue[i] = tmp[i]

    def subString(self,begin,end):
        '''返回位序号从begin到end-1的子串'''
        if begin<0 or begin>=end or end>self.curLen:
            raise IndexError("参数不合法")
        tmp = [None] * (end-begin)
        for i in range(begin,end):
            tmp[i-begin] = self.strValue[i] # 复制子串
        return SqString(tmp)

    def insert(self,i,str):
        '''在第i个字符之前插入子串str'''
        if i<0 or i>self.curLen:
            raise IndexError("插入位置不合法")
        length = str.length()
        newCapacity = self.curLen + length
        self.allocate(newCapacity)
        for j in range(self.curLen-1,i-1,-1):
            self.strValue[j+length] = self.strValue[j]
        for j in range(i,i+length):
            # print(j-i,str.charAt(j-i))
            self.strValue[j] = str.charAt(j-i)
        self.curLen = newCapacity

    def delete(self,begin,end):
        '''删除位序号从begin到end-1的子串'''
        if begin<0 or begin>=end or end>self.curLen:
            raise IndexError("参数不合法")
        for i in range(begin,end):
            self.strValue[i] = self.strValue[i+end-begin]
        self.curLen = self.curLen - end + begin

    def concat(self,str):
        '''将str连接到字符串的后面'''
        self.insert(self.curLen,str)

    def compareTo(self,str):
        '''比较str和当前字符串的大小'''
        n = self.curLen if self.curLen<str.length() else str.length()
        for i in range(n):
            if self.strValue[i]>str.charAt(i):
                return 1
            if self.strValue[i]<str.charAt(i):
                return -1
        if self.curLen > str.length():
            return 1
        elif self.curLen < str.length():
            return -1
        return 0

    def indexOf(self,str,begin):
        '''从位序号为begin的字符开始搜索与str相等的子串'''
        pass

    def BF(self,str,begin):
        count = 0
        if str.length()<=self.curLen and str is not None and self.curLen>0:
            i = begin
            length = str.length()
            while(i<=self.curLen-length):
                for j in range(length):
                    count += 1
                    if str.charAt(j)!=self.strValue[j+i]:
                        i += 1                      
                        break
                    elif j==length-1:
                        return i,count
        return -1,count

    def next(p):
        next = [0] * p.length() # next数组
        k = 0 # 模式串指针
        j = 1 # 主串指针
        next[0] = -1
        next[1] = 0
        while j<p.length()-1:
            if p.charAt(j)==p.charAt(k):
                next[j+1] = k+1
                k += 1
                j += 1
            elif k==0:
                next[j+1] = 0
                j += 1
            else:
                k = next[k]
        return next

    def KMP(self,p,begin):
        count = 0
        next = SqString.next(p) # 计算next值
        i = begin # # i为主串的字符指针
        j = 0
        while i < self.curLen and j < p.length():
            count += 1
            if j==-1 or self.strValue[i]==p.charAt(j):
                # 比较的字符相等或者比较主串的下一个字符
                i += 1
                j += 1
            else:
                j = next[j]
        if j == p.length():
            return i-j,count # 匹配
        else:
            return -1,count

    def display(self):
        '''打印字符串'''
        for i in range(self.curLen):
            print(self.strValue[i],end='')

s = SqString('abcbcaabc')
p = SqString('bcaa')
i,c = s.KMP(p,0)
if i>0:
    print('匹配')
else:
    print('不匹配')