if __name__ == '__main__':
    bst = BSTree()
    nums = input().split(' ')
    for i in range(len(nums)):
        nums[i] = int(nums[i])
    for d in nums:
        bst.insert(d, d)
    ans = math.inf
    pre = -math.inf
    p = bst.root
    st = []
    while p is not None or st:
        while p is not None:
            st.append(p)
            p = p.lchild
        p = st.pop()
        cur = p.data
        ans = min(ans,abs(cur-pre))
        pre=cur
        p=p.rchild
print(ans)
