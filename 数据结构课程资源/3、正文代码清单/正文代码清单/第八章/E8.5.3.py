# 方法一
if __name__ == '__main__':
    num = input().split(' ')
    n,m = int(num[0]),int(num[1])
    sl_list = []
    for j in range(n):
        data = input().split(' ')
        for i in range(len(data)):
            data[i] = int(data[i])
        sl = SqList(len(data))
        for i, x in zip(range(len(data)), data):
            sl.insert(i, RecordNode(x, x))
        sl_list.append(sl)
    target = int(input())
    j = 0
    while j<n:
        if sl_list[j].binarySearch(target)>=0:
            print(True)
            break
        j+=1
    if j == n:
        print(False)
# 方法二
if __name__ == '__main__':
    num = input().split(' ')
    n,m = int(num[0]),int(num[1])
    data_list = []
    for j in range(n):
        data = input().split(' ')
        for i in range(len(data)):
            data[i] = int(data[i])
        data_list.append(data)
    target = int(input())
    i,j=0,n-1
    while 0<=i<n and 0<=j<m:
        cur_ele = data_list[i][j]
        if cur_ele == target:
            print(True)
            break
        elif cur_ele>target:
            j-=1
        else:
            i+=1
    if not (0<=i<n and 0<=j<m):
        print(False)
