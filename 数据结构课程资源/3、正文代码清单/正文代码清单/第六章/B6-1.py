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
        self.e = [[0 for _ in range(vNum)] for _ in range(vNum)]  # 构造边集
        for i in range(eNum):
            a, b = e[i]
            m, n = self.locateVex(a), self.locateVex(b)
            self.e[m][n] = 1
            self.e[n][m] = 1

    def createDG(self, vNum, eNum, v, e):
        self.vNum = vNum
        self.eNum = eNum
        self.v = [None] * vNum  # 构造顶点集
        for i in range(vNum):
            self.v[i] = v[i]
        self.e = [[0 for _ in range(vNum)] for _ in range(vNum)]  # 构造边集
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
        self.e = [[sys.maxsize for _ in range(vNum)] for _ in range(vNum)]  # 初始化边集
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
        self.e = [[sys.maxsize for _ in range(vNum)] for _ in range(vNum)]  # 初始化边集
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
        if p is not None and p.nextArc is not None:
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


class ShortestPath(object):
    def Djikstra(g, v0):
        # 存放最短路径,p[v][k]表示从v0到v的最短路径中经过的第k个点
        p = [([-1] * g.getVNum()) for i in range(g.getVNum())]
        # 存放最短路径长度
        D = [sys.maxsize] * g.getVNum()
        # 若已找到最短路径，finish[v]为True
        finish = [False] * g.getVNum()
        v0 = g.locateVex(v0)
        for v in range(g.getVNum()):
            D[v] = g.getArcs(v0, v)
            if D[v] < sys.maxsize:
                # 从起点直接可以到达
                p[v][0] = v0
                p[v][1] = v
        p[v0][0] = v0  # 起点本身可以直接到达
        D[v0] = 0
        finish[v0] = True
        v = -1
        for i in range(1, g.getVNum()):
            minvalue = sys.maxsize
            for w in range(g.getVNum()):
                # 找出所有最短路径中的最小值
                if not finish[w]:
                    if D[w] < minvalue:
                        v = w
                        minvalue = D[w]
            finish[v] = True
            # 更新当前的最短路径
            for w in range(g.getVNum()):
                if not finish[w] and g.getArcs(v, w) < sys.maxsize and (minvalue + g.getArcs(v, w) < D[w]):
                    D[w] = minvalue + g.getArcs(v, w)
                    for k in range(g.getVNum()):
                        p[w][k] = p[v][k]
                        if p[w][k] == -1:
                            p[w][k] = w
                            break
        dis = {g.getVex(i): D[i] for i in range(g.getVNum())}
        # 返回到各点最短路的字典与路径矩阵
        return dis, p

    def printDjikstraPath(g, v0, p, dis):
        # v0到各点的输出最短路径,即p[v][0]到p[v][j]直到p[v][j]==-1
        u = v0
        v0 = g.locateVex(v0)
        for i in range(g.getVNum()):
            v = g.getVex(i)
            print('%s->%s的最短路径为:' % (u, v), end=' ')
            if p[i][0] != -1:
                print(g.getVex(p[v0][0]), end='')
            for k in range(1, g.getVNum()):
                if p[i][k] == -1:
                    break
                print('->%s' % g.getVex(p[i][k]), end='')
            print(' 长度: %s' % dis[v])


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
dis, p = ShortestPath.Djikstra(g, 'A')
ShortestPath.printDjikstraPath(g, 'A', p, dis)
