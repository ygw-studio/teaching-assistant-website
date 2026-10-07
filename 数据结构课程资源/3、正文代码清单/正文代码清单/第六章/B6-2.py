from abc import ABCMeta, abstractmethod, abstractproperty
import sys


class IGraph(metaclass=ABCMeta):
    @abstractmethod
    def createGraph(self):
        '''创建图'''
        pass

    @abstractmethod
    def getVNum(self):
        '''返回图中的顶点数'''
        pass

    @abstractmethod
    def getENum(self):
        '''返回图中的边数'''
        pass

    @abstractmethod
    def getVex(self, i):
        '''返回位置为i的顶点值'''
        pass

    @abstractmethod
    def locateVex(self, x):
        '''返回值为x的顶点位置'''
        pass

    @abstractmethod
    def firstAdj(self, i):
        '''返回结点的第一个邻接点'''
        pass

    @abstractmethod
    def nextAdj(self, i, j):
        '''返回相对于j的下一个邻接点'''
        pass


class MGraph(IGraph):
    # 图类别静态常量
    GRAPHKIND_UDG = 'UDG'
    GRAPHKIND_DG = 'DG'
    GRAPHKIND_UDN = 'UDN'
    GRAPHKIND_DN = 'DN'

    def __init__(self, kind=None, vNum=0, eNum=0, v=None, e=None):
        self.kind = kind  # 图的种类
        self.vNum = vNum  # 图的顶点数
        self.eNum = eNum  # 图的边数
        self.v = v  # 顶点列表
        self.e = e  # 邻接矩阵

    def createUDG(self, vNum, eNum, v, e):
        self.vNum = vNum
        self.eNum = eNum
        self.v = [None] * vNum  # 构造顶点集
        for i in range(vNum):
            self.v[i] = v[i]
        self.e = [[0] * vNum] * vNum  # 构造边集
        for i in range(eNum):
            a, b = e[i]
        m, n = self.locateVex(a), self.locateVex(b)
        self.e[m][n] = self.e[n][m] = 1

    def createDG(self, vNum, eNum, v, e):
        self.vNum = vNum
        self.eNum = eNum
        self.v = [None] * vNum  # 构造顶点集
        for i in range(vNum):
            self.v[i] = v[i]
        self.e = [[0] * vNum] * vNum  # 构造边集
        for i in range(eNum):
            a, b = e[i]
        m, n = self.locateVex(a), self.locateVex(b)
        self.e[m][n] = 1

    def createUDN(self, vNum, eNum, v, e):
        self.vNum = vNum
        self.eNum = eNum
        self.v = [None] * vNum  # 构造顶点集
        for i in range(vNum):
            self.v[i] = v[i]
        self.e = [[sys.maxsize] * vNum] * vNum  # 初始化边集
        for i in range(eNum):
            a, b, w = e[i]
        m, n = self.locateVex(a), self.locateVex(b)
        self.e[m][n] = self.e[n][m] = w

    def createDN(self, vNum, eNum, v, e):
        self.vNum = vNum
        self.eNum = eNum
        self.v = [None] * vNum  # 构造顶点集
        for i in range(vNum):
            self.v[i] = v[i]
        self.e = [[sys.maxsize] * vNum] * vNum  # 初始化边集
        for i in range(eNum):
            a, b, w = e[i]
        m, n = self.locateVex(a), self.locateVex(b)
        self.e[m][n] = w

    def locateVex(self, x):
        for i in range(self.vNum):
            if self.v[i] == x:
                return i
        return -1

    def firstAdj(self, i):
        if i < 0 or i >= self.vNum:
            raise Exception("第%s个顶点不存在" % i)
        for j in range(self.vNum):
            if self.e[i][j] != 0 and self.e[i][j] < sys.maxsize:
                return j
        return -1

    def nextAdj(self, i, j):
        if j == self.vNum - 1:
            return -1
        for k in range(j + 1, self.vNum):
            if self.e[i][k] != 0 and self.e[i][k] < sys.maxsize:
                return k
        return -1


class VNode(object):
    def __init__(self, data=None, firstNode=None):
        self.data = data  # 存放结点值
        self.firstArc = firstNode  # 第一条边


class ArcNode(object):
    def __init__(self, adjVex, value, nextArc=None):
        self.adjVex = adjVex  # 边指向的顶点的位置
        self.value = value  # 边的权值
        self.nextArc = nextArc  # 指向下一条边


