from functools import reduce


def singleNumber(nums):
    return reduce(lambda x, y: x ^ y, nums)


if __name__ == '__main__':
    tmp_input = input()
    tmp_input = tmp_input[1:len(tmp_input) - 1]
    input_arr = tmp_input.split(',')
    input_arr = [int(item) for item in input_arr]
    print(singleNumber(input_arr))
