class RecordNode(object): 
    def __init__(self,key,data): 
        self.key = key # 关键字 
        self.data = data # 数据元素的值 
  
class SqList(object): 
    def __init__(self,maxSize): 
        self.maxSize = maxSize # 顺序表的最大存储空间 
        self.list = [ None ] * self.maxSize # 待排序的记录集合 
        self.len = 0 # 顺序表的长度 
  
    def insert(self,i,x): 
        # 在第i个位置之前插入记录x 
        if self.len==self.maxSize: 
            raise Exception("顺序表已满") 
        if i<0 or i>self.len: 
            raise Exception("插入位置不合理") 
        for j in range(self.len,i,-1): 
            self.list[j] = self.list[j-1] 
        self.list[i] = x 
        self.len += 1 
  
    def display(self): 
        for i in range(self.len): 
            print(self.list[i].key,end=' ') 
        print() 
  
    def qSort(self,low,high): 
        if low<high: 
            p = self.Partition(low,high) 
            self.qSort(low,p-1) 
            self.qSort(p+1,high) 
  
  
    def Partition(self,low,high): 
        p = self.list[low] 
        while low<high: 
            while low<high and self.list[high].key>p.key: 
                high -= 1 
            if low<high: 
                self.list[low] = self.list[high] 
                low += 1 
            while low<high and self.list[low].key<p.key: 
                low += 1 
            if low<high: 
                self.list[high] = self.list[low] 
                high -= 1 
        self.list[low] = p 
        return low 
  
sl = SqList(8) 
data = [1,2,5,4,7,6,3,0] 
for i,x in zip(range(len(data)),data): 
    sl.insert(i,RecordNode(x,x)) 
sl.qSort(0,sl.len-1) 
sl.display() 