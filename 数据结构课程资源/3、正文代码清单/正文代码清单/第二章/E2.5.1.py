def plusOne(digits):
    n = len(digits)
    for i in range(n - 1, -1, -1):
        if digits[i] != 9:
            digits[i] += 1
            for j in range(i + 1, n):
                digits[j] = 0
            return digits
    return [1] + [0] * n

if __name__ == '__main__':
    tmp_input = input()
    tmp_input = tmp_input[1:len(tmp_input)-1]
    input_arr = tmp_input.split(',')
    input_arr=[int(item) for item in input_arr]
    output_arr=plusOne(input_arr)
    print('[',end='')
    for i in range(0,len(output_arr)):
        print(output_arr[i],end='')
        if i < len(output_arr)-1:
            print(',',end='')
    print(']')
