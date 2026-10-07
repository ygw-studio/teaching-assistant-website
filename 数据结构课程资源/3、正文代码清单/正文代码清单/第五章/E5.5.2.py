def isSameTree(self, p, q):
    if not p and not q:
        return True
    elif not p or not q:
        return False
    elif p.data != q.data:
        return False
    else:
        return self.isSameTree(p.lchild, q.lchild) and self.isSameTree(p.rchild, q.rchild)
