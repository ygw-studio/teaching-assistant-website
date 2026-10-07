if __name__ == '__main__':
    num = input().split(' ')
    n,m = int(num[0]),int(num[1])
    sl = SqList(m)
    data = []
    input_data = input().split(' ')
    for i in range(m):
        data.append(int(input_data[i]))
    for i, x in zip(range(len(data)), data):
        sl.insert(i, RecordNode(x, x))
    sl.qSort(0, len(sl.list)-1)
    sl.display()
