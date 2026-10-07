if __name__ == '__main__':
    nums = input().split(' ')
    sl = SqList(len(nums))
    data = []
    for i in range(len(nums)):
        data.append(int(nums[i]))
    for i, x in zip(range(len(data)), data):
        sl.insert(i, RecordNode(x, x))
    sl.qSort(0,len(nums)-1)
    ans=0
    for i in range(len(nums)):
        if sl.list[i].data!=int(nums[i]):
            ans+=1
    print(ans)