class ALGraph(IGraph):
    # 图类别静态常量
    GRAPHKIND_UDG = 'UDG'
    GRAPHKIND_DG = 'DG'
    GRAPHKIND_UDN = 'UDN'
    GRAPHKIND_DN = 'DN'

    def __init__(self, kind=None, vNum=0, eNum=0, v=None, e=None):
        self.kind = kind  # 图的种类
        self.vNum = vNum  # 图的顶点数
        self.eNum = eNum  # 图的边数
        self.v = v  # 顶点列表
        self.e = e  # 边信息

    def createGraph(self):
        if self.kind == self.GRAPHKIND_UDG:
            self.createUDG()
        elif self.kind == self.GRAPHKIND_DG:
            self.createDG()
        elif self.kind == self.GRAPHKIND_UDN:
            self.createUDN()
        elif self.kind == self.GRAPHKIND_DN:
            self.createDN()

    def createUDG(self):
        '''创建无向图'''
        v = self.v
        self.v = [None] * self.vNum
        for i in range(self.vNum):
            self.v[i] = VNode(v[i])
        for i in range(self.eNum):
            a, b = self.e[i]
            u, v = self.locateVex(a), self.locateVex(b)
            self.addArc(u, v, 1)
            self.addArc(v, u, 1)

    def createDG(self):
        '''创建有向图'''
        v = self.v
        self.v = [None] * self.vNum
        for i in range(self.vNum):
            self.v[i] = VNode(v[i])
        for i in range(self.eNum):
            a, b = self.e[i]
            u, v = self.locateVex(a), self.locateVex(b)
            self.addArc(u, v, 1)

    def createUDN(self):
        '''创建无向网'''
        v = self.v
        self.v = [None] * self.vNum
        for i in range(self.vNum):
            self.v[i] = VNode(v[i])
        for i in range(self.eNum):
            a, b, w = self.e[i]
            u, v = self.locateVex(a), self.locateVex(b)
            self.addArc(u, v, w)
            self.addArc(v, u, w)

    def createDN(self):
        '''创建有向网'''
        v = self.v
        self.v = [None] * self.vNum
        for i in range(self.vNum):
            self.v[i] = VNode(v[i])
        for i in range(self.eNum):
            a, b, w = self.e[i]
            u, v = self.locateVex(a), self.locateVex(b)
            self.addArc(u, v, w)

    def addArc(self, i, j, value):
        '''插入边结点'''
        arc = ArcNode(j, value)
        arc.nextArc = self.v[i].firstArc
        self.v[i].firstArc = arc

    def firstAdj(self, i):
        '''查找第一个邻接点'''
        if i < 0 or i >= self.vNum:
            raise Exception("第%s个结点不存在" % i)
        p = self.v[i].firstArc
        if p is not None:
            return p.adjVex
        return -1

    def nextAdj(self, i, j):
        '''返回i相对于j的下一个邻接点'''
        if i < 0 or i >= self.vNum:
            raise Exception("第%s个结点不存在" % i)
        p = self.v[i].firstArc
        while p is not None:
            if p.adjVex == j:
                break
            p = p.nextArc
        if p.nextArc is not None:
            return p.nextArc.adjVex
        return -1

    def getVNum(self):
        '''返回顶点数'''
        return self.vNum

    def getENum(self):
        '''返回边数'''
        return self.eNum

    def getVex(self, i):
        '''返回第i个顶点的值'''
        if i < 0 or i >= self.vNum:
            raise Exception("第%s个顶点不存在" % i)
        return self.v[i].data

    def locateVex(self, x):
        '''返回值为x的顶点的位置'''
        for i in range(self.vNum):
            if self.v[i].data == x:
                return i
        return -1

    def getArcs(self, u, v):
        '''返回顶点u到顶点v的距离'''
        if u < 0 or u >= self.vNum:
            raise Exception("第%s个结点不存在" % u)
        if v < 0 or v >= self.vNum:
            raise Exception("第%s个结点不存在" % v)
        p = self.v[u].firstArc
        while p is not None:
            if p.adjVex == v:
                return p.value
            p = p.nextArc
        return sys.maxsize


class CloseEdge(object):
    def __init__(self, adjVex, lowCost):
        self.adjVex = adjVex  # 在结合U中的顶点的值
        self.lowCost = lowCost  # 到集合U的最小距离


class MiniSpanTree(object):

    def PRIM(g, u):
        '''从值为u的顶点出发构造最小生成树，返回由生成树边组成的二维数组'''
        tree = [[None, None] for i in range(g.getVNum() - 1)]
        count = 0
        closeEdge = [None] * g.getVNum()
        k = g.locateVex(u)
        for j in range(g.getVNum()):
            if k != j:
                closeEdge[j] = CloseEdge(u, g.getArcs(k, j))
        closeEdge[k] = CloseEdge(u, 0)

        for i in range(1, g.getVNum()):
            k = MiniSpanTree.getMinMum(closeEdge)
            tree[count][0] = closeEdge[k].adjVex
            tree[count][1] = g.getVex(k)
            count += 1
            closeEdge[k].lowCost = 0
            for j in range(g.getVNum()):
                if g.getArcs(k, j) < closeEdge[j].lowCost:
                    closeEdge[j] = CloseEdge(g.getVex(k), g.getArcs(k, j))
        return tree

    def getMinMum(closeEdge):
        minvalue = sys.maxsize
        v = -1
        for i in range(len(closeEdge)):
            if closeEdge[i].lowCost != 0 and closeEdge[i].lowCost < minvalue:
                minvalue = closeEdge[i].lowCost
                v = i
        return v

    def printMiniSpanTree(g, tree):
        length = 0
        for edge in tree:
            u, v = edge[0], edge[1]
            edgeLength = g.getArcs(g.locateVex(u), g.locateVex(v))
            length += edgeLength
            print('%s-%s:%s,' % (u, v, edgeLength), end=' ')
        print('总权值: %s' % length)


v = ['A', 'B', 'C', 'D', 'E', 'F']
e = [
    ('A', 'B', 7), ('A', 'C', 5), ('A', 'D', 1),
    ('B', 'D', 6), ('B', 'E', 3),
    ('C', 'D', 7), ('C', 'F', 2),
    ('D', 'E', 6), ('D', 'F', 4),
    ('E', 'F', 7),
]
g = ALGraph(ALGraph.GRAPHKIND_UDN, len(v), len(e), v, e)
g.createGraph()
tree = MiniSpanTree.PRIM(g, 'A')
MiniSpanTree.printMiniSpanTree(g, tree)
