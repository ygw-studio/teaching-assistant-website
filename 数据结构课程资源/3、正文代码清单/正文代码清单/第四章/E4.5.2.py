def transpose(input_matrix):
    m,n=len(input_matrix),len(input_matrix[0])
    output_matrix = [[0]*m for _ in range(n)]
    for i in range(m):
        for j in range(n):
            output_matrix[j][i]=input_matrix[i][j]
    return output_matrix
if __name__ =='__main__':
    print(transpose([[1,2,3],[4,5,6],[7,8,9]]))
