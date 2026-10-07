def isPalindrome():
    ori_string = SqString(input())
    test_str = []
    for i in range(0,ori_string.length()):
        if ori_string.charAt(i).isalnum():
            test_str.append(ori_string.charAt(i).lower())
    test_string = SqString(test_str)
    left,right = 0,test_string.length()-1
    while left<right:
        if test_string.charAt(left) !=test_string.charAt(right):
            return False
        left,right=left+1,right-1
    return True
