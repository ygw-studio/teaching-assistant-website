def operate_input(tmp_e):
    res = tmp_e[1:len(tmp_e)-1].replace('(','').replace(')','').split(',')
    res_list=[]
    i=0
    while i < len(res)-1:
        res_list.append((int(res[i]),int(res[i+1])))
        i+=2
    return res_list
def DFS_valid(g,i,end):
    visited[i] = True
    v = g.firstAdj(i)
    if visited[end] == True:
        return True
    while v!=-1:
        if not visited[v]:
            DFS_valid(g,v,end)
        v = g.nextAdj(i,v)
    return visited[end]
if __name__ == '__main__':
    input_param = input().split(' ')
    n = int(input_param[0])
    e = operate_input(input_param[1])
    start = int(input_param[2])
    end = int(input_param[3])
    v = [i for i in range(n)]
    g =ALGraph('UDG',n,len(e),v,e)
    g.createGraph()
    global visited
    # 建立访问标志数组
    visited = [False] * g.getVNum()
    # 以每个顶点作为起始顶点进行遍历
print(DFS_valid(g,start,end))
