class OLNode(object):
    def __init__(self,data=None,right=None,down=None):
        self.data = data # 三元组存储的数据包括该元素所在的行、列和数值
        self.right = right # 行链表指针
        self.down = down # 列链表指针

class TripleNode(object):
    def __init__(self,value,row,col):
        self.value = value
        self.row = row
        self.col = col

class CrossList(object):
    def __init__(self,rows,cols):
        self.initHeader(rows,cols)

    def initHeader(self,rows,cols):
        self.rows = rows # 原始矩阵的行数
        self.cols = cols # 原始矩阵的列数 
        self.rhead = [None] * rows # 行指针——单纯地充当头指针，执行该列的第一个非零元素，其长度等于rows     
        self.chead = [None] * cols # 列指针——单纯地充当头指针，执行该行的第一个非零元素，所以其长度等于cols
        self.nums = 0 # 原始矩阵中非零元素的个数
        # 初始化行的头指针
        for i in range(rows):
            self.rhead[i] = OLNode()
        # 初始化列的头指针
        for i in range(cols):
            self.chead[i] = OLNode()       

    def insert(self,row,col,value):
        self.nums += 1
        data = TripleNode(value,row,col)
        newNode = OLNode(data)
        # 通过行、列头指针确定指向该新节点的指针
        t = self.rhead[row] # 找到该行的头指针
        while t.right is not None: # 找到该行的末尾
            t = t.right
        t.right = newNode # 让该行的末尾指向该新节点
        t = self.chead[col] # 找到该列的头指针
        while t.down is not None: # 找到该列的末尾
            t = t.down
        t.down = newNode # 让该列的末尾指向该新节点

    def printArrOfRC(self):
        print("原始矩阵 共%s行%s列,%s个非零元素" % (self.rows,self.cols,self.nums))
        print('----------------------------------------')
        print('从行来看')
        for row in range(self.rows):
            print('行%s:' % row,end='')
            t = self.rhead[row].right
            while t is not None:
                data = t.data
                print('(value:%s,row:%s,col:%s)' % (data.value,data.row,data.col),end=' ')
                t = t.right
            print()
        print('----------------------------------------')
        print('从列来看')
        for col in range(self.cols):
            print('列%s:' % col,end='')
            t = self.chead[col].down
            while t is not None:
                data = t.data
                print('(value:%s,row:%s,col:%s)' % (data.value,data.row,data.col),end=' ')
                t = t.down
            print()

    def List2CrossList(datas):
        '''根据列表格式的二维矩阵创建稀疏矩阵并返回'''
        rows = len(datas)
        cols = len(datas[0])
        cl = CrossList(rows,cols)
        for row in range(rows):
            for col in range(cols):
                value = datas[row][col]
                if value != 0:
                    cl.insert(row,col,value)
        return cl

cl = CrossList.List2CrossList(
    [
        [0,0,1,0],
        [1,0,0,4],
        [0,0,3,0],
        [1,2,0,4],
    ]
)
cl.printArrOfRC()