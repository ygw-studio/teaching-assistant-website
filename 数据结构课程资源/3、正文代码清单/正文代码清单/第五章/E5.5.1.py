def pruneTree(self, root):
    if root is None:
        return None
    root.lchild = self.pruneTree(root.lchild)
    root.rchild = self.pruneTree(root.rchild)
    if root.lchild is None and root.rchild is None and root.data == 0:
        return None
    return root
