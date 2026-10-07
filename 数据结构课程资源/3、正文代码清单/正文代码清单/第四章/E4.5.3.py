def reverseLeftWords(str,k):
    ori_string = SqString(str)
    front = ori_string.subString(0,k)
    ori_string.delete(0,k)
    ori_string.insert(ori_string.curLen,front)
    ori_string.display()

if __name__ == '__main__':
    tmp_input = input().split(' ')
    reverseLeftWords(tmp_input[0],int(tmp_input[1]))
