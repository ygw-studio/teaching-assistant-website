class BiTreeNode(object):
    def __init__(self,key,data,lchild=None,rchild=None):
        self.key = key # 结点关键字值
        self.data = data # 结点的数据值
        self.lchild = lchild # 结点的左孩子
        self.rchild = rchild # 结点的右孩子

class BSTree(object):
    def __init__(self,root=None):
        self.root = root # 树的根节点

    def display(self,p):
        if p is not None:
            print(p.data,end='')
            print('(',end='')
            self.display(p.lchild)
            print(',',end='')
            self.display(p.rchild)
            print(')',end='')

    def search(self,key):
        return self.searchBST(key,self.root)

    def searchBST(self,key,p):
        if p is None: # 查找树为空，查找失败
            return None
        if key==p.key: # 查找成功
            return p.data
        elif key<p.key: # 在左子树中查找
            return self.searchBST(key,p.lchild)
        else: # 在右子树中查找
            return self.searchBST(key,p.rchild)

    def insert(self,key,data):
        p = BiTreeNode(key,data) # 为元素建立结点
        if self.root is None: # 若根节点为空，建立新根节点
            self.root = p
        else:
            self.insertBST(self.root,p)

    def insertBST(self,r,p):
        if r.key<p.key: # 查找右子树
            if r.rchild is None:
                r.rchild = p
            else:
                self.insertBST(r.rchild,p)
        else: # 查找左子树
            if r.lchild is None:
                r.lchild = p
            else:
                self.insertBST(r.lchild,p)

    def remove(self,key):
        # 删除关键字为key的结点
        self.removeBST(key,self.root,None)

    def removeBST(self,key,p,parent):
        if p is None: # 树空，直接返回
            return
        if p.key>key: # 在左子树中删除
            self.removeBST(key,p.lchild,p)
        elif p.key<key: # 在右子树中删除
            self.removeBST(key,p.rchild,p)
        elif p.lchild is not None and p.rchild is not None: # 删除此节点，左右子树非空
            inNext = p.rchild
            while inNext.lchild is not None:
                inNext = inNext.lchild
            p.data = inNext.data
            p.key = inNext.key
            self.removeBST(p.key,p.rchild,p)
        else: # 只有一棵子树或者没有子树
            if parent is None:
                if p.lchild is not None:
                    self.root = p.lchild
                else:
                    self.root = p.rchild
                return
            if p==parent.lchild:
                if p.lchild is not None:
                    parent.lchild = p.lchild
                else:
                    parent.lchild = p.rchild
            elif p==parent.rchild:
                if p.lchild is not None:
                    parent.rchild = p.lchild
                else:
                    parent.rchild = p.rchild

    def inOrder(root,data):
        if root is not None:
            BSTree.inOrder(root.lchild,data)
            data.append(root.data)
            BSTree.inOrder(root.rchild,data)

    def toList(self):
        data = []
        BSTree.inOrder(self.root,data)
        return data

    def createBSTreee(nums):
        bst = BSTree()
        for num in nums:
            bst.insert(num,num)
        return bst

bst = BSTree.createBSTreee([15,5,3,12,10,13,6,7,16,20,18,23])
bst.display(bst.root)
print()
print(bst.toList())
bst.insert(11,11)
bst.display(bst.root)
print()
print(bst.toList())
bst.remove(13)
bst.display(bst.root)
print()
print(bst.toList())