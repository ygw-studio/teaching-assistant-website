if __name__ == '__main__':
    num= input()
    n,m=num.split(' ')[0],num.split(' ')[1]
    n = int(n)
    m = int(m)
    v = [i+1 for i in range(n)]
    e = []
    for i in range(1,m+1):
        from_person, to_person, weight = input().split(' ')
        from_person=int(from_person)
        to_person=int(to_person)
        weight = int(weight)
        e.append((from_person,to_person,weight))
    from_a,to_b = input().split(' ')
    from_a=int(from_a)
    to_b = int(to_b)
    g = ALGraph('UDN',n,m,v,e)
    g.createGraph()
    dis,p = ShortestPath.Dijkstra(g,from_a)
    price = 0
    i = 0
    while i <len(p[to_b-1])-1:
        if p[to_b-1][i+1]==-1:
            break
        else:
            price+=g.getArcs(p[to_b-1][i],p[to_b-1][i+1])
        i+=1
    res =  100/(1-price/100)
    print('%.8f' %res)
