class RecordNode(object):
    def __init__(self, key, data):
        self.key = key  # 关键字
        self.data = data  # 数据元素的值


class SqList(object):
    def __init__(self, maxSize):
        self.maxSize = maxSize  # 顺序表的最大存储空间
        self.list = [None] * self.maxSize  # 待排序的记录集合
        self.len = 0  # 顺序表的长度

    def insert(self, i, x):
        # 在第i个位置之前插入记录x
        if self.len == self.maxSize:
            raise Exception("顺序表已满")
        if i < 0 or i > self.len:
            raise Exception("插入位置不合理")
        for j in range(self.len, i, -1):
            self.list[j] = self.list[j - 1]
        self.list[i] = x
        self.len += 1

    def display(self):
        for i in range(self.len):
            print(self.list[i].key, end=' ')
        print()

    def binarySearch(self, key):
        if self.len > 0:
            # 查找表的上界与下界
            low = 0
            high = self.len - 1
            while low <= high:
                mid = (low + high) // 2  # 取中间元素位置
                if self.list[mid].key == key:
                    return mid
                elif self.list[mid].key < key:  # 查找范围为后半部分
                    low = mid + 1
                else:  # 查找范围为前半部分
                    high = mid - 1
        return low


if __name__ == '__main__':
    data = input().split(' ')
    for i in range(len(data)):
        data[i] = int(data[i])
    sl = SqList(len(data))
    target = int(input())
    for i, x in zip(range(len(data)), data):
        sl.insert(i, RecordNode(x, x))
    print(sl.binarySearch(target))
