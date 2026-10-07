def invertTree(self, root):
    if not root:
        return root
    lchild = self.invertTree(root.lchild)
    rchild = self.invertTree(root.rchild)
    root.lchild, root.rchild = rchild, lchild
    return root
