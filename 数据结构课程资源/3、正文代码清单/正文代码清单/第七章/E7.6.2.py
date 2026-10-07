if __name__ == '__main__':
    nums = input().split(' ')
    sl = SqList(len(nums))
    data = []
    for i in range(len(nums)):
        data.append(int(nums[i]))
    for i, x in zip(range(len(data)), data):
        sl.insert(i, RecordNode(x, x))
    sl.mergeSort()
    for i in range(len(nums)):
        if sl.list[i].data!=i:
            print(i)
            break
    if i == len(nums)-1 and sl.list[i].data==i:
        print(len(nums))
