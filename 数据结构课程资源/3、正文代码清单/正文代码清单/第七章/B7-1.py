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
  
  
    def bubbleSort(self): 
        flag = True 
        i = 1 
        while i<self.len and flag: 
            flag = False 
            for j in range(self.len-i): 
                if self.list[j+1].key < self.list[j].key: 
                    p = self.list[j] 
                    self.list[j] = self.list[j+1] 
                    self.list[j+1] = p 
                    flag = True 
            i += 1 
sl = SqList(8) 
data = [1,2,5,4,7,6,3,0] 
for i,x in zip(range(len(data)),data): 
    sl.insert(i,RecordNode(x,x)) 
sl.bubbleSort() 
sl.display() 