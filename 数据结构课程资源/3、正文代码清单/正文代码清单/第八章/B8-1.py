def longestValidParentheses(s):
    left = right = ans = 0
    length = len(s)
    for i in range(length):
        if s[i]=='(':
            left += 1
        else:
            right += 1
        if left == right:
            ans = max(ans,2*right) # 更新长度
        elif right > left:
            left = right = 0
    left = right = 0
    for i in range(length-1,-1,-1):
        if s[i]==')':
            right += 1
        else:
            left += 1
        if left == right:
            ans = max(ans,2*left)
        elif left>right:
            left = right = 0
    return ans

s = "()()()"
print(longestValidParentheses(s))