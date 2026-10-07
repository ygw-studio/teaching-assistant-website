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
  
    def merge(self,order,a,i,k,j): 
        t = i 
        m = i 
        n = k + 1 
        while m<=k and n<=j: 
            # 将具有较小关键字值的元素放入order[] 
            if a[m].key<=a[n].key: 
                order[t] = a[m] 
                t += 1 
                m += 1 
            else: 
                order[t] = a[n] 
                t += 1 
                n += 1 
        while m<=k: 
            order[t] = a[m] 
            t += 1 
            m += 1 
        while n<=j: 
            order[t] = a[n] 
            t += 1 
            n += 1 
  
    def mergepass(self,order,a,s,n): 
        p = 0 
        while p+2*s-1<=n-1: # 两两归并长度均为s的有序表 
            self.merge(order,a,p,p+s-1,p+2*s-1) 
            p = p+2*s 
        if p+s-1<n-1: # 归并长度不等的有序表 
            self.merge(order,a,p,p+s-1,n-1) 
        else: # 将一个有序表中的元素放入order[]中 
            for i in range(p,n): 
                order[i] = a[i] 
  
    def mergeSort(self): 
        s = 1 # 已排序的子序列的长度，初始值为1 
        order = [ None ] * self.len 
        while s<self.len: # 归并过程 
            self.mergepass(order,self.list,s,self.len) 
            s = s * 2 
            self.mergepass(self.list,order,s,self.len) 
            s = s * 2 
    
sl = SqList(50) 
data = [1,2,5,4,7,6,3,0] 
for i,x in zip(range(len(data)),data): 
    sl.insert(i,RecordNode(x,x)) 
sl.mergeSort() 
sl.display() 